"""Tests for deterministic platform-graph extraction."""

from __future__ import annotations

import json

import pytest

from examples.fm_agent.indexer.graph import GraphExtractor


@pytest.fixture
def extractor(tmp_path):
    return GraphExtractor(repo_name="test-repo", repo_path=str(tmp_path))


class TestGraphExtractor:
    """Cover serverless, CDK, package, catalog-info, and notification-meta parsing."""

    async def test_serverless_functions_and_queues(self, tmp_path, extractor) -> None:
        serverless = {
            "service": "event-bus",
            "functions": {
                "consumeNotificationEvent": {
                    "handler": "src/handlers/notification.consume",
                    "events": [{"sqs": {"arn": "arn:aws:sqs:us-east-1:123:notification-queue"}}],
                },
                "broadcastEvent": {
                    "handler": "src/handlers/broadcast.publish",
                    "events": [{"sns": {"topicName": "notification-topic"}}],
                },
            },
        }
        import yaml

        (tmp_path / "serverless.yml").write_text(yaml.safe_dump(serverless))

        await extractor.extract()

        types = {e.type for e in extractor.entities}
        assert "SERVICE" in types
        assert "LAMBDA" in types
        assert "QUEUE" in types
        assert "TOPIC" in types

        relations = {e.relation for e in extractor.edges}
        assert "DEPLOYED_BY" in relations
        assert "CONSUMES" in relations

    async def test_cdk_ssm_parameters(self, tmp_path, extractor) -> None:
        cdk_code = '''
import * as cdk from 'aws-cdk-lib';
import { StringParameter } from 'aws-cdk-lib/aws-ssm';

export class BaseStack extends cdk.Stack {
  constructor(scope, id, props) {
    super(scope, id, props);
    const endpointParam = StringParameter.API_S3_VPC_ENDPOINT_ID;
    const domainParam = StringParameter.CUSTOM_DOMAIN_CERTIFICATE_ARN;
  }
}
'''
        (tmp_path / "lib").mkdir()
        (tmp_path / "lib" / "base-stack.ts").write_text(cdk_code)

        await extractor.extract()

        ssm_params = [e for e in extractor.entities if e.type == "SSM_PARAM"]
        assert any("API_S3_VPC_ENDPOINT_ID" in e.name for e in ssm_params)
        assert any("CUSTOM_DOMAIN_CERTIFICATE_ARN" in e.name for e in ssm_params)
        assert any(e.relation == "PUBLISHES" for e in extractor.edges)

    async def test_package_dependencies(self, tmp_path, extractor) -> None:
        package = {
            "name": "notification-be",
            "dependencies": {"express": "^4.0.0", "lodash": "^4.0.0"},
        }
        (tmp_path / "package.json").write_text(json.dumps(package))

        await extractor.extract()

        deps = [e for e in extractor.edges if e.relation == "DEPENDS_ON"]
        assert any("express" in e.target_id for e in deps)

    async def test_catalog_info_ownership(self, tmp_path, extractor) -> None:
        catalog = {
            "apiVersion": "backstage.io/v1alpha1",
            "kind": "Component",
            "metadata": {"name": "notification-be", "owner": "platform-team"},
        }
        import yaml

        (tmp_path / "catalog-info.yaml").write_text(yaml.safe_dump(catalog))

        await extractor.extract()

        teams = [e for e in extractor.entities if e.properties.get("kind") == "team"]
        assert any("platform-team" in e.name for e in teams)

    async def test_notification_meta_taxonomy(self, tmp_path, extractor) -> None:
        product_dir = tmp_path / "meta-notifications" / "lms"
        group_dir = product_dir / "course_notifications"
        group_dir.mkdir(parents=True)
        (product_dir / "meta.json").write_text(json.dumps({
            "course_notifications": {"notifications": ["enrolled", "completed"]}
        }))

        await extractor.extract()

        assert any(e.type == "PRODUCT" and e.name == "lms" for e in extractor.entities)
        assert any(e.type == "NOTIFICATION_GROUP" for e in extractor.entities)
        assert any(e.type == "NOTIFICATION_TYPE" for e in extractor.entities)
        assert any(e.relation == "HAS_GROUP" for e in extractor.edges)
        assert any(e.relation == "HAS_TYPE" for e in extractor.edges)
        assert any(e.relation == "REGISTERED_WITH" for e in extractor.edges)

    async def test_serialize_cards(self, tmp_path, extractor) -> None:
        serverless = {
            "functions": {
                "fn1": {"handler": "h1", "events": [{"sqs": {"arn": "q1"}}]},
            },
        }
        import yaml

        (tmp_path / "serverless.yml").write_text(yaml.safe_dump(serverless))

        await extractor.extract()
        cards = extractor.serialize_cards()

        assert len(cards) == len(extractor.entities)
        assert all("# " in card for card in cards)
        assert all("Relations:" in card for card in cards)

    async def test_config_functions_yml_extracted(self, tmp_path, extractor) -> None:
        import yaml

        functions_yml = {
            "functions": {
                "sendEmail": {
                    "handler": "src/handlers/email.send",
                    "events": [{"sns": {"topicName": "email-topic"}}],
                },
                "processQueue": {
                    "handler": "src/handlers/queue.process",
                    "events": [{"sqs": {"arn": "arn:aws:sqs:us-east-1:123:email-queue"}}],
                },
            },
        }
        config_dir = tmp_path / "config" / "functions"
        config_dir.mkdir(parents=True)
        (config_dir / "email.yml").write_text(yaml.safe_dump(functions_yml))

        await extractor.extract()

        types = {e.type for e in extractor.entities}
        assert "SERVICE" in types
        assert "LAMBDA" in types
        assert "QUEUE" in types
        assert "TOPIC" in types

        lambdas = {e.name for e in extractor.entities if e.type == "LAMBDA"}
        assert "sendEmail" in lambdas
        assert "processQueue" in lambdas

        relations = {e.relation for e in extractor.edges}
        assert "DEPLOYED_BY" in relations
        assert "CONSUMES" in relations

        sources = {e.properties.get("source", "") for e in extractor.entities if e.type == "LAMBDA"}
        assert any("config/functions/email.yml" in s for s in sources)
