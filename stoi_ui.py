#!/usr/bin/env python3
"""
stoi_ui.py — STOI 交互式 UI 组件
提供统一的选择器、确认框、进度展示等 UI 元素
所有需要用户选择的命令都通过这里走
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.prompt import Prompt, Confirm
from rich import box

console = Console()

CLAUDE_DIR = Path("~/.claude/projects").expanduser()
LOG_FILE   = Path("~/.stoi/sessions.jsonl").expanduser()


# ── Agent 选择 ─────────────────────────────────────────────────────────────────
def select_agent() -> Optional[str]:
    """
    第一步：选择 Coding Agent
    返回 agent key: "claude_code" | "proxy" | None（取消）
    """
    console.print()
    console.print(Panel.fit(
        "[bold #FFB800]选择要分析的 Coding Agent[/bold #FFB800]",
        border_style="#FFB800",
    ))
    console.print()

    agents = [
        ("1", "claude_code", "🤖  Claude Code",  str(CLAUDE_DIR), _count_claude_sessions()),
        ("2", "proxy",       "🔌  STOI Proxy",   str(LOG_FILE),  _count_proxy_sessions()),
        ("3", "opencode",    "⚡  OpenCode",      "~/.local/share/opencode/", _count_opencode_sessions()),
        ("4", "gemini",      "🔷  Gemini CLI",    "~/.gemini/history/",       0),
    ]

    for num, key, label, path, count in agents:
        count_str = f"[dim]{count} 个会话[/dim]" if count > 0 else "[dim]暂无数据[/dim]"
        console.print(f"  [bold]{num}[/bold]  {label:<20} {count_str}")

    console.print()
    console.print("  [dim]q  退出[/dim]")
    console.print()

    choice = Prompt.ask("请选择", choices=["1", "2", "3", "4", "q"], default="1")
    if choice == "q":
        return None

    agent_map = {"1": "claude_code", "2": "proxy", "3": "opencode", "4": "gemini"}
    return agent_map[choice]


def _count_claude_sessions() -> int:
    if not CLAUDE_DIR.exists():
        return 0
    return len(list(CLAUDE_DIR.rglob("*.jsonl")))


def _count_proxy_sessions() -> int:
    if not LOG_FILE.exists():
        return 0
    try:
        lines = [l for l in LOG_FILE.read_text().splitlines() if l.strip()]
        return len(lines)
    except Exception:
        return 0


def _count_opencode_sessions() -> int:
    try:
        import sqlite3
        db_path = Path("~/.local/share/opencode/opencode.db").expanduser()
        if not db_path.exists():
            return 0
        db = sqlite3.connect(str(db_path))
        count = db.execute("SELECT COUNT(*) FROM session").fetchone()[0]
        db.close()
        return count
    except Exception:
        return 0


# ── Session 选择 ───────────────────────────────────────────────────────────────
def select_session(agent: str) -> Optional[dict]:
    """
    第二步：列出该 agent 的 session 列表，让用户选择
    返回 session dict 或 None（取消）
    """
    sessions = _list_sessions(agent)

    if not sessions:
        console.print(f"[yellow]⚠ 未找到 {agent} 的会话记录[/yellow]")
        if agent == "claude_code":
            console.print("[dim]请先使用 Claude Code 产生一些对话[/dim]")
        elif agent == "proxy":
            console.print("[dim]请先运行 stoi start 并使用 Claude Code[/dim]")
        return None

    console.print()
    console.print(Panel.fit(
        f"[bold #FFB800]选择会话[/bold #FFB800]  [dim]{agent}  •  共 {len(sessions)} 个[/dim]",
        border_style="#FFB800",
    ))
    console.print()

    # 表格展示
    table = Table(box=box.SIMPLE, show_header=True, header_style="bold #FFB800")
    table.add_column("#",       style="bold", width=4)
    table.add_column("时间",    style="dim",  width=16)
    table.add_column("会话名",              width=36)
    table.add_column("大小",    style="dim", width=8)
    table.add_column("轮次",    style="dim", width=6)

    for i, s in enumerate(sessions[:15], 1):
        mtime = datetime.fromtimestamp(s.get("mtime", 0)).strftime("%m-%d %H:%M")
        size  = f"{s.get('size', 0)//1024}K" if s.get("size") else "—"
        turns = str(s.get("turns", "—"))
        table.add_row(str(i), mtime, s.get("name", "")[:35], size, turns)

    console.print(table)
    console.print(f"  [dim]q  返回[/dim]")
    console.print()

    max_choice = min(len(sessions), 15)
    choices = [str(i) for i in range(1, max_choice + 1)] + ["q"]
    choice = Prompt.ask(f"请选择 (1-{max_choice})", choices=choices, default="1")

    if choice == "q":
        return None

    return sessions[int(choice) - 1]


def _list_sessions(agent: str) -> list[dict]:
    """列出指定 agent 的 session"""
    if agent == "claude_code":
        return _list_claude_sessions()
    elif agent == "proxy":
        return [{"path": str(LOG_FILE), "name": "STOI Proxy Log",
                 "mtime": LOG_FILE.stat().st_mtime if LOG_FILE.exists() else 0,
                 "size": LOG_FILE.stat().st_size if LOG_FILE.exists() else 0,
                 "agent": "proxy"}]
    elif agent == "opencode":
        return _list_opencode_sessions()
    return []


def _list_claude_sessions() -> list[dict]:
    if not CLAUDE_DIR.exists():
        return []
    sessions = []
    for f in CLAUDE_DIR.rglob("*.jsonl"):
        stat = f.stat()
        proj = f.parent.name[:20]
        sessions.append({
            "path":  str(f),
            "name":  f"{proj}/{f.stem[:16]}",
            "mtime": stat.st_mtime,
            "size":  stat.st_size,
            "agent": "claude_code",
        })
    sessions.sort(key=lambda x: x["mtime"], reverse=True)
    return sessions[:20]


def _list_opencode_sessions() -> list[dict]:
    try:
        import sqlite3
        db_path = Path("~/.local/share/opencode/opencode.db").expanduser()
        if not db_path.exists():
            return []
        db = sqlite3.connect(str(db_path))
        rows = db.execute(
            "SELECT id, title, time_updated FROM session ORDER BY time_updated DESC LIMIT 15"
        ).fetchall()
        db.close()
        sessions = []
        for sid, title, updated in rows:
            sessions.append({
                "id":    sid,
                "path":  str(db_path),
                "name":  (title or f"Session {sid[:8]}")[:35],
                "mtime": (updated or 0) / 1000,
                "agent": "opencode",
            })
        return sessions
    except Exception:
        return []


# ── 分析确认 ───────────────────────────────────────────────────────────────────
def confirm_analysis(session: dict, action: str) -> bool:
    """
    第三步：展示将要执行的操作，用户确认
    action: "analyze" | "insights" | "blame"
    """
    action_labels = {
        "analyze":  "📊 含屎量分析",
        "insights": "💡 AI 深度洞察",
        "blame":    "🔍 造屎元凶定位",
    }
    label = action_labels.get(action, action)

    console.print()
    console.print(Panel(
        f"[bold white]{label}[/bold white]\n\n"
        f"  会话：[cyan]{session.get('name', '')}[/cyan]\n"
        f"  时间：[dim]{datetime.fromtimestamp(session.get('mtime', 0)).strftime('%Y-%m-%d %H:%M')}[/dim]",
        border_style="#FFB800",
        title="[bold #FFB800]确认执行[/bold #FFB800]",
    ))
    console.print()

    return Confirm.ask("开始分析？", default=True)


# ── 完整交互流程 ───────────────────────────────────────────────────────────────
def interactive_select(action: str = "analyze") -> Optional[dict]:
    """
    完整的交互选择流程：选 Agent → 选 Session → 确认
    返回 session dict 或 None
    """
    # 选 Agent
    agent = select_agent()
    if not agent:
        return None

    # 选 Session
    session = select_session(agent)
    if not session:
        return None

    # 确认
    if not confirm_analysis(session, action):
        console.print("[dim]已取消[/dim]")
        return None

    return session
