#!/usr/bin/env python3
"""
stoi_insights.py — STOI AI 洞察引擎
参考 Claude Code /insights 指令设计
用 LLM 把 STOI 分析结果翻译成可操作的改进建议
"""

import json
import sys
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
from rich.live import Live
from rich.spinner import Spinner
from rich.text import Text

from stoi_config import load_config, is_configured, run_onboard, get_api_key

console = Console()

# ── Insights Prompt ───────────────────────────────────────────────────────────
INSIGHTS_SYSTEM = """你是 STOI（Shit Token On Investment）的 AI 分析师。
你的职责是分析 AI 编程工具的 Token 使用效率，给出具体、可操作的改进建议。

分析维度：
1. 缓存效率（Cache Hit Rate）：缓存命中率是否健康？是否有可避免的 cache miss？
2. 输出有效性（L4 反馈信号）：用户是否认可了 AI 的输出？有多少轮次被否定？
3. 多轮趋势：含屎量随轮次是上升还是下降？在哪一轮出现了拐点？
4. 成本影响：浪费了多少 token？换算成金钱大约是多少？

输出要求：
- 用中文回答
- 给出 3 条具体建议，每条必须包含：问题描述、根本原因、具体操作步骤、预期收益
- 语气直接，不要废话，不要"首先/其次/最后"这种模板
- 如果数据显示问题不严重，也要诚实说"整体健康，建议关注 X"
- 不超过 400 字"""

INSIGHTS_PROMPT_TEMPLATE = """
# STOI 分析数据

## 会话概览
- 总轮次：{total_turns}（有效轮：{valid_turns}，流式占位轮：{stub_turns}）
- 平均含屎量：{avg_score:.1f}%（{level}）
- 平均缓存命中率：{avg_hit:.1f}%
- 总 Token 消耗：{total_input:,}（浪费：{total_wasted:,}，约占 {waste_pct:.0f}%）
- 估算多花费用：约 ${extra_cost:.4f}（按 Anthropic 缓存 vs 非缓存价差估算）

## 用户反馈信号（L4）
- 明确否定的轮次：{invalid_turns}（"不对"/"还是不行"等）
- 明确认可的轮次：{valid_turns_l4}（"好了"/"可以了"等）
- 追加修改的轮次：{partial_turns}（"再帮我..."/"调整一下"等）

## 含屎量分布
{score_distribution}

## 趋势分析
{trend_analysis}

## 检测到的造屎元凶
{culprits}

请给出 3 条具体的改进建议。
"""


def format_insights_data(records: list[dict]) -> dict:
    """从 records 提取关键数据，格式化为 prompt 用的文本"""
    # 过滤掉 user 消息和 stub
    assistant_records = [r for r in records if r.get("role") != "user"]
    valid_records = [r for r in assistant_records if not r.get("stoi", {}).get("is_baseline")]
    stub_records  = [r for r in assistant_records if r.get("stoi", {}).get("is_baseline")]

    if not valid_records:
        return None

    scores   = [r["stoi"]["stoi_score"] for r in valid_records]
    hits     = [r["stoi"]["cache_hit_rate"] for r in valid_records]
    inputs   = [r["stoi"]["input_tokens"] for r in valid_records]
    wasted   = [r["stoi"]["wasted_tokens"] for r in valid_records]
    outputs  = [r["stoi"]["output_tokens"] for r in valid_records]

    avg_score = sum(scores) / len(scores)
    avg_hit   = sum(hits) / len(hits)
    total_input  = sum(inputs)
    total_wasted = sum(wasted)
    waste_pct    = total_wasted / max(total_input, 1) * 100

    # 估算多花费用：cache miss 的部分按全价算，cache hit 按 10% 算
    # 差价 = wasted_tokens * (1 - 0.1) * $3/1M = wasted * 0.0000027
    extra_cost = total_wasted * 0.0000027

    # 等级
    level_map = {(0,30): "✅ CLEAN", (30,50): "🟡 MILD_SHIT",
                 (50,75): "🟠 SHIT_OVERFLOW", (75,101): "💩 DEEP_SHIT"}
    level = "UNKNOWN"
    for (lo, hi), name in level_map.items():
        if lo <= avg_score < hi:
            level = name
            break

    # L4 反馈统计
    invalid_turns = sum(1 for r in valid_records if r.get("l4", {}).get("validity") == "invalid")
    valid_turns_l4 = sum(1 for r in valid_records if r.get("l4", {}).get("validity") == "valid")
    partial_turns  = sum(1 for r in valid_records if r.get("l4", {}).get("validity") == "partial")

    # 分布
    buckets = {"0-10%": 0, "10-30%": 0, "30-50%": 0, "50-75%": 0, "75-100%": 0}
    for s in scores:
        if s < 10:   buckets["0-10%"] += 1
        elif s < 30: buckets["10-30%"] += 1
        elif s < 50: buckets["30-50%"] += 1
        elif s < 75: buckets["50-75%"] += 1
        else:        buckets["75-100%"] += 1
    dist_lines = [f"  {k}: {v}轮" for k, v in buckets.items() if v > 0]

    # 趋势
    if len(scores) >= 4:
        first_half = scores[:len(scores)//2]
        second_half = scores[len(scores)//2:]
        first_avg = sum(first_half) / len(first_half)
        second_avg = sum(second_half) / len(second_half)
        delta = second_avg - first_avg
        if delta > 10:
            trend = f"含屎量呈上升趋势（前半段均值 {first_avg:.1f}% → 后半段 {second_avg:.1f}%）"
        elif delta < -10:
            trend = f"含屎量呈下降趋势（前半段均值 {first_avg:.1f}% → 后半段 {second_avg:.1f}%）"
        else:
            trend = f"含屎量相对稳定（前半段均值 {first_avg:.1f}%，后半段 {second_avg:.1f}%）"

        # 找突变点
        spikes = [(i, s) for i, s in enumerate(scores) if s > avg_score + 30]
        if spikes:
            spike_info = "；".join([f"第{i+1}轮突增至{s:.0f}%" for i, s in spikes[:3]])
            trend += f"\n突变点：{spike_info}"
    else:
        trend = "数据轮次较少，趋势分析需要更多数据"

    # 造屎元凶（从高 cache miss 的轮次推断）
    bad_turns = [r for r in valid_records if r["stoi"]["cache_hit_rate"] < 5 and r["stoi"]["input_tokens"] > 5000]
    if len(bad_turns) > len(valid_records) * 0.3:
        culprits = f"检测到大量 cache miss（{len(bad_turns)}/{len(valid_records)} 轮），常见原因：时间戳注入、tools 列表动态切换、绝对路径"
    elif len(bad_turns) > 0:
        culprits = f"偶发 cache miss（{len(bad_turns)} 轮），建议运行 stoi blame 定位具体原因"
    else:
        culprits = "未检测到明显的结构性 cache miss"

    return {
        "total_turns":    len(assistant_records),
        "valid_turns":    len(valid_records),
        "stub_turns":     len(stub_records),
        "avg_score":      avg_score,
        "level":          level,
        "avg_hit":        avg_hit,
        "total_input":    total_input,
        "total_wasted":   total_wasted,
        "waste_pct":      waste_pct,
        "extra_cost":     extra_cost,
        "invalid_turns":  invalid_turns,
        "valid_turns_l4": valid_turns_l4,
        "partial_turns":  partial_turns,
        "score_distribution": "\n".join(dist_lines),
        "trend_analysis": trend,
        "culprits":       culprits,
    }


def call_llm(prompt: str, system: str) -> str:
    """调用 LLM 生成 insights，支持多 provider"""
    cfg = load_config()
    llm = cfg.get("llm", {})
    provider  = llm.get("provider", "anthropic")
    api_key   = llm.get("api_key", "") or get_api_key(provider)
    model     = llm.get("model", "")
    base_url  = llm.get("base_url", "")

    if not api_key:
        raise ValueError(f"未配置 API Key，请先运行 stoi config")

    # ── Anthropic ──────────────────────────────────────────────────────────────
    if provider == "anthropic":
        try:
            import anthropic
        except ImportError:
            raise ImportError("请安装 anthropic: pip3 install anthropic")
        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model=model or "claude-haiku-3-5",
            max_tokens=1024,
            system=system,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text

    # ── OpenAI 兼容（OpenAI / Qwen / DeepSeek / custom）──────────────────────
    else:
        try:
            from openai import OpenAI
        except ImportError:
            raise ImportError("请安装 openai: pip3 install openai")
        url_map = {
            "openai":   "https://api.openai.com/v1",
            "qwen":     "https://dashscope.aliyuncs.com/compatible-mode/v1",
            "deepseek": "https://api.deepseek.com/v1",
        }
        client = OpenAI(
            api_key=api_key,
            base_url=base_url or url_map.get(provider, "https://api.openai.com/v1"),
        )
        model_default = {"qwen": "qwen-plus", "deepseek": "deepseek-chat"}.get(provider, "gpt-4o-mini")
        response = client.chat.completions.create(
            model=model or model_default,
            messages=[
                {"role": "system", "content": system},
                {"role": "user",   "content": prompt},
            ],
            max_tokens=1024,
        )
        return response.choices[0].message.content


def run_insights(records: list[dict], session_name: str = "") -> None:
    """主入口：给定 records，生成并展示 AI insights"""

    if not is_configured():
        console.print("[yellow]⚠ 尚未配置 LLM，启动初始配置...[/yellow]")
        console.print()
        run_onboard()
        console.print()

    data = format_insights_data(records)
    if not data:
        console.print("[dim]数据不足，无法生成 insights（需要至少 3 个有效轮次）[/dim]")
        return

    prompt = INSIGHTS_PROMPT_TEMPLATE.format(**data)

    console.print()
    console.print(Panel.fit(
        f"[bold #FFB800]💡 STOI Insights[/bold #FFB800]\n"
        f"[dim]{session_name or '当前 Session'}  •  {data['valid_turns']} 有效轮次  •  "
        f"均值 {data['avg_score']:.1f}%  {data['level']}[/dim]",
        border_style="#FFB800",
    ))
    console.print()

    # 流式输出
    result = ""
    try:
        cfg = load_config()
        provider = cfg.get("llm", {}).get("provider", "")

        with console.status("[dim]正在生成 AI 洞察...[/dim]", spinner="dots"):
            result = call_llm(prompt, INSIGHTS_SYSTEM)

        console.print(Markdown(result))

    except Exception as e:
        console.print(f"[red]LLM 调用失败: {e}[/red]")
        console.print("[dim]检查 API Key 是否正确，或运行 stoi config 重新配置[/dim]")
        return

    console.print()
    console.print("[dim]按 Q 退出  •  运行 stoi blame 查看详细造屎元凶分析[/dim]")
