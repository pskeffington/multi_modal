"""Narrow, human-approved Git context and unified-diff operations."""

from __future__ import annotations

import hashlib
import os
import re
import subprocess
from pathlib import Path, PurePosixPath

MAX_CONTEXT_BYTES = 16 * 1024
MAX_FILE_BYTES = 12 * 1024
MAX_CONTEXT_FILES = 24
MAX_PATCH_BYTES = 1024 * 1024


class GitWorkspaceError(ValueError):
    pass


def _git_env() -> dict[str, str]:
    env = {key: value for key, value in os.environ.items() if key in {"PATH", "LANG", "LC_ALL", "LC_CTYPE"}}
    env["GIT_CONFIG_NOSYSTEM"] = "1"
    env["GIT_CONFIG_GLOBAL"] = os.devnull
    env["GIT_OPTIONAL_LOCKS"] = "0"
    return env


def repository_root(selected_path: str | Path) -> Path:
    try:
        selected = Path(selected_path).expanduser().resolve(strict=True)
    except OSError as exc:
        raise GitWorkspaceError(f"Selected directory is unavailable: {exc}") from exc
    if not selected.is_dir():
        raise GitWorkspaceError("Choose a Git checkout directory")
    try:
        result = subprocess.run(
            ["git", "-c", "core.fsmonitor=false", "rev-parse", "--show-toplevel"],
            cwd=selected, env=_git_env(), text=True, capture_output=True, timeout=5, check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise GitWorkspaceError(f"Could not inspect the selected Git checkout: {exc}") from exc
    if result.returncode:
        raise GitWorkspaceError(result.stderr.strip() or "Selected directory is not a Git checkout")
    root = Path(result.stdout.strip()).resolve(strict=True)
    try:
        selected.relative_to(root)
    except ValueError as exc:
        raise GitWorkspaceError("Git reported a worktree root outside the selected directory") from exc
    return root


def _relative_path(raw: str) -> PurePosixPath:
    if (not raw or raw.startswith(("/", "\\")) or "\\" in raw
            or any(ord(char) < 32 or ord(char) == 127 for char in raw)):
        raise GitWorkspaceError("Only ordinary relative POSIX paths are accepted")
    path = PurePosixPath(raw)
    if path.is_absolute() or any(part in {"", ".", ".."} or part.lower() == ".git" for part in path.parts):
        raise GitWorkspaceError(f"Unsafe repository path: {raw}")
    return path


def _reject_symlink_components(root: Path, rel: PurePosixPath) -> Path:
    candidate = root
    for component in rel.parts:
        candidate = candidate / component
        if candidate.is_symlink():
            raise GitWorkspaceError(f"Symlink paths are not accepted: {rel.as_posix()}")
    resolved = candidate.resolve(strict=False)
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise GitWorkspaceError(f"Path escapes the selected checkout: {rel.as_posix()}") from exc
    return candidate


_SENSITIVE_NAMES = {".env", ".env.local", ".npmrc", ".pypirc", "credentials", "secrets", "id_rsa", "id_ed25519"}


def _is_sensitive_path(path: PurePosixPath) -> bool:
    return any(part.lower() in _SENSITIVE_NAMES or part.lower().startswith((".env", ".aws", ".ssh")) for part in path.parts)


def read_context(selected_path: str | Path, requested_paths: str) -> tuple[Path, list[str], str]:
    """Read only the explicit, bounded UTF-8 files selected by the user."""
    root = repository_root(selected_path)
    names = [line.strip() for line in requested_paths.splitlines() if line.strip()]
    if not names:
        raise GitWorkspaceError("Enter one or more repository-relative file paths")
    if len(names) > MAX_CONTEXT_FILES or len(set(names)) != len(names):
        raise GitWorkspaceError(f"Choose at most {MAX_CONTEXT_FILES} distinct files")
    chunks: list[str] = []
    total = 0
    normalized: list[str] = []
    for name in names:
        rel = _relative_path(name)
        if _is_sensitive_path(rel):
            raise GitWorkspaceError(f"Refusing to load a sensitive-looking path: {name}")
        path = _reject_symlink_components(root, rel)
        try:
            if not path.is_file():
                raise GitWorkspaceError(f"Not a regular file: {name}")
            fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
            with os.fdopen(fd, "rb") as source:
                raw = source.read(MAX_FILE_BYTES + 1)
        except OSError as exc:
            raise GitWorkspaceError(f"Cannot read {name}: {exc}") from exc
        if len(raw) > MAX_FILE_BYTES:
            raise GitWorkspaceError(f"{name} exceeds the {MAX_FILE_BYTES}-byte per-file context limit")
        try:
            content = raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise GitWorkspaceError(f"Only UTF-8 text files can be added to context: {name}") from exc
        if "\x00" in content:
            raise GitWorkspaceError(f"Binary content is not accepted: {name}")
        total += len(raw)
        if total > MAX_CONTEXT_BYTES:
            raise GitWorkspaceError(f"Selected context exceeds {MAX_CONTEXT_BYTES} bytes")
        normalized.append(rel.as_posix())
        chunks.append(f"--- BEGIN USER-SELECTED REPOSITORY FILE: {rel.as_posix()} ---\n{content}\n--- END USER-SELECTED REPOSITORY FILE ---")
    return root, normalized, "\n\n".join(chunks)


def extract_unified_diff(output: str) -> str:
    """Extract a single diff/patch fenced block or a raw unified diff."""
    if not output.strip():
        raise GitWorkspaceError("The local model response contains no output")
    for match in re.finditer(r"```(?:diff|patch)?\s*\n(.*?)```", output, flags=re.IGNORECASE | re.DOTALL):
        candidate = match.group(1).strip("\n") + "\n"
        if candidate.startswith(("diff --git ", "--- ")):
            _patch_shape(candidate)
            return candidate
    match = re.search(r"(?m)^(?:diff --git |--- (?:a/|/dev/null))", output)
    if not match:
        raise GitWorkspaceError("No unified diff found. Ask the model to return a fenced diff/patch.")
    candidate = output[match.start():].strip("\n") + "\n"
    _patch_shape(candidate)
    return candidate


def _patch_shape(patch: str) -> None:
    if len(patch.encode("utf-8")) > MAX_PATCH_BYTES:
        raise GitWorkspaceError(f"Patch exceeds {MAX_PATCH_BYTES} bytes")
    if "\x00" in patch:
        raise GitWorkspaceError("Patch contains binary data")
    lines = patch.splitlines()
    if not lines or not lines[0].startswith(("diff --git ", "--- ")):
        raise GitWorkspaceError("Patch must begin with a unified diff header")
    forbidden_headers = ("GIT binary patch", "Binary files ", "new file mode ", "deleted file mode ", "old mode ", "new mode ", "rename from ", "rename to ", "copy from ", "copy to ")
    for line in lines:
        if line.startswith("@@"):
            break
        if line.startswith(forbidden_headers):
            raise GitWorkspaceError("Binary, mode, and rename/copy patches are not accepted")
    if not any(line.startswith("@@") for line in lines):
        raise GitWorkspaceError("Patch has no unified diff hunks")


def _run_git(root: Path, args: list[str], patch: str | None = None) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            ["git", *args], cwd=root, env=_git_env(), input=patch,
            text=True, capture_output=True, timeout=10, check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise GitWorkspaceError(f"Git operation failed: {exc}") from exc


def validate_patch(selected_path: str | Path, patch: str) -> tuple[Path, list[str], str]:
    root = repository_root(selected_path)
    _patch_shape(patch)
    listing = _run_git(root, ["-c", "core.quotePath=false", "apply", "--numstat", "-"], patch)
    if listing.returncode:
        raise GitWorkspaceError(listing.stderr.strip() or "Git could not parse this patch")
    paths: list[str] = []
    for line in listing.stdout.splitlines():
        fields = line.split("\t", 2)
        if len(fields) != 3 or fields[0] == "-" or fields[1] == "-" or "\\" in fields[2] or '"' in fields[2]:
            raise GitWorkspaceError("Binary or unusual filename patch records are not accepted")
        rel = _relative_path(fields[2])
        if _is_sensitive_path(rel):
            raise GitWorkspaceError(f"Patch targets a sensitive-looking path: {rel.as_posix()}")
        target = _reject_symlink_components(root, rel)
        if target.exists() and not target.is_file():
            raise GitWorkspaceError(f"Patch target is not a regular file: {rel.as_posix()}")
        literal_path = f":(literal){rel.as_posix()}"
        tracked = _run_git(root, ["ls-files", "--error-unmatch", "--", literal_path])
        if target.exists() and tracked.returncode:
            raise GitWorkspaceError(f"Patch may not overwrite untracked or ignored files: {rel.as_posix()}")
        if not target.exists() and tracked.returncode == 0:
            raise GitWorkspaceError(f"Tracked patch target is missing: {rel.as_posix()}")
        paths.append(rel.as_posix())
    if not paths:
        raise GitWorkspaceError("Patch contains no file changes")
    if len(paths) > 40 or len(set(paths)) != len(paths):
        raise GitWorkspaceError("Patch has too many files or repeats a file path")
    literal_paths = [f":(literal){path}" for path in paths]
    status = _run_git(root, ["-c", "core.fsmonitor=false", "status", "--porcelain=v1", "--untracked-files=all", "--", *literal_paths])
    if status.returncode:
        raise GitWorkspaceError(status.stderr.strip() or "Could not inspect target file status")
    if status.stdout.strip():
        raise GitWorkspaceError("Patch touches files with existing Git changes; commit or revert those changes before applying")
    check = _run_git(root, ["apply", "--check", "--whitespace=error", "-"], patch)
    if check.returncode:
        raise GitWorkspaceError(check.stderr.strip() or "git apply --check rejected this patch")
    return root, paths, hashlib.sha256(patch.encode("utf-8")).hexdigest()


def apply_patch(selected_path: str | Path, patch: str) -> tuple[Path, list[str], str]:
    root, paths, digest = validate_patch(selected_path, patch)
    result = _run_git(root, ["apply", "--whitespace=error", "-"], patch)
    if result.returncode:
        raise GitWorkspaceError(result.stderr.strip() or "git apply did not apply the patch")
    return root, paths, digest
