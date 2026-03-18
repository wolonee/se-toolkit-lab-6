# Agent Architecture

## Overview

This is a CLI agent that answers questions by reading wiki documentation, examining source code, and querying a live backend API. It uses an LLM with function calling to decide which tools to invoke, then synthesizes answers with appropriate source references.

## Provider and Model

- **Provider**: Qwen Code API (OpenAI-compatible endpoint)
- **Model**: `qwen3-coder-plus`
- **Endpoint**: Configured via `LLM_API_BASE` (e.g., `http://<vm-ip>:42005/v1`)

## Configuration

The agent reads configuration from two environment files:

### `.env.agent.secret` (LLM configuration)

```
LLM_API_KEY=<your-llm-api-key>
LLM_API_BASE=http://<vm-ip>:<port>/v1
LLM_MODEL=qwen3-coder-plus
```

### `.env.docker.secret` (Backend API configuration)

```
LMS_API_KEY=<backend-api-key>
AGENT_API_BASE_URL=http://localhost:42002  # optional, defaults to localhost:42002
```

Environment variables take precedence over file values. The autochecker injects its own values at evaluation time, so the agent must read all configuration from environment variables rather than hardcoding.

## CLI Interface

### Usage

```bash
uv run agent.py "How many items are in the database?"
```

### Input

- First positional argument: the user's question (required)

### Output

The agent outputs a single JSON line to stdout:

```json
{
  "answer": "There are 42 items in the database.",
  "source": "API: GET /items/",
  "tool_calls": [
    {"tool": "query_api", "args": {"method": "GET", "path": "/items/"}, "result": "{\"status_code\": 200, ...}"}
  ]
}
```

| Field | Type | Description |
|-------|------|-------------|
| `answer` | string | The LLM's answer to the question |
| `source` | string | Reference to where the answer came from (wiki file, source file, or API endpoint) |
| `tool_calls` | array | All tool calls made during execution |

Each tool call entry contains:

- `tool`: Tool name (`list_files`, `read_file`, or `query_api`)
- `args`: Arguments passed to the tool
- `result`: The tool's return value

All debug/error output goes to stderr.

## Tools

### `list_files`

Lists files and directories at a given path.

**Parameters:**

- `path` (string): Relative directory path from project root (e.g., `"wiki"`)

**Returns:** Newline-separated list of entry names, or an error message.

### `read_file`

Reads the contents of a file.

**Parameters:**

- `path` (string): Relative file path from project root (e.g., `"wiki/git-workflow.md"`)

**Returns:** File contents as a string, or an error message.

### `query_api`

Queries the running backend API.

**Parameters:**

- `method` (string): HTTP method (GET, POST, PUT, DELETE, etc.)
- `path` (string): API endpoint path (e.g., `/items/`, `/analytics/completion-rate`)
- `body` (string, optional): JSON request body for POST/PUT requests

**Returns:** JSON string with `status_code` and `body`, or an error message.

**Authentication:** Sends `Authorization: Bearer <LMS_API_KEY>` header with every request.

### Path Security

The file tools (`list_files`, `read_file`) enforce security constraints:

1. **No absolute paths** - Paths must be relative to project root
2. **No path traversal** - Paths containing `..` are rejected
3. **Containment check** - Resolved path must be within project root
4. **Type validation** - `read_file` requires a file, `list_files` requires a directory

Invalid paths return an error string instead of raising exceptions.

## Agentic Loop

The agent follows an iterative loop:

```
┌─────────────────────────────────────────────────────────────┐
│  1. Send question + tool schemas to LLM                     │
│                          │                                  │
│                          ▼                                  │
│  2. LLM responds with tool_calls? ──yes──▶ 3. Execute tools │
│                          │                                  │
│                          no                                 │
│                          │                                  │
│                          ▼                                  │
│  4. Parse final answer JSON                                 │
│                          │                                  │
│                          ▼                                  │
│  5. Output result                                           │
└─────────────────────────────────────────────────────────────┘
```

**Steps:**

1. **Initial call**: Send system prompt + user question to LLM with all three tool schemas
2. **Tool detection**: If LLM returns `tool_calls`, execute each tool
3. **Feedback loop**: Append tool results as `tool` role messages, call LLM again
4. **Termination**: When LLM returns no tool calls, parse the content as JSON
5. **Output**: Return `answer`, `source`, and `tool_calls` array

**Limits:**

- Maximum 10 tool calls per question (prevents infinite loops)

## System Prompt Strategy

The system prompt teaches the LLM when to use each tool:

| Question Type | Tool Strategy |
|---------------|---------------|
| Wiki/documentation questions | `list_files("wiki")` → `read_file` |
| Source code questions | `read_file` on `backend/` files directly |
| Live data questions (counts, status codes) | `query_api` |
| Bug diagnosis | `query_api` to reproduce error → `read_file` to find bug |

The prompt instructs the LLM to:

- Always include a source reference in the answer
- Use API endpoints as source for `query_api` results (e.g., `"API: GET /items/"`)
- Not make up information—only use what it reads from files or API responses

## Architecture Diagram

```
┌──────────────┐     ┌─────────────────────────────────────────┐
│   Question   │ ──> │           agent.py                      │
│              │     │  ┌───────────────────────────────────┐  │
│              │     │  │        Agentic Loop               │  │
│              │     │  │  1. Call LLM with tools           │  │
│              │     │  │  2. Execute tool calls            │  │
│              │     │  │  3. Feed results back             │  │
│              │     │  │  4. Repeat until answer           │  │
│              │     │  └───────────────────────────────────┘  │
│              │     │           │           │                 │
│              │     │    ┌──────┘           └──────┐         │
│              │     │    ▼                          ▼         │
│              │     │ ┌──────┐              ┌──────────┐     │
│              │     │ │ LLM  │              │  Tools   │     │
│              │     │ │ API  │              │ (local)  │     │
│              │     │ └──────┘              └──────────┘     │
│              │     │                      │                 │
│              │     │                      ▼                 │
│              │     │              ┌──────────────┐         │
│              │     │              │ Backend API  │         │
│              │     │              │  (query_api) │         │
│              │     │              └──────────────┘         │
└──────────────┘     └─────────────────────────────────────────┘
                               │
                               ▼
                        ┌──────────────┐
                        │  JSON Output │
                        │  (stdout)    │
                        └──────────────┘
```

## Error Handling

| Error Type | Behavior |
|------------|----------|
| Missing question | Print usage to stderr, exit 1 |
| Missing LLM config | Print error to stderr, exit 1 |
| Missing LMS_API_KEY | Print warning to stderr, continue (query_api may fail) |
| HTTP error (4xx/5xx) | Output JSON with error field, exit 1 |
| Network error | Output JSON with error field, exit 1 |
| Tool error | Return error in tool result, continue loop |
| Max tool calls reached | Return partial answer with tool_calls so far |
| Success | Output JSON result, exit 0 |

## Running

```bash
# Configure environment files
cp .env.agent.example .env.agent.secret
cp .env.docker.example .env.docker.secret
# Edit both files with your credentials

# Run the agent
uv run agent.py "How many items are in the database?"
```

## Testing

Run the regression tests:

```bash
uv run pytest tests/test_agent.py -v
```

Tests verify:

- Valid JSON output with required fields
- Tool calls are executed and recorded
- Source references are included in answers
- Path security prevents directory traversal
- `query_api` tool works correctly

## Benchmark Evaluation

Run the local benchmark:

```bash
uv run run_eval.py
```

This runs 10 questions across all classes:

- Wiki lookup questions (read documentation)
- System facts (framework, ports, status codes)
- Data queries (item counts, analytics)
- Bug diagnosis (query API, read source code)
- Reasoning questions (LLM-judged)

The autochecker runs an additional 10 hidden questions and uses LLM-based judging for open-ended reasoning questions.

## Lessons Learned

Building this agent revealed several important patterns:

1. **Tool descriptions matter**: The LLM relies heavily on tool descriptions to decide which tool to call. Vague descriptions lead to wrong tool choices. Being explicit about when to use each tool (e.g., "Use query_api for live data questions") significantly improves accuracy.

2. **Authentication is critical**: The `query_api` tool must send the `LMS_API_KEY` header, not the `LLM_API_KEY`. Mixing these up causes silent failures where the API returns 401 errors.

3. **Environment variable precedence**: The autochecker injects its own credentials at evaluation time. Hardcoding any values (API base URLs, model names) causes failures. The agent must always read from environment variables first, then fall back to `.env` files.

4. **Error handling in tools**: Tools should never raise uncaught exceptions. Returning error strings allows the LLM to see the error and potentially retry or explain what went wrong.

5. **Source tracking**: Including source references helps users verify answers. For API queries, using the endpoint path as the source (e.g., `"API: GET /items/"`) provides traceability.

6. **Max tool call limit**: Without a limit, the LLM can get stuck in loops reading the same file repeatedly. The 10-call limit forces convergence.

## Final Evaluation Score

*To be filled after running the benchmark:*

- Local questions: _/10
- Hidden questions: _/10
- Overall: _/20
