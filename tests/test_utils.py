"""Tests for lib.utils."""

import pytest

from lib.utils import sanitize_module_name


@pytest.mark.parametrize("input_name, expected", [
    ("壳层 (lib/)", "unnamed"),       # CJK + parens content all removed
    ("My Module", "my-module"),
    ("壳层", "unnamed"),
    ("  Core  ", "core"),
    ("lib/cli", "lib-cli"),
    ("front-end", "front-end"),
    ("API (v2) Server", "api-server"),
    ("---test---", "test"),
    ("", "unnamed"),
    ("   ", "unnamed"),
    ("模块A (src/a)", "a"),            # CJK removed, parens content removed
    ("hello世界world", "helloworld"),
    ("lib", "lib"),
    ("tests (unit)", "tests"),
    ("Config Files", "config-files"),
])
def test_sanitize_module_name(input_name, expected):
    assert sanitize_module_name(input_name) == expected
