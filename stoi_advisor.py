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
    }
]


def search_knowledge(topic: str) -> str:
    """从知识库文件读取内容"""
    kb_file = KNOWLEDGE_DIR / f"{topic}.md"
    if not kb_file.exists():
        return f"[知识库文件 {topic}.md 不存在，请先运行 stoi knowledge --build]"
    return kb_file.read_text(encoding="utf-8")


def _build_analysis_summary(report) -> str:
    """把 STOIReport 转成 LLM 可读的摘要"""
    from stoi_core import STOIReport

    scored = [t for t in report.turns
              if not t.is_stub and not t.is_baseline and t.role == "assistant"]

    # 趋势
    trend = ""
    if len(scored) >= 4:
        mid = len(scored) // 2
        fa = sum(t.stoi_score for t in scored[:mid]) / mid
        sa = sum(t.stoi_score for t in scored[mid:]) / (len(scored) - mid)
        delta = sa - fa
        trend = f"{'↑上升' if delta > 5 else '↓下降' if delta < -5 else '→稳定'} {delta:+.1f}%（前半段 {fa:.1f}% → 后半段 {sa:.1f}%）"

    # 输入增长
    inputs = [t.input_tokens + t.cache_read + t.cache_write for t in scored]
    growth = ""
    if len(inputs) >= 2 and inputs[0] > 0:
        pct = (inputs[-1] - inputs[0]) / inputs[0] * 100
        growth = f"上下文从 {inputs[0]:,} → {inputs[-1]:,} tokens（增长 {pct:.0f}%）"

    issues = "\n".join(
        f"- [{i['severity']}] {i['title']}\n  {i['detail']}" for i in report.issues
    ) or "- 未发现明显问题"

    return f"""## STOI 分析数据

**会话信息**
- 工具：Claude Code，Session：{report.session_name}
- 模型：{report.model}
- 总轮次：{report.total_turns}（有效：{report.valid_turns}，流式占位：{report.total_turns - report.valid_turns}）

**L1：KV Cache 效率**
- 平均含屎量：{report.avg_stoi_score:.1f}%（{report.stoi_level}）
- 平均缓存命中率：{report.avg_cache_hit_rate:.1f}%
- 含屎量趋势：{trend or "数据不足"}
- 上下文增长：{growth or "数据不足"}
- 总花费：${report.total_cost_actual:.4f}，cache 节省：${report.total_cost_saved:.4f}

**L2：输出有效性**
- 有效率：{report.effectiveness_rate:.1f}%
- 被用户否定：{report.invalid_turns_count} 轮（浪费 ${report.waste_cost:.4f}）
- 部分有效：{report.partial_turns_count} 轮

**检测到的问题**
{issues}

请根据以上数据，使用 search_knowledge 工具查询相关知识，然后给出 3 条具体、可立即执行的改进建议。

建议格式（每条）：
**[问题类型]**
根因：XXX
操作：具体步骤（1-2句）
收益：预期节省 XX tokens 或 $X.XX"""


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

        SYSTEM = """你是 STOI Token 效率分析引擎。你的任务是：
1. 分析用户提供的 STOI 数据
2. 根据数据特征，使用 search_knowledge 工具查询相关知识（可查询1-3次）
3. 结合数据和知识，给出精准的改进建议

重要：只查询与当前数据问题相关的知识。如果含屎量很低，不要无谓地查 cache 优化。"""

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
                    topic = tc.input.get("topic", "")
                    reason = tc.input.get("reason", "")
                    if verbose:
                        print(f"  [查询知识库] {topic}: {reason}")
                    knowledge_used.append(topic)
                    result = search_knowledge(topic)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": tc.id,
                        "content": result[:3000],  # 限制长度
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
                    topic = json.loads(tc.function.arguments).get("topic", "")
                    reason = json.loads(tc.function.arguments).get("reason", "")
                    if verbose:
                        print(f"  [查询知识库] {topic}: {reason}")
                    knowledge_used.append(topic)
                    result = search_knowledge(topic)
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": result[:3000],
                    })

        return ["分析超时，请重试"]

    except Exception as e:
        return [f"建议生成失败：{e}"]
