"""Lint explicit PR Python files with the server's complete Ruff configuration.

Selection is the ACMR diff from --base to --head, optionally unioned with staged,
unstaged and untracked worktree files and repeated --owned repository paths.
Without --base, use merge-base(upstream/dev, --head). Files are linted from the
current worktree, not from an exported commit. Nothing is staged or rewritten.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

REPOSITORY = Path(__file__).resolve().parents[2]
RUFF_VERSION = "ruff 0.14.10"
WINDOWS_COMMAND_LIMIT = 24000


class GateError(RuntimeError):
    def __init__(self, message: str, code: int = 2):
        super().__init__(message)
        self.code = code


def run(command: list[str], cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(command, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)


def git(repo: Path, *arguments: str) -> bytes:
    result = run(["git", "-C", str(repo), *arguments], repo)
    if result.returncode:
        detail = result.stderr.decode("utf-8", errors="replace").strip()
        raise GateError(f"git failed ({result.returncode}): {detail}", result.returncode)
    return result.stdout


def resolve_range(repo: Path, base: str | None, head: str) -> tuple[str, str]:
    head_sha = git(repo, "rev-parse", "--verify", f"{head}^{{commit}}").decode("ascii").strip()
    if base is None:
        base_sha = git(repo, "merge-base", "upstream/dev", head_sha).decode("ascii").strip()
    else:
        base_sha = git(repo, "rev-parse", "--verify", f"{base}^{{commit}}").decode("ascii").strip()
    return base_sha, head_sha


def nul_paths(output: bytes) -> set[str]:
    if output and not output.endswith(b"\0"):
        raise GateError("git filename output is not NUL terminated")
    return {os.fsdecode(value) for value in output.split(b"\0") if value}


def changed_paths(repo: Path, *revisions: str, status: str = "ACMR") -> set[str]:
    return nul_paths(
        git(repo, "diff", "--name-only", "-z", f"--diff-filter={status}", "--find-renames", *revisions, "--")
    )


def _relative_python(repo: Path, name: str, *, owned: bool = False) -> str | None:
    path = Path(name)
    if path.suffix != ".py":
        if owned:
            raise GateError(f"--owned requires an explicit Python filename: {name}")
        return None
    if path.is_absolute() or ".." in path.parts or "\n" in name or "\r" in name:
        raise GateError(f"Expected a repository-relative filename: {name!r}")
    if not (repo / path).resolve().is_relative_to(repo.resolve()):
        raise GateError(f"Selected path escapes the repository: {name}")
    return path.as_posix()


def select_files(
    repo: Path, base: str, head: str, *, include_working_tree: bool, owned: list[str]
) -> tuple[list[Path], list[str]]:
    candidates = changed_paths(repo, base, head)
    deleted = changed_paths(repo, "HEAD", "--no-renames", status="D")
    deleted |= nul_paths(git(repo, "ls-files", "--deleted", "-z", "--"))
    if include_working_tree:
        candidates |= changed_paths(repo, "--cached", "HEAD") | changed_paths(repo)
        candidates |= nul_paths(git(repo, "ls-files", "--others", "--exclude-standard", "-z", "--"))
    selected = {_relative_python(repo, name) for name in candidates}
    selected.update(_relative_python(repo, name, owned=True) for name in owned)
    files, skipped = [], []
    for name in sorted(selected - {None}):
        path = repo / name
        if path.is_file():
            files.append(path.resolve())
        elif not path.exists() and name in deleted:
            skipped.append(name)
        else:
            raise GateError(f"Selected file is missing or not a file (not a confirmed deletion): {name}")
    return files, skipped


def batches(files: list[Path], prefix: list[str], limit: int = WINDOWS_COMMAND_LIMIT):
    """Budget the actual Windows command line, including quoting and UTF-16 units."""
    batch = []
    for path in files:
        candidate = [*prefix, *(str(item) for item in batch), str(path)]
        if len(subprocess.list2cmdline(candidate).encode("utf-16-le")) // 2 > limit:
            if not batch:
                raise GateError(f"A filename exceeds the command-line budget: {path}")
            yield batch
            batch = []
            candidate = [*prefix, str(path)]
            if len(subprocess.list2cmdline(candidate).encode("utf-16-le")) // 2 > limit:
                raise GateError(f"A filename exceeds the command-line budget: {path}")
        batch.append(path)
    if batch:
        yield batch


def ruff_command(repo: Path) -> list[str]:
    config = repo / "server" / "pyproject.toml"
    if not config.is_file():
        raise GateError(f"Server Ruff configuration is missing: {config}")
    return [sys.executable, "-m", "ruff", "check", "--config", str(config), "--no-cache"]


def _emit_process_output(result: subprocess.CompletedProcess) -> None:
    for value, stream in ((result.stdout, sys.stdout), (result.stderr, sys.stderr)):
        if value:
            print(value.decode("utf-8", errors="replace"), file=stream, end="")


def verify_shown_files(command: list[str], files: list[Path], cwd: Path) -> None:
    result = run([*command, "--show-files", "--", *(str(path) for path in files)], cwd)
    if result.returncode:
        _emit_process_output(result)
        raise GateError(f"Ruff --show-files failed with code {result.returncode}", result.returncode)
    actual = {Path(line).resolve() for line in result.stdout.decode("utf-8").splitlines() if line}
    expected = set(files)
    if actual != expected:
        missing = sorted(str(path) for path in expected - actual)
        extra = sorted(str(path) for path in actual - expected)
        raise GateError(f"Ruff --show-files set mismatch: missing={missing}, extra={extra}")


def check_files(repo: Path, files: list[Path]) -> int:
    command = ruff_command(repo)
    groups = list(batches(files, [*command, "--show-files", "--"]))
    cwd = repo / "server"
    for group in groups:
        verify_shown_files(command, group, cwd)
    print(f"Ruff --show-files exact set verified: {len(files)} files, {len(groups)} batches")
    exit_code = 0
    for index, group in enumerate(groups, start=1):
        result = run([*command, "--", *(str(path) for path in group)], cwd)
        _emit_process_output(result)
        print(f"Ruff batch {index}/{len(groups)}: files={len(group)} exit_code={result.returncode}")
        if result.returncode and not exit_code:
            exit_code = result.returncode
    return exit_code


def _parse_args(argv):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", help="Exact base revision; default: merge-base(upstream/dev, --head)")
    parser.add_argument(
        "--head", default="HEAD", help="Diff head revision (default HEAD); lint reads worktree contents"
    )
    parser.add_argument(
        "--include-working-tree",
        action="store_true",
        help="Union staged, unstaged and non-ignored untracked Python files",
    )
    parser.add_argument(
        "--owned",
        action="append",
        default=[],
        metavar="REPO_PATH.py",
        help="Add an explicit owned repository-relative Python file; repeatable",
    )
    return parser.parse_args(argv)


def main(argv=None, *, repo: Path = REPOSITORY) -> int:
    args = _parse_args(argv)
    repo = repo.resolve()
    try:
        base, head = resolve_range(repo, args.base, args.head)
        print(f"PR Python gate: base={base} head={head}")
        print(f"Source: current worktree; include_working_tree={args.include_working_tree}")
        version = run([sys.executable, "-m", "ruff", "--version"], repo / "server")
        if version.returncode:
            _emit_process_output(version)
            raise GateError(f"Ruff version check failed with code {version.returncode}", version.returncode)
        actual_version = version.stdout.decode("utf-8").strip()
        print(f"Version: {actual_version}")
        if actual_version != RUFF_VERSION:
            raise GateError(f"Required {RUFF_VERSION}, got {actual_version}")
        files, deleted = select_files(
            repo, base, head, include_working_tree=args.include_working_tree, owned=args.owned
        )
        print(f"Selected Python files: {len(files)}; skipped confirmed deletions: {len(deleted)}")
        for path in files:
            print(f"  {path.relative_to(repo).as_posix()}")
        for name in deleted:
            print(f"  deleted: {name}")
        code = check_files(repo, files)
    except GateError as exc:
        print(str(exc), file=sys.stderr)
        code = exc.code
    except OSError as exc:
        print(f"PR Python gate OS error: {exc}", file=sys.stderr)
        code = 2
    print(f"PR Python gate exit_code={code}")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
