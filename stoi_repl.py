#!/usr/bin/env python3
"""
stoi_repl.py — STOI 交互式 REPL 主界面
参考 Claude Code 的交互设计：极简启动，/ 触发命令，? 展开帮助
"""

import os
import sys
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Optional

from rich.console import Console
from rich.text import Text
from rich.prompt import Prompt
from rich.live import Live
from rich.table import Table
from rich import box

console = Console(highlight=False)

LOGO_SMALL = "💩"

COMMANDS = {
    "/report":    ("分析当前 session 的含屎量",          "快速，不调用 LLM"),
    "/insights":  ("AI 深度建议（调用 LLM + 知识库）",   "需要 API key"),
    "/sessions":  ("列出并切换 session",                 "支持 claude/opencode/gemini"),
    "/compare":   ("对比两个 session 的含屎量变化",       "选 before/after"),
    "/settings":  ("配置 LLM provider 和 API key",       ""),
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


# ── 启动界面 ──────────────────────────────────────────────────────────────────
def print_welcome():
    console.clear()
    console.print()
    # Logo 行
    console.print(f"  {LOGO_SMALL}  [bold white]STOI[/bold white]  [dim]v2.0[/dim]   "
                  f"[dim]{state.status_line}[/dim]")
    console.print()
    console.print("  [dim]/ for commands · ? for shortcuts · Ctrl+D to exit[/dim]")
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
        _run_report(llm=False)

    elif cmd == "/insights":
        if not state.current_session:
            console.print("  [yellow]请先用 /sessions 选择一个 session[/yellow]")
            return True
        _run_report(llm=True)

    elif cmd.startswith("/sessions"):
        parts = cmd.split()
        agent = parts[1] if len(parts) > 1 else None
        _run_sessions(agent)

    elif cmd == "/compare":
        _run_compare()

    elif cmd == "/settings":
        from stoi_config import run_onboard
        run_onboard()

    elif cmd == "/blame":
        _run_blame()

    elif cmd == "":
        pass  # 空行不报错

    else:
        console.print(f"  [dim]未知命令: {cmd}  输入 / 查看可用命令[/dim]")

    return True


def _run_report(llm: bool = False):
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

    if llm and report.llm_suggestions:
        console.print()
        console.print("  [bold #FFB800]💡 AI 改进建议[/bold #FFB800]  [dim](来自知识库)[/dim]")
        console.print()
        for s in report.llm_suggestions:
            # 清理 markdown 格式，终端友好输出
            clean = s.replace("**", "").replace("*", "")
            for line in clean.strip().splitlines():
                if line.strip():
                    console.print(f"  {line}")
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
        console.print("  [bold #FFB800]选择 Agent[/bold #FFB800]")
        console.print()
        for i, (key, name, items) in enumerate(agents_available, 1):
            count = len(items)
            console.print(f"  [bold]{i}[/bold]  {name}  [dim]{count} 个 session[/dim]")
        console.print()
        choice = Prompt.ask("  请选择", choices=[str(i) for i in range(1, len(agents_available)+1)], default="1")
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

    display_sessions = sessions[:15] if isinstance(sessions[0], Path) else sessions[:15]

    for i, s in enumerate(display_sessions[:10], 1):
        if isinstance(s, Path):
            mtime = datetime.fromtimestamp(s.stat().st_mtime).strftime("%m-%d %H:%M")
            name  = f"{s.parent.name[:16]}/{s.stem[:16]}"
            size  = f"{s.stat().st_size//1024}K"
            is_current = (state.current_session == s)
        else:
            mtime = datetime.fromtimestamp((s.get("updated") or 0)/1000).strftime("%m-%d %H:%M")
            name  = s.get("title", "")[:35]
            size  = ""
            is_current = False

        marker = "[green]●[/green]" if is_current else " "
        table.add_row(f"{marker}{i}", mtime, name, size)

    console.print(table)
    console.print()

    choices = [str(i) for i in range(1, min(len(display_sessions), 10)+1)] + ["q"]
    choice = Prompt.ask(f"  选择 session (1-{len(display_sessions[:10])}, q=取消)",
                        choices=choices, default="1")

    if choice == "q":
        return

    idx = int(choice) - 1
    if isinstance(display_sessions[idx], Path):
        state.current_session = display_sessions[idx]
        state.current_agent   = selected_agent
        s = display_sessions[idx]
        state.session_name = f"{s.parent.name[:16]}/{s.stem[:12]}"
    else:
        # OpenCode session
        state.current_session = Path("~/.local/share/opencode/opencode.db").expanduser()
        state.current_agent   = "opencode"
        state.session_name    = display_sessions[idx].get("title", "")[:30]

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
    b_choice = Prompt.ask("  选择", choices=[str(i) for i in range(1, min(len(files),10)+1)], default="2")

    console.print()
    console.print("  [dim]After（优化后）：[/dim]")
    _show_session_mini_list(files)
    a_choice = Prompt.ask("  选择", choices=[str(i) for i in range(1, min(len(files),10)+1)], default="1")

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
        readline.parse_and_bind("tab: complete")

    except ImportError:
        history_file = None

    while True:
        try:
            # 提示符：当前 session 名
            session_hint = f"[dim]{state.session_name}[/dim] " if state.session_name else ""
            console.print(f"  {session_hint}", end="")
            raw = input("> ").strip()

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
            if raw.startswith("/"):
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
