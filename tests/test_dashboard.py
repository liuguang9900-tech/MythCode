"""
Dashboard API 测试 — 使用 FastAPI TestClient 测试所有端点。
"""

import json
import pytest
from pathlib import Path

from agent.cost_tracker import CostTracker


@pytest.fixture
def temp_costs_file(tmp_path, monkeypatch):
    """创建临时 costs.json 并 patch CostTracker 的存储路径"""
    storage = tmp_path / "costs.json"

    # patch Path.home() 使 CostTracker 使用临时路径
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    monkeypatch.setattr(Path, "home", lambda: fake_home)
    # CostTracker 使用 Path.home() / ".mythcoder" / "costs.json"
    # 但我们在测试中直接覆盖 storage_path

    # 初始化空数据
    storage.parent.mkdir(parents=True, exist_ok=True)
    storage.write_text(json.dumps({
        "sessions": {},
        "total": {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
            "cost": 0.0,
        },
    }))

    return storage


@pytest.fixture
def client(temp_costs_file):
    """创建 FastAPI TestClient，使用临时 costs.json"""
    # 重置全局 tracker
    import dashboard.app as dash_app
    dash_app._tracker = None

    # 创建 tracker 并覆盖存储路径
    tracker = CostTracker(enabled=True)
    tracker.storage_path = temp_costs_file
    tracker._cache = None
    dash_app._tracker = tracker

    from fastapi.testclient import TestClient
    from dashboard.app import app
    return TestClient(app)


@pytest.fixture
def populated_client(temp_costs_file):
    """创建带有测试数据的 TestClient"""
    import dashboard.app as dash_app
    dash_app._tracker = None

    tracker = CostTracker(enabled=True)
    tracker.storage_path = temp_costs_file
    tracker._cache = None

    # 填充测试数据
    tracker.start_session("test-session-1", "gpt-4o")
    tracker.record("gpt-4o", 1000, 500, session_id="test-session-1")
    tracker.record("gpt-4o", 2000, 800, session_id="test-session-1")
    tracker.start_session("test-session-2", "claude-3-5-sonnet")
    tracker.record("claude-3-5-sonnet", 1500, 600, session_id="test-session-2")

    dash_app._tracker = tracker

    from fastapi.testclient import TestClient
    from dashboard.app import app
    return TestClient(app)


class TestDashboardHealth:
    """健康检查测试"""

    def test_health(self, client):
        res = client.get("/api/health")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "ok"
        assert "timestamp" in data


class TestDashboardOverview:
    """总览 API 测试"""

    def test_overview_empty(self, client):
        """空数据时返回零值"""
        res = client.get("/api/overview")
        assert res.status_code == 200
        data = res.json()
        assert data["total"]["total_tokens"] == 0
        assert data["session_count"] == 0
        assert data["call_count"] == 0

    def test_overview_with_data(self, populated_client):
        """有数据时返回正确统计"""
        res = populated_client.get("/api/overview")
        assert res.status_code == 200
        data = res.json()
        # 1000+500+2000+800+1500+600 = 6400
        assert data["total"]["total_tokens"] == 6400
        assert data["total"]["prompt_tokens"] == 4500
        assert data["total"]["completion_tokens"] == 1900
        assert data["session_count"] == 2
        assert data["call_count"] == 3
        assert data["total"]["cost"] > 0


class TestDashboardCalls:
    """调用列表 API 测试"""

    def test_calls_empty(self, client):
        res = client.get("/api/calls")
        assert res.status_code == 200
        data = res.json()
        assert data["calls"] == []
        assert data["total"] == 0

    def test_calls_with_data(self, populated_client):
        res = populated_client.get("/api/calls")
        assert res.status_code == 200
        data = res.json()
        assert len(data["calls"]) == 3
        assert data["total"] == 3
        # 按时间倒序，最新在前
        assert "call_id" in data["calls"][0]
        assert "session_id" in data["calls"][0]
        assert "model" in data["calls"][0]

    def test_calls_pagination(self, populated_client):
        res = populated_client.get("/api/calls?limit=2&offset=0")
        assert res.status_code == 200
        data = res.json()
        assert len(data["calls"]) == 2
        assert data["total"] == 3
        assert data["limit"] == 2
        assert data["offset"] == 0

    def test_calls_filter_by_session(self, populated_client):
        res = populated_client.get("/api/calls?session_id=test-session-1")
        assert res.status_code == 200
        data = res.json()
        assert len(data["calls"]) == 2
        for call in data["calls"]:
            assert call["session_id"] == "test-session-1"

    def test_calls_limit_max(self, populated_client):
        """limit 不能超过 1000"""
        res = populated_client.get("/api/calls?limit=2000")
        assert res.status_code == 422  # Validation error


class TestDashboardDaily:
    """按天聚合 API 测试"""

    def test_daily_default_days(self, client):
        res = client.get("/api/daily")
        assert res.status_code == 200
        data = res.json()
        assert len(data) == 30  # 默认 30 天

    def test_daily_custom_days(self, client):
        res = client.get("/api/daily?days=7")
        assert res.status_code == 200
        data = res.json()
        assert len(data) == 7

    def test_daily_with_data(self, populated_client):
        res = populated_client.get("/api/daily?days=7")
        assert res.status_code == 200
        data = res.json()
        # 至少有一天有数据
        has_data = any(d["total_tokens"] > 0 for d in data)
        assert has_data
        # 找到有数据的那天
        day_with_data = next(d for d in data if d["total_tokens"] > 0)
        assert day_with_data["call_count"] == 3
        assert day_with_data["total_tokens"] == 6400

    def test_daily_max_days(self, client):
        """days 不能超过 365"""
        res = client.get("/api/daily?days=500")
        assert res.status_code == 422


class TestDashboardSessions:
    """会话列表 API 测试"""

    def test_sessions_empty(self, client):
        res = client.get("/api/sessions")
        assert res.status_code == 200
        assert res.json() == []

    def test_sessions_with_data(self, populated_client):
        res = populated_client.get("/api/sessions")
        assert res.status_code == 200
        data = res.json()
        assert len(data) == 2
        for s in data:
            assert "session_id" in s
            assert "call_count" in s
            assert "model" in s

    def test_session_detail_found(self, populated_client):
        res = populated_client.get("/api/sessions/test-session-1")
        assert res.status_code == 200
        data = res.json()
        assert data["model"] == "gpt-4o"
        assert len(data["calls"]) == 2

    def test_session_detail_not_found(self, populated_client):
        res = populated_client.get("/api/sessions/nonexistent")
        assert res.status_code == 404


class TestDashboardBudget:
    """预算 API 测试"""

    def test_budget_no_config(self, populated_client):
        """未配置预算时返回 0"""
        res = populated_client.get("/api/budget")
        assert res.status_code == 200
        data = res.json()
        assert "daily_used" in data
        assert "monthly_used" in data
        assert "warnings" in data
        assert data["daily_budget"] == 0
        assert data["monthly_budget"] == 0


class TestDashboardModels:
    """模型聚合 API 测试"""

    def test_models_empty(self, client):
        res = client.get("/api/models")
        assert res.status_code == 200
        assert res.json() == []

    def test_models_with_data(self, populated_client):
        res = populated_client.get("/api/models")
        assert res.status_code == 200
        data = res.json()
        assert len(data) == 2  # gpt-4o 和 claude-3-5-sonnet
        models = {d["model"] for d in data}
        assert "gpt-4o" in models
        assert "claude-3-5-sonnet" in models


class TestDashboardIndex:
    """前端页面测试"""

    def test_index_html(self, client):
        res = client.get("/")
        assert res.status_code == 200
        assert "MythCoder Dashboard" in res.text
        assert "echarts" in res.text.lower()
