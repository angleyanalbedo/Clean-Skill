import os
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from unittest import TestCase, mock

from scripts.safe_clean_windows import (
    CACHE_DIR_NAMES,
    HIGH_RISK_PARTS,
    RULES,
    SAFE_EXTENSIONS,
    LARGE_FILE_EXTENSIONS,
    classify_large_item,
    discover_cache_roots,
    env_path,
    has_high_risk_part,
    has_reparse_point,
    is_protected_exact,
    norm,
    older_than,
    path_size,
    protected_roots,
)


class TestPathUtils(TestCase):
    def test_norm(self):
        path = Path("/home/test/appdata/local")
        result = norm(path)
        self.assertEqual(result, str(path).lower())

    def test_env_path(self):
        with mock.patch.dict(os.environ, {"TEST_ENV_VAR": "/home/test"}):
            result = env_path("TEST_ENV_VAR")
            self.assertEqual(result, Path("/home/test"))
        
        result = env_path("NON_EXISTENT_VAR")
        self.assertIsNone(result)


class TestProtectedRoots(TestCase):
    def test_protected_roots_contains_user_profile(self):
        roots = protected_roots()
        user_profile = env_path("USERPROFILE")
        if user_profile:
            self.assertIn(norm(user_profile), roots)

    def test_protected_roots_contains_common_locations(self):
        roots = protected_roots()
        home = Path.home()
        common_folders = ["Desktop", "Documents", "Downloads", "Pictures", "Videos", "Music", "OneDrive", "Saved Games"]
        for folder in common_folders:
            folder_path = home / folder
            if folder_path.exists():
                self.assertIn(norm(folder_path), roots)

    def test_is_protected_exact(self):
        roots = protected_roots()
        user_profile = env_path("USERPROFILE")
        if user_profile:
            self.assertTrue(is_protected_exact(user_profile, roots))
            self.assertFalse(is_protected_exact(user_profile / "AppData" / "Local" / "Temp", roots))


class TestRiskDetection(TestCase):
    def test_has_high_risk_part(self):
        high_risk_paths = [
            Path("/home/test/documents/config"),
            Path("/home/test/profile/settings"),
            Path("/home/test/appdata/roaming/license"),
            Path("/home/test/appdata/local/profiles"),
        ]
        for path in high_risk_paths:
            self.assertTrue(has_high_risk_part(path), f"Expected {path} to be high risk")

    def test_no_high_risk_part(self):
        safe_paths = [
            Path("/home/test/appdata/local/temp"),
            Path("/home/test/appdata/local/cache"),
            Path("/home/test/appdata/local/logs"),
        ]
        for path in safe_paths:
            self.assertFalse(has_high_risk_part(path), f"Expected {path} to NOT be high risk")


class TestReparsePoint(TestCase):
    def test_has_reparse_point_on_symlink(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            target = Path(tmpdir) / "target.txt"
            target.write_text("test")
            link = Path(tmpdir) / "link.txt"
            
            try:
                link.symlink_to(target)
                self.assertTrue(has_reparse_point(link))
                self.assertFalse(has_reparse_point(target))
            except OSError:
                self.skipTest("Symlinks not supported on this system")


class TestOlderThan(TestCase):
    def test_older_than_recent_file(self):
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b"test")
            temp_path = Path(f.name)
        
        try:
            now = datetime.now(timezone.utc).timestamp()
            self.assertFalse(older_than(temp_path, 7, now))
        finally:
            temp_path.unlink()

    def test_older_than_old_file(self):
        with tempfile.NamedTemporaryFile(delete=False, mode='w') as f:
            f.write("test")
            temp_path = Path(f.name)
            f.flush()
            os.fsync(f.fileno())
        
        old_timestamp = time.time() - (30 * 24 * 60 * 60)
        os.utime(temp_path, (old_timestamp, old_timestamp))
        
        try:
            current_time = time.time()
            mtime = temp_path.stat().st_mtime
            age_days = (current_time - mtime) / 86400
            self.assertTrue(older_than(temp_path, 7, current_time), 
                          f"File age {age_days:.1f} days should be > 7 days")
        finally:
            temp_path.unlink()

    def test_older_than_zero_days(self):
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b"test")
            temp_path = Path(f.name)
        
        try:
            now = datetime.now(timezone.utc).timestamp()
            self.assertTrue(older_than(temp_path, 0, now))
        finally:
            temp_path.unlink()


class TestPathSize(TestCase):
    def test_path_size_empty_file(self):
        with tempfile.NamedTemporaryFile(delete=False) as f:
            temp_path = Path(f.name)
        
        try:
            self.assertEqual(path_size(temp_path), 0)
        finally:
            temp_path.unlink()

    def test_path_size_small_file(self):
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b"hello world")
            temp_path = Path(f.name)
        
        try:
            self.assertEqual(path_size(temp_path), 11)
        finally:
            temp_path.unlink()

    def test_path_size_directory(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            dir_path = Path(tmpdir)
            (dir_path / "file1.txt").write_text("abc")
            (dir_path / "file2.txt").write_text("defgh")
            
            self.assertEqual(path_size(dir_path), 8)


class TestClassifyLargeItem(TestCase):
    def test_classify_cache_like_name(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_path = Path(tmpdir) / "appdata" / "local" / "cache"
            cache_path.mkdir(parents=True)
            action, reason = classify_large_item(cache_path)
            self.assertEqual(action, "review-cache")
            self.assertIn("cache-like name", reason)

    def test_classify_high_risk(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            risk_path = Path(tmpdir) / "appdata" / "local" / "save"
            risk_path.mkdir(parents=True)
            action, reason = classify_large_item(risk_path)
            self.assertEqual(action, "manual-review")
            self.assertIn("high-risk name", reason)

    def test_classify_temp_extension(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_path = Path(tmpdir) / "appdata" / "local" / "temp" / "file.log"
            temp_path.parent.mkdir(parents=True)
            temp_path.write_text("test")
            action, reason = classify_large_item(temp_path)
            self.assertEqual(action, "review-temp")
            self.assertIn("temporary/dump/backup-like", reason)


class TestDiscoverCacheRoots(TestCase):
    def test_discover_cache_roots(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            mock_localappdata = Path(tmpdir) / "LocalAppData"
            mock_localappdata.mkdir()
            
            (mock_localappdata / "cache").mkdir()
            (mock_localappdata / "MyApp" / "cache").mkdir(parents=True)
            (mock_localappdata / "AnotherApp" / "logs").mkdir(parents=True)
            (mock_localappdata / "safe_file.txt").write_text("test")
            
            with mock.patch.dict(os.environ, {"LOCALAPPDATA": str(mock_localappdata), "APPDATA": str(tmpdir)}):
                discovered = discover_cache_roots()
                
                paths_found = {item["path"] for item in discovered}
                self.assertIn(str(mock_localappdata / "cache"), paths_found)
                self.assertIn(str(mock_localappdata / "MyApp" / "cache"), paths_found)
                self.assertIn(str(mock_localappdata / "AnotherApp" / "logs"), paths_found)


class TestRules(TestCase):
    def test_rules_have_required_fields(self):
        for rule in RULES:
            self.assertTrue(hasattr(rule, "name"))
            self.assertTrue(hasattr(rule, "category"))
            self.assertTrue(hasattr(rule, "env"))
            self.assertTrue(hasattr(rule, "parts"))
            self.assertTrue(hasattr(rule, "mode"))
            self.assertTrue(hasattr(rule, "programdata"))

    def test_rules_cover_common_caches(self):
        categories = {rule.category for rule in RULES}
        self.assertIn("cache", categories)
        self.assertIn("crash", categories)
        self.assertIn("shader", categories)
        self.assertIn("developer-cache", categories)
        self.assertIn("browser-cache", categories)
        self.assertIn("game-cache", categories)
        self.assertIn("app-cache", categories)

    def test_rules_cover_developer_tools(self):
        rule_names = {rule.name for rule in RULES}
        developer_tools = ["pip-cache", "uv-cache", "npm-cache", "pnpm-store", "yarn-cache", "nuget-cache", "cargo-registry-cache", "gradle-caches"]
        for tool in developer_tools:
            self.assertIn(tool, rule_names)


class TestCacheDirNames(TestCase):
    def test_cache_dir_names_are_lowercase(self):
        for name in CACHE_DIR_NAMES:
            self.assertEqual(name, name.lower())

    def test_common_cache_names_present(self):
        common_names = {"cache", "caches", ".cache", "logs", "temp", "crashdumps", "webcache"}
        self.assertTrue(CACHE_DIR_NAMES & common_names)


class TestHighRiskParts(TestCase):
    def test_high_risk_parts_are_lowercase(self):
        for part in HIGH_RISK_PARTS:
            self.assertEqual(part, part.lower())

    def test_critical_security_parts_present(self):
        security_parts = {"secret", "token", "wallet", "license", "licence", "activation"}
        self.assertTrue(HIGH_RISK_PARTS & security_parts)

    def test_user_data_parts_present(self):
        user_data = {"desktop", "documents", "downloads", "music", "pictures", "videos", "onedrive"}
        self.assertTrue(HIGH_RISK_PARTS & user_data)


class TestLargeFileExtensions(TestCase):
    def test_large_extensions_contain_common_temp_types(self):
        temp_extensions = {".log", ".tmp", ".bak", ".old", ".dmp", ".cache"}
        self.assertTrue(LARGE_FILE_EXTENSIONS & temp_extensions)

    def test_large_extensions_contain_browser_downloads(self):
        browser_extensions = {".part", ".partial", ".crdownload", ".ytdl"}
        self.assertTrue(LARGE_FILE_EXTENSIONS & browser_extensions)

    def test_large_extensions_are_lowercase(self):
        for ext in LARGE_FILE_EXTENSIONS:
            self.assertEqual(ext, ext.lower(), f"Extension {ext} should be lowercase")


class TestSafeExtensions(TestCase):
    def test_safe_extensions_contain_media_types(self):
        media_extensions = {".png", ".jpg", ".mp3", ".mp4", ".avi"}
        self.assertTrue(SAFE_EXTENSIONS & media_extensions)

    def test_safe_extensions_contain_documents(self):
        doc_extensions = {".pdf", ".doc", ".docx", ".xls", ".xlsx"}
        self.assertTrue(SAFE_EXTENSIONS & doc_extensions)

    def test_safe_extensions_are_lowercase(self):
        for ext in SAFE_EXTENSIONS:
            self.assertEqual(ext, ext.lower(), f"Extension {ext} should be lowercase")


class TestClassifyLargeItemEnhanced(TestCase):
    def test_classify_large_temp_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_file = Path(tmpdir) / "old_data.log"
            temp_file.write_text("test")
            action, reason = classify_large_item(temp_file)
            self.assertEqual(action, "review-temp")
            self.assertIn("temporary/dump/backup-like", reason)

    def test_classify_large_backup_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            backup_file = Path(tmpdir) / "backup.bak"
            backup_file.write_text("test")
            action, reason = classify_large_item(backup_file)
            self.assertEqual(action, "review-temp")

    def test_classify_safe_document_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            pdf_file = Path(tmpdir) / "document.pdf"
            pdf_file.write_text("test")
            action, reason = classify_large_item(pdf_file)
            self.assertEqual(action, "skip")
            self.assertIn("important file type", reason)

    def test_classify_safe_media_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            media_file = Path(tmpdir) / "video.mp4"
            media_file.write_text("test")
            action, reason = classify_large_item(media_file)
            self.assertEqual(action, "skip")


if __name__ == "__main__":
    import unittest
    unittest.main()