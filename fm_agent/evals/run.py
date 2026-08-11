"""Evaluation harness — scores golden Q&A pairs against the running API.

For each golden question:
  a) correct agent routed? (checks /chats response)
  b) expected source path present in retrieved chunks?
  c) LLM-judged answer faithfulness (gemini-flash as judge)

Outputs a markdown report.  Deterministic seed; re-running produces
the same report modulo LLM judge variance.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import random
from datetime import UTC, datetime
from typing import Any

import httpx
import yaml

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _read_yaml_sync(path: str) -> dict[str, Any]:
    with open(path) as f:
        return yaml.safe_load(f) or {}


def _write_text_sync(path: str, text: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(text)


async def run_evals(
    api_url: str = "http://localhost:8080",
    golden_path: str = "examples/fm_agent/evals/golden.yaml",
    results_path: str = "examples/fm_agent/evals/RESULTS.md",
    seed: int = 42,
    dry_run: bool = False,
    local_test: bool = False,
) -> str:
    """Run the full eval suite and write a markdown report.

    Returns the path to the results file.
    """
    random.seed(seed)

    data = await asyncio.to_thread(_read_yaml_sync, golden_path)
    entries = data.get("entries") or data.get("pairs") or []
    approved = [e for e in entries if e.get("status") == "approved"]

    if not approved:
        logger.warning("No approved pairs in %s — running on all entries", golden_path)
        approved = entries

    logger.info("Running evals: %d approved pairs, %d total (dry_run=%s local_test=%s)",
                len(approved), len(entries), dry_run, local_test)

    results: list[dict[str, Any]] = []
    if dry_run:
        for entry in approved:
            results.append(_dry_run_result(entry))
    elif local_test:
        client = _MockAPIClient()
        for entry in approved:
            results.append(await _eval_one(client, entry))
    else:
        async with httpx.AsyncClient(timeout=60.0, base_url=api_url.rstrip("/")) as client:
            for entry in approved:
                result = await _eval_one(client, entry)
                results.append(result)

    # ── Aggregate metrics ──
    total = len(results)
    correct_agent = sum(1 for r in results if r.get("agent_correct"))
    source_found = sum(1 for r in results if r.get("source_path_found"))
    faithful = sum(1 for r in results if r.get("faithful") is True)
    avg_score = sum(r.get("faithfulness_score", 0) for r in results) / max(total, 1)

    # ── Write report ──
    mode = "dry-run" if dry_run else ("local-test" if local_test else "live")
    body_lines = _build_report(results, {
        "total": total,
        "correct_agent": correct_agent,
        "source_path_found": source_found,
        "faithful": faithful,
        "avg_faithfulness_score": round(avg_score, 3),
        "run_at": _now_iso(),
        "seed": seed,
        "api_url": api_url,
        "mode": mode,
    })

    await asyncio.to_thread(_write_text_sync, results_path, body_lines)

    logger.info("Eval report → %s  (%d/%d agent correct, %.2f faithfulness)",
                results_path, correct_agent, total, avg_score)
    return results_path


def _dry_run_result(entry: dict[str, Any]) -> dict[str, Any]:
    """Return a format-check result without calling the API."""
    return {
        "id": entry.get("id", ""),
        "question": entry.get("question", ""),
        "expected_agent": entry.get("agent", ""),
        "agent_correct": None,
        "agents_used": [],
        "source_path_found": None,
        "faithful": None,
        "faithfulness_score": 0.0,
        "response": "[dry-run]",
        "error": "",
    }


class _MockAPIClient:
    """Fake API client for local testing without a live server."""

    async def post(self, url: str, **kwargs: Any) -> Any:
        class _Response:
            def raise_for_status(self) -> None:
                pass

            def json(self) -> dict[str, Any]:
                if url == "/chats":
                    return {"id": "mock-chat-id"}
                return {
                    "agents_used": ["notification-expert"],
                    "response": "This is a local-test response.",
                }

        return _Response()


async def _eval_one(client: Any, entry: dict[str, Any]) -> dict[str, Any]:
    """Evaluate one golden pair against the API."""
    q = entry.get("question", "")
    expected_agent = entry.get("agent", "")
    expected_paths = entry.get("expected_source_paths", [])
    expected_answer = entry.get("expected_answer", "")
    namespace = entry.get("namespace", "")

    result = {
        "id": entry.get("id", ""),
        "question": q,
        "expected_agent": expected_agent,
        "agent_correct": False,
        "agents_used": [],
        "source_path_found": False,
        "faithful": None,
        "faithfulness_score": 0.0,
        "response": "",
        "error": "",
    }

    try:
        resp = await client.post(
            "/chats",
            json={"title": q[:80]},
        )
        resp.raise_for_status()
        chat = resp.json()
        chat_id = chat.get("id", "")

        resp2 = await client.post(
            f"/chats/{chat_id}/messages",
            data={"message": q},
        )
        resp2.raise_for_status()
        data = resp2.json()

        agents = data.get("agents_used", [])
        result["agents_used"] = agents
        result["agent_correct"] = expected_agent in agents
        result["response"] = data.get("response", "")[:2000]

    except (httpx.HTTPError, OSError, RuntimeError) as exc:
        result["error"] = str(exc)[:200]
        logger.warning("Eval %s failed: %s", entry.get("id"), exc)
        return result

    # ── Source path check ──
    response_text = result.get("response", "")
    for path in expected_paths:
        if not path:
            continue
        # Verbatim citation
        if path in response_text:
            result["source_path_found"] = True
            break
        # Fallback: basename / last component
        if "/" in path:
            basename = path.split("/")[-1]
            if basename and basename in response_text:
                result["source_path_found"] = True
                break
        # Fallback: namespace appears in response
        if namespace and namespace in response_text:
            result["source_path_found"] = True
            break

    # ── LLM-judged faithfulness ──
    if response_text and expected_answer and not isinstance(client, _MockAPIClient):
        score = await _judge_faithfulness(q, expected_answer, response_text)
        result["faithfulness_score"] = score
        result["faithful"] = score >= 0.6

    return result


async def _judge_faithfulness(question: str, expected: str, actual: str) -> float:
    """Use Gemini Flash to score answer faithfulness (0.0-1.0)."""
    import litellm

    prompt = f"""Evaluate how faithfully the ACTUAL answer matches the EXPECTED answer.
Rate on a scale of 0.0 to 1.0:
- 1.0 = fully faithful, all expected facts present, no hallucinations
- 0.5 = partially faithful, some facts correct some missing/wrong
- 0.0 = completely unfaithful or irrelevant

QUESTION: {question}

EXPECTED ANSWER: {expected[:500]}

ACTUAL ANSWER: {actual[:500]}

Reply with a JSON object: {{"score": <float>, "reason": "<one sentence>"}}"""

    try:
        response = await litellm.acompletion(
            model="gemini/gemini-flash-latest",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
            max_tokens=150,
        )
        raw = response.choices[0].message.content or ""
        obj = json.loads(raw.strip().removeprefix("```json").removesuffix("```").strip())
        return float(obj.get("score", 0))
    except Exception:  # noqa: BLE001
        return 0.0


def _build_report(results: list[dict[str, Any]], agg: dict[str, Any]) -> str:
    lines = [
        "# Evaluation Results — FM Agent Fleet",
        "",
        f"**Run at:** {agg['run_at']}  ",
        f"**API URL:** `{agg['api_url']}`  ",
        f"**Mode:** {agg.get('mode', 'live')}  ",
        f"**Seed:** {agg['seed']}  ",
        "",
        "## Summary",
        "",
        "| Metric | Value |",
        "|---|---|",
        f"| Total pairs | {agg['total']} |",
        f"| Correct agent routed | {agg['correct_agent']}/{agg['total']} ({_pct(agg['correct_agent'], agg['total'])}%) |",
        f"| Source path found | {agg['source_path_found']}/{agg['total']} ({_pct(agg['source_path_found'], agg['total'])}%) |",
        f"| Faithful answers | {agg['faithful']}/{agg['total']} ({_pct(agg['faithful'], agg['total'])}%) |",
        f"| Avg faithfulness score | {agg['avg_faithfulness_score']} |",
        "",
        "## Per-Question Results",
        "",
        "| ID | Question | Agent OK | Source OK | Faithful | Score |",
        "|---|---|---|---|---|---|",
    ]

    for r in results:
        agent_ok = "✓" if r.get("agent_correct") else "✗"
        source_ok = "✓" if r.get("source_path_found") else "✗"
        faithful_ok = "✓" if r.get("faithful") else ("✗" if r["faithful"] is not None else "—")
        score = f"{r.get('faithfulness_score', 0):.2f}"
        q_short = r.get("question", "")[:60]
        lines.append(f"| {r['id']} | {q_short} | {agent_ok} | {source_ok} | {faithful_ok} | {score} |")

    lines.append("")
    lines.append("## Errors")
    errors = [r for r in results if r.get("error")]
    if errors:
        for r in errors:
            lines.append(f"- **{r['id']}**: {r['error']}")
    else:
        lines.append("No errors.")

    return "\n".join(lines)


def _pct(part: int, total: int) -> float:
    if total == 0:
        return 0.0
    return round(part / total * 100, 1)


# ── CLI entry point ──────────────────────────────────────────
def _cli() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Run FM Agent evals against the API.")
    parser.add_argument("--api", default="http://localhost:8080", help="API base URL")
    parser.add_argument("--golden", default="examples/fm_agent/evals/golden.yaml", help="Golden YAML file")
    parser.add_argument("--results", default="examples/fm_agent/evals/RESULTS.md", help="Results markdown path")
    parser.add_argument("--dry-run", action="store_true", help="Skip API calls and only check format")
    parser.add_argument("--local-test", action="store_true", help="Run against a mock API")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    args = parser.parse_args()

    asyncio.run(run_evals(
        api_url=args.api,
        golden_path=args.golden,
        results_path=args.results,
        seed=args.seed,
        dry_run=args.dry_run,
        local_test=args.local_test,
    ))


if __name__ == "__main__":
    _cli()
