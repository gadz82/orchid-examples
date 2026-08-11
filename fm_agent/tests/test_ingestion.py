"""Tests for document ingestion strategy selection and endpoint cards."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock

import pytest

from examples.fm_agent.indexer.cards import (
    _build_endpoint_card,
    _extract_endpoint,
    _find_postman_collections,
    _walk_postman_items,
    generate_endpoint_cards,
)
from examples.fm_agent.indexer.secrets import SecretScanner
from examples.fm_agent.indexer.walker import ExclusionConfig, RepoWalker


class TestIngestionStrategy:
    """Cover strategy resolution from walker."""

    @pytest.fixture
    def walker(self):
        return RepoWalker(ExclusionConfig())

    def test_notification_readme_uses_hierarchical(self, walker) -> None:
        assert walker.get_ingestion_strategy("svc-notification", "readme") == "hierarchical"

    def test_other_readme_uses_headered(self, walker) -> None:
        assert walker.get_ingestion_strategy("svc-mailer", "readme") == "headered"

    def test_api_and_config_use_headered(self, walker) -> None:
        assert walker.get_ingestion_strategy("svc-notification", "api") == "headered"
        assert walker.get_ingestion_strategy("svc-notification", "config") == "headered"

    def test_eng_standards_uses_semantic(self, walker) -> None:
        assert walker.get_ingestion_strategy("eng-standards", "skill") == "semantic"


class TestPostmanEndpointCard:
    """Cover Postman collection detection, parsing, secret redaction, and card generation."""

    @pytest.fixture
    def postman_collection(self, tmp_path):
        collection = {
            "info": {"name": "Notification API"},
            "item": [
                {
                    "name": "Send notification",
                    "request": {
                        "method": "POST",
                        "url": {
                            "raw": "https://api.example.com/notifications",
                            "path": ["notifications"],
                        },
                    },
                },
                {
                    "name": "Get notification",
                    "request": {
                        "method": "GET",
                        "url": {
                            "raw": "https://api.example.com/notifications/:id",
                            "path": ["notifications", ":id"],
                        },
                    },
                },
                {
                    "name": "Subfolder",
                    "item": [
                        {
                            "name": "Delete notification",
                            "request": {
                                "method": "DELETE",
                                "url": "https://api.example.com/notifications/:id",
                            },
                        },
                    ],
                },
            ],
        }
        path = tmp_path / "postman_collection.json"
        path.write_text(json.dumps(collection))
        return path

    @pytest.fixture
    def postman_with_secret(self, tmp_path):
        collection = {
            "info": {"name": "Notification API"},
            "auth": {"type": "bearer", "bearer": [{"value": "AKIAIOSFODNN7EXAMPLE"}]},
            "item": [
                {
                    "name": "Send notification",
                    "request": {
                        "method": "POST",
                        "url": "https://api.example.com/notifications",
                    },
                },
            ],
        }
        path = tmp_path / "postman_collection.json"
        path.write_text(json.dumps(collection))
        return path

    def test_find_postman_collections_detects_collection(self, tmp_path, postman_collection) -> None:
        found = _find_postman_collections(str(tmp_path))
        assert str(postman_collection) in found

    def test_find_postman_collections_detects_nested(self, tmp_path) -> None:
        nested_dir = tmp_path / "postman"
        nested_dir.mkdir()
        nested_file = nested_dir / "api.json"
        nested_file.write_text("{}")
        found = _find_postman_collections(str(tmp_path))
        assert str(nested_file) in found

    def test_walk_postman_items_flattens_nested(self) -> None:
        items = [
            {"name": "A", "request": {}},
            {
                "name": "Folder",
                "item": [
                    {"name": "B", "request": {}},
                    {"name": "Subfolder", "item": [{"name": "C", "request": {}}]},
                ],
            },
        ]
        flat = _walk_postman_items(items)
        assert len(flat) == 3
        assert {i["name"] for i in flat} == {"A", "B", "C"}

    def test_extract_endpoint_parses_dict_url(self) -> None:
        item = {
            "name": "List notifications",
            "request": {
                "method": "GET",
                "url": {"path": ["notifications"]},
            },
        }
        ep = _extract_endpoint(item)
        assert ep == {"method": "GET", "path": "/notifications", "summary": "List notifications"}

    def test_extract_endpoint_parses_string_url(self) -> None:
        item = {
            "name": "Health",
            "request": {
                "method": "GET",
                "url": "https://api.example.com/health",
            },
        }
        ep = _extract_endpoint(item)
        assert ep["path"] == "https://api.example.com/health"

    def test_build_endpoint_card_extracts_endpoints(self, postman_collection) -> None:
        scanner = SecretScanner()
        card = _build_endpoint_card(str(postman_collection), scanner)

        assert card is not None
        assert card["title"] == "Notification API"
        endpoints = card["endpoints"]
        assert len(endpoints) == 3
        methods = {ep["method"] for ep in endpoints}
        assert methods == {"POST", "GET", "DELETE"}

    def test_build_endpoint_card_redacts_secrets(self, postman_with_secret) -> None:
        scanner = SecretScanner()
        card = _build_endpoint_card(str(postman_with_secret), scanner)

        assert card is not None
        text = json.dumps(card)
        assert "AKIAIOSFODNN7EXAMPLE" not in text

    async def test_generate_endpoint_cards_writes_to_namespace(self, tmp_path, postman_collection) -> None:
        writer = AsyncMock()
        manifest = AsyncMock()
        manifest.should_skip = AsyncMock(return_value=False)

        ctx = AsyncMock()
        ctx.writer = writer
        ctx.manifest = manifest

        repo_path = tmp_path / "notification-be"
        repo_path.mkdir()
        (repo_path / "postman_collection.json").write_text(postman_collection.read_text())

        await generate_endpoint_cards(ctx, [str(repo_path)])

        writer.upsert.assert_awaited_once()
        args, _kwargs = writer.upsert.call_args
        assert args[1] == "svc-notification"
        manifest.upsert.assert_awaited_once()
        assert manifest.upsert.call_args.args[0].pass_type == "cards"

    async def test_generate_endpoint_cards_skips_unchanged(self, tmp_path, postman_collection) -> None:
        writer = AsyncMock()
        manifest = AsyncMock()
        manifest.should_skip = AsyncMock(return_value=True)

        ctx = AsyncMock()
        ctx.writer = writer
        ctx.manifest = manifest

        repo_path = tmp_path / "notification-be"
        repo_path.mkdir()
        (repo_path / "postman_collection.json").write_text(postman_collection.read_text())

        await generate_endpoint_cards(ctx, [str(repo_path)])

        writer.upsert.assert_not_awaited()
