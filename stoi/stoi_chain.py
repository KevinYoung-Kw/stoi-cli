#!/usr/bin/env python3
"""
stoi_chain.py — 完整对话链条分析

读取 Claude Code session 的完整链条：
  User message → System Prompt → Tool calls → Tool results → Assistant output → Usage

基于洛小山四层优化方法论：
  L1 语法层：格式 token 浪费（JSON 缩进、Markdown 装饰）
  L2 语义层：tool result 内容冗余、重复的 context
  L3 架构层：cache miss 根因（动态字段注入）
  L4 输出层：Yapping、不必要的总结

每层给出可直接执行的具体建议（不是"建议优化"）
"""

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


# ── 数据结构 ────────────────────────────────────────────────────────────────
@dataclass
class ToolCall:
    tool_id:    str
    name:       str
    input_str:  str          # 工具输入（原始）
    input_tokens: int = 0    # 估算 token 数


@dataclass
class ToolResult:
    tool_id:      str
    content:      str        # 工具返回内容
    output_tokens: int = 0   # 估算 token 数
    is_large:     bool = False  # > 2000 tokens


@dataclass
class ChainTurn:
    turn_index:   int
    timestamp:    float
    user_text:    str = ""
    tool_calls:   list[ToolCall] = field(default_factory=list)
    tool_results: list[ToolResult] = field(default_factory=list)
    assistant_text: str = ""
    usage:        dict = field(default_factory=dict)
    # 计算字段
    total_input_tokens:  int = 0
    cache_read_tokens:   int = 0
    tool_result_tokens:  int = 0   # tool results 占的 token 估算
    stoi_score:          float = 0.0


@dataclass
class ChainAnalysis:
    session_name: str
    turns:        list[ChainTurn]
    # 汇总
    total_turns:           int = 0
    total_input_tokens:    int = 0
    total_tool_result_tokens: int = 0
    tool_result_ratio:     float = 0.0  # tool result 占总 input 的比例
    # 四层问题
    l1_syntax_issues:    list[dict] = field(default_factory=list)
    l2_semantic_issues:  list[dict] = field(default_factory=list)
    l3_cache_issues:     list[dict] = field(default_factory=list)
    l4_output_issues:    list[dict] = field(default_factory=list)
    # 可操作建议
    actionable_fixes:    list[dict] = field(default_factory=list)


# ── 简单 Token 估算 ──────────────────────────────────────────────────────────
def _estimate_tokens(text: str) -> int:
    """粗略估算 token 数（CJK 1字符≈1token，英文 4字符≈1token）"""
    if not text:
        return 0
    cjk = len(re.findall(r'[\u4e00-\u9fff\u3040-\u30ff]', text))
    ascii_tokens = max(1, (len(text) - cjk) // 4)
    return cjk + ascii_tokens


# ── Session 链条解析 ─────────────────────────────────────────────────────────
def parse_chain(session_path: Path, max_turns: int = 50) -> list[ChainTurn]:
    """
    解析 Claude Code session JSONL，提取完整的链条
    返回每轮的：user_text + tool_calls + tool_results + assistant_text + usage
    """
    turns = []
    current_assistant_tools: list[ToolCall] = []
    current_tool_results: list[ToolResult] = []
    pending_user: str = ""
    pending_ts: float = 0

    try:
        with open(session_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except Exception:
                    continue

                msg_type = obj.get("type", "")
                msg      = obj.get("message", {})
                if not isinstance(msg, dict):
                    continue
                content = msg.get("content", [])
                if not isinstance(content, list):
                    content = []

                ts = obj.get("timestamp", 0)
                if isinstance(ts, str):
                    try:
                        from datetime import datetime
                        ts = datetime.fromisoformat(ts.replace("Z","+00:00")).timestamp() * 1000
                    except Exception:
                        ts = 0

                if msg_type == "user":
                    # 收集 user 消息（文本 + tool results）
                    user_texts = []
                    for c in content:
                        if not isinstance(c, dict):
                            continue
                        if c.get("type") == "text":
                            user_texts.append(c.get("text", ""))
                        elif c.get("type") == "tool_result":
                            # tool result 是 user 消息里的
                            res_content = c.get("content", "")
                            if isinstance(res_content, list):
                                parts = []
                                for rc in res_content:
                                    if isinstance(rc, dict):
                                        parts.append(rc.get("text", ""))
                                res_content = "\n".join(parts)
                            current_tool_results.append(ToolResult(
                                tool_id=c.get("tool_use_id", ""),
                                content=str(res_content)[:3000],
                                output_tokens=_estimate_tokens(str(res_content)),
                                is_large=_estimate_tokens(str(res_content)) > 2000,
                            ))
                    if user_texts:
                        pending_user = "\n".join(user_texts)[:500]
                        pending_ts = float(ts)

                elif msg_type == "assistant":
                    usage = msg.get("usage", {})
                    inp   = usage.get("input_tokens", 0)
                    out   = usage.get("output_tokens", 0)
                    cr    = usage.get("cache_read_input_tokens", 0)
                    cw_raw = usage.get("cache_creation_input_tokens", 0)
                    cw = cw_raw if isinstance(cw_raw, int) else 0

                    # 跳过流式占位
                    if out == 0:
                        continue

                    # 收集 assistant 的 tool_use 和文本
                    assistant_text = ""
                    for c in content:
                        if not isinstance(c, dict):
                            continue
                        if c.get("type") == "text":
                            assistant_text += c.get("text", "")
                        elif c.get("type") == "tool_use":
                            inp_data = c.get("input", {})
                            inp_str  = json.dumps(inp_data, ensure_ascii=False)[:500] if isinstance(inp_data, dict) else str(inp_data)[:500]
                            current_assistant_tools.append(ToolCall(
                                tool_id=c.get("id", ""),
                                name=c.get("name", ""),
                                input_str=inp_str,
                                input_tokens=_estimate_tokens(inp_str),
                            ))

                    total_input = inp + cr + cw
                    tool_result_tokens = sum(r.output_tokens for r in current_tool_results)

                    turn = ChainTurn(
                        turn_index=len(turns),
                        timestamp=float(ts),
                        user_text=pending_user,
                        tool_calls=list(current_assistant_tools),
                        tool_results=list(current_tool_results),
                        assistant_text=assistant_text[:500],
                        usage=usage,
                        total_input_tokens=total_input,
                        cache_read_tokens=cr,
                        tool_result_tokens=tool_result_tokens,
                        stoi_score=round((inp / total_input * 100) if total_input > 0 else 0, 1),
                    )
                    turns.append(turn)

                    # 重置
                    current_assistant_tools = []
                    current_tool_results   = []
                    pending_user = ""

                    if len(turns) >= max_turns:
                        break

    except Exception:
        pass

    return turns


# ── 四层分析（洛小山方法论）──────────────────────────────────────────────────
def analyze_chain(turns: list[ChainTurn], session_name: str = "") -> ChainAnalysis:
    """
    基于完整链条，按洛小山四层方法论分析并给出可执行建议
    """
    analysis = ChainAnalysis(session_name=session_name, turns=turns)

    if not turns:
        return analysis

    # 基础统计
    analysis.total_turns          = len(turns)
    analysis.total_input_tokens   = sum(t.total_input_tokens for t in turns)
    analysis.total_tool_result_tokens = sum(t.tool_result_tokens for t in turns)
    if analysis.total_input_tokens > 0:
        analysis.tool_result_ratio = round(
            analysis.total_tool_result_tokens / analysis.total_input_tokens, 3
        )

    # ── L1 语法层：tool input 格式冗余 ───────────────────────────────────────
    json_heavy_tools = []
    for turn in turns:
        for tc in turn.tool_calls:
            # JSON 格式是否过度？
            if tc.input_tokens > 100:
                try:
                    data = json.loads(tc.input_str)
                    compact = json.dumps(data, separators=(',', ':'), ensure_ascii=False)
                    saving = tc.input_tokens - _estimate_tokens(compact)
                    if saving > 20:
                        json_heavy_tools.append({
                            "turn": turn.turn_index,
                            "tool": tc.name,
                            "tokens": tc.input_tokens,
                            "saving": saving,
                        })
                except Exception:
                    pass

    if json_heavy_tools:
        total_saving = sum(t["saving"] for t in json_heavy_tools)
        analysis.l1_syntax_issues.append({
            "type": "json_format",
            "detail": f"{len(json_heavy_tools)} 次 tool 调用使用了格式化 JSON，可压缩节省 ~{total_saving} tokens",
            "examples": json_heavy_tools[:2],
        })

    # ── L2 语义层：tool result 冗余 ───────────────────────────────────────────
    large_results = []
    repeated_tools = {}

    for turn in turns:
        for tr in turn.tool_results:
            if tr.is_large:
                large_results.append({
                    "turn": turn.turn_index,
                    "tokens": tr.output_tokens,
                    "preview": tr.content[:100],
                })

        # 统计工具调用频次
        for tc in turn.tool_calls:
            repeated_tools[tc.name] = repeated_tools.get(tc.name, 0) + 1

    if large_results:
        total_large = sum(r["tokens"] for r in large_results)
        analysis.l2_semantic_issues.append({
            "type": "large_tool_result",
            "detail": f"{len(large_results)} 个 tool result > 2000 tokens，合计 {total_large:,} tokens",
            "top_results": large_results[:3],
        })

    # 找最频繁的工具
    if repeated_tools:
        top_tool = max(repeated_tools, key=repeated_tools.get)
        if repeated_tools[top_tool] > 5:
            analysis.l2_semantic_issues.append({
                "type": "repeated_tool",
                "detail": f"{top_tool} 被调用了 {repeated_tools[top_tool]} 次，考虑缓存结果",
                "tool": top_tool,
                "count": repeated_tools[top_tool],
            })

    # ── L3 架构层：cache miss 根因 ────────────────────────────────────────────
    DYNAMIC_PATTERNS = {
        "timestamp": (r'\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}', "时间戳"),
        "uuid":      (r'[0-9a-f]{8}-[0-9a-f]{4}', "UUID"),
        "abs_path":  (r'/Users/[A-Za-z0-9_]+', "绝对路径"),
        "pid":       (r'\bpid[:\s=]+\d+', "进程ID"),
    }

    cache_miss_turns = [t for t in turns if t.stoi_score > 80 and not t.turn_index == 0]
    if len(cache_miss_turns) > len(turns) * 0.3:
        # 检查 tool result 里有没有动态内容进了 context
        dynamic_found = {}
        for turn in cache_miss_turns[:5]:
            for tr in turn.tool_results:
                for name, (pattern, label) in DYNAMIC_PATTERNS.items():
                    if re.search(pattern, tr.content):
                        dynamic_found[name] = label

        analysis.l3_cache_issues.append({
            "type": "cache_miss",
            "detail": f"{len(cache_miss_turns)}/{len(turns)} 轮 cache miss（含屎量 > 80%）",
            "dynamic_in_context": list(dynamic_found.values()),
        })

    # ── L4 输出层：assistant 输出冗余 ─────────────────────────────────────────
    yapping_turns = []
    YAPPING_RE = [
        r'(以上|如上|综上)(所述|内容|改动)',
        r'(总结|总结如下|主要改动)[:：]',
        r'如(需|果).{0,15}(告知|联系|提问)',
    ]
    for turn in turns:
        for pattern in YAPPING_RE:
            if re.search(pattern, turn.assistant_text):
                yapping_turns.append(turn.turn_index)
                break

    if len(yapping_turns) > len(turns) * 0.2:
        analysis.l4_output_issues.append({
            "type": "yapping",
            "detail": f"{len(yapping_turns)} 轮输出包含不必要的总结/确认废话",
            "turns": yapping_turns[:5],
        })

    # ── 生成可操作建议 ────────────────────────────────────────────────────────
    fixes = []

    if analysis.tool_result_ratio > 0.4:
        fixes.append({
            "priority": 1,
            "layer": "L2",
            "action": f"tool result 占总 input 的 {analysis.tool_result_ratio*100:.0f}%，是最大的 token 来源",
            "fix":    "在 CLAUDE.md 中加入：'文件读取结果超过 500 行时，只返回相关部分，不要返回全文'",
            "saving": f"预计节省 {analysis.total_tool_result_tokens//3:,} tokens/session",
        })

    if analysis.l3_cache_issues:
        issue = analysis.l3_cache_issues[0]
        dynamic = issue.get("dynamic_in_context", [])
        if dynamic:
            fixes.append({
                "priority": 2,
                "layer": "L3",
                "action": f"tool result 中包含 {'/'.join(dynamic)}，可能导致 cache miss",
                "fix":    "让 Claude Code 在处理 tool result 时过滤掉时间戳和绝对路径（在 CLAUDE.md 中注明）",
                "saving": "可将缓存命中率从当前提升 20-40%",
            })
        else:
            fixes.append({
                "priority": 2,
                "layer": "L3",
                "action": issue["detail"],
                "fix":    "运行 stoi blame 精确定位 cache miss 根因",
                "saving": "每次命中 cache 节省 ~90% 的 token 成本",
            })

    if analysis.l2_semantic_issues:
        for iss in analysis.l2_semantic_issues:
            if iss["type"] == "large_tool_result":
                fixes.append({
                    "priority": 3,
                    "layer": "L2",
                    "action": iss["detail"],
                    "fix":    "给 Claude Code 添加指令：'grep/find 结果超过 50 行时只返回文件名，不返回内容'",
                    "saving": f"节省约 {iss['top_results'][0]['tokens'] if iss['top_results'] else 0:,} tokens/次",
                })

    if analysis.l4_output_issues:
        fixes.append({
            "priority": 4,
            "layer": "L4",
            "action": analysis.l4_output_issues[0]["detail"],
            "fix":    "在 CLAUDE.md 加入：'完成任务后不要总结已做的事，直接等待下一个指令'",
            "saving": "减少 10-20% output tokens，降低延迟",
        })

    if json_heavy_tools:
        fixes.append({
            "priority": 5,
            "layer": "L1",
            "action": analysis.l1_syntax_issues[0]["detail"] if analysis.l1_syntax_issues else "",
            "fix":    "工具调用参数使用最小化 JSON（去掉空格和换行）",
            "saving": f"节省 ~{sum(t['saving'] for t in json_heavy_tools)} tokens",
        })

    analysis.actionable_fixes = sorted(fixes, key=lambda x: x["priority"])
    return analysis


# ── CLI 输出 ────────────────────────────────────────────────────────────────
def render_chain_report(analysis: ChainAnalysis) -> None:
    """在终端输出链条分析报告"""
    from rich.console import Console
    from rich.table import Table
    from rich import box

    console = Console(highlight=False)

    if not analysis.turns:
        console.print("  [dim]无链条数据[/dim]")
        return

    console.print()
    console.print(f"  [bold #FFB800]🔗 对话链条分析[/bold #FFB800]  "
                  f"[dim]{analysis.total_turns} 轮  |  {analysis.session_name[:30]}[/dim]")
    console.print()

    # Token 来源分解
    total = analysis.total_input_tokens
    tr_pct = analysis.tool_result_ratio * 100
    console.print(f"  [dim]总 input tokens[/dim]   [white]{total:,}[/white]")
    if tr_pct > 10:
        color = "red" if tr_pct > 50 else "yellow" if tr_pct > 30 else "white"
        console.print(f"  [dim]└ tool results[/dim]    [{color}]{analysis.total_tool_result_tokens:,} ({tr_pct:.0f}%)[/{color}]  [dim]← 往往是最大的浪费来源[/dim]")
    console.print()

    # 最近5轮明细
    if len(analysis.turns) > 0:
        console.print(f"  [bold white]最近轮次[/bold white]  [dim](最多显示5轮)[/dim]")
        table = Table(box=box.SIMPLE, show_header=True, header_style="dim", padding=(0,1))
        table.add_column("轮次", width=5)
        table.add_column("用户", width=22)
        table.add_column("工具调用", width=20)
        table.add_column("输入", width=8, justify="right")
        table.add_column("含屎", width=7, justify="right")

        for t in analysis.turns[-5:]:
            tool_names = ", ".join(set(tc.name for tc in t.tool_calls))[:20] or "—"
            user = (t.user_text[:20] + "…") if len(t.user_text) > 20 else (t.user_text or "—")
            score_color = "green" if t.stoi_score < 30 else "yellow" if t.stoi_score < 60 else "red"
            table.add_row(
                str(t.turn_index + 1),
                user,
                tool_names,
                f"{t.total_input_tokens:,}",
                f"[{score_color}]{t.stoi_score:.0f}%[/{score_color}]",
            )
        console.print(table)
        console.print()

    # 可操作建议
    if analysis.actionable_fixes:
        console.print(f"  [bold white]可操作建议[/bold white]  [dim]（按影响排序）[/dim]")
        console.print()
        for fix in analysis.actionable_fixes:
            layer_color = {"L1": "dim", "L2": "yellow", "L3": "red", "L4": "yellow"}.get(fix["layer"], "white")
            console.print(f"  [{layer_color}][{fix['layer']}][/{layer_color}] {fix['action']}")
            console.print(f"    [green]→ {fix['fix']}[/green]")
            console.print(f"    [dim]{fix['saving']}[/dim]")
            console.print()
    else:
        console.print("  [green]✅ 未发现明显的链条级浪费[/green]")
        console.print()
