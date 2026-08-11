"""Derived cards pass — LLM-generated service/module cards via Gemini Flash.

SPEC §4 pass 2: For each backend module in a repo, generate a 300-600 word
summary card using Gemini Flash.  Cards carry `authority=code` and are
regenerated ONLY when the module's git tree-hash differs from the manifest.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
from pathlib import Path
from typing import Any

from orchid_ai.core.repository import OrchidDocument

from .bootstrap import IndexerContext
from .manifest import ManifestRow, make_doc_id
from .secrets import SecretScanner
from .walker import POSTMAN_GLOBS, REPO_NAMESPACE_MAP

logger = logging.getLogger(__name__)

CARD_PROMPT = """You are generating a service/module card for a backend codebase.
Output a JSON object with these fields:
- summary: 300-600 word prose summary describing what this module does, its key responsibilities, and its public interface.
- endpoints: list of key endpoints/functions this module exposes (if applicable).
- dependencies: list of internal and external dependencies.
- config: key configuration points (env vars, config files, etc.).
- notes: any architectural notes, patterns, or caveats.

Be factual. Cite file paths. Do not invent functionality.
Output ONLY the JSON object, no markdown fences, no preamble."""

SOURCECODE_EXTENSIONS = {".ts", ".js", ".py", ".php", ".java", ".go", ".rs", ".rb"}


def _list_module_dirs(repo_path: str) -> list[str]:
    """Find backend module directories within a repo."""
    root = Path(repo_path)
    modules: list[str] = []

    # Common source directories
    for src_dir_name in ("src", "lib", "app", "apps"):
        src = root / src_dir_name
        if not src.is_dir():
            continue
        for entry in sorted(src.iterdir()):
            if entry.is_dir() and not entry.name.startswith((".", "__")):
                # Check if it contains source files
                has_src = any(
                    f.suffix in SOURCECODE_EXTENSIONS
                    for f in entry.rglob("*")
                    if f.is_file() and "node_modules" not in f.parts and "vendor" not in f.parts
                )
                if has_src:
                    modules.append(str(entry))

    # Also check root-level source directories
    for entry in sorted(root.iterdir()):
        if entry.is_dir() and not entry.name.startswith((".", "_")):
            full = str(entry)
            if full in modules:
                continue
            has_src = any(
                f.suffix in SOURCECODE_EXTENSIONS
                for f in entry.rglob("*")
                if f.is_file() and "node_modules" not in f.parts and "vendor" not in f.parts
            )
            if has_src and entry.name not in ("tests", "test", "__pycache__", "node_modules", "vendor", ".git"):
                modules.append(full)

    return modules


def _module_tree_hash(module_path: str) -> str:
    """Compute tree-hash of all source files in a module directory."""
    hasher = hashlib.sha256()
    root = Path(module_path)
    files = sorted(
        f for f in root.rglob("*")
        if f.is_file() and f.suffix in SOURCECODE_EXTENSIONS
        and "node_modules" not in f.parts and "vendor" not in f.parts
    )
    for f in files[:100]:  # Don't hash 10k files — first 100 is enough
        rel = f.relative_to(root)
        hasher.update(str(rel).encode())
        hasher.update(f.read_bytes()[:4096])
    return hasher.hexdigest()


def _gather_module_context(module_path: str) -> str:
    """Collect enough context for the LLM to generate a card."""
    root = Path(module_path)
    pieces: list[str] = []

    # README first
    for readme_name in ("README.md", "readme.md", "README", "README.txt"):
        readme = root / readme_name
        if readme.exists():
            pieces.append(f"### README ({readme_name})\n{readme.read_text()[:3000]}\n")
            break

    # Source file headers — first 100 lines of each key file
    source_files = sorted(
        f for f in root.rglob("*")
        if f.is_file() and f.suffix in SOURCECODE_EXTENSIONS
        and "node_modules" not in f.parts and "vendor" not in f.parts
    )[:15]

    for sf in source_files:
        text = sf.read_text()[:2000]
        pieces.append(f"### {sf.relative_to(root)}\n{text}\n")

    return "\n\n".join(pieces)[:12000]


async def _generate_card(ctx: IndexerContext, repo: str, module_path: str) -> dict[str, Any] | None:
    """Generate a module summary card using Gemini Flash."""
    import litellm

    context = _gather_module_context(module_path)
    if not context.strip():
        return None

    messages = [
        {"role": "user", "content": f"{CARD_PROMPT}\n\nRepository: {repo}\nModule: {os.path.basename(module_path)}\n\nSource files:\n\n{context}"}
    ]

    try:
        response = await litellm.acompletion(
            model="gemini/gemini-flash-latest",
            messages=messages,
            temperature=0.1,
            max_tokens=2000,
        )
        text = response.choices[0].message.content or ""
    except Exception as exc:  # noqa: BLE001
        logger.error("Card generation failed for %s/%s: %s", repo, module_path, exc)
        return None

    try:
        text = text.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1]
            if text.endswith("```"):
                text = text[:-3].strip()
        return json.loads(text)
    except json.JSONDecodeError:
        logger.warning("Card JSON parse failed for %s/%s, storing raw text", repo, module_path)
        return {"summary": text, "endpoints": [], "dependencies": [], "config": [], "notes": []}


async def generate_cards(
    ctx: IndexerContext,
    repo_paths: list[str],
    force: bool = False,
) -> None:
    """Generate derived module cards for all repos."""
    import os as _os

    total_cards = 0
    total_skipped = 0

    for repo_path in repo_paths:
        repo_name = _os.path.basename(repo_path.rstrip("/"))
        modules = _list_module_dirs(repo_path)
        logger.info("Cards: %d modules found in %s", len(modules), repo_name)

        for module_path in modules:
            module_rel = str(Path(module_path).relative_to(repo_path))
            tree_hash = _module_tree_hash(module_path)

            if not force:
                should_skip = await ctx.manifest.should_skip(repo_name, module_rel, "cards", tree_hash)
                if should_skip:
                    logger.debug("Card unchanged: %s/%s", repo_name, module_rel)
                    total_skipped += 1
                    continue

            card = await _generate_card(ctx, repo_name, module_path)
            if card is None:
                continue

            card_text = json.dumps(card, indent=2)
            namespace = _resolve_cards_namespace(repo_name)

            doc_id = make_doc_id(repo_name, module_rel, 0)
            metadata = {
                "tenant_id": ctx.scope.tenant_id,
                "scope": "tenant",
                "repo": repo_name,
                "path": module_rel,
                "doc_type": "derived-card",
                "authority": "code",
                "branch": "develop",
            }

            doc = OrchidDocument(
                id=doc_id,
                page_content=card_text,
                metadata=metadata,
            )
            await ctx.writer.upsert([doc], namespace)

            await ctx.manifest.upsert(ManifestRow(
                repo=repo_name,
                path=module_rel,
                pass_type="cards",
                tree_hash=tree_hash,
                doc_id=doc_id,
                chunks=1,
            ))

            logger.info("Card generated: %s/%s → %s", repo_name, module_rel, namespace)
            total_cards += 1

    logger.info("Cards pass complete: %d cards generated, %d unchanged", total_cards, total_skipped)
    print(f"\nCards pass: {total_cards} generated, {total_skipped} unchanged")


def _resolve_cards_namespace(repo_name: str) -> str:
    return REPO_NAMESPACE_MAP.get(repo_name, repo_name)


async def generate_endpoint_cards(
    ctx: IndexerContext,
    repo_paths: list[str],
    force: bool = False,
) -> None:
    """Generate API endpoint cards from Postman collections.

    One card is generated per collection file.  Secrets are stripped before the
    JSON is parsed and the card is stored under ``pass_type="cards"``.
    """
    scanner = SecretScanner()
    total = 0

    for repo_path in repo_paths:
        repo_name = os.path.basename(repo_path.rstrip("/"))
        namespace = _resolve_cards_namespace(repo_name)

        for collection_path in _find_postman_collections(repo_path):
            rel_path = os.path.relpath(collection_path, repo_path)
            content = Path(collection_path).read_text()
            tree_hash = hashlib.sha256(content.encode()).hexdigest()

            if not force:
                should_skip = await ctx.manifest.should_skip(repo_name, rel_path, "cards", tree_hash)
                if should_skip:
                    logger.debug("Endpoint card unchanged: %s/%s", repo_name, rel_path)
                    continue

            card = _build_endpoint_card(collection_path, scanner)
            if not card:
                logger.warning("No endpoints extracted from %s/%s", repo_name, rel_path)
                continue

            doc_id = make_doc_id(repo_name, rel_path, 0)
            card_text = json.dumps(card, indent=2)
            doc = OrchidDocument(
                id=doc_id,
                page_content=card_text,
                metadata={
                    "repo": repo_name,
                    "path": rel_path,
                    "doc_type": "api",
                    "authority": "code",
                    "branch": "develop",
                },
            )
            await ctx.writer.upsert([doc], namespace)
            await ctx.manifest.upsert(ManifestRow(
                repo=repo_name,
                path=rel_path,
                pass_type="cards",
                tree_hash=tree_hash,
                doc_id=doc_id,
                chunks=1,
            ))

            logger.info("Endpoint card generated: %s/%s → %s", repo_name, rel_path, namespace)
            total += 1

    logger.info("Endpoint cards pass complete: %d cards generated", total)
    print(f"\nEndpoint cards: {total} generated")


def _find_postman_collections(repo_path: str) -> list[str]:
    """Return absolute paths to Postman collection files in a repo."""
    root = Path(repo_path)
    results: list[str] = []
    for pattern in POSTMAN_GLOBS:
        results.extend(str(p) for p in root.rglob(pattern) if p.is_file())
    return sorted(results)


def _build_endpoint_card(path: str, scanner: SecretScanner) -> dict[str, Any] | None:
    """Parse a Postman collection, redact secrets, and return an endpoint card."""
    try:
        text = Path(path).read_text()
    except (OSError, UnicodeDecodeError):
        return None

    scan_result = scanner.scan(text, path=path)
    try:
        data = json.loads(scan_result.cleaned_text)
    except json.JSONDecodeError:
        logger.warning("Endpoint card JSON parse failed: %s", path)
        return None

    if not isinstance(data, dict):
        return None

    endpoints = [_extract_endpoint(item) for item in _walk_postman_items(data.get("item", []))]
    endpoints = [ep for ep in endpoints if ep]
    if not endpoints:
        return None

    return {
        "title": data.get("info", {}).get("name", "API Endpoints"),
        "endpoints": endpoints,
        "source": path,
    }


def _walk_postman_items(items: Any) -> list[dict[str, Any]]:
    """Flatten nested Postman folders into a list of request items."""
    result: list[dict[str, Any]] = []
    if not isinstance(items, list):
        return result
    for item in items:
        if not isinstance(item, dict):
            continue
        if "request" in item:
            result.append(item)
        result.extend(_walk_postman_items(item.get("item", [])))
    return result


def _extract_endpoint(item: dict[str, Any]) -> dict[str, Any] | None:
    """Extract method, path, and summary from a Postman request item."""
    request = item.get("request")
    if not isinstance(request, dict):
        return None

    method = request.get("method", "GET")
    url_data = request.get("url") or {}
    if isinstance(url_data, str):
        path = url_data
    elif isinstance(url_data, dict):
        raw_path = url_data.get("raw", "")
        path_parts = url_data.get("path", [])
        if isinstance(path_parts, list):
            path = "/" + "/".join(str(p) for p in path_parts)
        else:
            path = str(raw_path)
    else:
        path = ""

    return {
        "method": method,
        "path": path,
        "summary": item.get("name", ""),
    }
