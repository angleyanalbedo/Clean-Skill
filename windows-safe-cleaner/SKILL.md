---
name: windows-safe-cleaner
description: Safely scan and clean Windows AppData, LocalAppData, temp folders, logs, launcher caches, game download caches, and leftover application cache files. Use when Codex is asked to remove Windows junk files, reclaim disk space, clean AppData after uninstalling software, inspect cache bloat such as Ubisoft/Rainbow Six download cache, or design a cautious cleanup plan with dry-run reporting before deletion.
---

# Windows Safe Cleaner

## Core Rule

Never delete first. Always produce a dry-run report, explain what would be removed, and require explicit user confirmation before running with `--execute`.

Use `scripts/safe_clean_windows.py` for deterministic scanning and deletion. Read `references/safety-policy.md` before changing the script or adding new cleanup rules.

## Workflow

1. Run a dry-run scan:

```powershell
python windows-safe-cleaner\scripts\safe_clean_windows.py --report .\cleanup-report.json
```

2. Summarize the report by category, size, count, skipped paths, and risk level.

3. If the user explicitly approves deletion, run:

```powershell
python windows-safe-cleaner\scripts\safe_clean_windows.py --execute --yes --report .\cleanup-report.json
```

4. After execution, summarize deleted bytes, failed paths, and anything skipped because it was locked, unsafe, too new, or outside the allowlist.

## Cleanup Scope

Default scope is the current Windows user only:

- `%TEMP%`
- `%LOCALAPPDATA%\Temp`
- known app cache folders below `%LOCALAPPDATA%`
- known launcher cache folders, including Ubisoft Connect cache locations when present
- logs, crash dumps, thumbnail caches, GPU/shader/code caches

Do not clean `%PROGRAMDATA%` unless the user asks and understands it may require administrator permissions:

```powershell
python windows-safe-cleaner\scripts\safe_clean_windows.py --include-programdata --report .\cleanup-report.json
```

For a specific suspected cache path, use `--extra-path` only after checking it is not an install directory, save-game directory, configuration directory, or user data directory:

```powershell
python windows-safe-cleaner\scripts\safe_clean_windows.py --extra-path "C:\path\to\cache" --report .\cleanup-report.json
```

For broader AppData discovery, use `--discover-caches` in dry-run first. This searches for cache-like directory names under user AppData roots and still applies protected-path, age, and reparse-point checks:

```powershell
python windows-safe-cleaner\scripts\safe_clean_windows.py --discover-caches --report .\cleanup-report.json
```

## Safety Defaults

- Dry-run by default.
- Require `--execute` and `--yes` for deletion.
- Keep files newer than 7 days by default. Use `--min-age-days 0` only for obvious temp/cache directories.
- Skip symbolic links and reparse points.
- Skip protected locations, including Windows, Program Files, user profile root, AppData roots, Documents, Desktop, Downloads, Pictures, Videos, Music, OneDrive, game saves, and browser profile data.
- Delete contents of allowlisted cache directories, not arbitrary parent directories.
- Treat failed deletion as non-fatal and report it.

## Common Requests

- "Clean AppData junk": dry-run default user scope, then ask before execute.
- "Remove leftovers after uninstalling software": scan first; if a leftover vendor directory contains configs, saves, licenses, or databases, do not delete automatically.
- "Clean Rainbow Six / Ubisoft download cache": scan known Ubisoft cache paths; if the user gives a custom launcher/download cache path, add it with `--extra-path` and dry-run first.
- "Just delete it": still run dry-run first unless the user provides a recent report and explicit approval.

## Reporting Expectations

Report:

- total reclaimable size
- top largest directories
- rule/category counts
- skipped unsafe paths
- paths requiring manual review
- exact command needed for approved deletion

Avoid claiming space was reclaimed until the execute run confirms it.
