# Agent Architecture

## Overview

This is a CLI agent that answers questions by calling an LLM via an OpenAI-compatible API. This is Task 1 of the lab — it provides the basic plumbing without tools or an agentic loop.

## Provider and Model

- **Provider**: Qwen Code API (OpenAI-compatible endpoint)
- **Model**: `qwen3-coder-plus`
- **Endpoint**: Configured via `LLM_API_BASE` (e.g., `http://<vm-ip>:42005/v1`)

## Configuration

The agent reads configuration from `.env.agent.secret` in the project root:

```
LLM_API_KEY=<your-api-key>
LLM_API_BASE=http://<vm-ip>:<port>/v1
LLM_MODEL=qwen3-coder-plus
```

Environment variables take precedence over file values. The file is loaded at startup and missing variables cause the agent to exit with an error.

## CLI Interface

### Usage

```bash
uv run agent.py "What does REST stand for?"
```

### Input

- First positional argument: the user's question (required)
- If no argument is provided, the agent prints usage to stderr and exits with code 1

### Output

The agent outputs a single JSON line to stdout:

```json
{"answer": "Representational State Transfer.", "tool_calls": []}
```

- `answer`: The LLM's response text
- `tool_calls`: Always an empty array in Task 1 (tools are added in Task 2)

All debug/error output goes to stderr.

## Architecture

```
┌─────────────────┐     ┌──────────────┐     ┌─────────────────┐
│  Command Line   │ ──> │   agent.py   │ ──> │  LLM API (HTTP) │
│  (question)     │     │  (CLI tool)  │     │  (Qwen Code)    │
└─────────────────┘     └──────────────┘     └─────────────────┘
                               │
                               v
                        ┌──────────────┐
                        │  JSON Output │
                        │  (stdout)    │
                        └──────────────┘
```

### Flow

1. Parse command-line argument (the question)
2. Load configuration from `.env.agent.secret`
3. Build HTTP request to `/chat/completions` endpoint
4. Send request with system + user messages
5. Parse LLM response and extract answer
6. Output JSON result to stdout

## Error Handling

| Error Type | Behavior |
|------------|----------|
| Missing question | Print usage to stderr, exit 1 |
| Missing config | Print error to stderr, exit 1 |
| HTTP error (4xx/5xx) | Output JSON with error field, print details to stderr, exit 1 |
| Network error | Output JSON with error field, print details to stderr, exit 1 |
| Success | Output JSON result, exit 0 |

## Limitations (Task 1)

- No tool support (tools added in Task 2)
- Single-turn conversation only (no state management)
- No conversation history
- Minimal system prompt

## Running

```bash
# Make sure .env.agent.secret is configured
cp .env.agent.example .env.agent.secret
# Edit .env.agent.secret with your LLM credentials

# Run the agent
uv run agent.py "What does REST stand for?"
```

## Testing

Run the regression test:

```bash
uv run pytest tests/test_agent.py -v
```

The test verifies that:
- The agent outputs valid JSON
- The `answer` field exists and is a string
- The `tool_calls` field exists and is a list
