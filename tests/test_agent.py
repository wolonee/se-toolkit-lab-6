"""
Regression tests for agent.py (Task 1, 2, and 3)

Tests verify that the agent:
- Outputs valid JSON with required fields
- Executes tool calls correctly
- Includes source references in answers
- Uses appropriate tools for different question types
"""

import json
import subprocess
import sys


def test_agent_outputs_valid_json():
    """Test that agent.py outputs valid JSON with required fields (Task 1)."""
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


def test_merge_conflict_question():
    """
    Test that agent uses read_file tool for merge conflict question (Task 2).
    
    Expects:
    - read_file in tool_calls
    - wiki/git-workflow.md in source
    """
    result = subprocess.run(
        ["uv", "run", "agent.py", "How do you resolve a merge conflict?"],
        capture_output=True,
        text=True,
        timeout=120,  # Allow up to 2 minutes for LLM response
    )

    # Check exit code
    assert result.returncode == 0, f"Agent exited with code {result.returncode}, stderr: {result.stderr}"

    # Parse stdout as JSON
    try:
        output = json.loads(result.stdout)
    except json.JSONDecodeError as e:
        raise AssertionError(f"Agent output is not valid JSON: {e}\nstdout: {result.stdout}")

    # Check required fields exist
    assert "answer" in output, "Missing 'answer' field in output"
    assert "source" in output, "Missing 'source' field in output"
    assert "tool_calls" in output, "Missing 'tool_calls' field in output"

    # Check tool_calls contains read_file
    tool_names = [tc.get("tool") for tc in output["tool_calls"]]
    assert "read_file" in tool_names, \
        f"Expected 'read_file' in tool_calls, got: {tool_names}"

    # Check source contains wiki/git-workflow.md
    source = output.get("source", "")
    assert "wiki/git-workflow.md" in source, \
        f"Expected 'wiki/git-workflow.md' in source, got: {source}"


def test_wiki_listing_question():
    """
    Test that agent uses list_files tool for wiki listing question (Task 2).
    
    Expects:
    - list_files in tool_calls
    """
    result = subprocess.run(
        ["uv", "run", "agent.py", "What files are in the wiki?"],
        capture_output=True,
        text=True,
        timeout=120,  # Allow up to 2 minutes for LLM response
    )

    # Check exit code
    assert result.returncode == 0, f"Agent exited with code {result.returncode}, stderr: {result.stderr}"

    # Parse stdout as JSON
    try:
        output = json.loads(result.stdout)
    except json.JSONDecodeError as e:
        raise AssertionError(f"Agent output is not valid JSON: {e}\nstdout: {result.stdout}")

    # Check required fields exist
    assert "answer" in output, "Missing 'answer' field in output"
    assert "source" in output, "Missing 'source' field in output"
    assert "tool_calls" in output, "Missing 'tool_calls' field in output"

    # Check tool_calls contains list_files
    tool_names = [tc.get("tool") for tc in output["tool_calls"]]
    assert "list_files" in tool_names, \
        f"Expected 'list_files' in tool_calls, got: {tool_names}"


def test_backend_framework_question():
    """
    Test that agent uses read_file for backend source code question (Task 3).
    
    Expects:
    - read_file in tool_calls
    - FastAPI in answer
    - backend/ path in source
    """
    result = subprocess.run(
        ["uv", "run", "agent.py", "What Python web framework does the backend use?"],
        capture_output=True,
        text=True,
        timeout=120,
    )

    # Check exit code
    assert result.returncode == 0, f"Agent exited with code {result.returncode}, stderr: {result.stderr}"

    # Parse stdout as JSON
    try:
        output = json.loads(result.stdout)
    except json.JSONDecodeError as e:
        raise AssertionError(f"Agent output is not valid JSON: {e}\nstdout: {result.stdout}")

    # Check required fields exist
    assert "answer" in output, "Missing 'answer' field in output"
    assert "source" in output, "Missing 'source' field in output"
    assert "tool_calls" in output, "Missing 'tool_calls' field in output"

    # Check tool_calls contains read_file
    tool_names = [tc.get("tool") for tc in output["tool_calls"]]
    assert "read_file" in tool_names, \
        f"Expected 'read_file' in tool_calls, got: {tool_names}"

    # Check answer mentions FastAPI
    answer = output.get("answer", "").lower()
    assert "fastapi" in answer, \
        f"Expected 'FastAPI' in answer, got: {output.get('answer', '')}"


def test_query_api_tool():
    """
    Test that agent uses query_api for database count question (Task 3).
    
    Expects:
    - query_api in tool_calls
    - A number in the answer
    """
    result = subprocess.run(
        ["uv", "run", "agent.py", "How many items are in the database?"],
        capture_output=True,
        text=True,
        timeout=120,
    )

    # Check exit code
    assert result.returncode == 0, f"Agent exited with code {result.returncode}, stderr: {result.stderr}"

    # Parse stdout as JSON
    try:
        output = json.loads(result.stdout)
    except json.JSONDecodeError as e:
        raise AssertionError(f"Agent output is not valid JSON: {e}\nstdout: {result.stdout}")

    # Check required fields exist
    assert "answer" in output, "Missing 'answer' field in output"
    assert "tool_calls" in output, "Missing 'tool_calls' field in output"

    # Check tool_calls contains query_api
    tool_names = [tc.get("tool") for tc in output["tool_calls"]]
    assert "query_api" in tool_names, \
        f"Expected 'query_api' in tool_calls, got: {tool_names}"

    # Check answer contains a number
    import re
    answer = output.get("answer", "")
    numbers = re.findall(r"\d+", answer)
    assert len(numbers) > 0, \
        f"Expected a number in answer, got: {answer}"
