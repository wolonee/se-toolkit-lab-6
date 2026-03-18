#!/usr/bin/env python3
"""
Agent CLI - Task 3: The System Agent

Takes a question as command-line argument, uses an LLM with tool calling
to discover wiki files, read source code, and query the backend API.

Usage:
    uv run agent.py "How many items are in the database?"

Output:
    {
      "answer": "...",
      "source": "wiki/git-workflow.md#section",  # optional for system questions
      "tool_calls": [...]
    }
"""

import json
import os
import sys
from pathlib import Path
from typing import Any

import httpx


# =============================================================================
# Configuration
# =============================================================================

MAX_TOOL_CALLS = 10
DEFAULT_AGENT_API_BASE_URL = "http://localhost:42002"


def load_env_file(env_path: Path) -> dict[str, str]:
    """Load environment variables from a .env file without overwriting existing vars."""
    env_vars = {}
    if env_path.exists():
        with open(env_path, "r") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    key, value = line.split("=", 1)
                    key = key.strip()
                    value = value.strip()
                    if key not in os.environ:
                        env_vars[key] = value
    return env_vars


def load_config() -> tuple[str, str, str, str, str]:
    """
    Load all configuration from environment or .env files.
    
    Returns:
        (llm_api_base, llm_api_key, llm_model, lms_api_key, agent_api_base_url)
    """
    project_root = Path(__file__).parent
    
    # Load from .env files
    agent_env_path = project_root / ".env.agent.secret"
    docker_env_path = project_root / ".env.docker.secret"
    
    agent_env_vars = load_env_file(agent_env_path)
    docker_env_vars = load_env_file(docker_env_path)
    
    # LLM configuration (from .env.agent.secret)
    api_base = os.environ.get("LLM_API_BASE") or agent_env_vars.get("LLM_API_BASE")
    api_key = os.environ.get("LLM_API_KEY") or agent_env_vars.get("LLM_API_KEY")
    model = os.environ.get("LLM_MODEL") or agent_env_vars.get("LLM_MODEL")
    
    # Backend API configuration (from .env.docker.secret or env)
    lms_api_key = os.environ.get("LMS_API_KEY") or docker_env_vars.get("LMS_API_KEY")
    agent_api_base_url = os.environ.get("AGENT_API_BASE_URL") or \
                         docker_env_vars.get("AGENT_API_BASE_URL") or \
                         DEFAULT_AGENT_API_BASE_URL
    
    # Validate LLM config
    if not api_base:
        print("Error: LLM_API_BASE not set. Configure .env.agent.secret or set LLM_API_BASE env var.", file=sys.stderr)
        sys.exit(1)
    if not api_key:
        print("Error: LLM_API_KEY not set. Configure .env.agent.secret or set LLM_API_KEY env var.", file=sys.stderr)
        sys.exit(1)
    if not model:
        print("Error: LLM_MODEL not set. Configure .env.agent.secret or set LLM_MODEL env var.", file=sys.stderr)
        sys.exit(1)
    
    # LMS API key is optional - some questions may not need it
    if not lms_api_key:
        print("Warning: LMS_API_KEY not set. query_api tool may fail without authentication.", file=sys.stderr)
    
    return api_base, api_key, model, lms_api_key, agent_api_base_url


# =============================================================================
# Tool Definitions
# =============================================================================

def get_tool_schemas() -> list[dict[str, Any]]:
    """Return the tool schemas for function calling."""
    return [
        {
            "type": "function",
            "function": {
                "name": "list_files",
                "description": "List files and directories at a given path in the project repository. Use this to discover what files exist before reading them.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Relative directory path from project root (e.g., 'wiki', 'backend/src')."
                        }
                    },
                    "required": ["path"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "read_file",
                "description": "Read the contents of a file from the project repository. Use this to read wiki documentation, source code, or configuration files.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Relative file path from project root (e.g., 'wiki/git-workflow.md', 'backend/app/main.py')."
                        }
                    },
                    "required": ["path"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "query_api",
                "description": "Query the running backend API to get live data or test endpoints. Use this for questions about current database state, HTTP status codes, or API behavior. The backend requires authentication via Bearer token.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "method": {
                            "type": "string",
                            "description": "HTTP method (GET, POST, PUT, DELETE, etc.)"
                        },
                        "path": {
                            "type": "string",
                            "description": "API endpoint path (e.g., '/items/', '/analytics/completion-rate')"
                        },
                        "body": {
                            "type": "string",
                            "description": "Optional JSON request body (for POST/PUT requests)"
                        }
                    },
                    "required": ["method", "path"]
                }
            }
        }
    ]


def get_project_root() -> Path:
    """Get the project root directory."""
    return Path(__file__).parent


def validate_path(path_str: str, must_be_file: bool = False) -> tuple[bool, str | Path]:
    """
    Validate that a path is safe and within the project root.
    
    Returns:
        (is_valid, result_or_error)
        - If valid: (True, resolved_path)
        - If invalid: (False, error_message)
    """
    # Reject absolute paths
    if os.path.isabs(path_str):
        return (False, f"Absolute paths not allowed: {path_str}")
    
    # Reject path traversal
    if ".." in path_str.split(os.sep):
        return (False, f"Path traversal not allowed: {path_str}")
    
    project_root = get_project_root()
    resolved = (project_root / path_str).resolve()
    
    # Verify path is within project root
    try:
        resolved.relative_to(project_root.resolve())
    except ValueError:
        return (False, f"Path outside project root: {path_str}")
    
    # Check existence
    if not resolved.exists():
        return (False, f"Path does not exist: {path_str}")
    
    # Check type
    if must_be_file and not resolved.is_file():
        return (False, f"Expected a file, got a directory: {path_str}")
    
    if not must_be_file and not resolved.is_dir():
        return (False, f"Expected a directory, got a file: {path_str}")
    
    return (True, resolved)


def tool_list_files(args: dict[str, Any]) -> str:
    """
    List files and directories at a given path.
    
    Args:
        args: {"path": "wiki"}
    
    Returns:
        Newline-separated listing or error message.
    """
    path_str = args.get("path", "")
    
    is_valid, result = validate_path(path_str, must_be_file=False)
    if not is_valid:
        return f"Error: {result}"
    
    directory = result
    entries = []
    for entry in sorted(directory.iterdir()):
        entries.append(entry.name)
    
    return "\n".join(entries)


def tool_read_file(args: dict[str, Any]) -> str:
    """
    Read the contents of a file.
    
    Args:
        args: {"path": "wiki/git-workflow.md"}
    
    Returns:
        File contents or error message.
    """
    path_str = args.get("path", "")
    
    is_valid, result = validate_path(path_str, must_be_file=True)
    if not is_valid:
        return f"Error: {result}"
    
    file_path = result
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        return f"Error reading file: {e}"


def tool_query_api(args: dict[str, Any], lms_api_key: str, api_base_url: str) -> str:
    """
    Query the backend API.
    
    Args:
        args: {"method": "GET", "path": "/items/", "body": "..."}
        lms_api_key: API key for authentication
        api_base_url: Base URL of the backend API
    
    Returns:
        JSON string with status_code and body, or error message.
    """
    method = args.get("method", "GET").upper()
    path = args.get("path", "")
    body_str = args.get("body")
    
    if not path:
        return "Error: path is required"
    
    # Build URL
    base = api_base_url.rstrip("/")
    url = f"{base}{path}"
    
    # Prepare headers
    headers = {"Content-Type": "application/json"}
    if lms_api_key:
        headers["Authorization"] = f"Bearer {lms_api_key}"
    
    # Prepare body
    json_body = None
    if body_str:
        try:
            json_body = json.loads(body_str)
        except json.JSONDecodeError:
            return f"Error: Invalid JSON in body: {body_str[:100]}"
    
    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.request(method, url, headers=headers, json=json_body)
            
            # Try to parse response as JSON
            try:
                response_body = response.json()
            except (json.JSONDecodeError, Exception):
                response_body = response.text
            
            result = {
                "status_code": response.status_code,
                "body": response_body,
            }
            return json.dumps(result)
            
    except httpx.HTTPStatusError as e:
        return json.dumps({"status_code": e.response.status_code, "error": str(e)})
    except httpx.RequestError as e:
        return f"Error: Network error - {e}"
    except Exception as e:
        return f"Error: {e}"


TOOL_FUNCTIONS = {
    "list_files": tool_list_files,
    "read_file": tool_read_file,
}


# =============================================================================
# LLM Communication
# =============================================================================

def call_llm(
    messages: list[dict[str, Any]],
    api_base: str,
    api_key: str,
    model: str,
    tools: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Call the LLM API and return the response data."""
    url = f"{api_base}/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    
    body: dict[str, Any] = {
        "model": model,
        "messages": messages,
    }
    
    if tools:
        body["tools"] = tools
        body["tool_choice"] = "auto"
    
    with httpx.Client(timeout=40.0) as client:
        response = client.post(url, headers=headers, json=body)
        response.raise_for_status()
        return response.json()


# =============================================================================
# Agentic Loop
# =============================================================================

def run_agent_loop(
    question: str,
    api_base: str,
    api_key: str,
    model: str,
    lms_api_key: str,
    agent_api_base_url: str,
) -> dict[str, Any]:
    """
    Run the agentic loop: call LLM, execute tools, feed results back.
    
    Returns:
        {"answer": str, "source": str, "tool_calls": list}
    """
    project_root = get_project_root()
    
    # Build system prompt
    system_prompt = f"""You are a documentation and system agent for a software engineering project.
Your goal is to answer questions by reading documentation, source code, and querying the live API.

You have three tools:
1. list_files(path: str) - List files in a directory
2. read_file(path: str) - Read a file's contents
3. query_api(method: str, path: str, body: str?) - Query the backend API

Tool selection strategy:
- For wiki/documentation questions → use list_files("wiki") then read_file
- For source code questions → use read_file on backend/ files directly
- For live data questions (counts, status codes, API behavior) → use query_api
- For bug diagnosis → use query_api to reproduce the error, then read_file to find the bug

When you find the answer, respond with a JSON object:
{{
  "answer": "your answer here",
  "source": "wiki/filename.md#section-anchor or backend/path.py"
}}

Rules:
- Always include a source reference when reading files (format: path/to/file.md#section or path/to/file.py)
- For API queries, you can use the API endpoint as source (e.g., "API: GET /items/")
- If the section is unclear, use just the file path
- Keep answers concise and accurate
- Do not make up information - only use what you read from files or API responses
- For query_api, always include the Authorization header with the LMS API key

Project root: {project_root}
Backend API base URL: {agent_api_base_url}
"""
    
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": question},
    ]
    
    tools = get_tool_schemas()
    tool_calls_output: list[dict[str, Any]] = []
    tool_call_count = 0
    
    while tool_call_count < MAX_TOOL_CALLS:
        # Call LLM
        response_data = call_llm(messages, api_base, api_key, model, tools=tools)
        
        # Extract assistant message
        try:
            assistant_message = response_data["choices"][0]["message"]
        except (KeyError, IndexError) as e:
            print(f"Error parsing LLM response: {e}", file=sys.stderr)
            print(f"Raw response: {response_data}", file=sys.stderr)
            return {
                "answer": "Error: Could not parse LLM response.",
                "source": "",
                "tool_calls": tool_calls_output,
            }
        
        content = assistant_message.get("content") or ""
        tool_calls = assistant_message.get("tool_calls", [])
        
        # If no tool calls, we have a final answer
        if not tool_calls:
            # Parse the content as JSON to extract answer and source
            try:
                parsed = json.loads(content.strip())
                answer = parsed.get("answer", content.strip())
                source = parsed.get("source", "")
            except json.JSONDecodeError:
                # Fallback: use content as answer, empty source
                answer = content.strip()
                source = ""
            
            return {
                "answer": answer,
                "source": source,
                "tool_calls": tool_calls_output,
            }
        
        # Execute tool calls
        for tool_call in tool_calls:
            tool_call_id = tool_call.get("id", "")
            function = tool_call.get("function", {})
            tool_name = function.get("name", "")
            tool_args_str = function.get("arguments", "{}")
            
            try:
                tool_args = json.loads(tool_args_str)
            except json.JSONDecodeError:
                tool_args = {}
            
            # Execute the tool
            if tool_name in TOOL_FUNCTIONS:
                try:
                    result = TOOL_FUNCTIONS[tool_name](tool_args)
                except Exception as e:
                    result = f"Error executing tool: {e}"
            elif tool_name == "query_api":
                try:
                    result = tool_query_api(tool_args, lms_api_key, agent_api_base_url)
                except Exception as e:
                    result = f"Error executing tool: {e}"
            else:
                result = f"Error: Unknown tool '{tool_name}'"
            
            # Record the tool call for output
            tool_calls_output.append({
                "tool": tool_name,
                "args": tool_args,
                "result": result,
            })
            
            tool_call_count += 1
            
            # Feed result back to LLM as a tool message
            messages.append({
                "role": "tool",
                "tool_call_id": tool_call_id,
                "content": result,
            })
        
        # Add assistant message to history before continuing
        messages.append(assistant_message)
    
    # Hit max tool calls - return whatever we have
    return {
        "answer": "Reached maximum tool call limit. Could not find a complete answer.",
        "source": "",
        "tool_calls": tool_calls_output,
    }


# =============================================================================
# Output
# =============================================================================

def output_result(answer: str, source: str, tool_calls: list[dict[str, Any]], error: str | None = None) -> None:
    """Output the result as JSON to stdout."""
    result = {
        "answer": answer,
        "source": source,
        "tool_calls": tool_calls,
    }
    if error:
        result["error"] = error
    print(json.dumps(result, ensure_ascii=False))


# =============================================================================
# Main
# =============================================================================

def main() -> None:
    """Main entry point for the agent CLI."""
    # Parse command-line arguments
    if len(sys.argv) < 2:
        print("Usage: uv run agent.py \"<question>\"", file=sys.stderr)
        print("Example: uv run agent.py \"How many items are in the database?\"", file=sys.stderr)
        sys.exit(1)
    
    question = sys.argv[1]
    
    # Load configuration
    api_base, api_key, model, lms_api_key, agent_api_base_url = load_config()
    
    try:
        # Run the agentic loop
        result = run_agent_loop(question, api_base, api_key, model, lms_api_key, agent_api_base_url)
        output_result(
            answer=result["answer"],
            source=result["source"],
            tool_calls=result["tool_calls"],
        )
        sys.exit(0)
    except httpx.HTTPStatusError as e:
        error_msg = f"HTTP error: {e.response.status_code}"
        print(f"LLM API error: {error_msg}", file=sys.stderr)
        output_result(answer="", source="", tool_calls=[], error=error_msg)
        sys.exit(1)
    except httpx.RequestError as e:
        error_msg = f"Network error: {e}"
        print(f"LLM API error: {error_msg}", file=sys.stderr)
        output_result(answer="", source="", tool_calls=[], error=error_msg)
        sys.exit(1)
    except Exception as e:
        error_msg = f"Unexpected error: {e}"
        print(f"Error: {error_msg}", file=sys.stderr)
        output_result(answer="", source="", tool_calls=[], error=error_msg)
        sys.exit(1)


if __name__ == "__main__":
    main()
