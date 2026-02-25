"""Tests for lib/envelope.py"""

import json
import pytest
from unittest.mock import patch


def _capture_envelope(func, *args, **kwargs):
    """Call an envelope function and capture its JSON output."""
    with pytest.raises(SystemExit) as exc_info:
        with patch("builtins.print") as mock_print:
            func(*args, **kwargs)
    output = mock_print.call_args[0][0]
    return json.loads(output), exc_info.value.code


class TestOk:
    def test_basic_ok(self):
        from lib.envelope import ok
        result, code = _capture_envelope(ok, {"key": "value"})
        assert code == 0
        assert result["ok"] is True
        assert result["code"] == "SUCCESS"
        assert result["data"] == {"key": "value"}
        assert result["ai_actions"] == []
        assert result["manual_actions"] == []

    def test_ok_with_actions(self):
        from lib.envelope import ok
        result, code = _capture_envelope(
            ok, {"x": 1},
            ai_actions=[{"type": "fix"}],
            manual_actions=[{"type": "review"}],
        )
        assert code == 0
        assert result["ai_actions"] == [{"type": "fix"}]
        assert result["manual_actions"] == [{"type": "review"}]

    def test_ok_defaults(self):
        from lib.envelope import ok
        result, code = _capture_envelope(ok)
        assert result["data"] == {}


class TestFail:
    def test_basic_fail(self):
        from lib.envelope import fail
        result, code = _capture_envelope(fail, "NOT_FOUND", "File missing")
        assert code == 1
        assert result["ok"] is False
        assert result["code"] == "NOT_FOUND"
        assert result["message"] == "File missing"

    def test_fail_with_details(self):
        from lib.envelope import fail
        result, code = _capture_envelope(fail, "ERR", "msg", details={"path": "/x"})
        assert result["details"] == {"path": "/x"}


class TestSystemError:
    def test_system_error(self):
        from lib.envelope import system_error
        result, code = _capture_envelope(system_error, "crash")
        assert code == 2
        assert result["code"] == "SYSTEM_ERROR"
