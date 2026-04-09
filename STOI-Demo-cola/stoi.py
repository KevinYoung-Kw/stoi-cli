#!/usr/bin/env python3
"""
stoi.py — STOI 主命令行入口
Shit Token On Investment

用法:
  python3 stoi.py start      # 启动代理
  python3 stoi.py stats      # 打印报告 + TTS
  python3 stoi.py blame      # 找出 Cache 元凶
  python3 stoi.py analyze    # 离线分析 Claude Code 会话
  python3 stoi.py tui        # 启动 TUI 仪表盘
  python3 stoi.py trend      # ASCII 趋势图
  python3 stoi.py backfill-feedback-validity  # 回填反馈型 token 有效性
  python3 stoi.py feedback-validity           # 查看反馈型 token 有效性
"""

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich import box

console = Console()

LOG_FILE = Path("~/.stoi/sessions.jsonl").expanduser()
LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

STOI_LOGO = r"""
 ███████╗████████╗ ██████╗ ██╗
 ██╔════╝╚══██╔══╝██╔═══██╗██║
 ███████╗   ██║   ██║   ██║██║
 ╚════██║   ██║   ██║   ██║██║
 ███████║   ██║   ╚██████╔╝██║
 ╚══════╝   ╚═╝    ╚═════╝ ╚═╝
"""

COMMANDS = {
    "start":   "启动 API 代理（拦截 Claude Code 请求）",
    "stats":   "打印含屎量统计报告 + TTS 播报",
    "blame":   "扫描 System Prompt，找 Cache Miss 元凶",
    "analyze": "离线分析 ~/.claude/projects/ 会话文件",
    "tui":     "启动实时 TUI 仪表盘",
    "trend":   "打印多轮含屎量趋势 ASCII 图",
    "metrics": "步骤级质量分析（F/V/C/U + TE/SUS/FR/MG/RR）",
    "report":  "综合报告：含屎量 + 步骤级指标 + 根因分析",
    "backfill-feedback-validity": "回填 Claude Code 反馈型 token 有效性",
    "feedback-validity": "查看 Claude Code 反馈型 token 有效性",
}


def print_logo():
    console.print(Text(STOI_LOGO, style="bold #FFB800"))
    console.print(
        "  [bold white]Shit Token On Investment[/bold white]  "
        "[dim]— 含屎量实时监控系统 v1.1[/dim]\n"
    )


def speak(level: str):
    """macOS TTS 播报"""
    from stoi_engine import TTS_MESSAGES
    msg = TTS_MESSAGES.get(level, "")
    if msg:
        try:
            subprocess.Popen(["say", "-v", "Ting-Ting", msg])
        except Exception:
            pass


def load_log() -> list[dict]:
    if not LOG_FILE.exists():
        return []
    try:
        lines = LOG_FILE.read_text(encoding="utf-8").strip().splitlines()
        records = []
        for line in lines:
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return records
    except Exception:
        return []


# ── start ────────────────────────────────────────────────────────────────────
def cmd_start():
    print_logo()
    console.print("[bold #FFB800]▶ 启动 STOI 代理...[/bold #FFB800]\n")

    proxy_path = Path(__file__).parent / "stoi_proxy.py"
    if not proxy_path.exists():
        # 尝试从 Hackathon 目录复制过来
        src = Path("/Users/kevinyoung/.cola/outputs/STOI-Hackathon-路演-PPT/stoi_proxy.py")
        if src.exists():
            import shutil
            shutil.copy(src, proxy_path)
            console.print(f"[dim]已从 {src} 复制代理脚本[/dim]")

    if proxy_path.exists():
        console.print(
            f"[green]✓ 代理脚本就绪[/green]: {proxy_path}\n"
            "\n运行以下命令启动代理:\n"
            f"  [bold white]python3 {proxy_path}[/bold white]\n"
            "\n然后设置环境变量:\n"
            "  [bold white]export ANTHROPIC_BASE_URL=http://localhost:8888[/bold white]\n"
        )
    else:
        console.print("[red]✗ 未找到 stoi_proxy.py[/red]")
        console.print("[dim]请先将 stoi_proxy.py 放到当前目录[/dim]")


# ── stats ────────────────────────────────────────────────────────────────────
def cmd_stats():
    from stoi_engine import SHIT_EMOJI, SHIT_THRESHOLDS, get_score_color

    print_logo()
    records = load_log()

    if not records:
        console.print(Panel(
            "📭 还没有记录。\n\n"
            "先运行以下任一命令产生数据:\n"
            "  [bold white]python3 stoi.py analyze[/bold white]  — 离线分析 Claude Code 会话\n"
            "  [bold white]python3 stoi.py start[/bold white]    — 启动代理拦截实时请求",
            title="[bold #FFB800]💩 STOI 统计[/bold #FFB800]",
            border_style="#FFB800",
        ))
        return

    total_input   = sum(r["stoi"]["input_tokens"] for r in records)
    total_wasted  = sum(r["stoi"]["wasted_tokens"] for r in records)
    total_output  = sum(r["stoi"]["output_tokens"] for r in records)
    total_cache   = sum(r["stoi"]["cache_read"] for r in records)
    avg_score     = round(sum(r["stoi"]["stoi_score"] for r in records) / len(records), 1)
    hit_rate      = round(total_cache / total_input * 100, 1) if total_input > 0 else 0.0

    level = "DEEP_SHIT"
    for lvl, (lo, hi) in SHIT_THRESHOLDS.items():
        if lo <= avg_score < hi:
            level = lvl
            break

    color = get_score_color(avg_score)
    emoji = SHIT_EMOJI[level]

    # 主统计表格
    table = Table(
        title="💩 STOI 含屎量报告",
        box=box.DOUBLE_EDGE,
        border_style="#FFB800",
        title_style="bold #FFB800",
        show_header=False,
        padding=(0, 2),
    )
    table.add_column("指标", style="bold #FFB800", width=20)
    table.add_column("数值", style="white bold", width=20)

    table.add_row("会话总数",   f"{len(records)} 次")
    table.add_row(
        "平均含屎量",
        Text(f"{avg_score}%  {emoji}  {level}", style=f"bold {color}"),
    )
    table.add_row("缓存命中率",  Text(f"{hit_rate}%", style="green bold"))
    table.add_row("总输入消耗",  f"{total_input:,} tokens")
    table.add_row("白白浪费",    Text(f"{total_wasted:,} tokens  💩", style="red bold"))
    table.add_row("有效输出",    f"{total_output:,} tokens")

    console.print(table)

    # 等级分布
    level_counts: dict[str, int] = {}
    for r in records:
        lvl = r["stoi"]["level"]
        level_counts[lvl] = level_counts.get(lvl, 0) + 1

    console.print("\n[bold #FFB800]等级分布:[/bold #FFB800]")
    for lvl in ["CLEAN", "MILD_SHIT", "SHIT_OVERFLOW", "DEEP_SHIT"]:
        count = level_counts.get(lvl, 0)
        if count > 0:
            pct = round(count / len(records) * 100)
            bar = "█" * (pct // 5)
            em = SHIT_EMOJI[lvl]
            c = get_score_color({"CLEAN": 10, "MILD_SHIT": 40, "SHIT_OVERFLOW": 60, "DEEP_SHIT": 85}[lvl])
            console.print(f"  [{c}]{em} {lvl:<20}[/{c}]  {count:>4} 次  [{c}]{bar}[/{c}]  {pct}%")

    # TTS 播报
    console.print(f"\n[dim]🔊 语音播报: {level}...[/dim]")
    speak(level)


# ── blame ────────────────────────────────────────────────────────────────────
def cmd_blame():
    from stoi_engine import l3_cache_blame, l1_syntax_waste

    print_logo()
    console.print(Panel(
        "📋 请将 System Prompt 粘贴到下方\n"
        "[dim]输入完成后，在新行输入 END 并回车[/dim]",
        title="[bold #FFB800]🔍 STOI Blame — Cache 元凶分析[/bold #FFB800]",
        border_style="#FFB800",
    ))

    lines = []
    while True:
        try:
            line = input()
        except (EOFError, KeyboardInterrupt):
            break
        if line.strip() == "END":
            break
        lines.append(line)

    prompt = "\n".join(lines)

    if not prompt.strip():
        console.print("[yellow]⚠ 未输入内容[/yellow]")
        return

    l3 = l3_cache_blame(prompt)
    l1 = l1_syntax_waste(prompt)

    console.print("\n[bold #FFB800]═══ L3 缓存击穿分析 ═══[/bold #FFB800]\n")

    if l3["culprits"]:
        for c in l3["culprits"]:
            sev_color = {
                "HIGH": "red",
                "MEDIUM": "dark_orange",
                "LOW": "yellow",
            }.get(c["severity"], "white")
            console.print(f"  [{sev_color}]⚠ {c['desc']}[/{sev_color}]")
            console.print(f"    [dim]原因: {c['detail']}[/dim]")
            console.print(f"    [green]修复: {c['fix']}[/green]")
            if c["matches"]:
                console.print(f"    [dim]样例: {c['matches'][0]!r}[/dim]")
            console.print()
    else:
        console.print("  [green]✓ 未发现 Cache Miss 元凶[/green]")

    console.print(f"  综合严重度: [bold]{l3['severity']}[/bold]")
    console.print(f"  修复建议: {l3['suggestion']}\n")

    console.print("[bold #FFB800]═══ L1 语法废话分析 ═══[/bold #FFB800]\n")
    if l1["examples"]:
        for ex in l1["examples"]:
            console.print(f"  [yellow]⚠ {ex}[/yellow]")
        console.print(f"\n  预估浪费 token: [red]~{l1['token_estimate']}[/red]")
        console.print(f"  建议: {l1['suggestion']}\n")
    else:
        console.print("  [green]✓ 语法格式干净，无废话[/green]\n")


# ── analyze ──────────────────────────────────────────────────────────────────
def cmd_analyze(args: list[str]):
    from stoi_analyze import cmd_analyze as _analyze
    _analyze(args)


# ── tui ──────────────────────────────────────────────────────────────────────
def cmd_tui():
    from stoi_tui import run_tui as tui_main
    tui_main()


# ── trend ────────────────────────────────────────────────────────────────────
def cmd_trend():
    from stoi_engine import get_score_color, SHIT_EMOJI

    print_logo()
    records = load_log()

    if not records:
        console.print("[yellow]📭 无数据。先运行 stoi analyze 或 stoi start[/yellow]")
        return

    scores = [r["stoi"]["stoi_score"] for r in records[-30:]]
    times  = [r.get("ts", "")[:16] for r in records[-30:]]

    console.print("[bold #FFB800]📈 含屎量趋势（最近 30 轮）[/bold #FFB800]\n")

    # ASCII 柱状图 (垂直)
    height = 10
    max_score = 100.0
    bar_width = 2

    # 绘制
    col_width = max(bar_width + 1, 4)
    rows = []
    for row_i in range(height, 0, -1):
        threshold = (row_i / height) * max_score
        row_str = f"  {threshold:3.0f}% │"
        for score in scores:
            if score >= threshold:
                color = get_score_color(score)
                row_str += f"[{color}]{'█' * bar_width}[/{color}] "
            else:
                row_str += "   "
        rows.append(row_str)

    for r in rows:
        console.print(r)

    # X 轴
    console.print("       └" + "───" * len(scores))

    # 最新数据点标注
    console.print()
    if scores:
        latest_score = scores[-1]
        color = get_score_color(latest_score)
        console.print(f"  最新: [{color}]{latest_score}%[/{color}]  ({times[-1] if times else '—'})")
        avg = sum(scores) / len(scores)
        color_avg = get_score_color(avg)
        console.print(f"  均值: [{color_avg}]{avg:.1f}%[/{color_avg}]")
        console.print(f"  最高: [red]{max(scores)}%[/red]")
        console.print(f"  最低: [green]{min(scores)}%[/green]")


# ── feedback validity helpers ────────────────────────────────────────────────
def _print_feedback_summary(summary: dict, title: str):
    table = Table(title=title, box=box.ROUNDED, border_style="#FFB800")
    table.add_column("指标", style="cyan")
    table.add_column("数值", justify="right", style="bright_white")
    rows = [
        ("总 Prompt 数", str(summary["total_prompt_count"])),
        ("有效 Prompt 数", str(summary["valid_prompt_count"])),
        ("无效 Prompt 数", str(summary["invalid_prompt_count"])),
        ("总 Input Tokens", str(summary["total_input_tokens"])),
        ("有效 Input Tokens", str(summary["valid_input_tokens"])),
        ("无效 Input Tokens", str(summary["invalid_input_tokens"])),
        ("总 Output Tokens", str(summary["total_output_tokens"])),
        ("有效 Output Tokens", str(summary["valid_output_tokens"])),
        ("无效 Output Tokens", str(summary["invalid_output_tokens"])),
        ("总 Tokens", str(summary["total_tokens"])),
        ("有效 Tokens", str(summary["valid_tokens"])),
        ("无效 Tokens", str(summary["invalid_tokens"])),
        ("有效占比", f"{summary['valid_token_ratio'] * 100:.2f}%"),
        ("无效占比", f"{summary['invalid_token_ratio'] * 100:.2f}%"),
    ]
    for label, value in rows:
        table.add_row(label, value)
    console.print(table)


def _print_feedback_session_summaries(summaries: list, limit: int = None):
    if limit is not None:
        summaries = summaries[:limit]

    table = Table(title="Session 维度有效性汇总", box=box.ROUNDED, border_style="#FFB800")
    table.add_column("Session", style="cyan")
    table.add_column("项目", style="dim")
    table.add_column("Prompt", justify="right")
    table.add_column("有效 Tokens", justify="right")
    table.add_column("无效 Tokens", justify="right")
    table.add_column("有效占比", justify="right")
    for item in summaries:
        table.add_row(
            item["session_id"][:8] + "...",
            Path(item["project_path"]).name if item["project_path"] else "",
            str(item["total_prompt_count"]),
            str(item["valid_tokens"]),
            str(item["invalid_tokens"]),
            f"{item['valid_token_ratio'] * 100:.1f}%",
        )
    console.print(table)


def _print_feedback_rows(rows: list):
    table = Table(title="Prompt 维度明细", box=box.ROUNDED, border_style="#FFB800")
    table.add_column("Idx", justify="right", width=4)
    table.add_column("Prompt", style="bright_white")
    table.add_column("Input", justify="right", width=8)
    table.add_column("Output", justify="right", width=8)
    table.add_column("判定", justify="center", width=8)
    table.add_column("反馈", style="dim")
    for row in rows:
        preview = (row["prompt_text"] or "").replace("\n", " ")
        if len(preview) > 40:
            preview = preview[:37] + "..."
        feedback = (row["feedback_text"] or "").replace("\n", " ")
        if len(feedback) > 28:
            feedback = feedback[:25] + "..."
        table.add_row(
            str(row["prompt_index"]),
            preview,
            str(row["input_tokens"]),
            str(row["output_tokens"]),
            "无效" if row["token_effectiveness"] == "invalid" else "有效",
            feedback,
        )
    console.print(table)


# ── backfill feedback validity ───────────────────────────────────────────────
def cmd_backfill_feedback_validity(args: list):
    from claude_feedback_token_validity import ClaudeFeedbackTokenValidityService

    parser = argparse.ArgumentParser(prog="stoi backfill-feedback-validity", add_help=True)
    parser.add_argument("--session", "-s", help="会话ID")
    parser.add_argument("--format", choices=["table", "json"], default="table")
    parsed = parser.parse_args(args)

    service = ClaudeFeedbackTokenValidityService()
    result = service.backfill(session_id=parsed.session)
    if parsed.format == "json":
        import json
        console.print_json(json.dumps(result, ensure_ascii=False))
    else:
        console.print(f"[green]✓ 已回填 {result['session_count']} 个 session, {result['prompt_count']} 条 prompt[/green]")


# ── feedback validity ────────────────────────────────────────────────────────
def cmd_feedback_validity(args: list):
    from claude_feedback_token_validity import ClaudeFeedbackTokenValidityService

    parser = argparse.ArgumentParser(prog="stoi feedback-validity", add_help=True)
    parser.add_argument("--session", "-s", help="会话ID")
    parser.add_argument("--format", choices=["table", "json"], default="table")
    parser.add_argument("--limit", type=int, help="结果数量限制")
    parser.add_argument("--project", help="按项目路径过滤")
    parser.add_argument("--only", choices=["all", "valid", "invalid"], default="all")
    parsed = parser.parse_args(args)

    service = ClaudeFeedbackTokenValidityService()
    rows = service.get_rows(
        session_id=parsed.session,
        project_path=parsed.project,
        limit=parsed.limit if parsed.session else None,
        only=parsed.only,
    )

    if parsed.session:
        summary = service.summarize_rows(rows)
        if parsed.format == "json":
            import json
            console.print_json(json.dumps({"summary": summary, "rows": rows}, ensure_ascii=False))
        else:
            _print_feedback_summary(summary, f"Session {parsed.session} Token 有效性")
            _print_feedback_rows(rows)
    else:
        summary = service.summarize_rows(rows)
        session_summaries = service.summarize_by_session(rows)
        if parsed.format == "json":
            import json
            console.print_json(json.dumps({
                "summary": summary,
                "session_summaries": session_summaries,
            }, ensure_ascii=False))
        else:
            _print_feedback_summary(summary, "全局 Token 有效性")
            _print_feedback_session_summaries(session_summaries, limit=parsed.limit)


# ── metrics ──────────────────────────────────────────────────────────────────
def cmd_metrics(args: list[str]):
    """步骤级质量分析命令"""
    import argparse as ap
    from stoi_analyze import (
        parse_claude_code_session, find_latest_session, find_recent_sessions,
        compute_step_metrics, aggregate_step_metrics, print_step_metrics_report,
    )

    parser = ap.ArgumentParser(prog="stoi metrics", add_help=True)
    parser.add_argument("--latest", action="store_true", help="分析最新会话")
    parser.add_argument("--text", type=str, help="直接分析粘贴的文本")
    parser.add_argument("--format", choices=["table", "json"], default="table")
    parsed, remaining = parser.parse_known_args(args)

    print_logo()

    if parsed.text:
        # 直接分析粘贴的文本
        from stoi_metrics import analyze_output
        result = analyze_output(parsed.text)
        if parsed.format == "json":
            console.print_json(json.dumps({
                "composite_quality": result.composite_quality,
                "avg_factuality": result.avg_factuality,
                "avg_validity": result.avg_validity,
                "avg_coherence": result.avg_coherence,
                "avg_utility": result.avg_utility,
                "token_efficiency": result.token_efficiency,
                "step_utility_score": result.step_utility_score,
                "faithfulness_risk": result.faithfulness_risk,
                "monitorability_gain": result.monitorability_gain,
                "redundancy_ratio": result.redundancy_ratio,
                "total_reasoning_tokens": result.total_reasoning_tokens,
                "steps": len(result.steps),
            }, ensure_ascii=False))
        else:
            # Wrap into a record for print_step_metrics_report
            mock_record = {"step_metrics": result, "ts": "direct input"}
            agg = {
                "count": 1,
                "avg_factuality": result.avg_factuality,
                "avg_validity": result.avg_validity,
                "avg_coherence": result.avg_coherence,
                "avg_utility": result.avg_utility,
                "token_efficiency": result.token_efficiency,
                "step_utility_score": result.step_utility_score,
                "faithfulness_risk": result.faithfulness_risk,
                "monitorability_gain": result.monitorability_gain,
                "redundancy_ratio": result.redundancy_ratio,
                "composite_quality": result.composite_quality,
                "total_reasoning_tokens": result.total_reasoning_tokens,
                "total_steps": len(result.steps),
            }
            print_step_metrics_report(agg, [mock_record])
        return

    # 分析会话文件
    path = None
    if parsed.latest:
        path = find_latest_session()
        if not path:
            console.print("[yellow]⚠ 未找到 Claude Code 会话文件[/yellow]")
            return
    elif remaining:
        from pathlib import Path as P
        candidate = P(remaining[0])
        if candidate.exists():
            path = candidate
        else:
            console.print(f"[red]文件不存在: {remaining[0]}[/red]")
            return
    else:
        # Default: latest session
        path = find_latest_session()
        if not path:
            console.print("[yellow]⚠ 未找到 Claude Code 会话文件[/yellow]")
            return

    console.print(f"[bold #FFB800]🔍 分析: {path}[/bold #FFB800]\n")
    records = parse_claude_code_session(str(path))

    if not records:
        console.print("[yellow]该会话无有效记录[/yellow]")
        return

    compute_step_metrics(records)
    agg = aggregate_step_metrics(records)

    if parsed.format == "json":
        valid = [r for r in records if r.get("step_metrics") is not None]
        output = {
            "source": str(path),
            "total_turns": len(records),
            "analyzed_turns": len(valid),
            "aggregated": agg,
        }
        console.print_json(json.dumps(output, ensure_ascii=False, default=str))
    else:
        print_step_metrics_report(agg, records)


# ── report ──────────────────────────────────────────────────────────────────
def cmd_report(args: list[str]):
    """综合报告：含屎量 + 步骤级指标 + 根因分析"""
    import argparse as ap
    from datetime import timedelta
    from stoi_analyze import (
        parse_claude_code_session, find_recent_sessions,
        compute_step_metrics, aggregate_step_metrics, print_step_metrics_report,
    )
    from stoi_engine import get_score_color

    parser = ap.ArgumentParser(prog="stoi report", add_help=True)
    parser.add_argument("--days", type=int, default=7, help="分析最近 N 天的会话")
    parser.add_argument("--format", choices=["table", "json"], default="table")
    parsed = parser.parse_args(args)

    print_logo()

    # 加载所有会话
    files = find_recent_sessions(top=200)
    if not files:
        console.print("[yellow]⚠ 未找到 Claude Code 会话文件[/yellow]")
        return

    # 按日期过滤
    now = datetime.now().timestamp()
    cutoff = now - parsed.days * 86400
    recent_files = [f for f in files if f.stat().st_mtime >= cutoff]

    console.print(f"[bold #FFB800]📊 综合报告 — 最近 {parsed.days} 天 ({len(recent_files)} 个文件)[/bold #FFB800]\n")

    all_records = []
    for f in recent_files:
        records = parse_claude_code_session(str(f))
        all_records.extend(records)

    if not all_records:
        console.print("[yellow]该时间段无有效记录[/yellow]")
        return

    # Section 1: STOI Score Summary
    total_input   = sum(r["stoi"]["input_tokens"] for r in all_records)
    total_wasted  = sum(r["stoi"]["wasted_tokens"] for r in all_records)
    total_output  = sum(r["stoi"]["output_tokens"] for r in all_records)
    total_cache   = sum(r["stoi"]["cache_read"] for r in all_records)
    avg_score     = round(sum(r["stoi"]["stoi_score"] for r in all_records) / len(all_records), 1)
    cache_hit     = round(total_cache / total_input * 100, 1) if total_input > 0 else 0.0

    color = get_score_color(avg_score)
    level = "DEEP_SHIT"
    for lvl, (lo, hi) in SHIT_THRESHOLDS.items():
        if lo <= avg_score < hi:
            level = lvl
            break

    summary_table = Table(title="Section 1: STOI 含屎量汇总", box=box.ROUNDED, border_style="#FFB800")
    summary_table.add_column("指标", style="bold #FFB800")
    summary_table.add_column("数值", justify="right")
    summary_table.add_row("分析文件数", f"{len(recent_files)}")
    summary_table.add_row("总轮次", f"{len(all_records)}")
    summary_table.add_row("平均含屎量", f"[{color}]{avg_score}%  {SHIT_EMOJI[level]}[/{color}]")
    summary_table.add_row("缓存命中率", f"[green]{cache_hit}%[/green]")
    summary_table.add_row("总输入", f"{total_input:,} tokens")
    summary_table.add_row("白白浪费", f"[red]{total_wasted:,} tokens[/red]")
    summary_table.add_row("有效输出", f"{total_output:,} tokens")
    console.print(summary_table)

    # Section 2: Step-Level Metrics
    console.print()
    compute_step_metrics(all_records)
    agg = aggregate_step_metrics(all_records)
    print_step_metrics_report(agg, all_records)

    # Section 3: DEEP_SHIT Root Cause Analysis
    if parsed.format == "table":
        console.print()
        deep_shit = [r for r in all_records if r["stoi"]["level"] == "DEEP_SHIT"]
        if deep_shit:
            console.print("[bold red]Section 3: DEEP_SHIT 根因分析[/bold red]")
            cause_table = Table(box=box.SIMPLE, border_style="dim")
            cause_table.add_column("原因类型", style="bold red", width=20)
            cause_table.add_column("出现次数", justify="right", width=10)
            cause_table.add_column("说明", style="dim", width=50)

            no_cache = sum(1 for r in deep_shit if r["stoi"]["cache_read"] == 0)
            low_cache = sum(1 for r in deep_shit if 0 < r["stoi"]["cache_hit_rate"] < 30)
            high_creation = sum(1 for r in deep_shit if r["stoi"].get("cache_creation", 0) > r["stoi"]["input_tokens"] * 0.5)

            causes = [
                ("完全无缓存命中", no_cache, "cache_read=0，每次重新处理全部上下文"),
                ("缓存命中率低", low_cache, "0-30% 命中率，大量 token 被浪费"),
                ("频繁缓存重建", high_creation, "cache_creation 占比高，缓存频繁失效"),
            ]
            for name, count, desc in causes:
                if count > 0:
                    cause_table.add_row(name, str(count), desc)
            console.print(cause_table)
        else:
            console.print("[green]✅ 无 DEEP_SHIT 轮次，根因分析无需执行[/green]")


# ── help ─────────────────────────────────────────────────────────────────────
def cmd_help():
    print_logo()
    console.print("[bold #FFB800]用法:[/bold #FFB800]\n")

    table = Table(box=box.SIMPLE, border_style="dim", show_header=False, padding=(0, 2))
    table.add_column("命令", style="bold white", width=16)
    table.add_column("描述", style="dim", width=50)

    for cmd, desc in COMMANDS.items():
        table.add_row(f"stoi {cmd}", desc)

    console.print(table)
    console.print()


# ── 入口 ─────────────────────────────────────────────────────────────────────
def main():
    args = sys.argv[1:]

    if not args:
        cmd_help()
        return

    cmd = args[0].lower()
    rest = args[1:]

    cmd_map = {
        "start":   cmd_start,
        "stats":   cmd_stats,
        "blame":   cmd_blame,
        "tui":     cmd_tui,
        "trend":   cmd_trend,
        "help":    cmd_help,
        "--help":  cmd_help,
        "-h":      cmd_help,
    }

    if cmd == "analyze":
        cmd_analyze(rest)
    elif cmd == "metrics":
        cmd_metrics(rest)
    elif cmd == "report":
        cmd_report(rest)
    elif cmd == "backfill-feedback-validity":
        cmd_backfill_feedback_validity(rest)
    elif cmd == "feedback-validity":
        cmd_feedback_validity(rest)
    elif cmd in cmd_map:
        cmd_map[cmd]()
    else:
        console.print(f"[red]未知命令: {cmd}[/red]")
        cmd_help()


if __name__ == "__main__":
    main()
