"""Tests for lib/paths.py"""

from pathlib import Path
from lib import paths


class TestValidateBucket:
    def test_valid_buckets(self):
        for b in ("pm", "architect", "dev", "qa"):
            assert paths.validate_bucket(b) is None

    def test_invalid_bucket(self):
        assert paths.validate_bucket("invalid") == "INVALID_BUCKET"
        assert paths.validate_bucket("catalog") == "INVALID_BUCKET"
        assert paths.validate_bucket("") == "INVALID_BUCKET"


class TestIsBaseFile:
    def test_base_files(self):
        assert paths.is_base_file("pm", "decisions.md") is True
        assert paths.is_base_file("architect", "tech-stack.md") is True
        assert paths.is_base_file("architect", "decisions.md") is True
        assert paths.is_base_file("dev", "conventions.md") is True
        assert paths.is_base_file("qa", "strategy.md") is True

    def test_non_base_files(self):
        assert paths.is_base_file("pm", "custom.md") is False
        assert paths.is_base_file("architect", "custom.md") is False


class TestPaths:
    def test_memory_root(self):
        root = paths.memory_root(Path("/project"))
        assert root == Path("/project/.memory")

    def test_bucket_path(self):
        bp = paths.bucket_path("pm", Path("/project"))
        assert bp == Path("/project/.memory/pm")

    def test_topics_path(self):
        tp = paths.topics_path(Path("/project"))
        assert tp == Path("/project/.memory/catalog/topics.md")

    def test_module_file_path(self):
        mp = paths.module_file_path("auth", Path("/project"))
        assert mp == Path("/project/.memory/catalog/modules/auth.md")
