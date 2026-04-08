#!/usr/bin/env python3
"""
stoi_tavily.py — Tavily 搜索集成模块

为 STOI ReAct 顾问提供实时网络搜索能力，用于补充知识库和获取最新官方文档。
"""

import os
from typing import Optional

_TAVILY_AVAILABLE = False
try:
    from tavily import TavilyClient
    _TAVILY_AVAILABLE = True
except Exception:
    TavilyClient = None  # type: ignore


def _get_api_key() -> Optional[str]:
    return os.environ.get("TAVILY_API_KEY", "").strip() or None


def search_web(query: str, max_results: int = 5, search_depth: str = "basic") -> str:
    """
    使用 Tavily 搜索引擎查询网络内容。

    Args:
        query: 搜索关键词
        max_results: 返回结果数量 (1-10)
        search_depth: "basic" 或 "advanced"

    Returns:
        Markdown 格式的搜索结果字符串；若未配置 API key 或依赖缺失，返回错误提示。
    """
    if not _TAVILY_AVAILABLE:
        return (
            "[Tavily 未安装] 请先安装依赖：pip install tavily-python\n"
            "然后在环境变量中设置 TAVILY_API_KEY。"
        )

    api_key = _get_api_key()
    if not api_key:
        return (
            "[Tavily 未配置] 缺少 TAVILY_API_KEY 环境变量。\n"
            "请访问 https://tavily.com 获取免费 API key，然后运行：\n"
            "  export TAVILY_API_KEY=your_key\n"
            "或在 .env 文件中配置。"
        )

    try:
        client = TavilyClient(api_key=api_key)
        response = client.search(
            query=query,
            max_results=min(max(1, max_results), 10),
            search_depth=search_depth,
            include_answer=False,
        )
    except Exception as e:
        return f"[Tavily 搜索失败] {e}"

    results = response.get("results", [])
    if not results:
        return "未找到相关结果。"

    lines = [f"## Tavily 搜索结果: `{query}`\n"]
    for i, r in enumerate(results, 1):
        title = r.get("title", "无标题")
        url = r.get("url", "")
        content = (r.get("content") or "").strip()
        lines.append(f"{i}. **{title}**")
        lines.append(f"   - URL: {url}")
        if content:
            # 截断避免过长
            snippet = content[:600] + "..." if len(content) > 600 else content
            lines.append(f"   - 摘要: {snippet}")
        lines.append("")

    return "\n".join(lines)


def search_and_summarize(query: str, max_results: int = 5) -> str:
    """
    对 Tavily 搜索结果做一层简单包装，适合直接丢给 LLM 作为上下文。
    """
    raw = search_web(query, max_results=max_results, search_depth="advanced")
    if raw.startswith("["):
        return raw  # 错误信息原样返回

    header = (
        "以下是从 Tavily 实时搜索获取的最新信息，请结合 STOI 知识库进行判断。\n"
    )
    return header + raw
