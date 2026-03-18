# Agent Architecture

## Overview

This is a CLI documentation agent that answers questions by reading wiki files from the project repository. It uses an LLM with function calling to discover and read documentation, then synthesizes answers with source references.

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

Environment variables take precedence over file values.

## CLI Interface

### Usage

```bash
uv run agent.py "How do you resolve a merge conflict?"
```

### Input

- First positional argument: the user's question (required)

### Output

The agent outputs a single JSON line to stdout:

```json
{
  "answer": "Edit the conflicting file, choose which changes to keep, then stage and commit.",
  "source": "wiki/git-workflow.md#resolving-merge-conflicts",
  "tool_calls": [
    {"tool": "list_files", "args": {"path": "wiki"}, "result": "git-workflow.md\n..."},
    {"tool": "read_file", "args": {"path": "wiki/git-workflow.md"}, "result": "..."}
  ]
}
```

| Field | Type | Description |
|-------|------|-------------|
| `answer` | string | The LLM's answer to the question |
| `source` | string | Wiki section reference (e.g., `wiki/file.md#section`) |
| `tool_calls` | array | All tool calls made during execution |

Each tool call entry contains:

- `tool`: Tool name (`list_files` or `read_file`)
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

### Path Security

Both tools enforce security constraints:

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

1. **Initial call**: Send system prompt + user question to LLM with tool schemas
2. **Tool detection**: If LLM returns `tool_calls`, execute each tool
3. **Feedback loop**: Append tool results as `tool` role messages, call LLM again
4. **Termination**: When LLM returns no tool calls, parse the content as JSON
5. **Output**: Return `answer`, `source`, and `tool_calls` array

**Limits:**

- Maximum 10 tool calls per question (prevents infinite loops)

## System Prompt Strategy

The system prompt instructs the LLM to:

1. Use `list_files("wiki")` to discover available documentation
2. Use `read_file` to read relevant wiki files
3. Respond with a JSON object containing `answer` and `source`
4. Format source references as `wiki/filename.md#section-anchor`

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
| Missing config | Print error to stderr, exit 1 |
| HTTP error (4xx/5xx) | Output JSON with error field, exit 1 |
| Network error | Output JSON with error field, exit 1 |
| Tool error | Return error in tool result, continue loop |
| Max tool calls reached | Return partial answer with tool_calls so far |
| Success | Output JSON result, exit 0 |

## Running

```bash
# Configure .env.agent.secret with your LLM credentials
uv run agent.py "How do you resolve a merge conflict?"
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

## Limitations

- Single-turn conversation only (no persistent state between invocations)
- Maximum 10 tool calls per question
- Only reads from local file system (wiki directory)
- No web search or external knowledge beyond wiki files
