# Windows Safe Cleaner Safety Policy

## Non-Negotiable Rules

- Default to dry-run. Deletion requires `--execute --yes`.
- Only delete files or child directories selected by allowlisted rules.
- Never delete an entire user profile, AppData root, LocalAppData root, Roaming root, ProgramData root, drive root, Windows directory, Program Files directory, or known personal library.
- Never follow symlinks, junctions, or reparse points.
- Never delete browser cookies, login databases, extension stores, history databases, wallet files, license files, save-game folders, config folders, or documents.
- Prefer deleting cache contents over deleting the parent cache directory.
- Keep recent files by default using `--min-age-days 7`.
- Developer package caches are allowed only for tool-owned cache/store directories, never project directories.
- Large size alone is never a deletion signal. Use size to prioritize manual review, then require a cache allowlist or explicit user decision.

## High-Risk Names

Treat paths containing these names as manual review unless a narrower allowlist rule targets a child cache folder:

- `save`, `saves`, `saved games`, `profile`, `profiles`
- `config`, `settings`, `preferences`
- `license`, `licence`, `activation`
- `wallet`, `key`, `secret`, `token`
- `database`, `db`, `sqlite`
- `documents`, `desktop`, `downloads`, `pictures`, `videos`, `music`

## Safer Cache Names

These names are usually safe only when they are below an application data root or known launcher cache root:

- `cache`, `caches`, `code cache`, `gpucache`, `shadercache`
- `temp`, `tmp`
- `logs`, `crashdumps`
- `downloadcache`, `webcache`
- `npm-cache`, `_cacache`, `.cache`

## Developer Cache Notes

Safe candidates include package-manager cache or store contents owned by the tool:

- `uv`: `%LOCALAPPDATA%\uv\cache`
- `pip`: `%LOCALAPPDATA%\pip\Cache`
- `npm`: `%APPDATA%\npm-cache` or `%LOCALAPPDATA%\npm-cache`
- `pnpm`: `%LOCALAPPDATA%\pnpm\store`
- `yarn`: `%LOCALAPPDATA%\Yarn\Cache`
- `NuGet`: `%USERPROFILE%\.nuget\packages`
- `Cargo`: `%USERPROFILE%\.cargo\registry\cache` and `%USERPROFILE%\.cargo\git\checkouts`
- `Gradle`: `%USERPROFILE%\.gradle\caches`

Do not delete `node_modules`, virtual environments, project `.venv` folders, lockfiles, source worktrees, npm global package bins, package manager config files, or credential files.

## Large Item Review

Use `--large-path` to imitate a SpaceSniffer-style review workflow. The script should list large direct children of the selected path, classify them, and keep them outside the deletion plan unless they also match a specific allowlisted cache rule.

Use `--large-max-seconds` to keep large scans bounded. Entries with `partial_size: true` are incomplete measurements and should be treated as "large enough to investigate", not exact totals.

Suggested interpretation:

- `review-cache`: cache-like name; likely safe only after path review.
- `review-temp`: temporary, log, dump, backup, or old file; likely safe only after path review.
- `manual-review`: unknown large item; ask the user or inspect contents before deleting.
- `skip`: protected, symlink, junction, or otherwise unsafe.

## Ubisoft / Rainbow Six Notes

Ubisoft Connect and Rainbow Six Siege may leave large launcher caches. Safe candidates are cache directories under Ubisoft launcher data, not the installed game directory and not user save/config folders. If a user gives a custom path, run dry-run with `--extra-path` and inspect the report before deleting.

Do not delete directories that look like the live game install, for example folders containing large executable sets, game manifests required by the launcher, or files under a Steam/Epic/Ubisoft library unless the user explicitly says the game is uninstalled and approves the dry-run plan.
