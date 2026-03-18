#!/usr/bin/env python3
"""
Agent CLI - Task 1: Call an LLM from Code

Takes a question as command-line argument, sends it to an LLM via OpenAI-compatible API,
and returns a structured JSON answer.

Usage:
    uv run agent.py "What does REST stand for?"

Output:
    {"answer": "Representational State Transfer.", "tool_calls": []}
"""

import json
import os
import sys
from pathlib import Path

import httpx


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
                    # Only set if not already in environment
                    if key not in os.environ:
                        env_vars[key] = value
    return env_vars


def load_config() -> tuple[str, str, str]:
    """Load LLM configuration from environment or .env.agent.secret file."""
    # Load from .env.agent.secret in project root
    project_root = Path(__file__).parent
    env_path = project_root / ".env.agent.secret"
    env_vars = load_env_file(env_path)

    # Get configuration (env takes precedence over file)
    api_base = os.environ.get("LLM_API_BASE") or env_vars.get("LLM_API_BASE")
    api_key = os.environ.get("LLM_API_KEY") or env_vars.get("LLM_API_KEY")
    model = os.environ.get("LLM_MODEL") or env_vars.get("LLM_MODEL")

    if not api_base:
        print("Error: LLM_API_BASE not set. Configure .env.agent.secret or set LLM_API_BASE env var.", file=sys.stderr)
        sys.exit(1)
    if not api_key:
        print("Error: LLM_API_KEY not set. Configure .env.agent.secret or set LLM_API_KEY env var.", file=sys.stderr)
        sys.exit(1)
    if not model:
        print("Error: LLM_MODEL not set. Configure .env.agent.secret or set LLM_MODEL env var.", file=sys.stderr)
        sys.exit(1)

    return api_base, api_key, model


def call_lllm(question: str, api_base: str, api_key: str, model: str) -> str:
    """Call the LLM API and return the answer text."""
    url = f"{api_base}/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    body = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": "You are a helpful assistant. Answer the question concisely. Tools are disabled.",
            },
            {
                "role": "user",
                "content": question,
            },
        ],
    }

    with httpx.Client(timeout=40.0) as client:
        response = client.post(url, headers=headers, json=body)
        response.raise_for_status()
        data = response.json()

    # Extract answer from response
    try:
        answer = data["choices"][0]["message"]["content"]
        if not answer:
            answer = "I don't have an answer for that."
        return answer
    except (KeyError, IndexError, TypeError) as e:
        print(f"Error parsing LLM response: {e}", file=sys.stderr)
        print(f"Raw response: {data}", file=sys.stderr)
        return "Error: Could not parse LLM response."


def output_result(answer: str, error: str | None = None) -> None:
    """Output the result as JSON to stdout."""
    result = {
        "answer": answer,
        "tool_calls": [],
    }
    if error:
        result["error"] = error
    print(json.dumps(result, ensure_ascii=False))


def main() -> None:
    """Main entry point for the agent CLI."""
    # Parse command-line arguments
    if len(sys.argv) < 2:
        print("Usage: uv run agent.py \"<question>\"", file=sys.stderr)
        print("Example: uv run agent.py \"What does REST stand for?\"", file=sys.stderr)
        sys.exit(1)

    question = sys.argv[1]

    # Load configuration
    api_base, api_key, model = load_config()

    try:
        # Call LLM and get answer
        answer = call_lllm(question, api_base, api_key, model)
        output_result(answer)
        sys.exit(0)
    except httpx.HTTPStatusError as e:
        error_msg = f"HTTP error: {e.response.status_code}"
        print(f"LLM API error: {error_msg}", file=sys.stderr)
        output_result("", error_msg)
        sys.exit(1)
    except httpx.RequestError as e:
        error_msg = f"Network error: {e}"
        print(f"LLM API error: {error_msg}", file=sys.stderr)
        output_result("", error_msg)
        sys.exit(1)
    except Exception as e:
        error_msg = f"Unexpected error: {e}"
        print(f"Error: {error_msg}", file=sys.stderr)
        output_result("", error_msg)
        sys.exit(1)


if __name__ == "__main__":
    main()
