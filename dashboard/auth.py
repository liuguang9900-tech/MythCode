"""可选 Bearer token 认证中间件。"""

import os
from typing import Optional

from fastapi import Header, HTTPException


def get_dashboard_token() -> Optional[str]:
    """从环境变量获取 dashboard 访问令牌"""
    return os.environ.get("MYTHCODER_DASHBOARD_TOKEN")


async def verify_token(authorization: Optional[str] = Header(None)):
    """
    依赖项：验证 Bearer token。
    若未配置 MYTHCODER_DASHBOARD_TOKEN 环境变量，则跳过认证。
    """
    token = get_dashboard_token()
    if token is None:
        return  # 未配置 token，跳过认证
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="未授权：缺少 Bearer token")
    provided = authorization.split(" ", 1)[1]
    if provided != token:
        raise HTTPException(status_code=403, detail="无效的 token")
    return True
