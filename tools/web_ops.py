"""
Web 工具 — WebFetch 和 WebSearch。
"""

import asyncio
import json
import re
from typing import Optional
from urllib.parse import urlparse

from tools.base import BaseTool, ToolResult
from config import get_config
from utils.html_utils import extract_main_content, truncate_content


class WebFetchTool(BaseTool):
    """网页抓取工具 — 抓取 URL 并用 LLM 处理"""

    name = "web_fetch"
    description = "抓取 URL 网页内容，可选按 prompt 用 LLM 处理（支持 HTTP/HTTPS）。"
    parameters = {
        "url": {
            "type": "string",
            "description": "URL，http(s)://",
            "required": True,
        },
        "prompt": {
            "type": "string",
            "description": "处理指令，留空返回原文",
        },
        "raw_mode": {
            "type": "boolean",
            "description": "true 返回原始内容",
        },
    }

    async def execute(self, **kwargs) -> ToolResult:
        """执行网页抓取"""
        url = kwargs.get("url", "")
        prompt = kwargs.get("prompt", "")
        raw_mode = kwargs.get("raw_mode", False)

        if not url:
            return ToolResult(success=False, output="", error="URL 不能为空")

        # 验证 URL
        try:
            parsed = urlparse(url)
            if parsed.scheme not in ("http", "https"):
                return ToolResult(success=False, output="", error=f"不支持的协议: {parsed.scheme}")
        except Exception as e:
            return ToolResult(success=False, output="", error=f"无效的 URL: {e}")

        cfg = get_config()
        timeout = cfg.web.fetch_timeout
        user_agent = cfg.web.user_agent

        try:
            content, status_code = await self._fetch_url(url, timeout, user_agent)
        except asyncio.TimeoutError:
            return ToolResult(success=False, output="", error=f"请求超时（{timeout}s）")
        except Exception as e:
            return ToolResult(success=False, output="", error=f"抓取失败: {e}")

        # 提取正文
        main_content = extract_main_content(content)
        truncated = truncate_content(main_content, cfg.web.fetch_max_content_tokens)

        # 原始模式直接返回
        if raw_mode or not prompt:
            return ToolResult(
                success=True,
                output=truncated,
                metadata={
                    "url": url,
                    "status_code": status_code,
                    "content_length": len(main_content),
                },
            )

        # LLM 处理模式
        try:
            from llm.client import LLMClient
            llm = LLMClient()
            system = f"你是一个网页内容分析助手。根据用户的指令处理以下网页内容。\n\n网页内容:\n{truncated}"
            result = await llm.chat_simple(system, prompt)
            return ToolResult(
                success=True,
                output=result,
                metadata={
                    "url": url,
                    "status_code": status_code,
                    "prompt": prompt,
                    "original_length": len(main_content),
                },
            )
        except Exception as e:
            return ToolResult(
                success=True,
                output=truncated,
                error=f"LLM 处理失败: {e}",
                metadata={"url": url, "status_code": status_code},
            )

    async def _fetch_url(self, url: str, timeout: int, user_agent: str) -> tuple[str, int]:
        """抓取 URL 内容"""
        try:
            import httpx
        except ImportError:
            return await self._fetch_with_urllib(url, timeout, user_agent)

        headers = {"User-Agent": user_agent}
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            resp = await client.get(url, headers=headers)
            return resp.text, resp.status_code

    async def _fetch_with_urllib(self, url: str, timeout: int, user_agent: str) -> tuple[str, int]:
        """用 urllib 回退抓取"""
        import urllib.request

        def _sync_fetch():
            req = urllib.request.Request(url, headers={"User-Agent": user_agent})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read().decode("utf-8", errors="ignore"), resp.status

        return await asyncio.get_event_loop().run_in_executor(None, _sync_fetch)


class WebSearchTool(BaseTool):
    """网络搜索工具"""

    name = "web_search"
    description = "在互联网上搜索信息，返回结构化结果（标题、URL、摘要）。"
    parameters = {
        "query": {
            "type": "string",
            "description": "搜索查询",
            "required": True,
        },
        "max_results": {
            "type": "integer",
            "description": "最大结果数，默认 5",
        },
    }

    async def execute(self, **kwargs) -> ToolResult:
        """执行网络搜索"""
        query = kwargs.get("query", "")
        max_results = kwargs.get("max_results", 5)

        if not query:
            return ToolResult(success=False, output="", error="搜索查询不能为空")

        cfg = get_config()
        engine = cfg.web.search_engine

        try:
            if engine == "duckduckgo":
                results = await self._search_duckduckgo(query, max_results)
            elif engine == "google":
                results = await self._search_google(query, max_results, cfg.web)
            elif engine == "bing":
                results = await self._search_bing(query, max_results, cfg.web)
            else:
                return ToolResult(success=False, output="", error=f"不支持的搜索引擎: {engine}")

            if not results:
                return ToolResult(
                    success=True,
                    output=f"未找到与 '{query}' 相关的结果",
                    metadata={"query": query, "engine": engine, "result_count": 0},
                )

            # 格式化输出
            lines = [f"搜索结果（{engine}）：{query}", ""]
            for i, r in enumerate(results, 1):
                lines.append(f"{i}. {r['title']}")
                lines.append(f"   URL: {r['url']}")
                if r.get("snippet"):
                    lines.append(f"   摘要: {r['snippet']}")
                lines.append("")

            return ToolResult(
                success=True,
                output="\n".join(lines),
                metadata={
                    "query": query,
                    "engine": engine,
                    "result_count": len(results),
                    "results": results,
                },
            )
        except Exception as e:
            return ToolResult(success=False, output="", error=f"搜索失败: {e}")

    async def _search_duckduckgo(self, query: str, max_results: int) -> list[dict]:
        """DuckDuckGo 搜索（无需 API key）"""
        try:
            import httpx
        except ImportError:
            return []

        # 使用 DuckDuckGo HTML 版本
        url = "https://html.duckduckgo.com/html/"
        params = {"q": query}

        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            resp = await client.post(url, data=params)
            if resp.status_code != 200:
                return []

            return self._parse_duckduckgo_results(resp.text, max_results)

    def _parse_duckduckgo_results(self, html: str, max_results: int) -> list[dict]:
        """解析 DuckDuckGo 结果页"""
        try:
            from bs4 import BeautifulSoup
        except ImportError:
            return []

        soup = BeautifulSoup(html, "html.parser")
        results = []

        for item in soup.find_all("div", class_="result"):
            if len(results) >= max_results:
                break

            title_tag = item.find("a", class_="result__a")
            snippet_tag = item.find("a", class_="result__snippet")

            if title_tag:
                title = title_tag.get_text(strip=True)
                url = title_tag.get("href", "")
                snippet = snippet_tag.get_text(strip=True) if snippet_tag else ""

                # 清理 URL
                if url.startswith("//"):
                    url = "https:" + url

                results.append({
                    "title": title,
                    "url": url,
                    "snippet": snippet,
                })

        return results

    async def _search_google(self, query: str, max_results: int, web_cfg) -> list[dict]:
        """Google Custom Search API"""
        if not web_cfg.google_api_key or not web_cfg.google_cse_id:
            return await self._search_duckduckgo(query, max_results)

        try:
            import httpx
        except ImportError:
            return []

        url = "https://www.googleapis.com/customsearch/v1"
        params = {
            "key": web_cfg.google_api_key,
            "cx": web_cfg.google_cse_id,
            "q": query,
            "num": max_results,
        }

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(url, params=params)
            if resp.status_code != 200:
                return []

            data = resp.json()
            results = []
            for item in data.get("items", [])[:max_results]:
                results.append({
                    "title": item.get("title", ""),
                    "url": item.get("link", ""),
                    "snippet": item.get("snippet", ""),
                })
            return results

    async def _search_bing(self, query: str, max_results: int, web_cfg) -> list[dict]:
        """Bing Search API"""
        if not web_cfg.bing_api_key:
            return await self._search_duckduckgo(query, max_results)

        try:
            import httpx
        except ImportError:
            return []

        url = "https://api.bing.microsoft.com/v7.0/search"
        headers = {"Ocp-Apim-Subscription-Key": web_cfg.bing_api_key}
        params = {"q": query, "count": max_results}

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(url, headers=headers, params=params)
            if resp.status_code != 200:
                return []

            data = resp.json()
            results = []
            for item in data.get("webPages", {}).get("value", [])[:max_results]:
                results.append({
                    "title": item.get("name", ""),
                    "url": item.get("url", ""),
                    "snippet": item.get("snippet", ""),
                })
            return results
