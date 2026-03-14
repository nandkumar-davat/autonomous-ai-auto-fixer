import pytest
from pathlib import Path
from autofixer.remediation.context_retriever import ContextRetriever

def test_context_retrieval(tmp_path):
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    file_path = repo_dir / "app.py"
    
    lines = [f"line {i}" for i in range(1, 101)]
    file_path.write_text("\n".join(lines))
    
    retriever = ContextRetriever(workspace_dir=str(tmp_path))
    context = retriever.get_context("repo", "app.py", 50, window=10)
    
    assert "line 40" in context
    assert "line 50" in context
    assert "line 60" in context
    assert "line 1" not in context  # Out of window
    assert "line 100" not in context # Out of window

def test_context_retrieval_boundaries(tmp_path):
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    file_path = repo_dir / "app.py"
    file_path.write_text("line 1\nline 2\nline 3")
    
    retriever = ContextRetriever(workspace_dir=str(tmp_path))
    # Test line 1
    context = retriever.get_context("repo", "app.py", 1, window=5)
    assert context.startswith("line 1")
    
    # Test line 3
    context = retriever.get_context("repo", "app.py", 3, window=5)
    assert context.endswith("line 3")
