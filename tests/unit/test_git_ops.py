import pytest
from pathlib import Path
from autofixer.vcs.git_ops import GitOperations
from autofixer.models.enums import AgentMode

def test_apply_patch(tmp_path):
    # Setup mock workspace
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    
    repo_path = workspace / "my_repo"
    repo_path.mkdir()
    
    file_path = repo_path / "hello.py"
    file_path.write_text("print('hello world')")
    
    # Test applying patch
    ops = GitOperations(workspace_dir=str(workspace))
    
    ops.apply_patch(repo_path, "hello.py", "print('hello there')")
    
    new_content = file_path.read_text()
    assert new_content == "print('hello there')"

def test_cleanup_workspace(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    repo_path = workspace / "my_repo"
    repo_path.mkdir()
    
    ops = GitOperations(workspace_dir=str(workspace))
    assert repo_path.exists()
    
    ops.cleanup_workspace()
    
    # Workspace should exist but be empty
    assert ops.workspace_dir.exists()
    assert not repo_path.exists()
