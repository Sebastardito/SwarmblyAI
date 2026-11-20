"""Tool foundation for 3.4: specs, strict schemas, approvals and one broker."""

from __future__ import annotations

from .approvals import APPROVALS_SCHEMA, ApprovalError, ApprovalStore
from .broker import (DEFAULT_MAX_RESULT_CHARS, DEFAULT_TOKEN_TTL, PROVIDER_KINDS,
                     ToolBroker, ToolCall, ToolContext, ToolDenied, ToolResult,
                     ToolSpec, approval_hash_for, as_quoted_block)
from .schema import SchemaError, canonical_json, validate_arguments, validate_schema
from .author import (AUTHOR_HOSTS, AUTHOR_INPUT_SCHEMA, AUTHOR_SERVICES,
                     AuthorError, AuthorRateLimited, author_enabled, author_specs,
                     dedupe_works, normalise_works, register_author_tools)
from .mcp import (MCPClient, ManifestTool, ToolManifest)
from .mcp_registry import (KINDS, LOCAL_RIGHTS_NOTE, MCP_SERVERS_FILE,
                           MCP_SERVERS_SCHEMA, MCPApprovalError, MCPConfigError,
                           MCPError, MCPNotFound, MCPNotRunning, MCPProtocolError,
                           MCPRegistryError, MCPTimeout, MCPUnavailable,
                           REMOTE_HOST_NOTE, STATUSES, ServerConfig, ServerRegistry,
                           UNTRUSTED_NOTE)
from .standing import STANDING_FILE, STANDING_SCHEMA, StandingError, StandingStore


def register_sandbox(broker: "ToolBroker", *, project_path, runner=None):
    """Register the recipe-5 ``sandbox/python`` tool on ``broker``.

    This is a thin registration helper kept here so callers have one import;
    the sandbox package and its optional dependency are imported lazily, so
    the tool foundation works without the ``[sandbox]`` extra.
    """
    from ..sandbox import register_tool

    return register_tool(broker, project_path=project_path, runner=runner)


__all__ = [
    "APPROVALS_SCHEMA",
    "AUTHOR_HOSTS",
    "AUTHOR_INPUT_SCHEMA",
    "AUTHOR_SERVICES",
    "ApprovalError",
    "ApprovalStore",
    "AuthorError",
    "AuthorRateLimited",
    "DEFAULT_MAX_RESULT_CHARS",
    "DEFAULT_TOKEN_TTL",
    "KINDS",
    "LOCAL_RIGHTS_NOTE",
    "MCP_SERVERS_FILE",
    "MCP_SERVERS_SCHEMA",
    "MCPApprovalError",
    "MCPClient",
    "MCPConfigError",
    "MCPError",
    "MCPNotFound",
    "MCPNotRunning",
    "MCPProtocolError",
    "MCPRegistryError",
    "MCPTimeout",
    "MCPUnavailable",
    "ManifestTool",
    "PROVIDER_KINDS",
    "REMOTE_HOST_NOTE",
    "STATUSES",
    "STANDING_FILE",
    "STANDING_SCHEMA",
    "SchemaError",
    "StandingError",
    "StandingStore",
    "ServerConfig",
    "ServerRegistry",
    "ToolManifest",
    "UNTRUSTED_NOTE",
    "ToolBroker",
    "ToolCall",
    "ToolContext",
    "ToolDenied",
    "ToolResult",
    "ToolSpec",
    "approval_hash_for",
    "as_quoted_block",
    "author_enabled",
    "author_specs",
    "canonical_json",
    "dedupe_works",
    "normalise_works",
    "register_author_tools",
    "register_sandbox",
    "validate_arguments",
    "validate_schema",
]
