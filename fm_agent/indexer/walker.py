"""Filesystem walker with exclusions and repo→namespace mapping.

Walks the filesystem (NOT ``git ls-files`` — nested git repos like hydra's
``apps/<svc>`` are missed by ls-files on the parent) and applies exclusion
rules from ``corpus/exclusions.yml``.

Repo→namespace mapping (SPEC §3):

  notification-be         → svc-notification
  paas-notification-meta  → svc-notification
  mailer-service-be       → svc-mailer
  push-notification-service-be → svc-push
  serverless-event-bus    → svc-eventbus
  sync-bus-be             → svc-eventbus
  domains                 → svc-domains
  cdk-base-stack-devops   → svc-devops
  ci-paas-gitflow-devops  → svc-devops
  ci-templates-devops     → svc-devops (but README deduplicated)
  hydra/apps/messenger + relevant shared/ → svc-messenger

Exclusions:
  - vendor/, node_modules/, dist/, cdk.out/, .git/
  - generated clients (src/generated/)
  - datadog vendored tracer
  - .d.ts/.js sibling files
  - hydra/migrations (3,265 files)
  - .env*, *.pem, *key*, **/fixtures/**secrets** (secret scanning)
  - HIDs: .pdf, .xlsx, .pptx, .png, .jpg  (no binary parsers wired)
"""

from __future__ import annotations

import fnmatch
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml

logger = logging.getLogger(__name__)

# ── Repo → namespace mapping ──────────────────────────────────

REPO_NAMESPACE_MAP: dict[str, str] = {
    "notification-be": "svc-notification",
    "paas-notification-meta": "svc-notification",
    "mailer-service-be": "svc-mailer",
    "push-notification-service-be": "svc-push",
    "serverless-event-bus": "svc-eventbus",
    "sync-bus-be": "svc-eventbus",
    "domains": "svc-domains",
    "cdk-base-stack-devops": "svc-devops",
    "ci-paas-gitflow-devops": "svc-devops",
    "ci-templates-devops": "svc-devops",
}

# ── Default exclusion patterns ────────────────────────────────

DEFAULT_EXCLUDE_GLOBS: list[str] = [
    ".git/**", "vendor/**", "node_modules/**", "dist/**", "cdk.out/**",
    "__pycache__/**", ".venv/**", ".pytest_cache/**", ".ruff_cache/**",
    "**/src/generated/**",
    "**/migrations/**",
    ".env*", "*.pem", "*key*", "**/fixtures/**secrets**",
    "*.pdf", "*.xlsx", "*.pptx", "*.png", "*.jpg", "*.jpeg",
    "*.d.ts", "*.js",
]

DEFAULT_EXCLUDE_DIRS: set[str] = {
    ".git", "vendor", "node_modules", "dist", "cdk.out",
    "__pycache__", ".venv", ".pytest_cache", ".ruff_cache",
    "migrations",
}

DOC_EXTENSIONS: set[str] = {
    ".md", ".yaml", ".yml", ".json", ".ts", ".php", ".env",
    ".py", ".txt", ".rst",
}

# Files that get special treatment
OPENAPI_GLOBS = ["**/openapi*.yaml", "**/openapi*.yml", "**/swagger*.yaml", "**/swagger*.yml"]
CATALOG_INFO_GLOBS = ["**/catalog-info.yaml", "**/catalog-info.yml"]
CONFIG_GLOBS = ["**/config/functions/*.yml", "**/config/functions/*.yaml"]
DEPLOY_GLOBS = ["**/deploy.*.yml", "**/deploy.*.yaml"]
ENVDIST_GLOBS = ["**/env-dist", "**/env.dist"]
CDK_CONTEXT = ["**/cdk.context.json"]
POSTMAN_GLOBS = ["**/postman_collection.json", "**/postman/*.json"]


@dataclass
class ExclusionConfig:
    exclude_paths: list[str] = field(default_factory=list)
    exclude_patterns: list[str] = field(default_factory=list)
    help_center_sections: list[dict[str, str]] = field(default_factory=list)
    help_center_base_url: str = ""

    @classmethod
    def from_file(cls, path: str) -> ExclusionConfig:
        p = Path(path)
        if not p.exists():
            logger.warning("Exclusion file %s not found, using defaults", path)
            return cls()
        data = yaml.safe_load(p.read_text()) or {}
        return cls(
            exclude_paths=data.get("exclude_paths") or [],
            exclude_patterns=data.get("exclude_patterns") or [],
            help_center_sections=data.get("help_center_sections") or [],
            help_center_base_url=data.get("help_center_base_url", ""),
        )

    def all_globs(self) -> list[str]:
        return DEFAULT_EXCLUDE_GLOBS + self.exclude_patterns + self.exclude_paths

    def all_dirs(self) -> set[str]:
        return DEFAULT_EXCLUDE_DIRS | {os.path.normpath(p).split(os.sep)[0] for p in self.exclude_paths}


@dataclass
class WalkedFile:
    repo: str
    repo_path: str  # absolute path to the repo root
    relative_path: str  # relative path within the repo
    absolute_path: str
    extension: str
    namespace: str
    doc_type: str = ""  # resolved later: readme|api|config|skill|derived-card

    @property
    def file_id(self) -> str:
        return f"{self.repo}|{self.relative_path}"


class RepoWalker:
    """Walk filesystem repos applying exclusion rules."""

    def __init__(self, exclusions: ExclusionConfig) -> None:
        self._excl_globs = exclusions.all_globs()
        self._excl_dirs = exclusions.all_dirs()

    def is_excluded(self, relative_path: str) -> bool:
        norm = relative_path.replace("\\", "/")
        for pattern in self._excl_globs:
            if fnmatch.fnmatch(norm, pattern) or fnmatch.fnmatch(norm, pattern + "/**"):
                return True
        parts = norm.split("/")
        for part in parts:
            if part in self._excl_dirs:
                return True
        return False

    def get_doc_type(self, relative_path: str) -> str:
        """Infer doc_type from file path."""
        norm = relative_path.lower().replace("\\", "/")
        file_name = os.path.basename(norm)
        if any(fnmatch.fnmatch(norm, g) for g in POSTMAN_GLOBS):
            return "api"
        if any(fnmatch.fnmatch(norm, g) for g in OPENAPI_GLOBS):
            return "api"
        if any(fnmatch.fnmatch(norm, g) for g in CATALOG_INFO_GLOBS):
            return "config"
        if any(fnmatch.fnmatch(norm, g) for g in CONFIG_GLOBS):
            return "config"
        if any(fnmatch.fnmatch(norm, g) for g in DEPLOY_GLOBS):
            return "config"
        if any(fnmatch.fnmatch(norm, g) for g in CDK_CONTEXT):
            return "config"
        if any(fnmatch.fnmatch(norm, g) for g in ENVDIST_GLOBS):
            return "config"
        if file_name.lower().startswith("readme"):
            return "readme"
        if ".skills/" in norm or ".agents/" in norm or ".cursor/" in norm or ".ai/" in norm:
            return "skill"
        if file_name.lower() == "changelog.md":
            return "changelog"
        return "doc"

    def get_ingestion_strategy(self, namespace: str, doc_type: str) -> str:
        """Return the ingestion strategy name for a namespace + doc_type pair (SPEC §3)."""
        if namespace == "eng-standards":
            return "semantic"
        if namespace == "svc-notification" and doc_type == "readme":
            return "hierarchical"
        if doc_type in ("readme", "api", "config"):
            return "headered"
        return "headered"

    def resolve_namespace(self, repo: str, relative_path: str) -> str:
        """Map a repo + path to a RAG namespace (SPEC §3)."""
        repo_name = repo.rstrip("/").split("/")[-1]
        norm = relative_path.replace("\\", "/")

        # Hydra special case — only apps/messenger + relevant shared/
        if repo_name == "hydra":
            if norm.startswith("apps/messenger/") or norm == "apps/messenger":
                return "svc-messenger"
            if norm.startswith("shared/"):
                return "svc-messenger"
            return ""  # excluded from all other apps/

        # domains special case — .cursor/skills go to eng-standards
        if repo_name == "domains":
            if ".cursor/skills" in norm or ".ai/skills" in norm:
                return "eng-standards"
            return REPO_NAMESPACE_MAP.get(repo_name, repo_name)

        return REPO_NAMESPACE_MAP.get(repo_name, repo_name)

    def walk_repo(self, repo_path: str) -> list[WalkedFile]:
        """Walk a single repo, returning files to ingest."""
        repo_name = os.path.basename(repo_path.rstrip("/"))
        results: list[WalkedFile] = []
        root = Path(repo_path)

        if not root.is_dir():
            logger.warning("Repo path %s is not a directory", repo_path)
            return results

        for dirpath, dirnames, filenames in os.walk(root):
            # Skip excluded directories in-place
            dirnames[:] = [d for d in dirnames if d not in self._excl_dirs]

            for fname in filenames:
                abs_path = os.path.join(dirpath, fname)
                rel_path = os.path.relpath(abs_path, repo_path)
                if self.is_excluded(rel_path):
                    logger.debug("Excluded: %s/%s", repo_name, rel_path)
                    continue

                ext = os.path.splitext(fname)[1].lower()
                if ext not in DOC_EXTENSIONS:
                    continue

                namespace = self.resolve_namespace(repo_name, rel_path)
                if not namespace:
                    logger.debug("Unmapped: %s/%s", repo_name, rel_path)
                    continue

                # Dedupe: ci-templates-devops README
                if repo_name == "ci-templates-devops" and fname.lower().startswith("readme"):
                    logger.info("Skipping ci-templates-devops README (deduplicated with ci-paas-gitflow)")
                    continue

                doc_type = self.get_doc_type(rel_path)
                results.append(WalkedFile(
                    repo=repo_name,
                    repo_path=repo_path,
                    relative_path=rel_path,
                    absolute_path=abs_path,
                    extension=ext,
                    namespace=namespace,
                    doc_type=doc_type,
                ))

        logger.info("Walked %s: %d files collected", repo_name, len(results))
        return results
