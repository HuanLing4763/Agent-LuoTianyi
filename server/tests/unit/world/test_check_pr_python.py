"""Explicit-filename Ruff gate, using mocks and a disposable git repository."""

from __future__ import annotations

import subprocess
import sys

import pytest

from scripts import check_pr_python as gate

BASE = "a" * 40
HEAD = "b" * 40


def completed(command, stdout=b"", stderr=b"", code=0):
    return subprocess.CompletedProcess(command, code, stdout, stderr)


def make_file(repo, name, content="value = 1\n"):
    path = repo / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content.encode("utf-8"))
    return path.resolve()


def make_config(repo):
    return make_file(repo, "server/pyproject.toml", "[tool.ruff]\ninclude = ['src/nothing.py']\n")


def names_output(*names):
    return b"".join(name.encode("utf-8") + b"\0" for name in names)


def test_git_commands_fix_sha_and_keep_nul_paths(monkeypatch, tmp_path):
    files = [
        make_file(tmp_path, name)
        for name in (
            "server/scripts/汉 字.py",
            "server/tests/staged.py",
            "server/tests/work.py",
            "server/tests/new.py",
        )
    ]
    commands = []

    def fake_run(command, cwd):
        commands.append(command)
        args = command[3:]
        assert command[:3] == ["git", "-C", str(tmp_path)]
        assert cwd == tmp_path
        if args[0] == "rev-parse":
            return completed(command, (HEAD + "\n").encode())
        if args[0] == "merge-base":
            assert args == ["merge-base", "upstream/dev", HEAD]
            return completed(command, (BASE + "\n").encode())
        if args[0] == "ls-files":
            return completed(command, names_output("server/tests/new.py") if "--others" in args else b"")
        assert args[0] == "diff" and "-z" in args
        if "--diff-filter=D" in args:
            return completed(command)
        assert "--diff-filter=ACMR" in args
        if "--cached" in args:
            return completed(command, names_output("server/tests/staged.py"))
        if BASE in args:
            return completed(command, names_output("server/scripts/汉 字.py", "ignored.txt"))
        return completed(command, names_output("server/tests/work.py"))

    monkeypatch.setattr(gate, "run", fake_run)
    base, head = gate.resolve_range(tmp_path, None, "HEAD")
    selected, deleted = gate.select_files(
        tmp_path, base, head, include_working_tree=True, owned=["server/tests/new.py"]
    )
    assert set(selected) == set(files)
    assert not deleted
    assert any(BASE in command and HEAD in command for command in commands)


def test_explicit_base_resolves_both_refs(monkeypatch, tmp_path):
    calls = []

    def fake_git(repo, *args):
        calls.append(args)
        return ((BASE if args[-1] == "base-ref^{commit}" else HEAD) + "\n").encode()

    monkeypatch.setattr(gate, "git", fake_git)
    assert gate.resolve_range(tmp_path, "base-ref", "head-ref") == (BASE, HEAD)
    assert calls == [
        ("rev-parse", "--verify", "head-ref^{commit}"),
        ("rev-parse", "--verify", "HEAD^{commit}"),
        ("rev-parse", "--verify", "base-ref^{commit}"),
    ]


def test_candidate_deleted_is_skipped_but_typo_fails(monkeypatch, tmp_path):
    def fake_git(repo, *args):
        if "--diff-filter=D" in args or "--deleted" in args:
            return names_output("server/deleted.py")
        return names_output("server/deleted.py", "server/typo.py")

    monkeypatch.setattr(gate, "git", fake_git)
    with pytest.raises(gate.GateError, match="typo.py"):
        gate.select_files(tmp_path, BASE, HEAD, include_working_tree=True, owned=[])
    make_file(tmp_path, "server/typo.py")
    files, deleted = gate.select_files(tmp_path, BASE, HEAD, include_working_tree=True, owned=[])
    assert [path.name for path in files] == ["typo.py"]
    assert deleted == ["server/deleted.py"]


@pytest.mark.parametrize("name", ["", "../outside.py", "server", "server/file.txt", "/absolute.py", "line\nbreak.py"])
def test_owned_requires_exact_contained_python_filename(tmp_path, name):
    with pytest.raises(gate.GateError):
        gate._relative_python(tmp_path, name, owned=True)


def test_directory_disguised_as_python_is_not_a_file(monkeypatch, tmp_path):
    (tmp_path / "directory.py").mkdir()
    monkeypatch.setattr(gate, "git", lambda *args: b"")
    with pytest.raises(gate.GateError, match="not a file"):
        gate.select_files(tmp_path, BASE, HEAD, include_working_tree=True, owned=["directory.py"])


def test_nul_parser_rejects_unterminated_output():
    with pytest.raises(gate.GateError, match="NUL"):
        gate.nul_paths(b"server/a.py\n")


def test_ruff_exact_files_uses_server_config_and_propagates_exit(monkeypatch, tmp_path):
    config = make_config(tmp_path)
    files = [make_file(tmp_path, "server/scripts/a.py"), make_file(tmp_path, "server/tests/汉 字.py")]
    commands = []

    def fake_run(command, cwd):
        commands.append(command)
        assert cwd == tmp_path / "server"
        assert command[:4] == [sys.executable, "-m", "ruff", "check"]
        assert command[command.index("--config") + 1] == str(config)
        assert "--isolated" not in command
        assert command[command.index("--") + 1 :] == list(map(str, files))
        if "--show-files" in command:
            return completed(command, ("\n".join(map(str, files)) + "\n").encode())
        return completed(command, b"lint error\n", code=1)

    monkeypatch.setattr(gate, "run", fake_run)
    assert gate.check_files(tmp_path, files) == 1
    assert len(commands) == 2
    assert "--show-files" in commands[0] and "--show-files" not in commands[1]


@pytest.mark.parametrize("mode", ["missing", "extra"])
def test_ruff_show_files_mismatch_blocks_lint(monkeypatch, tmp_path, mode):
    make_config(tmp_path)
    files = [make_file(tmp_path, "server/a.py")]
    commands = []

    def fake_run(command, cwd):
        commands.append(command)
        shown = [] if mode == "missing" else [*files, tmp_path / "extra.py"]
        return completed(command, "\n".join(map(str, shown)).encode())

    monkeypatch.setattr(gate, "run", fake_run)
    with pytest.raises(gate.GateError, match="set mismatch"):
        gate.check_files(tmp_path, files)
    assert len(commands) == 1


def test_windows_batches_are_bounded_and_do_not_drop_files(tmp_path):
    files = [tmp_path / f"汉 字_{index}.py" for index in range(12)]
    prefix = ["python", "-m", "ruff", "check", "--show-files", "--"]
    limit = len(subprocess.list2cmdline([*prefix, *map(str, files[:2])]).encode("utf-16-le")) // 2
    groups = list(gate.batches(files, prefix, limit=limit))
    assert len(groups) > 1
    assert [path for group in groups for path in group] == files
    for group in groups:
        assert len(subprocess.list2cmdline([*prefix, *map(str, group)]).encode("utf-16-le")) // 2 <= limit
    with pytest.raises(gate.GateError, match="budget"):
        list(gate.batches(files, prefix, limit=1))


@pytest.mark.parametrize("version,code", [(b"ruff 0.14.10\n", 0), (b"ruff 0.14.9\n", 2)])
def test_main_reports_sha_version_and_code(monkeypatch, tmp_path, capsys, version, code):
    make_config(tmp_path)
    monkeypatch.setattr(gate, "resolve_range", lambda *args: (BASE, HEAD))
    monkeypatch.setattr(gate, "select_files", lambda *args, **kwargs: ([], []))
    monkeypatch.setattr(gate, "run", lambda command, cwd: completed(command, version))
    assert gate.main([], repo=tmp_path) == code
    output = capsys.readouterr()
    assert BASE in output.out and HEAD in output.out
    assert version.decode().strip() in output.out
    assert f"exit_code={code}" in output.out


def git_repo(repo, *args):
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        cwd=gate.REPOSITORY / "server",
        check=True,
        capture_output=True,
        timeout=30,
    )
    return result.stdout.decode("utf-8").strip()


def test_real_tmp_git_selects_pr_rename_worktree_and_owned_without_mutation(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    git_repo(repo, "init", "-q")
    git_repo(repo, "config", "user.email", "offline@example.invalid")
    git_repo(repo, "config", "user.name", "Offline Test")
    make_config(repo)
    for name in ("rename.py", "delete.py", "unchanged.py", "modified.py"):
        make_file(repo, f"server/{name}")
    git_repo(repo, "add", ".")
    git_repo(repo, "commit", "-qm", "base")
    base = git_repo(repo, "rev-parse", "HEAD")
    git_repo(repo, "update-ref", "refs/remotes/upstream/dev", base)
    git_repo(repo, "mv", "server/rename.py", "server/renamed 汉字.py")
    git_repo(repo, "rm", "server/delete.py")
    make_file(repo, "server/modified.py", "value = 2\n")
    make_file(repo, "server/added.py")
    git_repo(repo, "add", ".")
    git_repo(repo, "commit", "-qm", "head")
    head = git_repo(repo, "rev-parse", "HEAD")
    (repo / "server/added.py").unlink()
    make_file(repo, "server/staged.py")
    git_repo(repo, "add", "server/staged.py")
    make_file(repo, "server/unchanged.py", "value = 3\n")
    make_file(repo, "server/new 汉字.py")
    make_file(repo, "ignored.txt")
    make_file(repo, "server/owned.py")
    git_repo(repo, "config", "core.quotePath", "true")
    before = git_repo(repo, "status", "--porcelain=v1", "-z")
    assert gate.resolve_range(repo, None, "HEAD") == (base, head)
    selected, deleted = gate.select_files(repo, base, head, include_working_tree=True, owned=["server/owned.py"])
    assert {path.name for path in selected} == {
        "renamed 汉字.py",
        "modified.py",
        "staged.py",
        "unchanged.py",
        "new 汉字.py",
        "owned.py",
    }
    assert deleted == ["server/added.py"]
    assert git_repo(repo, "status", "--porcelain=v1", "-z") == before
    assert git_repo(repo, "rev-parse", "HEAD") == head


@pytest.fixture
def commit_repo(tmp_path):
    """Only synthetic content; never copy product configuration or secrets."""
    repo = tmp_path / "repo"
    repo.mkdir()
    git_repo(repo, "init", "-q")
    git_repo(repo, "config", "user.email", "offline@example.invalid")
    git_repo(repo, "config", "user.name", "Offline Test")
    git_repo(repo, "config", "core.autocrlf", "false")
    make_config(repo)
    make_file(repo, gate.GATE_PATH, "# synthetic gate fixture\n")
    make_file(repo, "server/owned.py")
    make_file(repo, "docs/note.txt", "base\n")
    git_repo(repo, "add", ".")
    git_repo(repo, "commit", "-qm", "base")
    base = git_repo(repo, "rev-parse", "HEAD")
    make_file(repo, "server/坏 文件.py", "print(undefined_name)\n")
    git_repo(repo, "add", ".")
    git_repo(repo, "commit", "-qm", "head")
    return repo, base, git_repo(repo, "rev-parse", "HEAD")


@pytest.fixture
def ruff_calls(monkeypatch):
    original_run = gate.run
    calls = []

    def run(command, cwd):
        if command[0] == "git":
            return original_run(command, cwd)
        calls.append(command)
        if "--version" in command:
            return completed(command, b"ruff 0.14.10\n")
        if "--show-files" in command:
            return completed(command, "\n".join(command[command.index("--") + 1 :]).encode("utf-8"))
        return completed(command)

    monkeypatch.setattr(gate, "run", run)
    return calls


def repo_snapshot(repo):
    files = {
        path.relative_to(repo).as_posix(): path.read_bytes()
        for path in repo.rglob("*")
        if ".git" not in path.relative_to(repo).parts and path.is_file()
    }
    return git_repo(repo, "rev-parse", "HEAD"), git_repo(repo, "ls-files", "--stage", "-z"), files


def test_fixed_clean_bad_file_fails_real_ruff_without_mutation(commit_repo, capsys):
    repo, base, head = commit_repo
    before = repo_snapshot(repo)
    assert gate.main(["--base", base, "--head", head], repo=repo) == 1
    output = capsys.readouterr()
    assert "mode: commit-validation" in output.out
    assert "F821" in output.out
    assert "exact set verified: 1 files" in output.out
    assert "exit_code=1" in output.out
    assert repo_snapshot(repo) == before


@pytest.mark.parametrize("change", ["delete", "edit", "index-edit", "staged-delete", "skip-worktree"])
def test_fixed_rejects_source_drift_before_ruff(commit_repo, ruff_calls, capsys, change):
    repo, base, head = commit_repo
    path = repo / "server/坏 文件.py"
    if change == "skip-worktree":
        git_repo(repo, "update-index", "--skip-worktree", "server/坏 文件.py")
    if change in {"delete", "staged-delete"}:
        path.unlink()
    else:
        path.write_text("value = 1\n", encoding="utf-8")
    if change in {"index-edit", "staged-delete"}:
        git_repo(repo, "add", "-u")
    if change == "index-edit":
        path.write_text("print(undefined_name)\n", encoding="utf-8")
    before = repo_snapshot(repo)
    assert gate.main(["--base", base, "--head", head], repo=repo) == 2
    assert "坏 文件.py" in capsys.readouterr().err
    assert not ruff_calls
    assert repo_snapshot(repo) == before


@pytest.mark.parametrize("candidate", [False, True])
def test_both_modes_reject_head_mismatch_before_ruff(commit_repo, ruff_calls, capsys, candidate):
    repo, base, head = commit_repo
    args = ["--base", base, "--head", base]
    if candidate:
        args.append("--include-working-tree")
    assert gate.main(args, repo=repo) == 2
    assert f"HEAD mismatch: actual={head}" in capsys.readouterr().err
    assert not ruff_calls


@pytest.mark.parametrize(
    "name",
    ["server/pyproject.toml", "server/ruff.toml", "server/.ruff.toml", "pyproject.toml", gate.GATE_PATH],
)
@pytest.mark.parametrize("staged", [False, True])
def test_fixed_rejects_gate_and_config_drift_before_ruff(commit_repo, ruff_calls, capsys, name, staged):
    repo, base, head = commit_repo
    make_file(repo, name, "# local override\n")
    if staged:
        git_repo(repo, "add", "--", name)
    before = repo_snapshot(repo)
    assert gate.main(["--base", base, "--head", head], repo=repo) == 2
    assert name in capsys.readouterr().err
    assert not ruff_calls
    assert repo_snapshot(repo) == before


@pytest.mark.parametrize("change", ["delete", "edit", "staged-delete"])
def test_candidate_local_changes_are_not_commit_proof(commit_repo, capsys, change):
    repo, base, head = commit_repo
    path = repo / "server/坏 文件.py"
    if change == "edit":
        path.write_text("value = 1\n", encoding="utf-8")
    else:
        path.unlink()
    if change == "staged-delete":
        git_repo(repo, "add", "-u")
    before = repo_snapshot(repo)
    assert gate.main(["--base", base, "--head", head, "--include-working-tree"], repo=repo) == 0
    output = capsys.readouterr().out
    assert "candidate-only (not commit proof)" in output
    assert "Commit scope verified" not in output
    if change != "edit":
        assert "deleted: server/坏 文件.py" in output
        assert "no lint executed" in output
    assert repo_snapshot(repo) == before


def test_committed_deletion_is_empty_not_a_local_skip(commit_repo, ruff_calls, capsys):
    repo, _, old_head = commit_repo
    git_repo(repo, "rm", "server/坏 文件.py")
    git_repo(repo, "commit", "-qm", "delete")
    assert gate.main(["--base", old_head], repo=repo) == 0
    output = capsys.readouterr().out
    assert "skipped confirmed deletions: 0" in output
    assert "empty scope, not a Python lint pass" in output
    assert len(ruff_calls) == 1 and "--version" in ruff_calls[0]
    ruff_calls.clear()
    assert gate.main(["--base", old_head, "--owned", "server/坏 文件.py"], repo=repo) == 2
    assert "absent from target commit" in capsys.readouterr().err
    assert not ruff_calls


@pytest.mark.parametrize("candidate", [False, True])
def test_untracked_owned_requires_candidate_mode(commit_repo, ruff_calls, capsys, candidate):
    repo, _, head = commit_repo
    make_file(repo, "server/本地 owned.py")
    args = ["--base", head, "--owned", "server/本地 owned.py"]
    if candidate:
        args.append("--include-working-tree")
    assert gate.main(args, repo=repo) == (0 if candidate else 2)
    output = capsys.readouterr()
    if candidate:
        assert "candidate-only" in output.out and "exact set verified: 1 files" in output.out
    else:
        assert "absent from target commit" in output.err and not ruff_calls


def test_fixed_owned_checks_unchanged_target_even_with_empty_diff(commit_repo, capsys):
    repo, _, head = commit_repo
    assert gate.main(["--base", head, "--owned", "server/坏 文件.py"], repo=repo) == 1
    assert "F821" in capsys.readouterr().out


def test_fixed_ignores_docs_and_missing_submodule(commit_repo, ruff_calls, capsys):
    repo, base, head = commit_repo
    git_repo(repo, "update-index", "--add", "--cacheinfo", f"160000,{head},mineflayer")
    git_repo(repo, "commit", "-qm", "submodule")
    make_file(repo, "docs/note.txt", "unrelated local edit\n")
    make_file(repo, "docs/local.txt", "unrelated untracked\n")
    assert gate.main(["--base", base], repo=repo) == 0
    assert "Commit scope verified" in capsys.readouterr().out
    assert len(ruff_calls) == 3


def test_fixed_accepts_git_normalized_crlf(commit_repo, ruff_calls):
    repo, base, head = commit_repo
    git_repo(repo, "config", "core.autocrlf", "true")
    (repo / "server/坏 文件.py").write_bytes(b"print(undefined_name)\r\n")
    assert gate.main(["--base", base, "--head", head], repo=repo) == 0
    assert len(ruff_calls) == 3


def test_empty_scope_never_invokes_ruff_check(monkeypatch, tmp_path, capsys):
    def unexpected_run(*args):
        pytest.fail("An empty list must not become an implicit directory lint")

    monkeypatch.setattr(gate, "run", unexpected_run)
    assert gate.check_files(tmp_path, []) == 0
    assert "empty scope, not a Python lint pass" in capsys.readouterr().out
