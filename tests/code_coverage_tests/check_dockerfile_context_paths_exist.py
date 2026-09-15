"""Every path a Dockerfile copies or bind-mounts from the build context must be tracked in git.

A path that exists only in someone's working copy, such as a deleted folder whose compiled files
linger on disk, builds locally and fails on a clean checkout.
"""

import re
import subprocess
import sys
from pathlib import Path
from typing import Final

REPO: Final = Path(__file__).resolve().parents[2]
DOCKERFILES: Final = (
    "Dockerfile",
    "docker/Dockerfile.non_root",
    "docker/Dockerfile.database",
    "backend/Dockerfile",
    "gateway/Dockerfile",
    "migrations/Dockerfile",
)
COPY_FROM_CONTEXT: Final = re.compile(r"^\s*COPY\s+(?!--from)(?:--\S+\s+)*(?P<args>\S.*)$")
BIND_SOURCE: Final = re.compile(r"type=bind,source=(?P<source>[^,\s]+)")


def context_paths(dockerfile_text: str) -> tuple[str, ...]:
    copied: Final = tuple(
        source
        for match in map(COPY_FROM_CONTEXT.match, dockerfile_text.splitlines())
        if match is not None
        for source in match.group("args").split()[:-1]
    )
    mounted: Final = tuple(match.group("source") for match in BIND_SOURCE.finditer(dockerfile_text))
    return tuple(path for path in (*copied, *mounted) if path not in (".", "./") and "*" not in path)


def is_tracked(path: str) -> bool:
    listed: Final = subprocess.run(
        ["git", "ls-files", "--", path.rstrip("/")], cwd=REPO, capture_output=True, text=True, check=True
    )
    return bool(listed.stdout.strip())


def main() -> int:
    missing: Final = tuple(
        f"{dockerfile}: {path}"
        for dockerfile in DOCKERFILES
        for path in context_paths((REPO / dockerfile).read_text(encoding="utf-8"))
        if not is_tracked(path)
    )
    for line in missing:
        print(f"untracked build context path  {line}")
    if missing:
        return 1
    print(f"Every build context path in {len(DOCKERFILES)} Dockerfiles is tracked.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
