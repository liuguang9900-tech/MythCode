"""
日志系统测试 — 结构化日志、trace_id、脱敏。
"""

import json
import logging
import pytest
from utils.logger import (
    setup_logger,
    get_logger,
    set_trace_id,
    get_trace_id,
    clear_trace_id,
    JSONFormatter,
    ConsoleFormatter,
    _sanitize_value,
)


class TestTraceId:
    """trace_id 测试"""

    def test_set_and_get_trace_id(self):
        tid = set_trace_id("test-trace-123")
        assert tid == "test-trace-123"
        assert get_trace_id() == "test-trace-123"

    def test_auto_generate_trace_id(self):
        tid = set_trace_id()
        assert len(tid) == 12
        assert get_trace_id() == tid

    def test_clear_trace_id(self):
        set_trace_id("test-123")
        clear_trace_id()
        assert get_trace_id() == ""


class TestSanitization:
    """脱敏测试"""

    def test_sanitize_api_key(self):
        data = {"api_key": "sk-secret123", "name": "test"}
        result = _sanitize_value(data)
        assert result["api_key"] == "***"
        assert result["name"] == "test"

    def test_sanitize_nested(self):
        data = {"config": {"token": "secret", "value": 123}}
        result = _sanitize_value(data)
        assert result["config"]["token"] == "***"
        assert result["config"]["value"] == 123

    def test_sanitize_list(self):
        data = [{"password": "secret"}, {"name": "ok"}]
        result = _sanitize_value(data)
        assert result[0]["password"] == "***"
        assert result[1]["name"] == "ok"

    def test_sanitize_authorization(self):
        data = {"authorization": "Bearer token123"}
        result = _sanitize_value(data)
        assert result["authorization"] == "***"

    def test_non_dict_unchanged(self):
        assert _sanitize_value("string") == "string"
        assert _sanitize_value(123) == 123
        assert _sanitize_value(None) is None


class TestJSONFormatter:
    """JSON 格式器测试"""

    def test_format_basic(self):
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test message",
            args=(),
            exc_info=None,
        )
        output = formatter.format(record)
        data = json.loads(output)
        assert data["level"] == "INFO"
        assert data["message"] == "Test message"
        assert "timestamp" in data

    def test_format_with_trace_id(self):
        set_trace_id("trace-abc")
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test",
            args=(),
            exc_info=None,
        )
        output = formatter.format(record)
        data = json.loads(output)
        assert data["trace_id"] == "trace-abc"
        clear_trace_id()


class TestLoggerSetup:
    """Logger 初始化测试"""

    def test_setup_logger_returns_logger(self):
        logger = setup_logger("test_logger", log_file="/tmp/test_pcitc.log")
        assert isinstance(logger, logging.Logger)
        assert logger.name == "test_logger"

    def test_get_logger_initializes(self):
        logger = get_logger("new_test_logger")
        assert isinstance(logger, logging.Logger)
        assert len(logger.handlers) > 0

    def test_no_duplicate_handlers(self):
        logger1 = setup_logger("dup_test")
        handler_count = len(logger1.handlers)
        logger2 = setup_logger("dup_test")
        assert len(logger2.handlers) == handler_count
