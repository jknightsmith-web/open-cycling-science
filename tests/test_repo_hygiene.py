"""Acceptance 17: rider files and databases cannot be committed by accident."""
import shutil
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]


@pytest.mark.skipif(shutil.which("git") is None or not (REPO / ".git").exists(), reason="needs a git checkout")
@pytest.mark.parametrize("path,ignored", [
    ("fixtures/real/ride.fit", True),
    ("some/where/activity.FIT", True),
    ("hub_session.tcx", True),
    ("data/cycling.db", True),
    ("cycling.db-wal", True),
    ("raw_files/abc", True),
    ("fixtures/synthetic/steady.fit", False),
    ("backend/config.py", False),
])
def test_gitignore(path, ignored):
    r = subprocess.run(["git", "check-ignore", "-q", path], cwd=REPO)
    assert (r.returncode == 0) is ignored
