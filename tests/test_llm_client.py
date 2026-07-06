"""
LLM 客户端测试 — 重试、脱敏、fallback 机制。
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from llm.client import LLMClient, _is_retryable, _sanitize_error


class TestRetryableDetection:
    """测试可重试异常检测"""

    def test_429_retryable(self):
        assert _is_retryable(Exception("Error: 429 Too Many Requests"))

    def test_500_retryable(self):
        assert _is_retryable(Exception("Internal Server Error 500"))

    def test_503_retryable(self):
        assert _is_retryable(Exception("503 Service Unavailable"))

    def test_timeout_retryable(self):
        assert _is_retryable(Exception("Request timeout"))

    def test_connection_reset_retryable(self):
        assert _is_retryable(Exception("Connection reset by peer"))

    def test_non_retryable(self):
        assert not _is_retryable(Exception("Invalid API key"))

    def test_non_retryable_auth(self):
        assert not _is_retryable(Exception("Authentication failed"))


class TestErrorSanitization:
    """测试错误信息脱敏"""

    def test_sanitize_api_key(self):
        err = Exception("Request failed with api_key=sk-abc123def456")
        sanitized = _sanitize_error(err)
        assert "sk-abc123def456" not in sanitized
        assert "***" in sanitized

    def test_sanitize_bearer_token(self):
        err = Exception("Authorization: Bearer sk-abc123def456")
        sanitized = _sanitize_error(err)
        assert "sk-abc123def456" not in sanitized

    def test_sanitize_sk_prefix(self):
        err = Exception("Error: sk-abcdefghijklmnopqrstuvwxyz1234567890")
        sanitized = _sanitize_error(err)
        assert "sk-abcdefghijklmnopqrstuvwxyz1234567890" not in sanitized

    def test_sanitize_token_param(self):
        err = Exception("token=abc123secret456")
        sanitized = _sanitize_error(err)
        assert "abc123secret456" not in sanitized

    def test_preserve_non_sensitive(self):
        err = Exception("Model not found: gpt-4o")
        sanitized = _sanitize_error(err)
        assert "gpt-4o" in sanitized


class TestLLMClient:
    """测试 LLM 客户端"""

    @pytest.fixture
    def mock_config(self):
        config = MagicMock()
        config.provider = "openai"
        config.name = "gpt-4o"
        config.api_key = "sk-test-key"
        config.api_base = "https://api.openai.com/v1"
        config.temperature = 0.2
        config.max_tokens = 8192
        config.timeout = 120
        return config

    @pytest.fixture
    def client(self, mock_config):
        return LLMClient(mock_config)

    def test_build_model_id_with_slash(self, client):
        client.config.name = "openai/gpt-4o"
        assert client._build_model_id() == "openai/gpt-4o"

    def test_build_model_id_without_slash(self, client):
        client.config.name = "gpt-4o"
        client.config.provider = "openai"
        assert client._build_model_id() == "openai/gpt-4o"

    def test_reset_usage(self, client):
        client.prompt_tokens = 100
        client.completion_tokens = 50
        client._request_count = 3
        client._last_recorded_prompt = 80
        client._last_recorded_completion = 40
        client._last_recorded_request_count = 2
        client.reset_usage()
        assert client.prompt_tokens == 0
        assert client.completion_tokens == 0
        assert client._request_count == 0
        assert client._last_recorded_prompt == 0
        assert client._last_recorded_completion == 0
        assert client._last_recorded_request_count == 0

    def test_get_usage(self, client):
        client.prompt_tokens = 100
        client.completion_tokens = 50
        client._request_count = 3
        usage = client.get_usage()
        assert usage["prompt_tokens"] == 100
        assert usage["completion_tokens"] == 50
        assert usage["total_tokens"] == 150
        assert usage["request_count"] == 3

    def test_get_usage_delta(self, client):
        """测试增量计算：首次返回全部，二次无新增返回 0"""
        client.prompt_tokens = 100
        client.completion_tokens = 50
        client._request_count = 2

        delta = client.get_usage_delta()
        assert delta["prompt_tokens"] == 100
        assert delta["completion_tokens"] == 50
        assert delta["total_tokens"] == 150
        assert delta["request_count"] == 2

        # 二次调用，无新增
        delta2 = client.get_usage_delta()
        assert delta2["prompt_tokens"] == 0
        assert delta2["completion_tokens"] == 0
        assert delta2["total_tokens"] == 0
        assert delta2["request_count"] == 0

        # 新增用量后
        client.prompt_tokens = 250
        client.completion_tokens = 120
        client._request_count = 3
        delta3 = client.get_usage_delta()
        assert delta3["prompt_tokens"] == 150
        assert delta3["completion_tokens"] == 70
        assert delta3["total_tokens"] == 220
        assert delta3["request_count"] == 1

    def test_get_usage_does_not_change_snapshot(self, client):
        """get_usage() 不应修改快照（纯读取）"""
        client.prompt_tokens = 100
        client.completion_tokens = 50
        client._request_count = 2
        _ = client.get_usage()
        # 快照应未变
        assert client._last_recorded_prompt == 0
        assert client._last_recorded_completion == 0
        # delta 仍应返回全部
        delta = client.get_usage_delta()
        assert delta["prompt_tokens"] == 100

    @pytest.mark.asyncio
    async def test_chat_simple_success(self, client, mock_config):
        """测试简单对话成功"""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Hello!"
        mock_response.usage = MagicMock()
        mock_response.usage.prompt_tokens = 10
        mock_response.usage.completion_tokens = 5

        with patch("llm.client.acompletion", new_callable=AsyncMock, return_value=mock_response):
            result = await client.chat_simple("system", "user")

        assert result == "Hello!"
        assert client.prompt_tokens == 10
        assert client.completion_tokens == 5
        assert client._request_count == 1

    @pytest.mark.asyncio
    async def test_chat_simple_retry_on_429(self, client):
        """测试 429 错误触发重试"""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Success"
        mock_response.usage = None

        call_count = 0
        async def mock_acompletion(**kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise Exception("429 Too Many Requests")
            return mock_response

        with patch("llm.client.acompletion", side_effect=mock_acompletion):
            client._retry_base_delay = 0.01  # 加速测试
            result = await client.chat_simple("system", "user")

        assert result == "Success"
        assert call_count == 3  # 重试 2 次后成功

    @pytest.mark.asyncio
    async def test_chat_simple_no_retry_on_auth_error(self, client):
        """测试认证错误不触发重试"""
        async def mock_acompletion(**kwargs):
            raise Exception("Authentication failed: invalid api_key")

        with patch("llm.client.acompletion", side_effect=mock_acompletion):
            with pytest.raises(RuntimeError, match="LLM 调用失败"):
                await client.chat_simple("system", "user")

    @pytest.mark.asyncio
    async def test_fallback_model(self, client):
        """测试 fallback 模型切换"""
        # 设置 fallback
        fallback_config = MagicMock()
        fallback_config.provider = "anthropic"
        fallback_config.name = "claude-3-5-sonnet"
        fallback_config.api_key = "sk-fallback-key"
        fallback_config.api_base = None
        client.set_fallback(fallback_config)
        client._retry_base_delay = 0.01

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Fallback success"
        mock_response.usage = None

        call_count = 0
        async def mock_acompletion(**kwargs):
            nonlocal call_count
            call_count += 1
            if "anthropic" in kwargs.get("model", ""):
                return mock_response
            raise Exception("500 Internal Server Error")

        with patch("llm.client.acompletion", side_effect=mock_acompletion):
            result = await client.chat_simple("system", "user")

        assert result == "Fallback success"

    @pytest.mark.asyncio
    async def test_stream_response_error_sanitized(self, client):
        """测试流式响应错误被脱敏"""
        async def mock_acompletion(**kwargs):
            raise Exception("api_key=sk-secret123456789012345")

        with patch("llm.client.acompletion", side_effect=mock_acompletion):
            client._retry_base_delay = 0.01
            results = []
            async for chunk in client._stream_response(model="test", messages=[]):
                results.append(chunk)

        assert len(results) == 1
        assert results[0]["type"] == "error"
        assert "sk-secret123456789012345" not in results[0]["error"]
