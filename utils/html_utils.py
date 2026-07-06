"""
HTML 处理工具函数。
"""

import re
from typing import Optional


def extract_main_content(html: str) -> str:
    """从 HTML 中提取正文内容（去除 nav/footer/script/style）"""
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        # 回退到简单正则
        return _simple_html_extract(html)

    soup = BeautifulSoup(html, "html.parser")

    # 移除不需要的标签
    for tag in soup.find_all(["script", "style", "nav", "footer", "header", "aside", "noscript"]):
        tag.decompose()

    # 优先提取 main 或 article
    main = soup.find("main") or soup.find("article")
    if main:
        return main.get_text(separator="\n", strip=True)

    return soup.get_text(separator="\n", strip=True)


def _simple_html_extract(html: str) -> str:
    """简单的 HTML 文本提取（无 bs4 时回退）"""
    # 移除 script 和 style
    html = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r"<style[^>]*>.*?</style>", "", html, flags=re.DOTALL | re.IGNORECASE)
    # 移除标签
    text = re.sub(r"<[^>]+>", " ", html)
    # 清理空白
    text = re.sub(r"\s+", " ", text).strip()
    return text


def html_to_markdown(html: str) -> str:
    """将 HTML 转换为 Markdown"""
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        return extract_main_content(html)

    soup = BeautifulSoup(html, "html.parser")
    lines = []

    for element in soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6", "p", "li", "pre", "code"]):
        text = element.get_text(strip=True)
        if not text:
            continue

        tag = element.name.lower()
        if tag == "h1":
            lines.append(f"# {text}")
        elif tag == "h2":
            lines.append(f"## {text}")
        elif tag == "h3":
            lines.append(f"### {text}")
        elif tag == "h4":
            lines.append(f"#### {text}")
        elif tag in ("h5", "h6"):
            lines.append(f"##### {text}")
        elif tag == "li":
            lines.append(f"- {text}")
        elif tag == "pre":
            lines.append(f"```\n{text}\n```")
        elif tag == "code":
            lines.append(f"`{text}`")
        else:
            lines.append(text)
        lines.append("")

    return "\n".join(lines).strip() if lines else soup.get_text(strip=True)


def truncate_content(text: str, max_tokens: int = 10000) -> str:
    """按 Token 估算截断内容（保留头尾）"""
    # 简单估算：1 token ≈ 4 字符
    max_chars = max_tokens * 4

    if len(text) <= max_chars:
        return text

    # 保留头部 70% 和尾部 30%
    head_chars = int(max_chars * 0.7)
    tail_chars = max_chars - head_chars

    head = text[:head_chars]
    tail = text[-tail_chars:]
    skipped = len(text) - max_chars

    return f"{head}\n\n... (已截断 {skipped} 字符) ...\n\n{tail}"
