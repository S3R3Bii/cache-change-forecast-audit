"""Verify the committed dependency snapshot preceding final score extraction."""

import hashlib, json, subprocess
from pathlib import Path


def verify(root):
    def git(*args):
        return subprocess.check_output(["git", *args], cwd=root)

    name = "data/dependency_freeze.json"
    raw = (root / name).read_bytes()
    assert raw == git("show", "HEAD:" + name)
    commit = git("log", "--format=%H", "--", name).decode().splitlines()[-1]
    assert raw == git("show", commit + ":" + name)
    m = json.loads(raw)
    subprocess.run(
        ["git", "merge-base", "--is-ancestor", m["development_commit"], commit],
        cwd=root,
        check=True,
    )
    assert not any(
        x.startswith(("results/final/", "data/final_verification"))
        for x in git("ls-tree", "-r", "--name-only", commit).decode().splitlines()
    )
    for item in m["files"]:
        content = (root / item["path"]).read_bytes()
        assert hashlib.sha256(content).hexdigest() == item["sha256"]
        assert content == git("show", commit + ":" + item["path"])
    return dict(
        status="PASS_COMMITTED_BEFORE_FINAL_SCORES",
        dependencies=len(m["files"]),
        development_commit=m["development_commit"],
        freeze_commit=commit,
    )


if __name__ == "__main__":
    print(json.dumps(verify(Path(__file__).resolve().parents[1])))
