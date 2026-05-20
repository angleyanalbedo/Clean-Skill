---
name: windows-safe-cleaner
description: Safely scan and clean Windows AppData, LocalAppData, temp folders, logs, launcher caches, game download caches, developer tool caches such as uv, pip, npm, pnpm, yarn, NuGet, Cargo, and Gradle, and leftover application cache files. Use when Codex is asked to remove Windows junk files, reclaim disk space, clean AppData after uninstalling software, inspect cache bloat such as Ubisoft/Rainbow Six download cache, clean package manager caches, or design a cautious cleanup plan with dry-run reporting before deletion.
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

Focus on **AppData cache directories** - this is where the real disk space is consumed.

**Default rules cover 77+ common cache locations** across these categories:

**Browser Caches:**
- Chrome, Edge, Firefox

**Game Launchers:**
- Steam, Epic, Ubisoft, EA, Battle.net, Minecraft

**Developer Tools:**
- npm, yarn, pnpm, pip, uv, Cargo, Gradle, NuGet
- Rustup, Deno, Swift, Dart pub, Go modules
- VS Code, JetBrains IDEs, Visual Studio, Qt

**Microsoft Apps:**
- OneDrive, Teams, Office, OneNote

**Communication Apps:**
- Discord, Slack, Zoom, DingTalk, Telegram, QQ

**Media Apps:**
- Spotify, OBS, Figma, Notion

**Utilities:**
- Adobe, WPS, 7-Zip, Bandizip, OBS

**System:**
- Windows Error Reports, Shader caches, Thumbnail caches

Do not clean `%PROGRAMDATA%` unless the user asks and understands it may require administrator permissions:

```powershell
python windows-safe-cleaner\scripts\safe_clean_windows.py --include-programdata --report .\cleanup-report.json
```

For a specific suspected cache path, use `--extra-path` only after checking it is not an install directory, save-game directory, configuration directory, or user data directory:

```powershell
python windows-safe-cleaner\scripts\safe_clean_windows.py --extra-path "C:\path\to\cache" --report .\cleanup-report.json
```

**Recommended Workflow for Finding Large Caches:**

1. Discover all cache directories first:
```powershell
python windows-safe-cleaner\scripts\safe_clean_windows.py --discover-caches --report discovered.json
```

2. Find large items in AppData:
```powershell
python windows-safe-cleaner\scripts\safe_clean_windows.py --large-path "$env:LOCALAPPDATA" --min-size-mb 100 --report large-caches.json
```

3. Scan specific large cache directories:
```powershell
python windows-safe-cleaner\scripts\safe_clean_windows.py --extra-path "$env:LOCALAPPDATA\MyApp\cache" --report cleanup.json
```

## Large File Detection & Classification

The cleaner automatically classifies large files based on extension and path:

**Likely Safe to Delete (review-temp):**
- `.log`, `.tmp`, `.temp`, `.bak`, `.old` - temporary and backup files
- `.dmp`, `.dump`, `.etl` - crash dumps and event traces
- `.cache`, `.ds_store`, `.thumbs.db` - system caches
- `.part`, `.partial`, `.crdownload` - incomplete downloads
- `.swp`, `.swo`, `.~` - editor temporary files

**NEVER Delete Automatically (skip):**
- `.pdf`, `.doc`, `.docx`, `.xls`, `.xlsx` - documents
- `.png`, `.jpg`, `.mp3`, `.mp4`, `.avi` - media files
- `.exe`, `.dll`, `.sys`, `.msi` - system files
- `.zip`, `.rar`, `.7z` - archives

**Requires Manual Review:**
- Unknown extensions outside cache directories
- Files in high-risk paths (save games, profiles, configs)

## Large File Cleanup Commands

**Find large items in AppData (SpaceSniffer-like):**
```powershell
python windows-safe-cleaner\scripts\safe_clean_windows.py --large-path "$env:LOCALAPPDATA" --min-size-mb 512 --report .\cleanup-report.json
```

**Find large items in entire user profile:**
```powershell
python windows-safe-cleaner\scripts\safe_clean_windows.py --large-path "$env:USERPROFILE" --min-size-mb 1024 --large-max-seconds 60 --report .\cleanup-report.json
```

**Clean only very old temp files (30+ days):**
```powershell
python windows-safe-cleaner\scripts\safe_clean_windows.py --min-age-days 30 --execute --yes --report .\cleanup-report.json
```

**Dry-run with detailed large file analysis:**
```powershell
python windows-safe-cleaner\scripts\safe_clean_windows.py --discover-caches --large-path "$env:LOCALAPPDATA" --min-size-mb 100 --report .\cleanup-report.json
```

## Safety Defaults

- Dry-run by default.
- Require `--execute` and `--yes` for deletion.
- Keep files newer than 7 days by default. Use `--min-age-days 0` only for obvious temp/cache directories.
- Skip symbolic links and reparse points.
- Skip protected locations, including Windows, Program Files, user profile root, AppData roots, Documents, Desktop, Downloads, Pictures, Videos, Music, OneDrive, game saves, and browser profile data.
- Delete contents of allowlisted cache directories, not arbitrary parent directories.
- Treat large files and directories as review items unless they also match an allowlisted cache rule.
- Treat `partial_size: true` large review entries as incomplete measurements caused by the inspection time budget.
- Treat failed deletion as non-fatal and report it.

## Common Requests

- "C盘满了/什么占用了最多空间": use `--discover-caches` and `--large-path "$env:LOCALAPPDATA"` to find large cache directories, summarize by size.
- "Clean browser/app cache": scan AppData for known cache paths; do not delete configs, cookies, or saved passwords.
- "Remove leftovers after uninstalling software": use `--discover-caches` to find orphaned cache directories; if a directory contains configs, saves, licenses, or databases, do not delete automatically.
- "Clean Rainbow Six / Ubisoft / Steam cache": scan known launcher cache paths; if the user provides a custom path, use `--extra-path` and dry-run first.
- "Clean uv/pip/npm/cargo caches": use the default scan; developer cache rules are allowlisted and still age-gated.
- "Just clean everything": still run dry-run first; use `--discover-caches` to find all cache-like directories.

## Reporting Expectations

Report:

- total reclaimable size
- top largest directories
- rule/category counts
- skipped unsafe paths
- paths requiring manual review
- large review items and why they are or are not safe candidates
- exact command needed for approved deletion

Avoid claiming space was reclaimed until the execute run confirms it.
