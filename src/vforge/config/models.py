"""Pydantic models describing ``application.yaml``.

All framework behaviour is driven from these models. Validation fails fast at
startup so misconfiguration never reaches runtime.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    """Base model that rejects unknown keys — typos fail fast."""

    model_config = ConfigDict(extra="forbid")


class AppConfig(StrictModel):
    name: str = "vforge-app"
    description: str = ""


class LLMConfig(StrictModel):
    """LLM provider settings. Usable globally and as a per-agent override."""

    provider: str = "anthropic"
    model: str | None = None
    api_key: str | None = None
    base_url: str | None = None
    api_version: str | None = None  # Azure OpenAI
    max_tokens: int = Field(default=16000, ge=1)
    extra: dict[str, Any] = Field(default_factory=dict)


class MCPServerConfig(StrictModel):
    name: str
    transport: Literal["stdio", "http"] = "stdio"
    # stdio transport
    command: str | None = None
    args: list[str] = Field(default_factory=list)
    env: dict[str, str] = Field(default_factory=dict)
    # http transport
    url: str | None = None
    headers: dict[str, str] = Field(default_factory=dict)
    # resilience
    timeout: float = Field(default=30.0, gt=0)
    max_retries: int = Field(default=2, ge=0)

    @model_validator(mode="after")
    def _validate_transport(self) -> "MCPServerConfig":
        if self.transport == "stdio" and not self.command:
            raise ValueError(f"MCP server '{self.name}': stdio transport requires 'command'")
        if self.transport == "http" and not self.url:
            raise ValueError(f"MCP server '{self.name}': http transport requires 'url'")
        return self


class MemoryConfig(StrictModel):
    provider: Literal["in_memory"] = "in_memory"
    max_messages: int = Field(default=200, ge=1)


class AgentConfig(StrictModel):
    name: str
    description: str = ""
    prompt: str | None = None  # path to a prompt file (relative to app dir)
    system: str | None = None  # inline system prompt (alternative to `prompt`)
    skills: list[str] = Field(default_factory=list)
    mcp_servers: list[str] = Field(default_factory=list)
    llm: LLMConfig | None = None
    memory: MemoryConfig | None = None
    max_iterations: int = Field(default=25, ge=1)

    @model_validator(mode="after")
    def _validate_prompt(self) -> "AgentConfig":
        if not self.prompt and not self.system:
            raise ValueError(f"Agent '{self.name}': provide either 'prompt' (file) or 'system'")
        return self


class ServerConfig(StrictModel):
    host: str = "0.0.0.0"
    port: int = Field(default=8000, ge=1, le=65535)
    ui_dir: str | None = None
    """Path (relative to the app dir) of a static UI build (e.g. an Angular
    ``dist/``) served at ``/`` instead of the built-in console. The console
    API under ``/api`` stays available either way."""


class AuthConfig(StrictModel):
    api_key: str | None = None  # when set, X-API-Key is required on /a2a and /api


class PeerConfig(StrictModel):
    """A remote agent reachable over A2A, addressable via call_next_agent."""

    name: str
    url: str
    api_key: str | None = None


class OTelConfig(StrictModel):
    """OpenTelemetry tracing. Requires the ``vforge[otel]`` extra when enabled."""

    enabled: bool = False
    endpoint: str | None = None  # OTLP/HTTP endpoint, e.g. http://localhost:4318
    service_name: str | None = None  # defaults to app.name
    console_export: bool = False  # additionally print spans to stdout (debugging)


class ObservabilityConfig(StrictModel):
    log_level: str = "INFO"
    json_logs: bool = False
    otel: OTelConfig = Field(default_factory=OTelConfig)


class RAGConfig(StrictModel):
    enabled: bool = False
    provider: Literal["chroma"] = "chroma"
    collection: str = "vforge"
    persist_directory: str | None = None
    documents_dir: str | None = None
    chunk_size: int = Field(default=1000, ge=100)
    chunk_overlap: int = Field(default=100, ge=0)
    top_k: int = Field(default=4, ge=1)


class VForgeConfig(StrictModel):
    """Root configuration model for a VForge application."""

    app: AppConfig = Field(default_factory=AppConfig)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    agents: list[AgentConfig] = Field(default_factory=list)
    mcp: dict[str, list[MCPServerConfig]] = Field(default_factory=lambda: {"servers": []})
    memory: MemoryConfig = Field(default_factory=MemoryConfig)
    server: ServerConfig = Field(default_factory=ServerConfig)
    auth: AuthConfig = Field(default_factory=AuthConfig)
    peers: list[PeerConfig] = Field(default_factory=list)
    observability: ObservabilityConfig = Field(default_factory=ObservabilityConfig)
    rag: RAGConfig = Field(default_factory=RAGConfig)

    @model_validator(mode="after")
    def _validate(self) -> "VForgeConfig":
        if not self.agents:
            raise ValueError("Configuration must define at least one agent under 'agents'")

        names = [agent.name for agent in self.agents]
        if len(names) != len(set(names)):
            raise ValueError(f"Duplicate agent names in configuration: {names}")

        server_names = {server.name for server in self.mcp_servers}
        for agent in self.agents:
            unknown = set(agent.mcp_servers) - server_names
            if unknown:
                raise ValueError(
                    f"Agent '{agent.name}' references unknown MCP servers: {sorted(unknown)}"
                )

        peer_names = {peer.name for peer in self.peers}
        overlap = peer_names & set(names)
        if overlap:
            raise ValueError(f"Peer names collide with local agent names: {sorted(overlap)}")
        return self

    @property
    def mcp_servers(self) -> list[MCPServerConfig]:
        return self.mcp.get("servers", [])
