"""
Dashboard FastAPI 应用 — Token 用量可视化 API。

端点：
  GET /api/overview        — 总览 KPI
  GET /api/calls           — 每次 LLM 调用列表（分页+过滤）
  GET /api/daily           — 按天聚合统计
  GET /api/sessions        — 会话列表
  GET /api/sessions/{id}   — 会话详情
  GET /api/budget          — 预算使用情况
  GET /api/models          — 按模型聚合统计
  GET /api/stream          — SSE 实时推送
  GET /api/health          — 健康检查
  GET /                    — 前端页面
"""

import asyncio
import json
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from agent.cost_tracker import CostTracker
from config import get_config
from dashboard.auth import verify_token

app = FastAPI(
    title="MythCoder Dashboard",
    description="Token 用量可视化 API",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS（本地开发用，生产可收紧）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# 全局 CostTracker 实例（只读访问 costs.json）
_tracker: Optional[CostTracker] = None


def get_tracker() -> CostTracker:
    """获取全局 CostTracker 实例（延迟初始化）"""
    global _tracker
    if _tracker is None:
        cfg = get_config()
        _tracker = CostTracker(enabled=cfg.cost.track_cross_session)
    return _tracker


def _reload_tracker() -> CostTracker:
    """强制重新加载 costs.json（清缓存）"""
    tracker = get_tracker()
    tracker._cache = None
    return tracker


def _parse_iso(ts: str) -> Optional[datetime]:
    """解析 ISO 8601 时间字符串"""
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None


# ============================================================
# API 端点
# ============================================================


@app.get("/api/health")
async def health():
    """健康检查"""
    return {"status": "ok", "timestamp": datetime.now(timezone.utc).isoformat()}


@app.get("/api/overview", dependencies=[Depends(verify_token)])
async def get_overview():
    """总览统计（KPI 卡片数据）"""
    tracker = _reload_tracker()
    total = tracker.get_total()
    today = tracker.get_period_costs("today")
    yesterday = tracker.get_period_costs("yesterday")
    week = tracker.get_period_costs("week")
    month = tracker.get_period_costs("month")

    data = tracker._load()
    sessions = data.get("sessions", {})
    call_count = sum(len(s.get("calls", [])) for s in sessions.values())
    last_call_time = None
    for s in sessions.values():
        t = s.get("last_call_time") or s.get("start_time")
        if t and (last_call_time is None or t > last_call_time):
            last_call_time = t

    return {
        "total": total,
        "today": today,
        "yesterday": yesterday,
        "this_week": week,
        "this_month": month,
        "session_count": len(sessions),
        "call_count": call_count,
        "last_call_time": last_call_time,
    }


@app.get("/api/calls", dependencies=[Depends(verify_token)])
async def get_calls(
    session_id: Optional[str] = None,
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
):
    """获取每次 LLM 调用列表（支持分页和过滤）"""
    tracker = _reload_tracker()
    data = tracker._load()
    sessions = data.get("sessions", {})

    all_calls = []
    for sid, session in sessions.items():
        if session_id and sid != session_id:
            continue
        for call in session.get("calls", []):
            call_copy = dict(call)
            call_copy["session_id"] = sid
            ts = call.get("timestamp", "")
            if start_date and ts < start_date:
                continue
            if end_date and ts > end_date:
                continue
            all_calls.append(call_copy)

    # 按时间倒序
    all_calls.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
    total = len(all_calls)
    page = all_calls[offset : offset + limit]

    return {"calls": page, "total": total, "limit": limit, "offset": offset}


@app.get("/api/daily", dependencies=[Depends(verify_token)])
async def get_daily_stats(days: int = Query(30, ge=1, le=365)):
    """按天聚合统计（填充缺失日期）"""
    tracker = _reload_tracker()
    data = tracker._load()
    sessions = data.get("sessions", {})

    daily_map = defaultdict(
        lambda: {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
            "cost": 0.0,
            "call_count": 0,
        }
    )

    for session in sessions.values():
        for call in session.get("calls", []):
            dt = _parse_iso(call.get("timestamp", ""))
            if dt is None:
                continue
            date_str = dt.strftime("%Y-%m-%d")
            daily_map[date_str]["prompt_tokens"] += call.get("prompt_tokens", 0)
            daily_map[date_str]["completion_tokens"] += call.get("completion_tokens", 0)
            daily_map[date_str]["total_tokens"] += call.get("total_tokens", 0)
            daily_map[date_str]["cost"] += call.get("cost", 0.0)
            daily_map[date_str]["call_count"] += 1

    # 填充缺失的日期（最近 N 天）
    now = datetime.now(timezone.utc)
    result = []
    for i in range(days):
        date = (now - timedelta(days=days - 1 - i)).strftime("%Y-%m-%d")
        stat = daily_map.get(
            date,
            {
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0,
                "cost": 0.0,
                "call_count": 0,
            },
        )
        result.append({"date": date, **stat})

    return result


@app.get("/api/sessions", dependencies=[Depends(verify_token)])
async def get_sessions(limit: int = Query(50, ge=1, le=500)):
    """会话列表"""
    tracker = _reload_tracker()
    sessions = tracker.list_sessions(limit=limit)
    data = tracker._load()
    for s in sessions:
        sid = s["session_id"]
        full = data["sessions"].get(sid, {})
        s["call_count"] = len(full.get("calls", []))
        s["prompt_tokens"] = full.get("prompt_tokens", 0)
        s["completion_tokens"] = full.get("completion_tokens", 0)
    return sessions


@app.get("/api/sessions/{session_id}", dependencies=[Depends(verify_token)])
async def get_session_detail(session_id: str):
    """会话详情（含 calls）"""
    tracker = _reload_tracker()
    data = tracker._load()
    if session_id not in data["sessions"]:
        raise HTTPException(status_code=404, detail="Session not found")
    return data["sessions"][session_id]


@app.get("/api/budget", dependencies=[Depends(verify_token)])
async def get_budget():
    """预算使用情况"""
    tracker = _reload_tracker()
    cfg = get_config()
    return tracker.check_budget(
        daily_budget=cfg.cost.daily_budget,
        monthly_budget=cfg.cost.monthly_budget,
    )


@app.get("/api/models", dependencies=[Depends(verify_token)])
async def get_model_stats():
    """按模型聚合统计"""
    tracker = _reload_tracker()
    data = tracker._load()
    model_map = defaultdict(
        lambda: {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
            "cost": 0.0,
            "call_count": 0,
        }
    )
    for session in data["sessions"].values():
        for call in session.get("calls", []):
            model = call.get("model", "unknown")
            model_map[model]["prompt_tokens"] += call.get("prompt_tokens", 0)
            model_map[model]["completion_tokens"] += call.get("completion_tokens", 0)
            model_map[model]["total_tokens"] += call.get("total_tokens", 0)
            model_map[model]["cost"] += call.get("cost", 0.0)
            model_map[model]["call_count"] += 1
    return [{"model": k, **v} for k, v in model_map.items()]


@app.get("/api/stream", dependencies=[Depends(verify_token)])
async def stream_events():
    """SSE 实时推送：监控 costs.json 文件变化，2 秒轮询"""
    tracker = get_tracker()

    async def event_generator():
        last_mtime = 0
        while True:
            try:
                if tracker.storage_path.exists():
                    current_mtime = tracker.storage_path.stat().st_mtime
                    if current_mtime > last_mtime:
                        last_mtime = current_mtime
                        tracker._cache = None  # 清缓存强制重读
                        overview = await get_overview()
                        yield f"data: {json.dumps(overview, ensure_ascii=False)}\n\n"
            except Exception:
                pass
            await asyncio.sleep(2)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ============================================================
# 静态文件与前端页面
# ============================================================

STATIC_DIR = Path(__file__).parent / "static"
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/", dependencies=[Depends(verify_token)])
async def index():
    """返回前端页面"""
    index_path = STATIC_DIR / "index.html"
    if not index_path.exists():
        raise HTTPException(status_code=404, detail="前端页面未找到")
    return FileResponse(str(index_path))
