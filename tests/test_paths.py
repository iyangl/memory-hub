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


class TestValidateDocsFilename:
    def test_valid_docs_filename(self):
        assert paths.validate_docs_filename("decisions.md") is None
        assert paths.validate_docs_filename("caching.md") is None

    def test_rejects_blank_filename(self):
        assert paths.validate_docs_filename("") == "INVALID_DOCS_FILENAME"
        assert paths.validate_docs_filename("   ") == "INVALID_DOCS_FILENAME"

    def test_rejects_path_traversal_or_separators(self):
        assert paths.validate_docs_filename("../secret.md") == "INVALID_DOCS_FILENAME"
        assert paths.validate_docs_filename("nested/file.md") == "INVALID_DOCS_FILENAME"
        assert paths.validate_docs_filename(r"nested\\file.md") == "INVALID_DOCS_FILENAME"

    def test_rejects_absolute_paths(self):
        assert paths.validate_docs_filename("/tmp/secret.md") == "INVALID_DOCS_FILENAME"
        assert paths.validate_docs_filename("C:/temp/secret.md") == "INVALID_DOCS_FILENAME"
        assert paths.validate_docs_filename(r"C:\\temp\\secret.md") == "INVALID_DOCS_FILENAME"


class TestPaths:
    def test_memory_root(self):
        root = paths.memory_root(Path("/project"))
        assert root == Path("/project/.memory")

    def test_bucket_path(self):
        bp = paths.bucket_path("pm", Path("/project"))
        assert bp == Path("/project/.memory/docs/pm")

    def test_topics_path(self):
        tp = paths.topics_path(Path("/project"))
        assert tp == Path("/project/.memory/catalog/topics.md")

    def test_module_file_path(self):
        mp = paths.module_file_path("auth", Path("/project"))
        assert mp == Path("/project/.memory/catalog/modules/auth.md")

    def test_inbox_path(self):
        inbox = paths.inbox_root(Path("/project"))
        assert inbox == Path("/project/.memory/inbox")

    def test_session_path(self):
        session = paths.session_root(Path("/project"))
        assert session == Path("/project/.memory/session")

    def test_session_file_path(self):
        fp = paths.session_file_path("foo", ".json", Path("/project"))
        assert fp == Path("/project/.memory/session/foo.json")

    def test_save_trace_root(self):
        trace_root = paths.save_trace_root(Path("/project"))
        assert trace_root == Path("/project/.memory/session/save-trace")

    def test_save_trace_file_path(self):
        trace_file = paths.save_trace_file_path("trace.json", Path("/project"))
        assert trace_file == Path("/project/.memory/session/save-trace/trace.json")

    def test_brief_path(self):
        brief = paths.brief_path(Path("/project"))
        assert brief == Path("/project/.memory/BRIEF.md")

    def test_manifest_path(self):
        manifest = paths.manifest_path(Path("/project"))
        assert manifest == Path("/project/.memory/manifest.json")
