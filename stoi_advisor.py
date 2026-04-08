#!/usr/bin/env python3
"""
stoi_advisor.py — STOI ReAct 建议引擎

架构：LLM + Tool Call（按需查知识库）
不是把所有知识塞进 system prompt，而是让 LLM 根据数据决定查哪个知识文件

Flow:
  1. LLM 收到 STOI 分析数据
  2. LLM 决定需要查哪个知识领域（tool call: search_knowledge）
  3. 知识库返回相关内容
  4. LLM 结合数据 + 知识给出具体建议

知识库文件（stoi_knowledge/）：
  kv_cache.md          KV Cache 优化模式
  context_engineering.md  上下文工程最佳实践
  claude_code_skills.md   Claude Code 专项优化
  prompt_design.md     Prompt 设计规范
  thinking_tokens.md   CoT/Thinking token 效率
"""

import json
from pathlib import Path
from typing import Optional

from stoi_tavily import search_web

KNOWLEDGE_DIR = Path(__file__).parent / "stoi_knowledge"

# ── 知识库工具 ────────────────────────────────────────────────────────────────
AVAILABLE_TOPICS = {
    "kv_cache":           "KV Cache 命中率优化，cache miss 根因分析，时间戳/UUID/路径注入修复",
    "context_engineering":"上下文膨胀检测，压缩策略，Lost in the Middle，session 拆分原则",
    "claude_code_skills": "Claude Code CLAUDE.md 配置，skills 设计，memory 管理，cache 友好的提示结构",
    "prompt_design":      "System Prompt 最佳实践，格式优化（YAML vs JSON），输出长度控制，负向约束",
    "thinking_tokens":    "CoT/thinking token 冗余模式，推理效率优化，budget_tokens 设置",
}

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_knowledge",
            "description": "查询 STOI 知识库，获取特定 Token 效率优化领域的专业知识和最佳实践",
            "parameters": {
                "type": "object",
                "properties": {
                    "topic": {
                        "type": "string",
                        "enum": list(AVAILABLE_TOPICS.keys()),
                        "description": f"要查询的知识领域。可选：{', '.join(AVAILABLE_TOPICS.keys())}",
                    },
                    "reason": {
                        "type": "string",
                        "description": "为什么需要查询这个知识领域（基于 STOI 数据的哪个问题）",
                    }
                },
                "required": ["topic", "reason"],
            },
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_web",
            "description": "使用 Tavily 搜索引擎获取最新官方文档、博客或社区最佳实践，当知识库内容不足或需要 2025 最新信息时使用",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "搜索关键词（建议英文以获得更准确的官方文档结果）",
                    },
                    "reason": {
                        "type": "string",
                        "description": "为什么需要联网搜索（例如：验证某个 beta header 是否存在、查找最新模型阈值）",
                    }
                },
                "required": ["query", "reason"],
            },
        }
    }
]


def search_knowledge(topic: str) -> str:
    """从知识库文件读取内容"""
    kb_file = KNOWLEDGE_DIR / f"{topic}.md"
    if not kb_file.exists():
        return f"[知识库文件 {topic}.md 不存在，请先运行 stoi knowledge --build]"
    return kb_file.read_text(encoding="utf-8")


def _build_analysis_summary(report) -> str:
    """把 STOIReport 转成 LLM 可读的摘要，包含真实对话片段"""
    scored = [t for t in report.turns
              if not t.is_stub and not t.is_baseline and t.role == "assistant"]

    # 趋势
    trend = ""
    if len(scored) >= 4:
        mid = len(scored) // 2
        fa = sum(t.stoi_score for t in scored[:mid]) / mid
        sa = sum(t.stoi_score for t in scored[mid:]) / (len(scored) - mid)
        delta = sa - fa
        trend = f"{'↑上升' if delta > 5 else '↓下降' if delta < -5 else '→稳定'} {delta:+.1f}%（{fa:.1f}% → {sa:.1f}%）"

    # 上下文增长
    inputs = [t.input_tokens + t.cache_read + t.cache_write for t in scored]
    growth = ""
    if len(inputs) >= 2 and inputs[0] > 0:
        pct = (inputs[-1] - inputs[0]) / inputs[0] * 100
        growth = f"{inputs[0]:,} → {inputs[-1]:,} tokens（+{pct:.0f}%）"

    issues = "\n".join(
        f"- [{i['severity']}] {i['title']}: {i['detail']}" for i in report.issues
    ) or "- 未发现明显问题"

    # 找含屎量最高的 3 轮真实对话片段
    worst = sorted(scored, key=lambda t: t.stoi_score, reverse=True)[:3]
    worst_samples = ""
    for t in worst:
        if t.content:
            # 找对应的 user followup
            user_next = ""
            for turn in report.turns:
                if turn.role == "user" and turn.turn_index > t.turn_index and turn.content:
                    user_next = turn.content[:80]
                    break
            worst_samples += f"\n  [轮{t.turn_index} 含屎量{t.stoi_score:.0f}%]\n"
            worst_samples += f"  AI输出: {t.content[:150]}...\n"
            if user_next:
                worst_samples += f"  用户回应: {user_next}\n"
            if t.feedback_signal:
                worst_samples += f"  有效性评估: {t.token_effectiveness} ({t.feedback_signal})\n"

    # 找被否定的轮次样本
    invalid_samples = ""
    invalid_turns = [t for t in scored if t.token_effectiveness == "invalid"][:2]
    for t in invalid_turns:
        if t.content and t.feedback_signal:
            invalid_samples += f"\n  [轮{t.turn_index}被否定]\n"
            invalid_samples += f"  AI: {t.content[:120]}...\n"
            invalid_samples += f"  用户反应: {t.feedback_signal}\n"

    return f"""## STOI 分析数据

**会话**: {report.session_name} | 模型: {report.model}
**轮次**: {report.total_turns} 总 / {report.valid_turns} 有效
**花费**: ${report.total_cost_actual:.4f} 实际，cache 节省 ${report.total_cost_saved:.4f}

**L1 Cache 效率**
- 含屎量均值: {report.avg_stoi_score:.1f}% ({report.stoi_level})
- 缓存命中率: {report.avg_cache_hit_rate:.1f}%
- 趋势: {trend or "稳定"}
- 上下文增长: {growth or "正常"}

**L2 输出有效性**
- 有效率: {report.effectiveness_rate:.1f}% | 被否定: {report.invalid_turns_count} 轮 (${report.waste_cost:.4f})

**检测问题**
{issues}

**含屎量最高的轮次（真实对话）**{worst_samples or "  无明显高含屎量轮次"}

**被用户否定的轮次**{invalid_samples or "  无（或无法判断）"}

---
**用户场景**: Claude Code 用户，AI 辅助编程工具
**不要建议**: 向量数据库、RAG、embedding 等与 Claude Code 无关的方案
**要建议**: /compact、CLAUDE.md 配置、session 拆分、System Prompt 清理

请用 search_knowledge 查询（优先 claude_code_skills），结合上面的真实数据给出 3 条具体建议。

格式（每条 3-4 行）:
**[问题名]** 描述
**操作**: 具体 Claude Code 命令或配置文件改法
**预期收益**: 节省量"""


def get_suggestions(report, verbose: bool = False) -> list[str]:
    """
    ReAct 模式：LLM 按需查知识库，给出专业建议
    支持 qwen / anthropic / openai
    """
    try:
        from stoi_config import load_config, get_api_key
        cfg = load_config()
        llm = cfg.get("llm", {})
        provider = llm.get("provider", "")
        api_key  = llm.get("api_key", "") or get_api_key(provider)
        model    = llm.get("model", "")
        base_url = llm.get("base_url", "")

        if not api_key:
            return ["未配置 API Key，运行 stoi config 配置"]

        summary = _build_analysis_summary(report)

        SYSTEM = """你是 STOI（Shit Token On Investment）Token 效率分析引擎，专门帮助 Claude Code 用户优化 AI 编程工具的 token 消耗。

你的任务：
1. 分析 STOI 数据，判断主要问题在哪里
2. 用 search_knowledge 工具查询知识库（优先查 claude_code_skills）
3. 给出 3 条针对 Claude Code 实际使用场景的具体建议

原则：
- 建议必须是 Claude Code 用户能直接执行的（如"/compact 命令"、"修改 CLAUDE.md"、"拆分 session"）
- 不要给"用向量数据库"、"引入 RAG"这种与 Claude Code 无关的建议
- 如果数据显示某个指标很健康（如含屎量 < 10%），直接说"该指标良好"，不要无谓建议
- 建议要简洁，每条不超过 5 行"""

        messages = [{"role": "user", "content": summary}]

        # ReAct 循环
        max_rounds = 4
        knowledge_used = []

        for round_i in range(max_rounds):
            if provider == "anthropic":
                import anthropic
                client = anthropic.Anthropic(api_key=api_key)
                resp = client.messages.create(
                    model=model or "claude-sonnet-4-5",
                    max_tokens=1500,
                    system=SYSTEM,
                    tools=[{
                        "name": t["function"]["name"],
                        "description": t["function"]["description"],
                        "input_schema": t["function"]["parameters"],
                    } for t in TOOLS],
                    messages=messages,
                )
                # 处理 Anthropic 响应
                tool_calls = [b for b in resp.content if b.type == "tool_use"]
                text_blocks = [b for b in resp.content if b.type == "text"]

                if not tool_calls:
                    # 最终回答
                    text = text_blocks[0].text if text_blocks else ""
                    return [text.strip()] if text.strip() else ["分析完成，当前 session 状态良好"]

                # 执行 tool calls
                messages.append({"role": "assistant", "content": resp.content})
                tool_results = []
                for tc in tool_calls:
                    tc_name = tc.name
                    reason = tc.input.get("reason", "")
                    if tc_name == "search_knowledge":
                        topic = tc.input.get("topic", "")
                        if verbose:
                            print(f"  [查询知识库] {topic}: {reason}")
                        knowledge_used.append(topic)
                        result = search_knowledge(topic)
                    elif tc_name == "search_web":
                        query = tc.input.get("query", "")
                        if verbose:
                            print(f"  [联网搜索] {query}: {reason}")
                        result = search_web(query, max_results=5)
                    else:
                        result = "未知工具"
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": tc.id,
                        "content": result[:4000],  # 限制长度
                    })
                messages.append({"role": "user", "content": tool_results})

            else:
                # OpenAI 兼容（qwen/deepseek/openai）
                from openai import OpenAI
                url_map = {
                    "qwen":     "https://dashscope.aliyuncs.com/compatible-mode/v1",
                    "deepseek": "https://api.deepseek.com/v1",
                }
                client = OpenAI(
                    api_key=api_key,
                    base_url=base_url or url_map.get(provider, "https://api.openai.com/v1"),
                )
                full_messages = [{"role": "system", "content": SYSTEM}] + messages

                resp = client.chat.completions.create(
                    model=model or "qwen-max",
                    messages=full_messages,
                    tools=TOOLS,
                    tool_choice="auto",
                    max_tokens=1500,
                )

                msg = resp.choices[0].message
                tool_calls = msg.tool_calls or []

                if not tool_calls:
                    text = msg.content or ""
                    return [text.strip()] if text.strip() else ["分析完成，当前 session 状态良好"]

                # 执行 tool calls
                messages.append({"role": "assistant", "content": msg.content, "tool_calls": [
                    {"id": tc.id, "type": "function",
                     "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
                    for tc in tool_calls
                ]})

                for tc in tool_calls:
                    args = json.loads(tc.function.arguments)
                    reason = args.get("reason", "")
                    tc_name = tc.function.name
                    if tc_name == "search_knowledge":
                        topic = args.get("topic", "")
                        if verbose:
                            print(f"  [查询知识库] {topic}: {reason}")
                        knowledge_used.append(topic)
                        result = search_knowledge(topic)
                    elif tc_name == "search_web":
                        query = args.get("query", "")
                        if verbose:
                            print(f"  [联网搜索] {query}: {reason}")
                        result = search_web(query, max_results=5)
                    else:
                        result = "未知工具"
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": result[:4000],
                    })

        return ["分析超时，请重试"]

    except Exception as e:
        return [f"建议生成失败：{e}"]
