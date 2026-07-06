"""
跨会话费用追踪器 — 记录每次 LLM 调用的 token 用量和费用。
存储路径：~/.mythcoder/costs.json
支持日/月预算检查和告警。
线程安全：使用 fcntl 文件锁防止并发写入冲突。
"""

import json
import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


# 模型价格（每百万 token，美元）
_MODEL_PRICES = {
    "gpt-4o": {"input": 2.50, "output": 10.00},
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "gpt-4-turbo": {"input": 10.00, "output": 30.00},
    "gpt-4.1": {"input": 2.00, "output": 8.00},
    "gpt-4.1-mini": {"input": 0.40, "output": 1.60},
    "claude-3-5-sonnet": {"input": 3.00, "output": 15.00},
    "claude-3-5-sonnet-20241022": {"input": 3.00, "output": 15.00},
    "claude-3-5-haiku": {"input": 0.80, "output": 4.00},
    "claude-3-opus": {"input": 15.00, "output": 75.00},
    "claude-3-haiku": {"input": 0.25, "output": 1.25},
    "deepseek-chat": {"input": 0.14, "output": 0.28},
    "deepseek-reasoner": {"input": 0.55, "output": 2.19},
    "deepseek-v4-pro": {"input": 0.27, "output": 1.10},
    "glm-4": {"input": 0.50, "output": 0.50},
    "glm-4-plus": {"input": 5.00, "output": 5.00},
    "glm-4-flash": {"input": 0.00, "output": 0.00},
}


def get_model_price(model_name: str) -> Optional[dict]:
    """获取模型价格"""
    if model_name in _MODEL_PRICES:
        return _MODEL_PRICES[model_name]
    # 模糊匹配
    lower = model_name.lower()
    for key, price in _MODEL_PRICES.items():
        if key in lower or lower in key:
            return price
    return None


def calculate_cost(model_name: str, prompt_tokens: int, completion_tokens: int) -> Optional[float]:
    """计算单次调用费用（美元）"""
    price = get_model_price(model_name)
    if not price:
        return None
    return (prompt_tokens / 1_000_000) * price["input"] + \
           (completion_tokens / 1_000_000) * price["output"]


class CostTracker:
    """跨会话费用追踪器"""

    def __init__(self, workspace_root: Optional[str] = None, enabled: bool = True):
        self.enabled = enabled
        # 存储在用户目录，跨项目共享
        self.storage_path = Path.home() / ".mythcoder" / "costs.json"
        self._cache: Optional[dict] = None
        self._current_session_id: Optional[str] = None
        self._load()

    def _load(self) -> dict:
        """加载费用数据"""
        if self._cache is not None:
            return self._cache

        if not self.storage_path.exists():
            self._cache = {
                "sessions": {},
                "total": {
                    "prompt_tokens": 0,
                    "completion_tokens": 0,
                    "total_tokens": 0,
                    "cost": 0.0,
                },
            }
            return self._cache

        try:
            with open(self.storage_path, "r", encoding="utf-8") as f:
                self._cache = json.load(f)
                if "sessions" not in self._cache:
                    self._cache["sessions"] = {}
                if "total" not in self._cache:
                    self._cache["total"] = {
                        "prompt_tokens": 0,
                        "completion_tokens": 0,
                        "total_tokens": 0,
                        "cost": 0.0,
                    }
        except (json.JSONDecodeError, IOError):
            self._cache = {
                "sessions": {},
                "total": {
                    "prompt_tokens": 0,
                    "completion_tokens": 0,
                    "total_tokens": 0,
                    "cost": 0.0,
                },
            }
        return self._cache

    def _save(self) -> None:
        """保存费用数据（带文件锁，防止并发写入冲突）"""
        if not self._cache:
            return
        try:
            self.storage_path.parent.mkdir(parents=True, exist_ok=True)
            # 使用临时文件 + 原子替换，避免写入中断导致数据损坏
            tmp_path = self.storage_path.with_suffix(".tmp")
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(self._cache, f, ensure_ascii=False, indent=2)

            # 文件锁确保原子替换
            self._atomic_replace(tmp_path, self.storage_path)
        except IOError as e:
            logger.warning(f"保存费用数据失败: {e}")

    def _atomic_replace(self, src: Path, dst: Path) -> None:
        """原子替换文件（带文件锁）"""
        try:
            # POSIX 系统使用 fcntl 文件锁
            import fcntl
            lock_path = dst.with_suffix(".lock")
            with open(lock_path, "w") as lock_file:
                try:
                    fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
                    src.replace(dst)
                finally:
                    fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
        except ImportError:
            # Windows 无 fcntl，直接替换
            src.replace(dst)

    def start_session(self, session_id: str, model_name: str) -> None:
        """开始新会话"""
        self._current_session_id = session_id
        data = self._load()
        if session_id not in data["sessions"]:
            data["sessions"][session_id] = {
                "model": model_name,
                "start_time": datetime.now(timezone.utc).isoformat(),
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0,
                "cost": 0.0,
                "calls": [],
            }
            self._save()

    def record(
        self,
        model_name: str,
        prompt_tokens: int,
        completion_tokens: int,
        session_id: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> Optional[float]:
        """
        记录一次 LLM 调用。
        返回本次调用费用。
        会向 session["calls"] 追加粒度记录，供前端可视化使用。
        """
        if not self.enabled:
            return None

        cost = calculate_cost(model_name, prompt_tokens, completion_tokens)
        if cost is None:
            cost = 0.0

        data = self._load()
        total_tokens = prompt_tokens + completion_tokens
        now_iso = datetime.now(timezone.utc).isoformat()

        # 更新总计
        data["total"]["prompt_tokens"] += prompt_tokens
        data["total"]["completion_tokens"] += completion_tokens
        data["total"]["total_tokens"] += total_tokens
        data["total"]["cost"] += cost

        # 更新会话 + 追加 call 记录
        sid = session_id or self._current_session_id
        if sid and sid in data["sessions"]:
            session = data["sessions"][sid]
            session["prompt_tokens"] += prompt_tokens
            session["completion_tokens"] += completion_tokens
            session["total_tokens"] += total_tokens
            session["cost"] += cost
            session["last_call_time"] = now_iso

            # 追加每次调用粒度记录（供前端可视化）
            call_record = {
                "call_id": f"{sid}_{len(session['calls'])}",
                "timestamp": now_iso,
                "model": model_name,
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": total_tokens,
                "cost": cost,
            }
            if metadata:
                call_record["metadata"] = metadata
            session["calls"].append(call_record)

            # 防止 calls 数组无限增长（保留最近 1000 条）
            if len(session["calls"]) > 1000:
                session["calls"] = session["calls"][-1000:]

        self._save()
        return cost

    def get_session_costs(self, session_id: Optional[str] = None) -> dict:
        """获取会话费用"""
        data = self._load()
        sid = session_id or self._current_session_id
        if sid and sid in data["sessions"]:
            return data["sessions"][sid]
        return {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
            "cost": 0.0,
        }

    def get_total(self) -> dict:
        """获取跨会话累计费用"""
        data = self._load()
        return data["total"]

    def get_period_costs(self, period: str = "today") -> dict:
        """
        获取指定时段的费用
        period: today/yesterday/week/month/all
        """
        data = self._load()
        now = datetime.now(timezone.utc)

        if period == "all":
            return data["total"]

        totals = {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
            "cost": 0.0,
        }

        for sid, session in data["sessions"].items():
            # 用 last_call_time 或 start_time 判断
            time_str = session.get("last_call_time") or session.get("start_time")
            if not time_str:
                continue
            try:
                session_time = datetime.fromisoformat(time_str.replace("Z", "+00:00"))
            except (ValueError, TypeError):
                continue

            in_period = False
            if period == "today":
                in_period = session_time.date() == now.date()
            elif period == "yesterday":
                from datetime import timedelta
                yesterday = now.date() - timedelta(days=1)
                in_period = session_time.date() == yesterday
            elif period == "week":
                from datetime import timedelta
                week_ago = now - timedelta(days=7)
                in_period = session_time >= week_ago
            elif period == "month":
                in_period = session_time.year == now.year and session_time.month == now.month

            if in_period:
                totals["prompt_tokens"] += session.get("prompt_tokens", 0)
                totals["completion_tokens"] += session.get("completion_tokens", 0)
                totals["total_tokens"] += session.get("total_tokens", 0)
                totals["cost"] += session.get("cost", 0.0)

        return totals

    def check_budget(self, daily_budget: float = 0, monthly_budget: float = 0) -> dict:
        """
        检查预算使用情况。
        返回 {daily_used, daily_budget, daily_pct, monthly_used, monthly_budget, monthly_pct, warnings}
        """
        daily = self.get_period_costs("today")
        monthly = self.get_period_costs("month")

        daily_pct = (daily["cost"] / daily_budget * 100) if daily_budget > 0 else 0
        monthly_pct = (monthly["cost"] / monthly_budget * 100) if monthly_budget > 0 else 0

        warnings = []
        if daily_budget > 0 and daily["cost"] >= daily_budget:
            warnings.append(f"日预算已用尽: ${daily['cost']:.4f} / ${daily_budget:.4f}")
        elif daily_budget > 0 and daily_pct >= 80:
            warnings.append(f"日预算接近上限: {daily_pct:.1f}%")

        if monthly_budget > 0 and monthly["cost"] >= monthly_budget:
            warnings.append(f"月预算已用尽: ${monthly['cost']:.4f} / ${monthly_budget:.4f}")
        elif monthly_budget > 0 and monthly_pct >= 80:
            warnings.append(f"月预算接近上限: {monthly_pct:.1f}%")

        return {
            "daily_used": daily["cost"],
            "daily_budget": daily_budget,
            "daily_pct": daily_pct,
            "monthly_used": monthly["cost"],
            "monthly_budget": monthly_budget,
            "monthly_pct": monthly_pct,
            "warnings": warnings,
        }

    def list_sessions(self, limit: int = 10) -> list[dict]:
        """列出最近的会话"""
        data = self._load()
        sessions = []
        for sid, session in data["sessions"].items():
            sessions.append({
                "session_id": sid,
                "model": session.get("model", "?"),
                "cost": session.get("cost", 0.0),
                "total_tokens": session.get("total_tokens", 0),
                "start_time": session.get("start_time", ""),
                "last_call_time": session.get("last_call_time", ""),
            })
        # 按时间倒序
        sessions.sort(key=lambda x: x.get("last_call_time") or x.get("start_time", ""), reverse=True)
        return sessions[:limit]

    def clear_history(self, older_than_days: int = 30) -> int:
        """清理旧的历史记录，返回清理的会话数"""
        from datetime import timedelta
        data = self._load()
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(days=older_than_days)

        removed = 0
        to_remove = []
        for sid, session in data["sessions"].items():
            time_str = session.get("last_call_time") or session.get("start_time")
            if not time_str:
                continue
            try:
                session_time = datetime.fromisoformat(time_str.replace("Z", "+00:00"))
                if session_time < cutoff:
                    to_remove.append(sid)
            except (ValueError, TypeError):
                continue

        for sid in to_remove:
            del data["sessions"][sid]
            removed += 1

        if removed > 0:
            self._save()

        return removed
