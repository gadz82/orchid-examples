"""Graph extraction pass — deterministic parsers for platform dependency graph.

Parses serverless.yml, CDK stacks, package.json/composer.json deps,
catalog-info.yaml ownership, and paas-notification-meta taxonomy tree.
Emits Neo4j nodes/edges and serializes text cards into the
``platform-graph`` Qdrant namespace.

No LLM — deterministic only.  Idempotent: MERGE on stable natural keys.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

import yaml
from orchid_ai.core.graph_store import OrchidEdge, OrchidEntity

logger = logging.getLogger(__name__)

ENTITY_TYPES = {"SERVICE", "QUEUE", "TOPIC", "LAMBDA", "SSM_PARAM", "ENDPOINT", "PRODUCT", "NOTIFICATION_GROUP", "NOTIFICATION_TYPE"}
EDGE_RELATIONS = {"CONSUMES", "PUBLISHES", "READS_PARAM", "DEPENDS_ON", "DEPLOYED_BY", "HAS_GROUP", "HAS_TYPE", "REGISTERED_WITH"}


class GraphExtractor:
    """Extracts entities and edges from a repo's config files."""

    def __init__(self, repo_name: str, repo_path: str) -> None:
        self.repo = repo_name
        self.path = repo_path
        self.entities: list[OrchidEntity] = []
        self.edges: list[OrchidEdge] = []

    async def extract(self) -> None:
        self._extract_serverless()
        self._extract_cdk_stacks()
        self._extract_package_deps()
        self._extract_catalog_info()
        self._extract_notification_meta()

    def _eid(self, etype: str, name: str) -> str:
        return f"{self.repo}|{etype}|{name}"

    def _entity(self, etype: str, name: str, **props: Any) -> OrchidEntity:
        return OrchidEntity(
            id=self._eid(etype, name),
            type=etype,
            name=name,
            properties=props,
            metadata={"repo": self.repo},
        )

    def _edge(self, source_id: str, rel: str, target_id: str, **props: Any) -> OrchidEdge:
        return OrchidEdge(
            source_id=source_id,
            target_id=target_id,
            relation=rel,
            properties=props,
            metadata={"repo": self.repo},
        )

    # ── Serverless.yml parsing ────────────────────────────────

    def _extract_serverless(self) -> None:
        root = Path(self.path)
        candidates: list[Path] = []
        for pattern in ("serverless.yml", "serverless.yaml"):
            p = root / pattern
            if p.exists():
                candidates.append(p)
        for pattern in ("config/functions/*.yml", "config/functions/*.yaml"):
            candidates.extend(sorted(root.glob(pattern)))
        if not candidates:
            return

        svc_name = self.repo
        svc_id = self._eid("SERVICE", svc_name)
        if not any(e.id == svc_id for e in self.entities):
            self.entities.append(self._entity("SERVICE", svc_name, source="serverless.yml"))

        for p in candidates:
            try:
                data = yaml.safe_load(p.read_text()) or {}
            except (OSError, yaml.YAMLError):
                continue
            functions = data.get("functions") or {}
            for fn_name, fn_cfg in functions.items():
                fn_id = self._eid("LAMBDA", fn_name)
                fn_props: dict[str, Any] = {"service": svc_name, "source": str(p.relative_to(root))}
                if isinstance(fn_cfg, dict):
                    fn_props["handler"] = fn_cfg.get("handler", "")
                    events = fn_cfg.get("events") or []
                    self._parse_serverless_events(events, fn_id, fn_name, svc_name, str(p))
                self.entities.append(self._entity("LAMBDA", fn_name, **fn_props))
                self.edges.append(self._edge(svc_id, "DEPLOYED_BY", fn_id))

    def _parse_serverless_events(self, events: list[Any], fn_id: str, fn_name: str, svc_name: str, source_path: str) -> None:
        for evt in events:
            if not isinstance(evt, dict):
                continue
            for evt_type, evt_cfg in evt.items():
                if evt_type in ("sqs",):
                    queue_name = isinstance(evt_cfg, dict) and evt_cfg.get("arn", "") or ""
                    if not queue_name:
                        queue_name = evt_type
                    qid = self._eid("QUEUE", queue_name)
                    self.entities.append(self._entity("QUEUE", queue_name, source=source_path))
                    self.edges.append(self._edge(fn_id, "CONSUMES", qid))
                elif evt_type in ("sns",):
                    topic_name = isinstance(evt_cfg, dict) and evt_cfg.get("topicName", "") or evt_type
                    tid = self._eid("TOPIC", topic_name)
                    self.entities.append(self._entity("TOPIC", topic_name, source=source_path))
                    self.edges.append(self._edge(fn_id, "CONSUMES", tid))

    # ── CDK stack parsing ─────────────────────────────────────

    def _extract_cdk_stacks(self) -> None:
        for root, _dirs, files in os.walk(self.path):
            for fn in files:
                if not fn.endswith(".ts"):
                    continue
                fp = os.path.join(root, fn)
                try:
                    content = Path(fp).read_text()
                except (OSError, UnicodeDecodeError) as exc:
                    logger.debug("Skipping %s: %s", fp, exc)
                    continue
                if "StringParameter" not in content and "CfnQueue" not in content:
                    continue

                import re

                svc_name = self.repo
                svc_id = self._eid("SERVICE", svc_name)
                if not any(e.id == svc_id for e in self.entities):
                    self.entities.append(self._entity("SERVICE", svc_name, source=os.path.relpath(fp, self.path)))

                for m in re.finditer(r'(?:CfnQueue|Queue)\s*\(\s*this\s*,\s*["\'](\w+)["\']', content):
                    qname = m.group(1)
                    self.entities.append(self._entity("QUEUE", qname, source=os.path.relpath(fp, self.path)))

                for m in re.finditer(r'(?:CfnTopic|Topic)\s*\(\s*this\s*,\s*["\'](\w+)["\']', content):
                    tname = m.group(1)
                    self.entities.append(self._entity("TOPIC", tname, source=os.path.relpath(fp, self.path)))

                for m in re.finditer(r'StringParameter\.([A-Z0-9_]+)', content):
                    param_name = f"CDK-BASE-STACK_{m.group(1)}"
                    pid = self._eid("SSM_PARAM", param_name)
                    self.entities.append(self._entity("SSM_PARAM", param_name, source=os.path.relpath(fp, self.path)))
                    self.edges.append(self._edge(svc_id, "PUBLISHES", pid))

    # ── Package dependencies ──────────────────────────────────

    def _extract_package_deps(self) -> None:
        svc_name = self.repo
        svc_id = self._eid("SERVICE", svc_name)

        for pkg_file in ("package.json", "composer.json"):
            p = Path(self.path) / pkg_file
            if not p.exists():
                continue
            try:
                data = json.loads(p.read_text())
            except (json.JSONDecodeError, ValueError):
                continue
            deps = {**data.get("dependencies", {}), **data.get("devDependencies", {})}
            for dep_name in deps:
                dep_id = self._eid("SERVICE", dep_name)
                self.edges.append(self._edge(svc_id, "DEPENDS_ON", dep_id, type="package"))

    # ── Catalog-info ownership ────────────────────────────────

    def _extract_catalog_info(self) -> None:
        for pattern in ("catalog-info.yaml", "catalog-info.yml"):
            p = Path(self.path) / pattern
            if p.exists():
                data = yaml.safe_load(p.read_text()) or {}
                break
        else:
            return

        svc_name = self.repo
        svc_id = self._eid("SERVICE", svc_name)
        metadata = data.get("metadata") or {}
        owner = metadata.get("owner", "")

        if owner:
            owner_id = self._eid("SERVICE", f"team:{owner}")
            self.entities.append(self._entity("SERVICE", f"team:{owner}", source="catalog-info", kind="team"))
            self.edges.append(self._edge(svc_id, "DEPENDS_ON", owner_id, relation_type="ownership"))

    # ── Notification meta taxonomy ────────────────────────────

    def _extract_notification_meta(self) -> None:
        base = Path(self.path) / "meta-notifications"
        if not base.is_dir():
            return

        for product_dir in sorted(base.iterdir()):
            if not product_dir.is_dir():
                continue
            meta_file = product_dir / "meta.json"
            product_name = product_dir.name
            pid = self._eid("PRODUCT", product_name)
            self.entities.append(self._entity("PRODUCT", product_name))

            taxonomy: dict[str, Any] = {}
            if meta_file.exists():
                try:
                    taxonomy = json.loads(meta_file.read_text()) or {}
                except (json.JSONDecodeError, ValueError):
                    pass

            for group_dir in sorted(product_dir.iterdir()):
                if not group_dir.is_dir() or group_dir.name.startswith("."):
                    continue
                gid = self._eid("NOTIFICATION_GROUP", f"{product_name}/{group_dir.name}")
                self.entities.append(self._entity("NOTIFICATION_GROUP", f"{product_name}/{group_dir.name}"))
                self.edges.append(self._edge(pid, "HAS_GROUP", gid))

                group_meta = taxonomy.get(group_dir.name, {}) if isinstance(taxonomy, dict) else {}
                types = group_meta.get("notifications", []) if isinstance(group_meta, dict) else []
                for notif in types:
                    if not isinstance(notif, str):
                        continue
                    nid = self._eid("NOTIFICATION_TYPE", f"{product_name}/{group_dir.name}/{notif}")
                    self.entities.append(self._entity("NOTIFICATION_TYPE", f"{product_name}/{group_dir.name}/{notif}"))
                    self.edges.append(self._edge(gid, "HAS_TYPE", nid))

            # Register product with notification-be
            be_id = self._eid("SERVICE", "notification-be")
            self.edges.append(self._edge(pid, "REGISTERED_WITH", be_id))

    # ── Text card serialization ───────────────────────────────

    def serialize_cards(self) -> list[str]:
        """Serialize each entity + 1-hop neighbourhood as a text card."""
        cards: list[str] = []
        adj: dict[str, list[str]] = {}
        for e in self.edges:
            adj.setdefault(e.source_id, []).append(f"{e.relation} → {e.target_id}")
            adj.setdefault(e.target_id, []).append(f"← {e.source_id} {e.relation}")

        for ent in self.entities:
            props_str = ", ".join(f"{k}={v}" for k, v in ent.properties.items() if v)
            lines = [
                f"# {ent.type}: {ent.name}",
                f"ID: {ent.id}",
                f"Repo: {ent.metadata.get('repo', self.repo)}",
                f"Properties: {props_str}" if props_str else "",
                "Relations:",
            ]
            neighbours = adj.get(ent.id, [])
            for n in sorted(neighbours)[:20]:
                lines.append(f"  - {n}")
            cards.append("\n".join(line for line in lines if line))

        return cards
