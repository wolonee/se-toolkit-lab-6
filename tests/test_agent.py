"""
Regression tests for agent.py (Task 1)

Tests verify that the agent:
- Outputs valid JSON
- Has required 'answer' and 'tool_calls' fields
- Exits with code 0 on success
"""

import json
import subprocess
import sys


def test_agent_outputs_valid_json():
    """Test that agent.py outputs valid JSON with required fields."""
    result = subprocess.run(
        ["uv", "run", "agent.py", "What is 2 + 2?"],
        capture_output=True,
        text=True,
    )

    # Check exit code
    assert result.returncode == 0, f"Agent exited with code {result.returncode}, stderr: {result.stderr}"

    # Parse stdout as JSON
    try:
        output = json.loads(result.stdout)
    except json.JSONDecodeError as e:
        raise AssertionError(f"Agent output is not valid JSON: {e}\nstdout: {result.stdout}")

    # Check required fields
    assert "answer" in output, "Missing 'answer' field in output"
    assert isinstance(output["answer"], str), "'answer' should be a string"

    assert "tool_calls" in output, "Missing 'tool_calls' field in output"
    assert isinstance(output["tool_calls"], list), "'tool_calls' should be a list"


def test_agent_missing_question():
    """Test that agent.py exits with error when no question is provided."""
    result = subprocess.run(
        ["uv", "run", "agent.py"],
        capture_output=True,
        text=True,
    )

    # Should exit with non-zero code
    assert result.returncode != 0, "Agent should exit with non-zero code when no question provided"

    # Should print usage to stderr
    assert "Usage" in result.stderr or "question" in result.stderr.lower(), \
        f"Agent should print usage to stderr, got: {result.stderr}"
