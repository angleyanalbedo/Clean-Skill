# Windows Safe Cleaner

A security-focused Windows disk cleanup tool that safely identifies and removes large junk files, temporary data, and cache files while protecting important user data.

## ✨ Features

- **🔒 Safety First**: Dry-run by default, requires explicit `--execute --yes` for deletion
- **📊 Large File Detection**: Intelligent classification of large files based on extension and path
- **🛡️ Protected Locations**: Automatically skips protected paths (Desktop, Documents, Downloads, etc.)
- **🔍 Smart Classification**: Categorizes files as safe-to-delete, manual-review, or skip
- **⚡ Performance**: Time-limited scanning prevents long waits
- **📋 Detailed Reports**: JSON reports with complete analysis results

## 🚀 Quick Start

### 1. Dry Run (Preview What Will Be Deleted)

```powershell
python scripts/safe_clean_windows.py --report cleanup-report.json
```

### 2. Review the Report

Check `cleanup-report.json` for:
- Total reclaimable size
- Items to be deleted by category
- Large items requiring manual review
- Skipped items (unsafe paths)

### 3. Execute Cleanup

```powershell
python scripts/safe_clean_windows.py --execute --yes --report cleanup-report.json
```

## 📖 Usage Examples

**Important:** Focus on `%LOCALAPPDATA%` and `%APPDATA%` for meaningful cleanup. `%TEMP%` is typically small (<100MB) and not worth scanning.

### Discover and Analyze Cache Directories

```powershell
# Step 1: Discover all cache directories in AppData
python scripts/safe_clean_windows.py --discover-caches --report discovered.json

# Step 2: Find large items (>100MB) taking up space
python scripts/safe_clean_windows.py `
  --large-path "$env:LOCALAPPDATA" `
  --min-size-mb 100 `
  --report large-caches.json

# Step 3: Review and clean specific large caches
python scripts/safe_clean_windows.py --extra-path "$env:LOCALAPPDATA\MyApp\cache" --report cleanup.json
```

### Clean Developer Tool Caches

```powershell
# Clean npm, pip, yarn, cargo, gradle caches
python scripts/safe_clean_windows.py --report dev-cache.json

# Execute with confirmation
python scripts/safe_clean_windows.py --execute --yes --report dev-cache.json
```

### Clean Game Launcher Caches

```powershell
# Clean Ubisoft, Steam, Epic launcher caches
python scripts/safe_clean_windows.py --include-programdata --report game-cache.json

# Scan specific game cache
python scripts/safe_clean_windows.py --extra-path "$env:LOCALAPPDATA\Ubisoft Game Launcher\cache" --report ubisoft.json
```

### SpaceSniffer-like Analysis

```powershell
# Find largest directories in AppData
python scripts/safe_clean_windows.py `
  --large-path "$env:LOCALAPPDATA" `
  --min-size-mb 512 `
  --large-max-seconds 60 `
  --report space-analysis.json
```

### Developer Cache Cleanup

```powershell
# Clean npm, pip, yarn, cargo caches
python scripts/safe_clean_windows.py --report dev-cache.json
```

### Discover Hidden Caches

```powershell
# Auto-discover cache directories
python scripts/safe_clean_windows.py --discover-caches --report discovered.json
```

### Include ProgramData (Requires Admin)

```powershell
# Include Ubisoft launcher caches in ProgramData
python scripts/safe_clean_windows.py --include-programdata --report full-scan.json
```

## 📁 File Classification

### 🔴 Likely Safe to Delete

| Extension | Type | Risk Level |
|-----------|------|------------|
| `.log` | Log files | Low |
| `.tmp`, `.temp` | Temporary files | Low |
| `.bak`, `.old` | Backup files | Low |
| `.dmp`, `.dump` | Crash dumps | Low |
| `.cache` | Application cache | Low |
| `.part`, `.partial` | Incomplete downloads | Low |
| `.crdownload` | Chrome downloads | Low |
| `.ds_store` | macOS metadata | Low |
| `.thumbs.db` | Windows thumbnails | Low |

### 🟢 Do NOT Delete

| Extension | Type | Reason |
|-----------|------|--------|
| `.pdf`, `.doc`, `.xls` | Documents | User data |
| `.png`, `.jpg`, `.mp4` | Media | User data |
| `.exe`, `.dll`, `.sys` | System files | Critical |
| `.zip`, `.rar`, `.7z` | Archives | May contain data |

### 🟡 Manual Review Required

- Unknown extensions outside cache directories
- Files in high-risk paths (save games, profiles, configs)
- Large directories with mixed content

## ⚙️ Command Line Options

| Option | Description | Default |
|--------|-------------|---------|
| `--execute` | Run actual deletion (requires `--yes`) | False |
| `--yes` | Confirm deletion | False |
| `--report <file>` | Output JSON report | cleanup-report.json |
| `--min-age-days <n>` | Only delete files older than n days | 7 |
| `--discover-caches` | Auto-discover cache directories | False |
| `--extra-path <path>` | Add custom path to scan | None |
| `--include-programdata` | Include ProgramData rules | False |
| `--large-path <path>` | Scan path for large items | None |
| `--min-size-mb <n>` | Minimum size for large item report | 512 |
| `--top <n>` | Maximum large items to report | 50 |
| `--large-max-seconds <n>` | Time limit for large scan | 30 |

## 🔒 Safety Features

1. **Dry-Run Default**: Always shows what will be deleted before any action
2. **Double Confirmation**: Requires `--execute --yes` to delete
3. **Protected Paths**: Never touches Desktop, Documents, Downloads, etc.
4. **Symbolic Link Protection**: Skips junctions and reparse points
5. **Age Protection**: Keeps recent files by default (7 days)
6. **Non-Fatal Errors**: Continues on errors, reports failures

## 📦 Project Structure

```
windows-safe-cleaner/
├── README.md                  # This file
├── SKILL.md                   # AI agent skill documentation
├── ENHANCEMENTS.md            # Feature enhancements guide
├── references/
│   └── safety-policy.md       # Detailed safety policy
├── scripts/
│   └── safe_clean_windows.py # Main cleanup script
└── tests/
    └── test_cleaner.py       # Test suite (36 tests)
```

## 🧪 Testing

Run the complete test suite:

```bash
python -m pytest tests/test_cleaner.py -v
```

**Test Coverage:**
- Path utilities and normalization
- Protected path detection
- High-risk path identification
- Symbolic link/reparse point handling
- File age calculations
- Path size computation
- Large file classification
- Extension-based categorization
- Cache directory discovery
- Rule validation

## 🎯 Common Use Cases

### "My C: drive is full"

```powershell
# Find largest items
python scripts/safe_clean_windows.py --large-path "$env:LOCALAPPDATA" --min-size-mb 1024 --report scan.json

# Review the JSON report
Get-Content scan.json | ConvertFrom-Json | Select-Object -ExpandProperty large_items
```

### "Clean up after uninstalling software"

```powershell
# Discover leftover caches
python scripts/safe_clean_windows.py --discover-caches --report leftovers.json

# Review before deletion
python scripts/safe_clean_windows.py --discover-caches --execute --yes --report leftovers.json
```

### "Find what is taking up space"

```powershell
# SpaceSniffer-like analysis
python scripts/safe_clean_windows.py --large-path "$env:USERPROFILE" --min-size-mb 512 --report space.json

# Review large items by classification
Get-Content space.json | ConvertFrom-Json | Select-Object -ExpandProperty large_items | Where-Object {$_.classification -eq "review-temp"}
```

## 📊 Report Format

```json
{
  "generated_at": "2026-05-20T10:30:00+00:00",
  "dry_run": true,
  "min_age_days": 7,
  "total_bytes": 5368709120,
  "items": [
    {
      "path": "C:\\Users\\User\\AppData\\Local\\Temp\\old.log",
      "rule": "local-temp",
      "category": "temp",
      "bytes": 1073741824,
      "type": "file"
    }
  ],
  "large_items": [
    {
      "path": "C:\\Users\\User\\AppData\\Local\\MyApp\\cache",
      "bytes": 4294967296,
      "type": "dir",
      "classification": "review-cache",
      "reason": "cache-like name; review before deleting"
    }
  ],
  "skipped": [
    {
      "path": "C:\\Users\\User\\Documents",
      "reason": "protected root"
    }
  ]
}
```

## 🤝 Contributing

When adding new cleanup rules:

1. Follow the allowlist pattern in `scripts/safe_clean_windows.py`
2. Update `references/safety-policy.md` with new paths
3. Add tests in `tests/test_cleaner.py`
4. Update this README with new features

## ⚠️ Disclaimer

This tool is designed to be **conservative** and **safe**. It will:
- Never delete files without explicit confirmation
- Always skip protected locations
- Report what it cannot delete
- Continue on errors instead of stopping

**Always review the dry-run report before executing cleanup.**

## 📄 License

MIT License - See LICENSE file for details

## 🔗 Related

- [CCleaner](https://www.ccleaner.com/) - Industry-standard cleaner
- [BleachBit](https://www.bleachbit.org/) - Open-source alternative
- [WinDirStat](https://windirstat.net/) - Disk space analyzer
- [SpaceSniffer](http://www.uderzo.it/main_products/space_sniffer/) - Visual disk usage
