# Task 3 Plan – The System Agent

## Goal

Extend the Task 2 documentation agent so it can query the running backend API in addition to reading local files. This enables:

- **Static system facts**: framework, ports, expected status codes (from source or live API).
- **Data-dependent answers**: item counts, analytics outputs (from live API).

The agentic loop remains the same: the model decides which tool(s) to call, the CLI executes them, and the model produces the final answer.

## Tool: `query_api`

### Schema

Register a third function-calling tool alongside `list_files` and `read_file`:

- **Name**: `query_api`
- **Parameters**:
  - `method` (string, required) — e.g. `GET`, `POST`
  - `path` (string, required) — e.g. `/items/`
  - `body` (string, optional) — JSON string for the request body
  - (Optional extension for robustness) `auth` (boolean) — when `false`, do not send auth header (useful for “what happens without auth?” questions)
- **Returns**: a JSON **string** like:
  - `{"status_code": 200, "body": {...}}`

### Configuration and authentication

- Read backend base URL from `AGENT_API_BASE_URL`, defaulting to `http://localhost:42002`.
- Read backend key from `LMS_API_KEY` (environment variable). Do **not** use `LLM_API_KEY`.
- Send authentication as:
  - `Authorization: Bearer <LMS_API_KEY>` (matches backend `HTTPBearer` auth dependency)

### Failure behavior

Never raise uncaught exceptions from the tool; return an error string or a JSON string with an error field so the LLM can react.

## System prompt strategy

Update the system prompt to teach the model when to use which tool:

- **Wiki questions** → `list_files` + `read_file` under `wiki/`.
- **Backend implementation questions** → `read_file` on `backend/` (source of truth).
- **Live system/data questions** (counts, status codes, analytics outputs) → `query_api`.
- Encourage multi-step diagnosis: query an endpoint, read the failing router code, explain the bug.

## Implementation steps

- Update `agent.py`
  - Add `query_api` tool schema.
  - Implement `_tool_query_api` using `httpx` with:
    - base URL: `AGENT_API_BASE_URL` (default localhost)
    - `Authorization` header when `auth` is not explicitly `false`
    - JSON parsing for request `body` when provided
    - JSON parsing for response body when possible, otherwise return text
  - Keep security rules for file tools unchanged.
- Update `AGENT.md`
  - Document `query_api`, auth, and how the model chooses tools.
  - Include benchmark lessons learned and final score (≥ 200 words).

## Benchmark iteration

Run:

```bash
uv run run_eval.py
```

Then iterate:

- Use the failure hint to decide whether to adjust:
  - tool schema descriptions (to steer tool choice),
  - prompt instructions (to encourage chaining tools),
  - `query_api` behavior (auth/base URL/body parsing),
  - or file-reading paths for source-code questions.

### Initial benchmark run (to be filled after first run)

- **Initial score**: 0/10 (runner could not start)
- **First failure**: `run_eval.py` exited early due to missing required environment variables:
  `AUTOCHECKER_API_URL`, `AUTOCHECKER_EMAIL`, `AUTOCHECKER_PASSWORD`.
- **Iteration strategy**:
  - When credentials are available, run `uv run run_eval.py` once to get the first failing question.
  - Fix one failure at a time (tool usage, prompt steering, or tool implementation), then rerun with `--index N` for fast feedback.
