from __future__ import annotations

import tempfile
import unittest
from argparse import Namespace
from pathlib import Path

from mc_mod_i18n.web_state import default_cache_root, resolve_cache_root, validate_cache_clear_target, shared_cache_scope_dir


def args(**overrides):
    values = {
        "source_locale": "en_us",
        "target_locale": "zh_cn",
        "provider": "openai-compatible",
        "model": "gpt-4o-mini",
        "api_url": "https://api.openai.com/v1",
        "glossary": None,
        "overwrite_existing": False,
        "skip_translated": False,
        "pack_format": 15,
    }
    values.update(overrides)
    return Namespace(**values)


class TestDefaultCacheRoot(unittest.TestCase):
    def test_default_cache_root_uses_workdir_cache(self):
        with tempfile.TemporaryDirectory() as tmp:
            workdir = Path(tmp)
            result = default_cache_root(workdir)
            self.assertEqual((workdir / "cache").resolve(), result)


class TestResolveCacheRoot(unittest.TestCase):
    def test_resolve_cache_root_with_none_returns_default(self):
        with tempfile.TemporaryDirectory() as tmp:
            workdir = Path(tmp)
            result = resolve_cache_root(workdir, None)
            self.assertEqual(default_cache_root(workdir), result)

    def test_resolve_cache_root_with_relative_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            workdir = Path(tmp)
            result = resolve_cache_root(workdir, "my-cache")
            self.assertEqual((workdir / "my-cache").resolve(), result)

    def test_resolve_cache_root_rejects_file_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            workdir = Path(tmp)
            file_path = workdir / "not-a-dir"
            file_path.write_text("x", encoding="utf-8")
            with self.assertRaises(ValueError):
                resolve_cache_root(workdir, str(file_path))


class TestValidateCacheClearTarget(unittest.TestCase):
    def test_validate_cache_clear_target_rejects_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            workdir = Path(tmp)
            with self.assertRaises(ValueError):
                validate_cache_clear_target(Path("/"), workdir)


class TestSharedCacheScopeDir(unittest.TestCase):
    def test_shared_cache_scope_dir_deterministic(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache_root = Path(tmp)
            a = args()
            dir1 = shared_cache_scope_dir(cache_root, a)
            dir2 = shared_cache_scope_dir(cache_root, a)
            self.assertEqual(dir1, dir2)


if __name__ == "__main__":
    unittest.main()
