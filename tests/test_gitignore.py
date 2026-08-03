"""Private data must never reach GitHub: .gitignore has to cover every place
the app keeps it."""

import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
MUST_IGNORE = ["testset/private/", "private/", "chroma/", ".chroma/", "*.sqlite3", "logs/", ".env*", ".venv/"]
PRIVATE_FILES = ["testset/private/items.json", "private/audit.sqlite3", "private/photos/front.jpg",
                 "chroma/chroma.sqlite3", "logs/run.log", ".env", ".env.local"]


def test_gitignore_lists_every_private_place():
    lines = {line.strip() for line in (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()}
    assert [pattern for pattern in MUST_IGNORE if pattern not in lines] == []
    assert "!.env.example" in lines  # the example file, with no real keys, is uploaded


@pytest.mark.skipif(not shutil.which("git") or not (ROOT / ".git").exists(), reason="needs the git repo")
def test_git_really_ignores_them():
    def ignored(path):
        return subprocess.run(["git", "check-ignore", "-q", "--no-index", path], cwd=ROOT).returncode == 0
    assert [path for path in PRIVATE_FILES if not ignored(path)] == []
    assert not ignored(".env.example")
