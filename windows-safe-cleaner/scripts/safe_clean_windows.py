#!/usr/bin/env python3
"""
Safe Windows cache cleaner.

Dry-run is the default. Deletion requires --execute --yes.
The script intentionally uses conservative allowlists and guardrails.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import stat
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


CACHE_DIR_NAMES = {
    "cache",
    "caches",
    "code cache",
    "gpucache",
    "shadercache",
    "shader cache",
    "webcache",
    "downloadcache",
    "_cacache",
    ".cache",
    "crashdumps",
    "logs",
}

HIGH_RISK_PARTS = {
    "desktop",
    "documents",
    "downloads",
    "music",
    "pictures",
    "videos",
    "onedrive",
    "saved games",
    "save",
    "saves",
    "profile",
    "profiles",
    "config",
    "settings",
    "preferences",
    "license",
    "licence",
    "activation",
    "wallet",
    "secret",
    "token",
}


@dataclass(frozen=True)
class Rule:
    name: str
    category: str
    env: str
    parts: tuple[str, ...]
    mode: str = "contents"
    programdata: bool = False


RULES: tuple[Rule, ...] = (
    Rule("user-temp", "temp", "TEMP", ()),
    Rule("local-temp", "temp", "LOCALAPPDATA", ("Temp",)),
    Rule("windows-error-reports", "crash", "LOCALAPPDATA", ("Microsoft", "Windows", "WER", "ReportArchive")),
    Rule("windows-error-queue", "crash", "LOCALAPPDATA", ("Microsoft", "Windows", "WER", "ReportQueue")),
    Rule("directx-shader-cache", "shader", "LOCALAPPDATA", ("D3DSCache",)),
    Rule("nvidia-gl-cache", "shader", "LOCALAPPDATA", ("NVIDIA", "GLCache")),
    Rule("ubisoft-cache", "launcher-cache", "LOCALAPPDATA", ("Ubisoft Game Launcher", "cache")),
    Rule("ubisoft-webcache", "launcher-cache", "LOCALAPPDATA", ("Ubisoft Game Launcher", "webcache")),
    Rule("ubisoft-programdata-cache", "launcher-cache", "PROGRAMDATA", ("Ubisoft", "Ubisoft Game Launcher", "cache"), programdata=True),
    Rule("pip-cache", "developer-cache", "LOCALAPPDATA", ("pip", "Cache")),
    Rule("uv-cache", "developer-cache", "LOCALAPPDATA", ("uv", "cache")),
    Rule("npm-cache", "developer-cache", "APPDATA", ("npm-cache",)),
    Rule("npm-cache-local", "developer-cache", "LOCALAPPDATA", ("npm-cache",)),
    Rule("pnpm-store", "developer-cache", "LOCALAPPDATA", ("pnpm", "store")),
    Rule("yarn-cache", "developer-cache", "LOCALAPPDATA", ("Yarn", "Cache")),
    Rule("nuget-cache", "developer-cache", "USERPROFILE", (".nuget", "packages")),
    Rule("cargo-registry-cache", "developer-cache", "USERPROFILE", (".cargo", "registry", "cache")),
    Rule("cargo-git-checkouts", "developer-cache", "USERPROFILE", (".cargo", "git", "checkouts")),
    Rule("gradle-caches", "developer-cache", "USERPROFILE", (".gradle", "caches")),
)


def norm(path: Path) -> str:
    return os.path.normcase(str(path.resolve(strict=False)))


def is_relative_to(path: Path, base: Path) -> bool:
    try:
        path.resolve(strict=False).relative_to(base.resolve(strict=False))
        return True
    except ValueError:
        return False


def env_path(name: str) -> Path | None:
    value = os.environ.get(name)
    return Path(value).expanduser() if value else None


def protected_roots() -> set[str]:
    roots: set[Path] = set()
    for env_name in ("USERPROFILE", "APPDATA", "LOCALAPPDATA", "PROGRAMDATA", "WINDIR", "SystemRoot"):
        value = env_path(env_name)
        if value:
            roots.add(value)
    for env_name in ("ProgramFiles", "ProgramFiles(x86)"):
        value = env_path(env_name)
        if value:
            roots.add(value)
    home = Path.home()
    roots.update(
        home / name
        for name in ("Desktop", "Documents", "Downloads", "Pictures", "Videos", "Music", "OneDrive", "Saved Games")
    )
    return {norm(root) for root in roots}


def has_reparse_point(path: Path) -> bool:
    try:
        attrs = path.stat(follow_symlinks=False).st_file_attributes
    except AttributeError:
        return path.is_symlink()
    except OSError:
        return True
    return bool(attrs & stat.FILE_ATTRIBUTE_REPARSE_POINT)


def is_protected_exact(path: Path, protected: set[str]) -> bool:
    return norm(path) in protected


def has_high_risk_part(path: Path) -> bool:
    parts = {part.lower() for part in path.parts}
    return bool(parts & HIGH_RISK_PARTS)


def path_size(path: Path) -> int:
    try:
        if path.is_file():
            return path.stat(follow_symlinks=False).st_size
        total = 0
        for root, dirs, files in os.walk(path):
            root_path = Path(root)
            dirs[:] = [d for d in dirs if not has_reparse_point(root_path / d)]
            for file_name in files:
                file_path = root_path / file_name
                try:
                    if not has_reparse_point(file_path):
                        total += file_path.stat(follow_symlinks=False).st_size
                except OSError:
                    pass
        return total
    except OSError:
        return 0


def path_size_limited(path: Path, deadline: float) -> tuple[int, bool]:
    truncated = False
    try:
        if path.is_file():
            return path.stat(follow_symlinks=False).st_size, False
        total = 0
        for root, dirs, files in os.walk(path):
            if time.monotonic() >= deadline:
                truncated = True
                break
            root_path = Path(root)
            dirs[:] = [d for d in dirs if not has_reparse_point(root_path / d)]
            for file_name in files:
                if time.monotonic() >= deadline:
                    truncated = True
                    break
                file_path = root_path / file_name
                try:
                    if not has_reparse_point(file_path):
                        total += file_path.stat(follow_symlinks=False).st_size
                except OSError:
                    pass
        return total, truncated
    except OSError:
        return 0, False


LARGE_FILE_EXTENSIONS = {
    ".log", ".tmp", ".temp", ".dmp", ".dump", ".etl",
    ".bak", ".old", ".cache", ".tmpy", ".~",
    ".swp", ".swo", ".ds_store", ".thumbs.db",
    ".ico", ".win", ".lst", ".err", ".crdownload",
    ".part", ".partial", ".ytdl",
}

SAFE_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp",
    ".mp3", ".mp4", ".avi", ".mov", ".mkv", ".webm",
    ".zip", ".rar", ".7z", ".tar", ".gz", ".bz2",
    ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
    ".exe", ".dll", ".sys", ".msi",
}


def classify_large_item(path: Path) -> tuple[str, str]:
    if has_reparse_point(path):
        return "skip", "reparse point or symlink"
    if is_protected_exact(path, protected_roots()):
        return "skip", "protected root"
    
    leaf = path.name.lower()
    parent = path.parent.name.lower()
    
    if leaf in CACHE_DIR_NAMES or parent in CACHE_DIR_NAMES:
        return "review-cache", "cache-like name; review before deleting"
    
    if has_high_risk_part(path):
        return "manual-review", "high-risk name; likely user data, config, saves, or credentials"
    
    suffix = path.suffix.lower()
    
    if suffix in LARGE_FILE_EXTENSIONS:
        return "review-temp", "temporary/dump/backup-like file extension; likely safe to delete"
    
    if suffix in SAFE_EXTENSIONS:
        return "skip", "likely important file type; do not delete automatically"
    
    return "manual-review", "large item outside cleanup allowlist"


def inspect_large_items(paths: list[str], min_size_mb: int, top: int, max_seconds: int) -> tuple[list[dict], list[dict]]:
    large_items: list[dict] = []
    skipped: list[dict] = []
    min_bytes = min_size_mb * 1024 * 1024
    deadline = time.monotonic() + max_seconds
    for raw in paths:
        if time.monotonic() >= deadline:
            skipped.append({"path": raw, "reason": "large item inspection time budget exhausted"})
            break
        root = Path(raw).expanduser()
        if not root.exists():
            skipped.append({"path": str(root), "reason": "path does not exist"})
            continue
        if has_reparse_point(root):
            skipped.append({"path": str(root), "reason": "reparse point or symlink"})
            continue
        for child in children(root):
            if has_reparse_point(child):
                skipped.append({"path": str(child), "reason": "child is reparse point or symlink"})
                continue
            size, truncated = path_size_limited(child, deadline)
            if size < min_bytes and not truncated:
                continue
            action, reason = classify_large_item(child)
            large_items.append(
                {
                    "path": str(child),
                    "bytes": size,
                    "partial_size": truncated,
                    "type": "dir" if child.is_dir() else "file",
                    "classification": action,
                    "reason": reason,
                }
            )
    return sorted(large_items, key=lambda x: x["bytes"], reverse=True)[:top], skipped


def older_than(path: Path, min_age_days: int, now: float) -> bool:
    if min_age_days <= 0:
        return True
    try:
        mtime = path.stat(follow_symlinks=False).st_mtime
    except OSError:
        return False
    return (now - mtime) >= min_age_days * 86400


def children(path: Path) -> Iterable[Path]:
    try:
        yield from path.iterdir()
    except OSError:
        return


def discover_cache_roots() -> list[dict]:
    discovered: list[dict] = []
    bases = [p for p in (env_path("LOCALAPPDATA"), env_path("APPDATA")) if p]
    max_depth = 5
    for base in bases:
        if not base.exists():
            continue
        stack: list[tuple[Path, int]] = [(base, 0)]
        while stack:
            current, depth = stack.pop()
            if depth > max_depth or has_reparse_point(current):
                continue
            if depth > 0 and current.name.lower() in CACHE_DIR_NAMES and not has_high_risk_part(current.parent):
                discovered.append(
                    {
                        "path": str(current),
                        "rule": "discovered-cache",
                        "category": "app-cache",
                        "mode": "contents",
                    }
                )
                continue
            try:
                for child in current.iterdir():
                    if child.is_dir():
                        stack.append((child, depth + 1))
            except OSError:
                continue
    seen: set[str] = set()
    unique: list[dict] = []
    for item in discovered:
        key = norm(Path(item["path"]))
        if key not in seen:
            seen.add(key)
            unique.append(item)
    return unique


def candidate_roots(include_programdata: bool, extra_paths: list[str], discover_caches: bool) -> tuple[list[dict], list[dict]]:
    candidates: list[dict] = []
    skipped: list[dict] = []
    for rule in RULES:
        if rule.programdata and not include_programdata:
            continue
        base = env_path(rule.env)
        if not base:
            skipped.append({"rule": rule.name, "reason": f"environment variable {rule.env} is not set"})
            continue
        target = base.joinpath(*rule.parts)
        if target.exists():
            candidates.append({"path": str(target), "rule": rule.name, "category": rule.category, "mode": rule.mode})
    for raw in extra_paths:
        target = Path(raw).expanduser()
        candidates.append({"path": str(target), "rule": "extra-path", "category": "manual-cache", "mode": "contents"})
    if discover_caches:
        candidates.extend(discover_cache_roots())
    return candidates, skipped


def build_plan(
    include_programdata: bool,
    extra_paths: list[str],
    min_age_days: int,
    discover_caches: bool,
    large_paths: list[str],
    min_size_mb: int,
    top: int,
    large_max_seconds: int,
) -> dict:
    protected = protected_roots()
    roots, skipped = candidate_roots(include_programdata, extra_paths, discover_caches)
    large_items, large_skipped = inspect_large_items(large_paths, min_size_mb, top, large_max_seconds)
    skipped.extend(large_skipped)
    now = datetime.now(timezone.utc).timestamp()
    items: list[dict] = []

    allowed_bases = [p for p in (env_path("TEMP"), env_path("LOCALAPPDATA"), env_path("APPDATA"), env_path("USERPROFILE")) if p]
    if include_programdata and env_path("PROGRAMDATA"):
        allowed_bases.append(env_path("PROGRAMDATA"))  # type: ignore[arg-type]

    for root in roots:
        root_path = Path(root["path"]).expanduser()
        if not root_path.exists():
            skipped.append({**root, "reason": "path does not exist"})
            continue
        if is_protected_exact(root_path, protected):
            skipped.append({**root, "reason": "protected root"})
            continue
        if has_reparse_point(root_path):
            skipped.append({**root, "reason": "reparse point or symlink"})
            continue
        if not any(is_relative_to(root_path, base) or norm(root_path) == norm(base) for base in allowed_bases):
            skipped.append({**root, "reason": "outside allowed user data roots"})
            continue
        if root["rule"] == "extra-path":
            leaf = root_path.name.lower()
            if leaf not in CACHE_DIR_NAMES and has_high_risk_part(root_path):
                skipped.append({**root, "reason": "manual path has high-risk name; inspect before deleting"})
                continue
        elif root["category"] != "developer-cache" and has_high_risk_part(root_path):
            skipped.append({**root, "reason": "allowlisted root contains high-risk name"})
            continue

        for child in children(root_path):
            if has_reparse_point(child):
                skipped.append({**root, "path": str(child), "reason": "child is reparse point or symlink"})
                continue
            if is_protected_exact(child, protected):
                skipped.append({**root, "path": str(child), "reason": "child is protected root"})
                continue
            if not older_than(child, min_age_days, now):
                skipped.append({**root, "path": str(child), "reason": f"newer than {min_age_days} days"})
                continue
            size = path_size(child)
            items.append(
                {
                    "path": str(child),
                    "rule": root["rule"],
                    "category": root["category"],
                    "bytes": size,
                    "type": "dir" if child.is_dir() else "file",
                }
            )

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "dry_run": True,
        "min_age_days": min_age_days,
        "include_programdata": include_programdata,
        "discover_caches": discover_caches,
        "large_paths": large_paths,
        "min_size_mb": min_size_mb,
        "large_max_seconds": large_max_seconds,
        "items": sorted(items, key=lambda x: x["bytes"], reverse=True),
        "large_items": large_items,
        "skipped": skipped,
        "total_bytes": sum(item["bytes"] for item in items),
    }


def delete_item(path: Path) -> tuple[bool, str | None]:
    try:
        if has_reparse_point(path):
            return False, "reparse point or symlink"
        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink()
        return True, None
    except Exception as exc:  # noqa: BLE001 - report and continue cleanup.
        return False, str(exc)


def execute_plan(plan: dict) -> dict:
    deleted: list[dict] = []
    failed: list[dict] = []
    for item in plan["items"]:
        path = Path(item["path"])
        ok, error = delete_item(path)
        if ok:
            deleted.append(item)
        else:
            failed.append({**item, "error": error})
    plan = dict(plan)
    plan["dry_run"] = False
    plan["deleted"] = deleted
    plan["failed"] = failed
    plan["deleted_bytes"] = sum(item["bytes"] for item in deleted)
    return plan


def human_size(num: int) -> str:
    size = float(num)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024 or unit == "TB":
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{num} B"


def main() -> int:
    parser = argparse.ArgumentParser(description="Safely scan and clean Windows cache folders.")
    parser.add_argument("--execute", action="store_true", help="Delete planned items. Dry-run is default.")
    parser.add_argument("--yes", action="store_true", help="Required with --execute.")
    parser.add_argument("--include-programdata", action="store_true", help="Include allowlisted ProgramData cache rules.")
    parser.add_argument("--discover-caches", action="store_true", help="Discover cache-like directories below user AppData roots.")
    parser.add_argument("--extra-path", action="append", default=[], help="Additional cache directory to scan by contents.")
    parser.add_argument("--large-path", action="append", default=[], help="Inspect direct children of this path for large files/directories without deleting them.")
    parser.add_argument("--min-size-mb", type=int, default=512, help="Minimum size for --large-path report entries.")
    parser.add_argument("--top", type=int, default=50, help="Maximum large-path entries to include.")
    parser.add_argument("--large-max-seconds", type=int, default=30, help="Time budget for large-path inspection.")
    parser.add_argument("--min-age-days", type=int, default=7, help="Only include items at least this many days old.")
    parser.add_argument("--report", default="cleanup-report.json", help="Write JSON report to this path.")
    args = parser.parse_args()

    if os.name != "nt":
        raise SystemExit("This cleaner is intended for Windows only.")
    if args.min_age_days < 0:
        raise SystemExit("--min-age-days cannot be negative.")
    if args.min_size_mb < 0:
        raise SystemExit("--min-size-mb cannot be negative.")
    if args.top < 1:
        raise SystemExit("--top must be at least 1.")
    if args.large_max_seconds < 1:
        raise SystemExit("--large-max-seconds must be at least 1.")
    if args.execute and not args.yes:
        raise SystemExit("--execute requires --yes.")

    plan = build_plan(
        args.include_programdata,
        args.extra_path,
        args.min_age_days,
        args.discover_caches,
        args.large_path,
        args.min_size_mb,
        args.top,
        args.large_max_seconds,
    )
    result = execute_plan(plan) if args.execute else plan

    report_path = Path(args.report)
    report_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")

    action = "Deleted" if args.execute else "Would delete"
    bytes_key = "deleted_bytes" if args.execute else "total_bytes"
    print(f"{action}: {human_size(result.get(bytes_key, 0))}")
    print(f"Items: {len(result.get('deleted', result['items'])) if args.execute else len(result['items'])}")
    print(f"Large review items: {len(result.get('large_items', []))}")
    print(f"Skipped: {len(result['skipped'])}")
    if args.execute:
        print(f"Failed: {len(result['failed'])}")
    print(f"Report: {report_path.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
