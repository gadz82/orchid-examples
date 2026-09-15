"""Shared e2e test fixtures and helpers."""

from __future__ import annotations

from .auth import (
    DEFAULT_TENANT,
    DEFAULT_TOKEN,
    DEFAULT_USER,
    admin_auth,
    auth_context,
    make_auth_context,
    other_tenant_admin,
    other_tenant_auth,
)
from .mock_llm import FakeChatModel, FakeChatModelFactory, mock_llm_response
from .mock_mcp import (
    MockCacheableMCPClient,
    MockMCPClient,
    mock_cacheable_mcp_client,
    mock_mcp_client,
)
from .mock_vector import (
    InMemoryVectorReader,
    InMemoryVectorStore,
    InMemoryVectorStoreAdmin,
    InMemoryVectorWriter,
    in_memory_vector_store,
    mock_vector_reader,
    mock_vector_writer,
    seed_documents,
)

__all__ = [
    "DEFAULT_TENANT",
    "DEFAULT_TOKEN",
    "DEFAULT_USER",
    "FakeChatModel",
    "FakeChatModelFactory",
    "InMemoryVectorReader",
    "InMemoryVectorStore",
    "InMemoryVectorStoreAdmin",
    "InMemoryVectorWriter",
    "MockCacheableMCPClient",
    "MockMCPClient",
    "admin_auth",
    "auth_context",
    "in_memory_vector_store",
    "make_auth_context",
    "mock_cacheable_mcp_client",
    "mock_llm_response",
    "mock_mcp_client",
    "mock_vector_reader",
    "mock_vector_writer",
    "other_tenant_admin",
    "other_tenant_auth",
    "seed_documents",
]
