import pytest
import subprocess
from pathlib import Path
from unittest.mock import patch, MagicMock
from autofixer.validation.linter import LinterValidator

def test_determine_language():
    validator = LinterValidator()
    assert validator._determine_language("test.py") == "python"
    assert validator._determine_language("test.js") == "javascript"
    assert validator._determine_language("test.unknown") is None

def test_validate_file_not_found():
    validator = LinterValidator(workspace_dir="/tmp/fake")
    success, msg = validator.validate_file("repo", "missing.py")
    assert success is False
    assert "File not found" in msg

@patch("subprocess.run")
def test_validate_file_python_success(mock_run, tmp_path):
    # Setup tmp file
    repo_dir = tmp_path / "myrepo"
    repo_dir.mkdir()
    file_path = repo_dir / "valid.py"
    file_path.write_text("print('hello')")
    
    mock_run.return_value = MagicMock(returncode=0)
    
    validator = LinterValidator(workspace_dir=str(tmp_path))
    success, msg = validator.validate_file("myrepo", "valid.py")
    
    assert success is True
    mock_run.assert_called_once()

@patch("subprocess.run")
def test_validate_file_python_failure(mock_run, tmp_path):
    repo_dir = tmp_path / "myrepo"
    repo_dir.mkdir()
    file_path = repo_dir / "invalid.py"
    file_path.write_text("import os")
    
    mock_run.return_value = MagicMock(returncode=1, stdout="Syntax error", stderr="")
    
    validator = LinterValidator(workspace_dir=str(tmp_path))
    success, msg = validator.validate_file("myrepo", "invalid.py")
    
    assert success is False
    assert "Syntax error" in msg
