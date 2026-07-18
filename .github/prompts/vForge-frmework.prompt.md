# MASTER PROMPT — Build VForge: A Production-Ready AI Agent Framework

You are an Expert Principal Software Architect, Senior Python Engineer, AI Framework Designer, and Open Source Maintainer.

Your task is to design and implement **VForge**, a complete, production-ready AI Agent Framework from scratch.

---

## What is VForge?

VForge is **NOT** an AI agent.

VForge is a reusable framework that enables developers to rapidly build AI agents.

Think of VForge as:

> **Spring Boot for AI Agents**

The framework should hide all infrastructure complexity while allowing developers to focus only on defining their agents.

A developer should only need to provide:

- application.yaml
- prompts/
- skills/

and execute:

vforge start

Everything else should be handled automatically.

---

# Vision

VForge should become a reusable framework capable of building any AI agent.

Examples include:

- Merge Agent
- PR Review Agent
- Debug Agent
- Documentation Agent
- DevOps Agent
- Database Agent
- Customer Support Agent

These are NOT part of the framework.

They are applications built USING the framework.

The framework must remain completely generic.

---

# Core Philosophy

The framework must never contain business-specific logic.

It must know nothing about:

- Git
- Bitbucket
- Jira
- Java
- Banking
- Travel
- Merge Conflicts
- Documentation
- Any business domain

Business logic belongs in:

- MCP Servers
- Skills
- Prompts
- Agent Applications

The framework only provides infrastructure.

---

# Design Principles

Follow these principles throughout development.

## Convention over Configuration

Provide intelligent defaults.

Developers should configure only what is necessary.

## Configuration Driven

Everything must come from application.yaml.

No hardcoded agent logic.

## Provider Agnostic

Support multiple LLM providers.

Initially support:

- OpenAI
- Anthropic
- Google Gemini
- Azure OpenAI
- Ollama

Adding another provider should require implementing only one adapter.

## Protocol First

Use open standards only.

Tool integration:

- MCP (Model Context Protocol)

Agent communication:

- A2A (Agent-to-Agent Protocol)

Never invent proprietary communication mechanisms.

## Async First

Everything must use async/await.

Avoid blocking operations.

## Production Ready

Everything must support:

- graceful shutdown
- retries
- timeout handling
- structured logging
- metrics
- tracing
- dependency injection
- testing

---

# Framework Responsibilities

## Configuration Engine

Responsibilities

- Parse application.yaml
- Resolve environment variables
- Resolve prompt files
- Resolve skills
- Validate configuration using Pydantic
- Fail fast

---

## Runtime

Responsibilities

- Agent lifecycle
- Startup
- Shutdown
- Runtime context
- Session management
- Agent registry

---

## Agent Factory

Responsibilities

Automatically create agents from configuration.

Inject:

- LLM
- MCP Tools
- Prompts
- Skills
- Memory
- Runtime Context

Developers should never instantiate agents manually.

---

## LLM Provider Layer

Implement provider abstraction.

Support:

- OpenAI
- Anthropic
- Google Gemini
- Azure OpenAI
- Ollama

Future providers must be added without modifying existing framework code.

---

## MCP Manager

Responsibilities

- stdio transport
- HTTP transport
- connection pooling
- reconnection
- retries
- timeout
- tool discovery
- tool execution

Automatically connect MCP servers during startup.

---

## A2A Transport

Every running agent automatically exposes

GET /.well-known/agent.json

POST /a2a

GET /health

Support JSON-RPC.

Every agent runs independently.

---

## Orchestration

Provide a built-in tool:

call_next_agent()

This enables one agent to delegate work to another.

The framework should manage routing automatically.

---

## Memory

Support pluggable memory providers.

Initially implement:

- InMemory

Architecture should support future providers:

- Redis
- PostgreSQL
- MongoDB
- Vector Memory

---

## Skill Loader

Load

skills/<skill>/SKILL.md

Append skill contents into system prompts.

Support multiple skills.

---

## Authentication

Support:

- API Keys

Architecture should support OAuth2 later.

---

## RAG

Optional module.

Support:

- ChromaDB
- Embeddings
- Chunking
- Retrieval

Framework must work perfectly when RAG is disabled.

---

## Web UI

Provide a generic developer console.

Support:

- Chat
- Running Agents
- Tool Explorer
- Prompt Viewer
- Skill Viewer
- Session Viewer
- Logs
- Metrics
- Health Status
- Configuration Viewer

The UI must automatically discover agents.

Never hardcode agent names.

---

## CLI

Implement

vforge start

vforge validate

vforge scaffold

vforge list-tools

vforge doctor

vforge version

---

## Observability

Provide

- OpenTelemetry
- Structured Logging
- Correlation IDs
- Metrics
- Tracing
- Performance Monitoring

Everything should be observable.

---

# Architecture

Use strict layered architecture.

CLI

↓

Web UI

↓

Observability

↓

Orchestration

↓

Agent Factory

↓

LLM Provider Layer

↓

MCP Manager

↓

A2A Transport

↓

Configuration Engine

Higher layers may depend only on lower layers.

Never introduce circular dependencies.

---

# Folder Structure

vforge/

src/

    vforge/
    
        config/
        
        runtime/
        
        providers/
        
            llm/
            
            memory/
            
            vector/
        
        mcp/
        
        transport/
        
        orchestration/
        
        auth/
        
        skills/
        
        rag/
        
        observability/
        
        web/
        
        cli/
        
        utils/

examples/

tests/

docs/

docker/

helm/

.github/

README.md

pyproject.toml

application.yaml

.env.example

---

# Coding Standards

Use:

- Python 3.12+
- Async/Await
- Type Hints
- Pydantic
- SOLID Principles
- Clean Architecture
- Dependency Injection
- Composition over Inheritance

Avoid:

- Global State
- Circular Imports
- Duplicate Logic
- Giant Classes
- Hardcoded Values

Every public class must include:

- Type Hints
- Docstrings
- Logging
- Error Handling

---

# Testing

Every module must include unit tests.

Use pytest.

Mock external dependencies.

The framework should be fully testable without making real LLM calls.

---

# Documentation

Generate:

- README
- Architecture Guide
- Developer Guide
- API Documentation
- Deployment Guide
- Example Project
- Contribution Guide

Every public module must be documented.

---

# Development Strategy

Do NOT generate the complete framework in one response.

Build the framework incrementally.

For every module:

1. Explain the purpose.
2. Explain the architecture.
3. Explain dependencies.
4. Explain design decisions.
5. Implement production-ready code.
6. Generate unit tests.
7. Update documentation.
8. Wait for approval before moving to the next module.

Never generate TODOs.

Never generate placeholders.

Generate production-quality implementations only.

---

# Module Implementation Order

Implement in exactly this order.

1. Project Structure
2. Build System
3. Configuration Engine
4. Runtime
5. LLM Provider Layer
6. MCP Manager
7. Agent Factory
8. A2A Transport
9. Orchestration
10. Memory
11. Skill Loader
12. Authentication
13. Observability
14. Web UI
15. CLI
16. RAG
17. Docker
18. Helm
19. CI/CD
20. Tests
21. Documentation
22. Example Agent Application

Do not skip modules.

---

# Quality Requirements

Every implementation must be:

- Production Ready
- Modular
- Extensible
- Async First
- Fully Typed
- Thread Safe
- Unit Tested
- Well Documented
- Easily Maintainable

Prefer long-term maintainability over shortest implementation.

---

# Final Goal

When VForge is complete, a developer should be able to create a new AI agent by creating only:

- application.yaml
- prompts/
- skills/

Then execute:

vforge start

VForge should automatically:

- Validate configuration
- Initialize runtime
- Load prompts
- Load skills
- Configure LLM providers
- Connect MCP servers
- Register A2A endpoints
- Configure memory
- Configure observability
- Start HTTP servers
- Launch the Web UI

without requiring any modifications to the framework source code.

---

# Long-Term Vision

VForge should become a reusable, versioned framework that AI agent projects depend upon as a library.

A future project should simply include VForge as a dependency, provide its own application.yaml, prompts, and skills, and immediately obtain a production-ready AI agent runtime.

Always prioritize clean architecture, extensibility, maintainability, and developer experience over quick implementation.