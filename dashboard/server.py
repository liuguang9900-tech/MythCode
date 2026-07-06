"""Dashboard 服务器启动器 — 封装 uvicorn 启动逻辑。"""

import os
import sys
import threading
import webbrowser


def run_dashboard(
    port: int = 8080,
    host: str = "127.0.0.1",
    open_browser: bool = True,
    token: str | None = None,
) -> None:
    """
    启动 Dashboard Web 服务器。

    Args:
        port: 监听端口
        host: 监听地址（默认 127.0.0.1，仅本地访问）
        open_browser: 是否自动打开浏览器
        token: 可选访问令牌
    """
    # 确保配置已加载
    from config import init_config

    init_config()

    # 设置可选 token
    if token:
        os.environ["MYTHCODER_DASHBOARD_TOKEN"] = token

    # 延迟导入 FastAPI 依赖（仅在使用时才需要）
    try:
        import uvicorn
    except ImportError:
        print("错误：未安装 dashboard 依赖。请运行：")
        print("  pip install 'mythcoder[dashboard]'")
        sys.exit(1)

    from dashboard.app import app

    # 自动打开浏览器（延迟 1.5 秒，等服务器启动）
    if open_browser:
        url = f"http://{host}:{port}"
        if token:
            url += f"?token={token}"
        timer = threading.Timer(1.5, lambda: webbrowser.open(url))
        timer.daemon = True
        timer.start()

    print(f"MythCoder Dashboard 启动中...")
    print(f"  地址: http://{host}:{port}")
    print(f"  文档: http://{host}:{port}/docs")
    print(f"  按 Ctrl+C 退出")

    uvicorn.run(app, host=host, port=port, log_level="info")


def main():
    """命令行入口（MythCoder-dashboard 脚本）"""
    import argparse

    parser = argparse.ArgumentParser(description="MythCoder Dashboard - Token 用量可视化")
    parser.add_argument("-p", "--port", type=int, default=8080, help="端口号")
    parser.add_argument("--host", default="127.0.0.1", help="监听地址")
    parser.add_argument("--no-browser", action="store_true", help="不自动打开浏览器")
    parser.add_argument("--token", default=None, help="访问令牌")
    args = parser.parse_args()

    run_dashboard(
        port=args.port,
        host=args.host,
        open_browser=not args.no_browser,
        token=args.token,
    )


if __name__ == "__main__":
    main()
