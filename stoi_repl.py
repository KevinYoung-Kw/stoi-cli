#!/usr/bin/env python3
"""
stoi_repl.py — STOI 交互式 REPL 主界面
参考 Claude Code 的交互设计：极简启动，/ 触发命令，? 展开帮助
"""

import json
import os
import sys
import subprocess
import shutil
from pathlib import Path
from datetime import datetime
from typing import Optional

from rich.console import Console
from rich.text import Text
def _ask(prompt_text: str, choices: list = None, default: str = "") -> str:
    """readline 兼容的输入，支持 Tab/上下键历史"""
    if choices:
        hint = f"[{'/'.join(choices[:6])}{'...' if len(choices)>6 else ''}]"
        try:
            val = input(f"  {prompt_text} {hint}: ").strip() or default
            return val if (not choices or val in choices) else default
        except (EOFError, KeyboardInterrupt):
            return "q" if "q" in (choices or []) else default
    else:
        try:
            return input(f"  {prompt_text}: ").strip() or default
        except (EOFError, KeyboardInterrupt):
            return default
from rich.live import Live
from rich.table import Table
from rich import box

console = Console(highlight=False)

LOGO = r"""
 ███████╗████████╗ ██████╗ ██╗
 ██╔════╝╚══██╔══╝██╔═══██╗██║
 ███████╗   ██║   ██║   ██║██║
 ╚════██║   ██║   ██║   ██║██║
 ███████║   ██║   ╚██████╔╝██║
 ╚══════╝   ╚═╝    ╚═════╝ ╚═╝"""

COMMANDS = {
    "/report":    ("分析当前 session 的含屎量",          "快速，不调用 LLM"),
    "/insights":  ("AI 深度建议（调用 LLM + 知识库）",   "需要 API key"),
    "/sessions":  ("列出并切换 session",                 "支持 claude/opencode/gemini"),
    "/status":    ("查看实时监控状态",                    "需先运行 stoi start"),
    "/compare":   ("对比两个 session 的含屎量变化",       "选 before/after"),
    "/settings":  ("配置 LLM provider 和 API key",       ""),
    "/output":    ("输出质量分析（Yapping/重复/多方案检测）",   "需先运行 stoi start"),
    "/overview":  ("全局 Token 效率报告（全部历史 session）",    "比 /report 更全面"),
    "/setup":     ("一键配置 MCP，让 Claude Code 直接调用 STOI", ""),
    "/blame":     ("定位 Cache Miss 的造屎元凶",          ""),
    "/?":         ("显示所有快捷键",                      ""),
    "/clear":     ("清屏",                               ""),
    "/quit":      ("退出",                               ""),
}

SHORTCUTS = [
    ("↑ ↓",         "浏览历史命令"),
    ("Tab",         "自动补全命令"),
    ("Ctrl+C",      "取消当前操作"),
    ("Ctrl+D",      "退出 STOI"),
    ("/",           "输入命令"),
    ("?",           "显示帮助"),
]

# ── 状态 ─────────────────────────────────────────────────────────────────────
class REPLState:
    def __init__(self):
        self.current_agent  = "claude_code"
        self.current_session: Optional[Path] = None
        self.session_name   = ""
        self.history        = []
        self._detect_sessions()

    def _detect_sessions(self):
        """启动时自动检测可用的 session"""
        from stoi_core import find_claude_sessions
        files = find_claude_sessions(1)
        if files:
            self.current_session = files[0]
            self.session_name = f"{files[0].parent.name[:16]}/{files[0].stem[:12]}"

    @property
    def status_line(self) -> str:
        agent_display = {
            "claude_code": "Claude Code",
            "opencode": "OpenCode",
            "gemini": "Gemini CLI",
        }.get(self.current_agent, self.current_agent)

        if self.current_session:
            return f"{agent_display} · {self.session_name}"
        return f"{agent_display} · 未选择 session"


state = REPLState()

ZH_DIGITS = "零一二三四五六七八九"


def _speak_integer_zh(num: int) -> str:
    if num == 0:
        return ZH_DIGITS[0]

    parts = []
    zero_pending = False
    remain = num
    for value, unit in ((100, "百"), (10, "十"), (1, "")):
        digit, remain = divmod(remain, value)
        if digit == 0:
            if parts and remain > 0:
                zero_pending = True
            continue
        if zero_pending:
            parts.append(ZH_DIGITS[0])
            zero_pending = False
        if value == 10 and digit == 1 and not parts:
            parts.append(unit)
        else:
            parts.append(f"{ZH_DIGITS[digit]}{unit}")
    return "".join(parts)


def _speak_percent_zh(score: float) -> str:
    normalized = f"{round(score, 1):.1f}"
    integer_str, decimal_str = normalized.split(".")
    spoken = _speak_integer_zh(int(integer_str))
    if decimal_str != "0":
        spoken += "点" + "".join(ZH_DIGITS[int(ch)] for ch in decimal_str)
    return spoken


def _broadcast_stoi_score(score: float) -> None:
    from stoi_config import load_config

    cfg = load_config()
    tts_cfg = cfg.get("tts", {})
    if not tts_cfg.get("enabled", True):
        return

    say_bin = shutil.which("say")
    if not say_bin:
        return

    voice = tts_cfg.get("voice") or "Ting-Ting"
    message = f"含屎量百分之{_speak_percent_zh(score)}"
    cmd = [say_bin, message]
    if voice:
        cmd = [say_bin, "-v", voice, message]

    try:
        subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception:
        pass


# ── 启动界面 ──────────────────────────────────────────────────────────────────
def print_welcome():
    console.clear()
    console.print(Text(LOGO, style="bold #FFB800"))
    console.print(
        f"  [bold white]Shit Token On Investment[/bold white]  [dim]v2.0[/dim]   "
        f"[dim]{state.status_line}[/dim]"
    )
    console.print()
    console.print("  [dim]/ for commands · ? for shortcuts · Ctrl+D to exit[/dim]")
    console.print("  [dim]/setup to configure MCP for Claude Code integration[/dim]")
    console.print()


def print_shortcuts():
    console.print()
    console.print("  [bold #FFB800]快捷键[/bold #FFB800]")
    console.print()
    left = SHORTCUTS[:3]
    right = SHORTCUTS[3:]
    for i in range(max(len(left), len(right))):
        l = f"  [bold]{left[i][0]:<12}[/bold] [dim]{left[i][1]}[/dim]" if i < len(left) else ""
        r = f"  [bold]{right[i][0]:<12}[/bold] [dim]{right[i][1]}[/dim]" if i < len(right) else ""
        console.print(f"{l:<40}{r}")
    console.print()
    console.print("  [bold #FFB800]命令[/bold #FFB800]")
    console.print()
    for cmd, (desc, note) in COMMANDS.items():
        note_str = f"  [dim]{note}[/dim]" if note else ""
        console.print(f"  [bold #FFB800]{cmd:<14}[/bold #FFB800] {desc}{note_str}")
    console.print()


# ── 命令处理 ──────────────────────────────────────────────────────────────────
def handle_command(cmd: str) -> bool:
    """处理 / 命令，返回 False 表示退出"""
    cmd = cmd.strip()

    if cmd in ("/quit", "/exit", "/q"):
        return False

    elif cmd == "/clear":
        print_welcome()

    elif cmd in ("/?", "/help", "?"):
        print_shortcuts()

    elif cmd == "/report":
        if not state.current_session:
            console.print("  [yellow]请先用 /sessions 选择一个 session[/yellow]")
            return True
        _run_report(llm=False, speak_summary=True)

    elif cmd == "/insights":
        if not state.current_session:
            console.print("  [yellow]请先用 /sessions 选择一个 session[/yellow]")
            return True
        _run_report(llm=True, speak_summary=False)

    elif cmd.startswith("/sessions"):
        parts = cmd.split()
        agent = parts[1] if len(parts) > 1 else None
        _run_sessions(agent)

    elif cmd == "/compare":
        _run_compare()

    elif cmd == "/settings":
        from stoi_config import run_onboard
        run_onboard()

    elif cmd == "/status":
        _run_status()

    elif cmd == "/output":
        _run_output_analysis()

    elif cmd == "/overview":
        _run_overview()

    elif cmd == "/setup":
        _run_setup()

    elif cmd == "/blame":
        _run_blame()

    elif cmd == "":
        pass  # 空行不报错

    else:
        console.print(f"  [dim]未知命令: {cmd}  输入 / 查看可用命令[/dim]")

    return True


def _run_report(llm: bool = False, speak_summary: bool = False):
    from stoi_core import analyze
    from stoi_report import render_cli

    console.print()
    with console.status("[dim]分析中...[/dim]", spinner="dots"):
        report = analyze(
            path=state.current_session,
            source=state.current_agent,
            llm_enabled=llm,
        )

    if not report.valid_turns:
        console.print("  [yellow]session 为空或无法解析[/yellow]")
        return

    render_cli(report)
    if speak_summary:
        _broadcast_stoi_score(report.avg_stoi_score)

    if llm and report.llm_suggestions:
        console.print()
        console.print("  [bold #FFB800]💡 AI 改进建议[/bold #FFB800]  [dim](基于知识库)[/dim]")
        console.print()
        for s in report.llm_suggestions:
            _render_suggestion(s)
        console.print()


def _run_sessions(filter_agent: Optional[str] = None):
    """列出 session，让用户选择"""
    from stoi_core import find_claude_sessions, find_opencode_sessions

    console.print()

    # 检测可用的 agents
    agents_available = []
    claude_files = find_claude_sessions(20)
    if claude_files:
        agents_available.append(("claude_code", "Claude Code", claude_files))

    oc_sessions = find_opencode_sessions(10)
    if oc_sessions:
        agents_available.append(("opencode", "OpenCode", oc_sessions))

    if not agents_available:
        console.print("  [yellow]未找到任何 session[/yellow]")
        console.print("  [dim]请先使用 Claude Code 或 OpenCode 产生对话[/dim]")
        return

    # 选 agent（如果有多个）
    if not filter_agent and len(agents_available) > 1:
        try:
            import questionary
            agent_choices = [
                questionary.Choice(f"{name}  ({len(items)} sessions)", value=key)
                for key, name, items in agents_available
            ]
            selected_key = questionary.select(
                "选择 Agent",
                choices=agent_choices,
                style=questionary.Style([
                    ("selected", "fg:#FFB800 bold"),
                    ("pointer", "fg:#FFB800 bold"),
                    ("question", "fg:white bold"),
                ])
            ).ask()
            if not selected_key:
                return
            selected_agent, _, sessions = next(
                (a, s, items) for a, s, items in agents_available if a == selected_key
            )
        except Exception:
            # fallback
            for i, (key, name, items) in enumerate(agents_available, 1):
                console.print(f"  [bold]{i}[/bold]  {name}  [dim]{len(items)} sessions[/dim]")
            choice = _ask("选择", choices=[str(i) for i in range(1, len(agents_available)+1)], default="1")
            selected_agent, _, sessions = agents_available[int(choice)-1]
    else:
        selected_agent, _, sessions = agents_available[0]

    # 列出该 agent 的 sessions
    console.print()
    console.print(f"  [bold #FFB800]Sessions[/bold #FFB800]  [dim]{selected_agent}[/dim]")
    console.print()

    table = Table(box=None, show_header=False, padding=(0, 1))
    table.add_column("", style="bold", width=4)
    table.add_column("时间", style="dim", width=14)
    table.add_column("名称", width=38)
    table.add_column("", style="dim", width=6)

    try:
        import questionary

        def _session_label(s, idx):
            if isinstance(s, Path):
                mtime = datetime.fromtimestamp(s.stat().st_mtime).strftime("%m-%d %H:%M")
                name  = f"{s.parent.name[:16]}/{s.stem[:14]}"
                size  = f"{s.stat().st_size//1024}K"
                marker = "● " if state.current_session == s else "  "
                return f"{marker}{mtime}  {name:<34}  {size}"
            else:
                mtime = datetime.fromtimestamp((s.get("updated") or 0)/1000).strftime("%m-%d %H:%M")
                return f"  {mtime}  {s.get('title','')[:40]}"

        session_choices = [
            questionary.Choice(_session_label(s, i), value=i)
            for i, s in enumerate(sessions[:20])
        ] + [questionary.Choice("  ─ 取消", value=-1)]

        selected_idx = questionary.select(
            f"选择 session  ({len(sessions)} 个，↑↓ 导航，Enter 确认)",
            choices=session_choices,
            use_shortcuts=False,
            style=questionary.Style([
                ("selected", "fg:#FFB800 bold"),
                ("pointer", "fg:#FFB800 bold"),
                ("question", "fg:white bold"),
                ("answer", "fg:#FFB800 bold"),
            ])
        ).ask()

        if selected_idx is None or selected_idx == -1:
            return
        choice_num = selected_idx + 1  # 1-indexed for rest of function
        # override the idx logic below
        idx = selected_idx

    except Exception:
        # fallback to number input with pagination
        page_size, page, total = 10, 0, len(sessions)
        while True:
            start, end = page * page_size, min((page+1)*page_size, total)
            table = Table(box=None, show_header=False, padding=(0,1))
            table.add_column("", width=4); table.add_column("时间", width=14, style="dim")
            table.add_column("名称", width=36); table.add_column("", width=6, style="dim")
            for i, s in enumerate(sessions[start:end], start+1):
                if isinstance(s, Path):
                    mtime = datetime.fromtimestamp(s.stat().st_mtime).strftime("%m-%d %H:%M")
                    name = f"{s.parent.name[:14]}/{s.stem[:14]}"
                    size = f"{s.stat().st_size//1024}K"
                    marker = "[green]●[/green]" if state.current_session==s else " "
                else:
                    mtime = datetime.fromtimestamp((s.get("updated") or 0)/1000).strftime("%m-%d %H:%M")
                    name, size, marker = s.get("title","")[:30], "", " "
                table.add_row(f"{marker}{i}", mtime, name, size)
            console.print(table)
            if total > page_size:
                console.print(f"  [dim]第{page+1}/{(total-1)//page_size+1}页 · n下页 p上页[/dim]\n")
            nums = [str(i) for i in range(start+1, end+1)]
            choice = _ask(f"选择(1-{total},n/p翻页,q取消)", choices=nums+["n","p","q"], default="q")
            if choice=="n" and end<total: page+=1; continue
            elif choice=="p" and page>0: page-=1; continue
            elif choice=="q": return
            else: idx=int(choice)-1; break

    if choice == "q":
        return

    idx = int(choice) - 1
    if isinstance(sessions[idx], Path):
        state.current_session = sessions[idx]
        state.current_agent   = selected_agent
        s = sessions[idx]
        state.session_name = f"{s.parent.name[:16]}/{s.stem[:12]}"
    else:
        # OpenCode session
        state.current_session = Path("~/.local/share/opencode/opencode.db").expanduser()
        state.current_agent   = "opencode"
        state.session_name    = sessions[idx].get("title", "")[:30]

    console.print(f"  [green]✓[/green] 已切换到: [white]{state.session_name}[/white]")
    console.print()


def _run_compare():
    """对比两个 session"""
    console.print()
    console.print("  [bold #FFB800]Compare[/bold #FFB800]  [dim]选择 Before / After session[/dim]")
    console.print()

    from stoi_core import find_claude_sessions, analyze
    files = find_claude_sessions(10)
    if len(files) < 2:
        console.print("  [yellow]至少需要 2 个 session 才能对比[/yellow]")
        return

    # 选 before
    console.print("  [dim]Before（优化前）：[/dim]")
    _show_session_mini_list(files)
    b_choice = _ask("  选择", choices=[str(i) for i in range(1, min(len(files),10)+1)], default="2")

    console.print()
    console.print("  [dim]After（优化后）：[/dim]")
    _show_session_mini_list(files)
    a_choice = _ask("  选择", choices=[str(i) for i in range(1, min(len(files),10)+1)], default="1")

    b_path = files[int(b_choice)-1]
    a_path = files[int(a_choice)-1]

    if b_path == a_path:
        console.print("  [yellow]请选择不同的 session[/yellow]")
        return

    with console.status("[dim]对比分析中...[/dim]", spinner="dots"):
        r_before = analyze(b_path)
        r_after  = analyze(a_path)

    from stoi_report import render_compare
    render_compare(r_before, r_after)


def _show_session_mini_list(files):
    for i, f in enumerate(files[:10], 1):
        mtime = datetime.fromtimestamp(f.stat().st_mtime).strftime("%m-%d %H:%M")
        name  = f"{f.parent.name[:14]}/{f.stem[:14]}"
        marker = "[green]●[/green]" if state.current_session == f else " "
        console.print(f"  {marker}[bold]{i}[/bold]  [dim]{mtime}[/dim]  {name}")
    console.print()


def _run_output_analysis():
    """基于 session 文件直接分析输出质量（不需要代理模式）"""
    from stoi_output_analysis import load_session_conversation, analyze_output_quality
    from stoi_core import find_claude_sessions

    console.print()

    # 直接读当前 session 文件
    session_path = state.current_session
    if not session_path or not Path(session_path).exists():
        files = find_claude_sessions(1)
        if not files:
            console.print("  [yellow]未找到 session 文件[/yellow]")
            return
        session_path = files[0]
        console.print(f"  [dim]自动选取: {Path(session_path).name}[/dim]")

    with console.status(f"[dim]读取并分析对话...[/dim]", spinner="dots"):
        records = load_session_conversation(Path(session_path))

    if not records:
        console.print("  [yellow]session 为空或无输出文本[/yellow]")
        return

    with console.status(f"[dim]分析 {len(records)} 轮输出质量...[/dim]", spinner="dots"):
        result = analyze_output_quality(records)

    if "error" in result:
        console.print(f"  [yellow]{result['error']}[/yellow]")
        return

    score = result["output_waste_score"]
    color = "green" if score < 20 else "yellow" if score < 40 else "red"

    console.print(f"  [bold #FFB800]📤 输出质量分析[/bold #FFB800]  [dim]{result['analyzed_turns']} 轮（来自代理模式）[/dim]")
    console.print()
    console.print(f"  [dim]输出浪费分[/dim]   [{color}]{score:.1f}/100[/{color}]  [dim]（越低越好）[/dim]")
    console.print(f"  [dim]Yapping 率[/dim]   [white]{result['avg_yapping_rate']*100:.1f}%[/white]  [dim]礼貌废话占比[/dim]")
    console.print(f"  [dim]重复输出率[/dim]   [white]{result['repetition_rate']*100:.1f}%[/white]  [dim]相邻轮次高度相似[/dim]")
    console.print(f"  [dim]多方案浪费[/dim]   [white]{result['multi_solution_pct']*100:.1f}%[/white]  [dim]轮次[/dim]")
    console.print(f"  [dim]过度输出率[/dim]   [white]{result['overthinking_pct']*100:.1f}%[/white]  [dim]简单问题给长回答[/dim]")
    console.print()

    if result["issues"]:
        console.print("  [bold white]发现的问题[/bold white]")
        for iss in result["issues"]:
            sev_color = "red" if iss["severity"] == "HIGH" else "yellow"
            console.print(f"  [{sev_color}]▸ {iss['detail']}[/{sev_color}]")
            console.print(f"    [dim]→ {iss['fix']}[/dim]")
    else:
        console.print("  [green]✅ 输出质量良好[/green]")
    console.print()
    console.print("  [dim]方法论来源：Yuan et al. 2026 (Graph-Based CoT Pruning), Jiang et al. 2026 (Forest of Errors)[/dim]")
    console.print()


def _run_overview():
    """全局 Token 效率报告——基于 stats-cache.json，覆盖所有历史 session"""
    from stoi_core import get_global_efficiency_report
    from datetime import datetime

    console.print()
    with console.status("[dim]读取全局统计...[/dim]", spinner="dots"):
        r = get_global_efficiency_report()

    if "error" in r:
        console.print(f"  [yellow]{r['error']}[/yellow]")
        return

    # 全局含屎量等级
    stoi = r["global_stoi"]
    hit  = r["global_hit_rate"]
    color_map = {(0,30): "green", (30,50): "yellow", (50,75): "dark_orange", (75,101): "red"}
    color = next((c for (lo,hi),c in color_map.items() if lo <= stoi < hi), "white")
    emoji = "✅" if stoi < 30 else "🟡" if stoi < 50 else "🟠" if stoi < 75 else "💩"

    console.print(f"  [bold #FFB800]💩 STOI 全局报告[/bold #FFB800]  [dim]基于 {r['total_sessions']} 个 session，{r['total_messages']:,} 条消息[/dim]")
    console.print()

    # 核心数字
    console.print(f"  [dim]全局含屎量[/dim]   [{color}]{stoi:.1f}% {emoji}[/{color}]")
    console.print(f"  [dim]缓存命中率[/dim]   [white]{hit:.1f}%[/white]  [dim]（命中越高越省钱）[/dim]")
    console.print(f"  [dim]平均 session 长度[/dim]  [white]{r['avg_session_len']:.0f}[/white] 条消息")
    console.print(f"  [dim]重复发送消息[/dim]  [yellow]{r['repeat_messages']}[/yellow] 条  [dim]（5分钟内重发同一条）[/dim]")
    console.print()

    # 模型使用情况
    console.print(f"  [bold white]模型使用效率[/bold white]")
    for m in r["model_stats"][:3]:
        hit_c = "green" if m["hit_rate"] > 70 else "yellow" if m["hit_rate"] > 40 else "red"
        console.print(f"  [dim]{m['model'][:25]:<27}[/dim] 命中率 [{hit_c}]{m['hit_rate']:>5.1f}%[/{hit_c}]  [dim]{m['input']/1e9:.2f}B input tokens[/dim]")
    console.print()

    # 最近7天趋势
    recent = r.get("recent_days", [])
    if recent:
        console.print(f"  [bold white]最近 {len(recent)} 天活动[/bold white]")
        for d in recent[-5:]:
            msgs = d.get("messageCount", 0)
            sess = d.get("sessionCount", 0)
            tools = d.get("toolCallCount", 0)
            tool_ratio = f"{tools/msgs:.2f}" if msgs > 0 else "0"
            bar_w = min(20, int(msgs / 500))
            bar = "█" * bar_w
            console.print(f"  [dim]{d['date']}[/dim]  [{color}]{bar:<20}[/{color}]  [white]{msgs:>5}[/white] msgs / [dim]{sess}[/dim] sessions  tool/msg [dim]{tool_ratio}[/dim]")
    console.print()

    # 问题总结
    issues = []
    if stoi > 50:
        issues.append(f"⚠ 全局含屎量 {stoi:.0f}%——历史上大量 token 未能命中缓存")
    if r["avg_session_len"] > 1000:
        issues.append(f"⚠ 平均 session {r['avg_session_len']:.0f} 条消息过长，建议 800 条后 /compact 或新建 session")
    if r["repeat_messages"] > 20:
        issues.append(f"⚠ {r['repeat_messages']} 条重复发送——重发前补充上下文比原样重发效果好")

    if issues:
        console.print(f"  [bold red]发现 {len(issues)} 个可优化点：[/bold red]")
        for iss in issues:
            console.print(f"  {iss}")
    else:
        console.print("  [green]✅ 整体使用模式健康[/green]")
    console.print()


def _run_setup():
    """一键配置 MCP，让 Claude Code 直接调用 STOI"""
    import shutil
    console.print()
    console.print("  [bold #FFB800]⚙ STOI MCP 配置[/bold #FFB800]")
    console.print()

    mcp_script = Path(__file__).parent / "stoi_mcp.py"
    if not mcp_script.exists():
        console.print("  [red]未找到 stoi_mcp.py[/red]")
        return

    # 检测支持的 Coding Agent
    agents_found = []
    claude_settings = Path("~/.claude/settings.json").expanduser()
    if claude_settings.exists():
        agents_found.append(("Claude Code", claude_settings))

    if not agents_found:
        console.print("  [yellow]未检测到支持的 Coding Agent[/yellow]")
        console.print(f"  [dim]手动添加：在 Claude Code settings.json 的 mcpServers 中加入 stoi[/dim]")
        _show_mcp_manual(mcp_script)
        return

    console.print("  检测到以下 Coding Agent，将自动配置 MCP：")
    console.print()
    for name, path in agents_found:
        console.print(f"  [dim]·[/dim] [white]{name}[/white]  [dim]{path}[/dim]")
    console.print()

    choice = _ask("确认配置？(y/n)", choices=["y", "n"], default="y")
    if choice != "y":
        console.print("  [dim]已取消[/dim]")
        return

    # 用 claude mcp add 命令注册（最可靠的方式）
    import subprocess
    mcp_path = str(mcp_script.resolve())
    for name, settings_path in agents_found:
        try:
            result = subprocess.run(
                ["claude", "mcp", "add", "stoi", "--", "python3", mcp_path],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0:
                console.print(f"  [green]✅ {name} MCP 配置完成（claude mcp add）[/green]")
            else:
                # Fallback: write settings.json directly
                data = json.loads(settings_path.read_text(encoding="utf-8"))
                if "mcpServers" not in data:
                    data["mcpServers"] = {}
                data["mcpServers"]["stoi"] = {
                    "command": "python3",
                    "args": [mcp_path],
                }
                settings_path.write_text(json.dumps(data, indent=2, ensure_ascii=False))
                console.print(f"  [green]✅ {name} MCP 配置完成（settings.json）[/green]")
        except Exception as e:
            console.print(f"  [red]✗ 配置失败: {e}[/red]")
            _show_mcp_manual(mcp_script)
            return

    console.print()
    console.print("  [bold white]重启 Claude Code 后，直接问它：[/bold white]")
    console.print()
    console.print('  [dim]"分析一下我最近的 Claude Code session 效率"[/dim]')
    console.print('  [dim]"我的含屎量怎么样，有什么优化建议？"[/dim]')
    console.print('  [dim]"帮我分析这段 System Prompt 有没有造成 Cache Miss"[/dim]')
    console.print()
    console.print("  Claude Code 会自动调用 STOI 工具返回分析结果。")
    console.print()


def _show_mcp_manual(mcp_script: Path):
    """显示手动配置说明"""
    console.print()
    console.print("  [bold white]手动配置方法：[/bold white]")
    console.print()
    console.print('  在 [dim]~/.claude/settings.json[/dim] 中添加：')
    console.print()
    config = {
        "mcpServers": {
            "stoi": {
                "command": "python3",
                "args": [str(mcp_script.resolve())]
            }
        }
    }
    for line in json.dumps(config, indent=2, ensure_ascii=False).splitlines():
        console.print(f"  [dim]{line}[/dim]")
    console.print()


def _run_status():
    """显示实时监控状态（需要 stoi start 先跑）"""
    import json
    stats_file = Path("~/.stoi/realtime_stats.json").expanduser()
    console.print()

    if not stats_file.exists():
        console.print("  [dim]代理未运行。运行 stoi start 开始实时监控。[/dim]")
        console.print()
        return

    try:
        stats = json.loads(stats_file.read_text())
    except Exception:
        console.print("  [red]状态文件损坏[/red]")
        return

    avg = stats.get("avg_stoi", 0)
    color_map = {"CLEAN": "green", "MILD_SHIT": "yellow", "SHIT_OVERFLOW": "dark_orange", "DEEP_SHIT": "red"}
    emoji_map = {"CLEAN": "✅", "MILD_SHIT": "🟡", "SHIT_OVERFLOW": "🟠", "DEEP_SHIT": "💩"}
    level = stats.get("current_level", "CLEAN")
    color = color_map.get(level, "white")
    emoji = emoji_map.get(level, "")

    console.print(f"  [bold #FFB800]💩 实时监控状态[/bold #FFB800]  [dim]proxy 运行中[/dim]")
    console.print()
    console.print(f"  [dim]会话开始[/dim]   {stats.get('session_start','')[:19]}")
    console.print(f"  [dim]总请求数[/dim]   [white]{stats.get('total_requests', 0)}[/white]")
    console.print(f"  [dim]平均含屎量[/dim]  [{color}]{avg:.1f}%  {emoji} {level}[/{color}]")
    console.print(f"  [dim]累计输入[/dim]   [white]{stats.get('total_input', 0):,}[/white] tokens")
    console.print(f"  [dim]累计浪费[/dim]   [red]{stats.get('total_wasted', 0):,}[/red] tokens")

    recent = stats.get("recent", [])
    if recent:
        from stoi_repl import make_sparkline  # self-import won't work, inline it
        chars = " ▁▂▃▄▅▆▇█"
        mn, mx = 0.0, 100.0
        spark = ""
        for v in recent[-20:]:
            idx = max(0, min(8, int(v / 100 * 8)))
            spark += chars[idx]
        console.print(f"  [dim]最近趋势[/dim]   [#FFB800]{spark}[/#FFB800]")
    console.print()


def _render_suggestion(text: str):
    """把 LLM 返回的 markdown 渲染成终端友好格式"""
    import re
    lines = text.strip().splitlines()
    suggestion_num = 0
    for line in lines:
        line = line.strip()
        if not line:
            continue
        # ### 标题 → 黄色标题
        if line.startswith("###"):
            title = line.lstrip("#").strip()
            console.print(f"\n  [bold #FFB800]▸ {title}[/bold #FFB800]")
        # **粗体内容** → 白色加粗
        elif line.startswith("**") and line.endswith("**"):
            content = line.strip("*")
            console.print(f"  [bold white]{content}[/bold white]")
        # **标签**: 内容 → 标签加粗
        elif re.match(r'^\*\*[^*]+\*\*[:：]', line):
            parts = re.split(r'\*\*[:：]\s*', line.replace("**", ""), 1)
            label = re.sub(r'^\*\*', '', line.split("**")[1])
            rest = line.split("**:", 1)[-1].strip() if "**:" in line else line.split("**：", 1)[-1].strip()
            console.print(f"  [bold #FFB800]{label}[/bold #FFB800]  {rest}")
        # - 列表 → 缩进
        elif line.startswith("- ") or line.startswith("* "):
            content = line[2:]
            # 去掉行内 **
            content = re.sub(r'\*\*([^*]+)\*\*', r'\1', content)
            console.print(f"    [dim]·[/dim] {content}")
        # 数字列表
        elif re.match(r'^\d+\.', line):
            content = re.sub(r'^\d+\.\s*', '', line)
            content = re.sub(r'\*\*([^*]+)\*\*', r'\1', content)
            console.print(f"    {content}")
        # 普通行
        else:
            clean = re.sub(r'\*\*([^*]+)\*\*', r'\1', line)
            clean = re.sub(r'\*([^*]+)\*', r'\1', clean)
            if clean:
                console.print(f"  {clean}")


def _run_blame():
    console.print()
    console.print("  [bold #FFB800]Blame[/bold #FFB800]  [dim]粘贴 System Prompt，找 Cache Miss 元凶[/dim]")
    console.print("  [dim]输入内容后，空行+回车结束[/dim]")
    console.print()

    lines = []
    try:
        while True:
            line = input("  ")
            if line == "" and lines and lines[-1] == "":
                break
            lines.append(line)
    except (EOFError, KeyboardInterrupt):
        pass

    prompt = "\n".join(lines).strip()
    if not prompt:
        console.print("  [dim]已取消[/dim]")
        return

    from stoi_engine import l3_cache_blame
    result = l3_cache_blame(prompt)
    culprits = result.get("culprits", [])

    if not culprits:
        console.print()
        console.print("  [green]✅ 未发现造屎元凶，System Prompt 结构干净[/green]")
    else:
        console.print()
        console.print(f"  [red]发现 {len(culprits)} 个造屎元凶：[/red]")
        for c in culprits:
            color = "red" if c["severity"] == "HIGH" else "yellow"
            console.print(f"  [{color}]▸ {c['desc']}[/{color}]  [{c['severity']}]")
            console.print(f"    [dim]{c['fix']}[/dim]")
    console.print()


# ── 主循环 ────────────────────────────────────────────────────────────────────
def run():
    print_welcome()

    try:
        import readline
        # 历史记录
        history_file = Path("~/.stoi/.repl_history").expanduser()
        history_file.parent.mkdir(parents=True, exist_ok=True)
        try:
            readline.read_history_file(str(history_file))
        except FileNotFoundError:
            pass

        # Tab 补全
        commands_list = list(COMMANDS.keys())
        def completer(text, state):
            options = [c for c in commands_list if c.startswith(text)]
            return options[state] if state < len(options) else None
        readline.set_completer(completer)
        readline.set_completer_delims(' ')
        # macOS uses libedit - needs different binding
        if 'libedit' in readline.__doc__ or readline.__doc__ is None:
            readline.parse_and_bind("bind ^I rl_complete")
        else:
            readline.parse_and_bind("tab: complete")

    except ImportError:
        history_file = None

    def _print_statusbar():
        """底部状态栏，仿 Claude Code 风格"""
        icon = "💩"
        session = state.session_name or "未选择 session"
        console.print(
            f"  [dim]─────────────────────────────────────────────────────────────────────────────[/dim]"
        )
        console.print(
            f"  [dim]{icon} In[/dim] [white]{session}[/white]  "
            f"[dim]/ commands · ? help · Ctrl+D exit[/dim]"
        )

    while True:
        try:
            _print_statusbar()
            raw = input("  ❯ ").strip()

            if history_file:
                try:
                    import readline
                    readline.append_history_file(1, str(history_file))
                except Exception:
                    pass

            # 直接输入 ? 展开帮助
            if raw == "?":
                print_shortcuts()
                continue

            # / 开头是命令
            if raw == "/":
                print_shortcuts()   # bare / shows help
            elif raw.startswith("/"):
                if not handle_command(raw):
                    break
            elif raw == "":
                continue
            else:
                console.print(f"  [dim]输入 / 使用命令，? 查看帮助[/dim]")

        except KeyboardInterrupt:
            console.print()
            console.print("  [dim]Ctrl+C — 输入 /quit 或 Ctrl+D 退出[/dim]")
        except EOFError:
            console.print()
            break

    console.print()
    console.print("  [dim]再见 🐑[/dim]")
    console.print()


if __name__ == "__main__":
    run()
