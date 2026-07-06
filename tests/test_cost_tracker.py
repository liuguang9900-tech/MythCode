"""
费用追踪器测试 — 记录、预算检查、文件锁。
"""

import json
import pytest
from pathlib import Path
from agent.cost_tracker import CostTracker


class TestCostTracker:
    """费用追踪器测试"""

    @pytest.fixture
    def tracker(self, tmp_path, monkeypatch):
        """创建临时费用追踪器"""
        storage = tmp_path / "costs.json"
        tracker = CostTracker(enabled=True)
        # 覆盖存储路径到临时目录
        tracker.storage_path = storage
        tracker._cache = None  # 重置缓存
        return tracker

    def test_start_session(self, tracker):
        """测试开始会话"""
        tracker.start_session("test-session", "gpt-4o")
        data = tracker._load()
        assert "test-session" in data["sessions"]
        assert data["sessions"]["test-session"]["model"] == "gpt-4o"

    def test_record_usage(self, tracker):
        """测试记录用量"""
        tracker.start_session("test-session", "gpt-4o")
        tracker.record("gpt-4o", prompt_tokens=100, completion_tokens=50, session_id="test-session")

        data = tracker._load()
        session = data["sessions"]["test-session"]
        assert session["prompt_tokens"] == 100
        assert session["completion_tokens"] == 50
        assert session["total_tokens"] == 150

    def test_total_accumulation(self, tracker):
        """测试累计统计"""
        tracker.start_session("session1", "gpt-4o")
        tracker.record("gpt-4o", prompt_tokens=100, completion_tokens=50, session_id="session1")
        tracker.start_session("session2", "gpt-4o")
        tracker.record("gpt-4o", prompt_tokens=200, completion_tokens=100, session_id="session2")

        total = tracker.get_period_costs("all")
        assert total["prompt_tokens"] == 300
        assert total["completion_tokens"] == 150
        assert total["total_tokens"] == 450

    def test_cost_calculation(self, tracker):
        """测试费用计算"""
        tracker.start_session("test-session", "gpt-4o")
        # gpt-4o: input=$2.50/M, output=$10.00/M
        tracker.record("gpt-4o", prompt_tokens=1000000, completion_tokens=500000, session_id="test-session")

        total = tracker.get_period_costs("all")
        # input: 1M * $2.50 = $2.50
        # output: 0.5M * $10.00 = $5.00
        # total: $7.50
        assert total["cost"] > 0

    def test_budget_check_no_alert(self, tracker):
        """测试预算未超限"""
        tracker.start_session("test-session", "gpt-4o")
        tracker.record("gpt-4o", prompt_tokens=100, completion_tokens=50, session_id="test-session")

        result = tracker.check_budget(daily_budget=100.0)
        assert len(result["warnings"]) == 0

    def test_budget_check_exceeded(self, tracker):
        """测试预算超限"""
        tracker.start_session("test-session", "gpt-4o")
        tracker.record("gpt-4o", prompt_tokens=1000000, completion_tokens=500000, session_id="test-session")

        result = tracker.check_budget(daily_budget=1.0)
        assert len(result["warnings"]) > 0

    def test_unknown_model_no_cost(self, tracker):
        """测试未知模型无费用计算"""
        tracker.start_session("test-session", "unknown-model")
        tracker.record("unknown-model", prompt_tokens=100, completion_tokens=50, session_id="test-session")

        total = tracker.get_period_costs("all")
        # 未知模型不计费，但 token 仍累计
        assert total["prompt_tokens"] == 100
        assert total["cost"] == 0.0

    def test_persistence(self, tracker, tmp_path):
        """测试数据持久化"""
        tracker.start_session("test-session", "gpt-4o")
        tracker.record("gpt-4o", prompt_tokens=100, completion_tokens=50, session_id="test-session")

        # 重新加载
        storage_path = tracker.storage_path
        new_tracker = CostTracker(enabled=True)
        new_tracker.storage_path = storage_path
        new_tracker._cache = None
        total = new_tracker.get_period_costs("all")

        assert total["prompt_tokens"] == 100
        assert total["completion_tokens"] == 50

    def test_atomic_save(self, tracker, tmp_path):
        """测试原子保存（无 .tmp 残留）"""
        tracker.start_session("test-session", "gpt-4o")
        tracker.record("gpt-4o", prompt_tokens=100, completion_tokens=50, session_id="test-session")

        # 不应有 .tmp 文件残留
        tmp_files = list(tmp_path.glob("*.tmp"))
        assert len(tmp_files) == 0


class TestCostTrackerCalls:
    """calls[] 粒度记录测试（供前端可视化）"""

    @pytest.fixture
    def tracker(self, tmp_path):
        """创建临时费用追踪器"""
        tracker = CostTracker(enabled=True)
        tracker.storage_path = tmp_path / "costs.json"
        tracker._cache = None
        return tracker

    def test_record_appends_call(self, tracker):
        """record() 应追加 call 记录到 calls[]"""
        tracker.start_session("s1", "gpt-4o")
        tracker.record("gpt-4o", 100, 50, session_id="s1")
        tracker.record("gpt-4o", 200, 100, session_id="s1")

        data = tracker._load()
        calls = data["sessions"]["s1"]["calls"]
        assert len(calls) == 2
        assert calls[0]["prompt_tokens"] == 100
        assert calls[0]["completion_tokens"] == 50
        assert calls[0]["total_tokens"] == 150
        assert calls[0]["cost"] > 0
        assert "timestamp" in calls[0]
        assert "call_id" in calls[0]
        assert calls[0]["model"] == "gpt-4o"
        assert calls[1]["prompt_tokens"] == 200

    def test_call_id_unique(self, tracker):
        """call_id 应唯一"""
        tracker.start_session("s1", "gpt-4o")
        for _ in range(5):
            tracker.record("gpt-4o", 100, 50, session_id="s1")
        data = tracker._load()
        call_ids = [c["call_id"] for c in data["sessions"]["s1"]["calls"]]
        assert len(set(call_ids)) == 5

    def test_calls_truncated_at_1000(self, tracker):
        """calls[] 超过 1000 条应截断"""
        tracker.start_session("s1", "gpt-4o")
        for _ in range(1005):
            tracker.record("gpt-4o", 1, 1, session_id="s1")
        data = tracker._load()
        assert len(data["sessions"]["s1"]["calls"]) == 1000

    def test_metadata_stored(self, tracker):
        """metadata 应被存储"""
        tracker.start_session("s1", "gpt-4o")
        tracker.record("gpt-4o", 100, 50, session_id="s1",
                       metadata={"user_input": "hello"})
        data = tracker._load()
        assert data["sessions"]["s1"]["calls"][0]["metadata"]["user_input"] == "hello"

    def test_calls_empty_without_session(self, tracker):
        """无有效 session_id 时不应崩溃"""
        # 不 start_session，直接 record
        result = tracker.record("gpt-4o", 100, 50, session_id="nonexistent")
        # 不应崩溃，total 仍应更新
        data = tracker._load()
        assert data["total"]["prompt_tokens"] == 100
