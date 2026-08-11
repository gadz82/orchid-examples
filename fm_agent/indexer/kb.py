"""Help Center crawler — ``fm-indexer kb``.

Crawls whitelisted sections from an external Help Center (SPEC §3
``product-kb`` namespace).  Enumerates articles, fetches en-us as
canonical, strips chrome, ingests headered.  Idempotent on
``(article_id, updated_at)``.  Config-driven section list.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import re
from typing import Any
from urllib.parse import urljoin

import httpx
from orchid_ai.core.repository import OrchidDocument

from .bootstrap import IndexerContext
from .manifest import ManifestRow, make_doc_id
from .walker import ExclusionConfig

logger = logging.getLogger(__name__)


class HelpCenterCrawler:
    """Crawl whitelisted Help Center sections into ``product-kb``."""

    def __init__(
        self,
        ctx: IndexerContext,
        sections: list[dict[str, Any]],
        base_url: str = "",
    ) -> None:
        self._ctx = ctx
        self._sections = sections
        self._base_url = base_url.rstrip("/") if base_url else ""

    @classmethod
    def from_config(
        cls,
        ctx: IndexerContext,
        config_path: str = "examples/fm_agent/corpus/exclusions.yml",
    ) -> HelpCenterCrawler:
        """Load sections from exclusions.yml or a standalone KB config."""
        config = ExclusionConfig.from_file(config_path)
        return cls(ctx, config.help_center_sections, config.help_center_base_url)

    async def crawl(self) -> dict[str, int]:
        """Crawl all configured sections. Returns {section_name: articles_count}."""
        stats: dict[str, int] = {}

        for section_cfg in self._sections:
            section_name = section_cfg.get("name", section_cfg.get("id", "unknown"))
            section_id = section_cfg.get("id", "")
            section_url = section_cfg.get("url", "")
            logger.info("Crawling section: %s (%s)", section_name, section_url)

            try:
                articles = await self._enumerate_articles(section_url, section_id)
            except (httpx.HTTPError, OSError, RuntimeError) as exc:
                logger.error("Failed to enumerate articles for %s: %s", section_name, exc)
                stats[section_name] = 0
                continue

            ingested = 0
            for article in articles:
                try:
                    ok = await self._ingest_article(article)
                    if ok:
                        ingested += 1
                except (httpx.HTTPError, OSError, RuntimeError) as exc:
                    logger.error("Failed to ingest article %s: %s", article.get("id", "?"), exc)

            stats[section_name] = ingested
            logger.info("Section %s: %d/%d articles ingested", section_name, ingested, len(articles))

        return stats

    async def _enumerate_articles(self, section_url: str, section_id: str) -> list[dict[str, Any]]:
        """Fetch article list from a section page. Requires httpx."""
        import httpx

        articles: list[dict[str, Any]] = []
        url = section_url if section_url else self._build_section_url(section_id)

        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            resp = await client.get(url, headers={"Accept-Language": "en-US"})
            resp.raise_for_status()
            html = resp.text

            # Extract article links — generic pattern: look for common Help Center patterns
            links = re.findall(r'href="(/hc/[^"]+)"', html)
            link_set: set[str] = set()
            for link in links:
                if link not in link_set and "/articles/" in link:
                    link_set.add(link)

            for link in sorted(link_set):
                article_url = urljoin(url, link) if not link.startswith("http") else link
                article_id_match = re.search(r'/articles/(\d+)', article_url)
                if article_id_match:
                    article_id = article_id_match.group(1)
                else:
                    article_id = link

                articles.append({
                    "id": article_id,
                    "url": article_url,
                    "section": section_id,
                })

            logger.info("Found %d articles in section %s", len(articles), section_id)

        return articles

    def _build_section_url(self, section_id: str) -> str:
        return f"{self._base_url}/sections/{section_id}"

    async def _fetch_article(self, article_url: str) -> str | None:
        """Fetch and clean article content."""
        import httpx

        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            try:
                resp = await client.get(
                    article_url,
                    headers={"Accept-Language": "en-US"},
                )
                resp.raise_for_status()
                html = resp.text
            except (httpx.HTTPError, OSError) as exc:
                logger.warning("Failed to fetch article %s: %s", article_url, exc)
                return None

            # Strip nav/footer chrome — extract article body
            body_match = re.search(r'<article[^>]*>(.*?)</article>', html, re.DOTALL | re.IGNORECASE)
            if body_match:
                html = body_match.group(1)

            # Simple HTML→text conversion
            text = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
            text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL | re.IGNORECASE)
            text = re.sub(r'<[^>]+>', '\n', text)
            text = re.sub(r'\n{3,}', '\n\n', text)
            text = re.sub(r' {2,}', ' ', text)
            text = text.strip()

            if not text or len(text) < 50:
                logger.warning("Article %s has insufficient content (%d chars)", article_url, len(text))
                return None

            return text

    async def _ingest_article(self, article: dict[str, Any]) -> bool:
        """Fetch, chunk, and upsert a single KB article."""
        article_id = article.get("id", "")
        article_url = article.get("url", "")
        section = article.get("section", "")

        content = await self._fetch_article(article_url)
        if content is None:
            return False

        # Check idempotency via content hash
        content_hash = hashlib.sha256(content.encode()).hexdigest()
        should_skip = await self._ctx.manifest.should_skip(
            "help-center", f"articles/{article_id}", "docs", content_hash,
        )
        if should_skip:
            logger.debug("KB article unchanged: %s", article_id)
            return True

        from orchid_ai.documents.strategies import HeaderedIngestion
        strategy = HeaderedIngestion()

        chunks = await strategy.ingest(
            text=content,
            filename=f"articles/{article_id}.html",
            scope=self._ctx.scope,
        )

        documents: list[OrchidDocument] = []
        for i, chunk in enumerate(chunks):
            doc_id = make_doc_id("help-center", f"articles/{article_id}", i)
            metadata = dict(chunk.metadata)
            metadata.update({
                "article_id": article_id,
                "locale": "en-us",
                "section": section,
                "source": "help-center",
                "authority": "doc",
            })
            documents.append(OrchidDocument(
                id=doc_id,
                page_content=chunk.text,
                metadata=metadata,
            ))

        if documents:
            await self._ctx.writer.upsert(documents, "product-kb")

        await self._ctx.manifest.upsert(ManifestRow(
            repo="help-center",
            path=f"articles/{article_id}",
            pass_type="docs",
            tree_hash=content_hash,
            chunks=len(documents),
        ))

        logger.info("KB article ingested: %s → product-kb (%d chunks)", article_id, len(documents))
        await asyncio.sleep(0.5)  # Rate limiting
        return True
