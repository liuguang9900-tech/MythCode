"""Dashboard API 响应数据模型（Pydantic）。"""

from typing import Optional

from pydantic import BaseModel


class TokenStats(BaseModel):
    """Token 用量统计"""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    cost: float = 0.0


class OverviewResponse(BaseModel):
    """总览 KPI 响应"""
    total: TokenStats
    today: TokenStats
    yesterday: TokenStats
    this_week: TokenStats
    this_month: TokenStats
    session_count: int = 0
    call_count: int = 0
    last_call_time: Optional[str] = None


class CallRecord(BaseModel):
    """单次 LLM 调用记录"""
    call_id: str
    session_id: str
    timestamp: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    cost: float
    metadata: Optional[dict] = None


class CallsResponse(BaseModel):
    """调用列表响应（分页）"""
    calls: list[CallRecord]
    total: int
    limit: int
    offset: int


class DailyStat(BaseModel):
    """按天聚合统计"""
    date: str  # YYYY-MM-DD
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    cost: float = 0.0
    call_count: int = 0


class SessionSummary(BaseModel):
    """会话摘要"""
    session_id: str
    model: str
    cost: float
    total_tokens: int
    prompt_tokens: int
    completion_tokens: int
    start_time: str
    last_call_time: str
    call_count: int = 0


class BudgetResponse(BaseModel):
    """预算使用情况"""
    daily_used: float
    daily_budget: float
    daily_pct: float
    monthly_used: float
    monthly_budget: float
    monthly_pct: float
    warnings: list[str] = []


class ModelStat(BaseModel):
    """按模型聚合统计"""
    model: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    cost: float = 0.0
    call_count: int = 0


class HealthResponse(BaseModel):
    """健康检查"""
    status: str
    timestamp: str
