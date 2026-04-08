#!/usr/bin/env python3
"""
stoi_tui.py — STOI 交互式 TUI
支持选择 Agent / Session，实时查看含屎量分析
"""

import json
import os
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Optional

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, ScrollableContainer
from textual.reactive import reactive
from textual.widgets import (
    Header, Footer, Static, Label, Button,
    ListView, ListItem, RadioSet, RadioButton,
    DataTable, Rule,
)
from textual.screen import Screen
from rich.text import Text

from stoi_engine import (
    calc_stoi, SHIT_EMOJI, SHIT_THRESHOLDS,
    get_score_color, TTS_MESSAGES,
)

# ── 路径配置 ──────────────────────────────────────────────────────────────────
CLAUDE_DIR   = Path("~/.claude/projects").expanduser()
OPENCODE_DIR = Path("~/.opencode").expanduser()
GEMINI_DIR   = Path("~/.gemini/history").expanduser()
LOG_FILE     = Path("~/.stoi/sessions.jsonl").expanduser()

AGENTS = {
    "claude_code": {"name": "Claude Code",  "icon": "🤖", "dir": CLAUDE_DIR},
    "opencode":    {"name": "OpenCode",     "icon": "⚡", "dir": OPENCODE_DIR},
    "gemini":      {"name": "Gemini CLI",   "icon": "🔷", "dir": GEMINI_DIR},
    "proxy":       {"name": "STOI Proxy",   "icon": "🔌", "dir": LOG_FILE.parent},
}

SPARKLINE_CHARS = " ▁▂▃▄▅▆▇█"


def make_bar(score: float, width: int = 20) -> str:
    filled = int(score / 100 * width)
    empty  = width - filled
    if score < 30:
        char = "█"
        color = "green"
    elif score < 50:
        char = "█"
        color = "yellow"
    elif score < 75:
        char = "█"
        color = "dark_orange"
    else:
        char = "█"
        color = "red"
    return f"[{color}]{'█' * filled}[/{color}][dim]{'░' * empty}[/dim]"


def make_sparkline(values: list[float], width: int = 24) -> str:
    if not values:
        return "─" * width
    # 取最后 width 个
    vals = values[-width:]
    mn, mx = 0.0, 100.0
    result = ""
    for v in vals:
        if v == 0:
            result += "▁"
        else:
            idx = max(1, min(8, int(v / 100 * 8)))
            result += SPARKLINE_CHARS[idx]
    return result.ljust(width, " ")


def score_style(score: float) -> str:
    if score < 30:   return "bold green"
    elif score < 50: return "bold yellow"
    elif score < 75: return "bold dark_orange"
    else:            return "bold red"


OPENCODE_DB = Path("~/.local/share/opencode/opencode.db").expanduser()


def find_opencode_sessions() -> list[dict]:
    """扫描 OpenCode SQLite 数据库中的会话"""
    sessions = []
    if not OPENCODE_DB.exists():
        return sessions
    try:
        import sqlite3, json as _json
        db = sqlite3.connect(str(OPENCODE_DB))
        rows = db.execute("""
            SELECT s.id, s.title, s.time_updated,
                   COUNT(m.id) as msg_count
            FROM session s
            LEFT JOIN message m ON m.session_id = s.id
                AND json_extract(m.data, '$.role') = 'assistant'
                AND json_extract(m.data, '$.tokens.input') > 0
            GROUP BY s.id
            ORDER BY s.time_updated DESC
            LIMIT 20
        """).fetchall()
        for r in rows:
            sid, title, updated, turns = r
            sessions.append({
                "id": sid,
                "path": OPENCODE_DB,
                "name": (title or f"Session {sid[:8]}")[:35],
                "mtime": (updated or 0) / 1000,
                "turns": turns or 0,
                "agent": "opencode",
            })
        db.close()
    except Exception:
        pass
    return sessions


def find_gemini_sessions() -> list[dict]:
    """扫描 Gemini CLI 的历史 checkpoint 文件"""
    sessions = []
    gemini_dirs = [
        Path("~/.gemini/history").expanduser(),
        Path("~/.gemini").expanduser(),
    ]
    for base in gemini_dirs:
        if not base.exists():
            continue
        for f in list(base.glob("*.json")) + list(base.glob("checkpoint_*.json")):
            stat = f.stat()
            sessions.append({
                "path": f,
                "name": f.stem[:30],
                "size": stat.st_size,
                "mtime": stat.st_mtime,
                "agent": "gemini",
            })
    sessions.sort(key=lambda x: x["mtime"], reverse=True)
    return sessions[:20]


def find_claude_sessions() -> list[dict]:
    """扫描 Claude Code 的 session 文件"""
    sessions = []
    if not CLAUDE_DIR.exists():
        return sessions
    for proj_dir in CLAUDE_DIR.iterdir():
        if not proj_dir.is_dir():
            continue
        for f in proj_dir.glob("*.jsonl"):
            stat = f.stat()
            sessions.append({
                "path": f,
                "name": f"{proj_dir.name[:20]}/{f.stem[:12]}",
                "size": stat.st_size,
                "mtime": stat.st_mtime,
                "agent": "claude_code",
            })
    sessions.sort(key=lambda x: x["mtime"], reverse=True)
    return sessions[:20]


def parse_opencode_session(session_id: str) -> list[dict]:
    """从 OpenCode SQLite 读取指定 session 的 token 数据"""
    records = []
    if not OPENCODE_DB.exists():
        return records
    try:
        import sqlite3, json as _json
        db = sqlite3.connect(str(OPENCODE_DB))
        rows = db.execute("""
            SELECT data, time_created FROM message
            WHERE session_id = ?
            AND json_extract(data, '$.role') = 'assistant'
            ORDER BY time_created ASC
        """, (session_id,)).fetchall()
        for i, (data_str, ts_ms) in enumerate(rows):
            d = _json.loads(data_str)
            t = d.get("tokens", {})
            cache_info = t.get("cache", {})
            if isinstance(cache_info, dict):
                cache_read  = cache_info.get("read", 0)
                cache_write = cache_info.get("write", 0)
            else:
                cache_read = cache_write = 0
            usage = {
                "input_tokens": t.get("input", 0),
                "output_tokens": t.get("output", 0),
                "cache_read_input_tokens": cache_read,
                "cache_creation_input_tokens": cache_write,
            }
            total = usage["input_tokens"] + cache_read + cache_write
            if total == 0:
                continue
            stoi = calc_stoi(usage, turn_index=len(records))
            records.append({
                "turn": len(records),
                "ts": ts_ms or 0,
                "usage": usage,
                "stoi": stoi,
            })
        db.close()
    except Exception:
        pass
    return records


def parse_gemini_session(path: Path) -> list[dict]:
    """解析 Gemini CLI checkpoint JSON"""
    records = []
    try:
        import json as _json
        data = _json.loads(path.read_text(encoding="utf-8"))
        # Gemini checkpoint format varies — try common structures
        turns = data if isinstance(data, list) else data.get("turns", data.get("messages", []))
        for i, turn in enumerate(turns):
            usage = turn.get("usageMetadata", turn.get("usage", {}))
            if not usage:
                continue
            # Map Gemini fields to STOI standard
            input_tokens  = usage.get("promptTokenCount", usage.get("input_tokens", 0))
            output_tokens = usage.get("candidatesTokenCount", usage.get("output_tokens", 0))
            cache_read    = usage.get("cachedContentTokenCount", usage.get("cache_read_input_tokens", 0))
            stoi_usage = {
                "input_tokens": max(0, input_tokens - cache_read),
                "output_tokens": output_tokens,
                "cache_read_input_tokens": cache_read,
                "cache_creation_input_tokens": 0,
            }
            if input_tokens == 0:
                continue
            stoi = calc_stoi(stoi_usage, turn_index=len(records))
            records.append({
                "turn": len(records),
                "ts": 0,
                "usage": stoi_usage,
                "stoi": stoi,
            })
    except Exception:
        pass
    return records


def parse_session_file(path: Path, agent: str = "claude_code") -> list[dict]:
    """解析 session 文件，返回每轮的 usage 数据"""
    records = []
    try:
        with open(path, encoding="utf-8") as f:
            for i, line in enumerate(f):
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except Exception:
                    continue

                usage = None
                ts = obj.get("timestamp", 0)

                if agent == "claude_code":
                    msg = obj.get("message", {})
                    if isinstance(msg, dict) and "usage" in msg:
                        usage = msg["usage"]
                        if isinstance(ts, str):
                            try:
                                ts = datetime.fromisoformat(ts.replace("Z", "+00:00")).timestamp() * 1000
                            except Exception:
                                ts = 0

                elif agent == "opencode":
                    # OpenCode: read from SQLite, path is the DB file
                    # This branch won't be hit for line-by-line parsing
                    # OpenCode uses _parse_opencode_db instead
                    pass

                elif agent == "proxy":
                    if "usage" in obj:
                        usage = obj["usage"]
                        ts_str = obj.get("ts", "")
                        try:
                            ts = datetime.fromisoformat(ts_str).timestamp() * 1000
                        except Exception:
                            ts = 0

                if usage and (usage.get("input_tokens", 0) + usage.get("cache_read_input_tokens", 0)) > 0:
                    stoi = calc_stoi(usage, turn_index=len(records))
                    records.append({
                        "turn": len(records),
                        "ts": ts,
                        "usage": usage,
                        "stoi": stoi,
                    })
    except Exception as e:
        pass
    return records


# ── 屏幕1：Agent 选择 ─────────────────────────────────────────────────────────
class AgentSelectScreen(Screen):
    """选择要分析的 Coding Agent"""

    BINDINGS = [
        Binding("q", "quit_app", "退出"),
        Binding("enter", "select", "确认"),
    ]

    CSS = """
    AgentSelectScreen {
        background: #0D0D0D;
        align: center middle;
    }
    #agent-panel {
        width: 60;
        height: auto;
        border: solid #FFB800;
        padding: 1 2;
        background: #111111;
    }
    .agent-title {
        text-align: center;
        color: #FFB800;
        text-style: bold;
        margin-bottom: 1;
    }
    .agent-subtitle {
        text-align: center;
        color: #666666;
        margin-bottom: 1;
    }
    RadioButton {
        background: #111111;
        margin: 0 0 1 0;
    }
    RadioButton:focus {
        background: #1A1A1A;
    }
    #confirm-btn {
        margin-top: 1;
        width: 100%;
        background: #FFB800;
        color: #000000;
        text-style: bold;
    }
    #confirm-btn:hover {
        background: #FFC933;
    }
    .hint {
        color: #444444;
        text-align: center;
        margin-top: 1;
    }
    """

    def compose(self) -> ComposeResult:
        with Vertical(id="agent-panel"):
            yield Label("💩 STOI — 含屎量分析", classes="agent-title")
            yield Label("选择要分析的 Coding Agent", classes="agent-subtitle")
            yield Rule()
            with RadioSet(id="agent-radio"):
                yield RadioButton("🤖  Claude Code  (~/.claude/projects/)", id="claude_code", value=True)
                yield RadioButton("⚡  OpenCode     (~/.opencode/)", id="opencode")
                yield RadioButton("🔷  Gemini CLI   (~/.gemini/history/)", id="gemini")
                yield RadioButton("🔌  STOI Proxy   (~/.stoi/sessions.jsonl)", id="proxy")
            yield Button("→ 选择会话", id="confirm-btn", variant="primary")
            yield Label("↑↓ 移动  Space 选中  Enter 确认  Q 退出", classes="hint")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "confirm-btn":
            radio_set = self.query_one("#agent-radio", RadioSet)
            selected = str(radio_set.pressed_button.id) if radio_set.pressed_button else "claude_code"
            self.app.selected_agent = selected
            self.app.push_screen(SessionSelectScreen())

    def action_select(self) -> None:
        """Enter key triggers confirm button"""
        self._go_next()

    def on_key(self, event) -> None:
        """捕获按键，空格/回车都触发跳转（RadioButton 会消费 Enter，用 Space 也行）"""
        if event.key in ("enter", "space") and not isinstance(self.focused, Button):
            # 如果焦点不在 Button 上，空格/回车跳转
            pass  # RadioButton 处理选中；Button 处理跳转
        if event.key == "enter":
            # 无论焦点在哪，Enter 总是跳转（RadioButton 用 Space 选中）
            self._go_next()
            event.stop()

    def _go_next(self) -> None:
        radio_set = self.query_one('#agent-radio', RadioSet)
        selected = str(radio_set.pressed_button.id) if radio_set.pressed_button else 'claude_code'
        self.app.selected_agent = selected
        self.app.push_screen(SessionSelectScreen())

    def action_quit_app(self) -> None:
        self.app.exit()


# ── 屏幕2：Session 选择 ───────────────────────────────────────────────────────
class SessionSelectScreen(Screen):

    BINDINGS = [
        Binding("q", "go_back", "返回"),
        Binding("enter", "select_session", "分析"),
        Binding("escape", "go_back", "返回"),
    ]

    CSS = """
    SessionSelectScreen {
        background: #0D0D0D;
        align: center middle;
    }
    #session-panel {
        width: 80;
        height: 30;
        border: solid #FFB800;
        background: #111111;
    }
    #session-title {
        background: #1A1A1A;
        color: #FFB800;
        text-style: bold;
        padding: 0 2;
        height: 3;
        content-align: left middle;
    }
    ListView {
        height: 1fr;
        background: #0D0D0D;
    }
    ListItem {
        padding: 0 2;
        background: #0D0D0D;
        color: #CCCCCC;
    }
    ListItem:hover {
        background: #1A1A1A;
        color: white;
    }
    ListItem.--highlight {
        background: #2A1A00;
        color: #FFB800;
    }
    #session-footer {
        background: #1A1A1A;
        color: #555555;
        padding: 0 2;
        height: 3;
        content-align: left middle;
    }
    """

    def compose(self) -> ComposeResult:
        agent = AGENTS.get(self.app.selected_agent, AGENTS["claude_code"])
        yield Label(
            f"  {agent['icon']} {agent['name']} — 选择会话文件",
            id="session-title"
        )
        with ScrollableContainer(id="session-panel"):
            lv = ListView(id="session-list")
            yield lv
        yield Label(
            "  ↑↓ 移动  Enter 分析  Esc/Q 返回",
            id="session-footer"
        )

    def on_mount(self) -> None:
        self._load_sessions()

    def _load_sessions(self) -> None:
        lv = self.query_one("#session-list", ListView)
        agent = self.app.selected_agent

        if agent == "claude_code":
            sessions = find_claude_sessions()
            self.app.session_list = sessions
            for s in sessions:
                mtime = datetime.fromtimestamp(s["mtime"]).strftime("%m-%d %H:%M")
                size_kb = s["size"] // 1024
                label = f"  {mtime}  {s['name']:<30}  {size_kb:>5} KB"
                lv.append(ListItem(Label(label)))
        elif agent == "proxy":
            if LOG_FILE.exists():
                mtime = datetime.fromtimestamp(LOG_FILE.stat().st_mtime).strftime("%m-%d %H:%M")
                size_kb = LOG_FILE.stat().st_size // 1024
                label = f"  {mtime}  STOI Proxy Log{'':<20}  {size_kb:>5} KB"
                lv.append(ListItem(Label(label)))
                self.app.session_list = [{
                    "path": LOG_FILE, "agent": "proxy",
                    "name": "STOI Proxy Log", "mtime": LOG_FILE.stat().st_mtime
                }]
            else:
                lv.append(ListItem(Label("  [dim]未找到 proxy 日志，请先运行 stoi start[/dim]")))
        elif agent == "opencode":
            sessions = find_opencode_sessions()
            self.app.session_list = sessions
            if not sessions:
                lv.append(ListItem(Label("  [dim]未找到 OpenCode 会话 (~/.local/share/opencode/)[/dim]")))
            for s in sessions:
                mtime = datetime.fromtimestamp(s["mtime"]).strftime("%m-%d %H:%M")
                label = f"  {mtime}  {s['name']:<35}  {s.get('turns',0):>3} 轮"
                lv.append(ListItem(Label(label)))

        elif agent == "gemini":
            sessions = find_gemini_sessions()
            self.app.session_list = sessions
            if not sessions:
                lv.append(ListItem(Label("  [dim]未找到 Gemini CLI 会话 (~/.gemini/history/)[/dim]")))
            for s in sessions:
                mtime = datetime.fromtimestamp(s["mtime"]).strftime("%m-%d %H:%M")
                size_kb = s["size"] // 1024
                label = f"  {mtime}  {s['name']:<30}  {size_kb:>5} KB"
                lv.append(ListItem(Label(label)))

        else:
            lv.append(ListItem(Label(f"  [dim]{agent} 暂不支持[/dim]")))

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        idx = event.list_view.index
        if self.app.session_list and idx < len(self.app.session_list):
            self.app.selected_session = self.app.session_list[idx]
            self.app.push_screen(DashboardScreen())

    def action_go_back(self) -> None:
        self.app.pop_screen()


# ── 屏幕3：含屎量 Dashboard ───────────────────────────────────────────────────
class DashboardScreen(Screen):

    BINDINGS = [
        Binding("q", "go_back", "返回"),
        Binding("r", "refresh_data", "刷新"),
        Binding("s", "speak_result", "播报"),
        Binding("b", "show_blame", "Blame"),
        Binding("escape", "go_back", "返回"),
    ]

    CSS = """
    DashboardScreen {
        background: #0D0D0D;
        color: white;
    }
    #top-bar {
        height: 3;
        background: #111111;
        border-bottom: solid #FFB800;
        padding: 0 2;
        align: left middle;
    }
    #main-content {
        height: 1fr;
    }
    #left-panel {
        width: 30;
        background: #0D0D0D;
        border-right: solid #222222;
        padding: 1;
        align: center top;
    }
    #score-big {
        text-align: center;
        margin-bottom: 1;
    }
    #score-bar {
        text-align: center;
        margin-bottom: 1;
    }
    #score-level {
        text-align: center;
        margin-bottom: 2;
    }
    #stats-box {
        width: 100%;
        background: #111111;
        border: solid #222222;
        padding: 1;
        margin-bottom: 1;
    }
    #right-panel {
        width: 1fr;
        background: #0D0D0D;
        padding: 1;
    }
    #sparkline-box {
        background: #111111;
        border: solid #222222;
        padding: 1;
        margin-bottom: 1;
        height: 7;
    }
    #turns-table {
        height: 1fr;
        background: #0D0D0D;
    }
    #suggestions-box {
        background: #0F1A0F;
        border: solid #1A3A1A;
        padding: 1;
        height: 8;
    }
    #bottom-bar {
        height: 3;
        background: #111111;
        border-top: solid #222222;
        padding: 0 2;
        align: left middle;
    }
    """

    records: reactive[list] = reactive([])
    avg_score: reactive[float] = reactive(0.0)

    def compose(self) -> ComposeResult:
        session = self.app.selected_session or {}
        agent_name = AGENTS.get(self.app.selected_agent, {}).get("name", "Unknown")
        session_name = session.get("name", "未知会话")

        yield Static(
            f"  💩 STOI  •  {agent_name}  •  {session_name[:40]}  "
            f"[dim]按 R 刷新  S 播报  B Blame  Q 返回[/dim]",
            id="top-bar"
        )

        with Horizontal(id="main-content"):
            # 左侧面板：大字分数
            with Vertical(id="left-panel"):
                yield Static("", id="score-big")
                yield Static("", id="score-bar")
                yield Static("", id="score-level")
                with Vertical(id="stats-box"):
                    yield Static("", id="stats-content")
                yield Static("", id="suggestions-box")

            # 右侧面板：趋势 + 明细表
            with Vertical(id="right-panel"):
                with Vertical(id="sparkline-box"):
                    yield Static("[bold #FFB800]多轮含屎量趋势[/bold #FFB800]", id="sparkline-title")
                    yield Static("", id="sparkline-display")
                    yield Static("", id="sparkline-stats")
                yield Static("[bold #FFB800]对话轮次明细[/bold #FFB800]")
                yield DataTable(id="turns-table")

        yield Static("", id="bottom-bar")

    def on_mount(self) -> None:
        # 初始化表格
        table = self.query_one("#turns-table", DataTable)
        table.add_columns("轮次", "时间", "含屎量", "缓存命中", "输入", "输出", "状态")
        self._load_data()

    def _load_data(self) -> None:
        session = self.app.selected_session
        if not session:
            return

        agent = session.get("agent", self.app.selected_agent)
        path  = session.get("path")

        if agent == "opencode":
            # OpenCode: parse from SQLite by session ID
            self.records = parse_opencode_session(session.get("id", ""))
        elif agent == "gemini":
            self.records = parse_gemini_session(Path(path))
        else:
            self.records = parse_session_file(Path(path), agent)

        self._update_display()

    def _update_display(self) -> None:
        session = self.app.selected_session or {}
        records = self.records
        if not records:
            self.query_one("#score-big", Static).update("[dim]暂无数据[/dim]")
            return

        # 过滤掉基准轮，只算有效轮次
        scored = [r for r in records if not r["stoi"].get("is_baseline", False)]
        if not scored:
            scored = records  # fallback

        avg_score = sum(r["stoi"]["stoi_score"] for r in scored) / len(scored)
        self.avg_score = avg_score

        # 确定等级
        level = "DEEP_SHIT"
        for lvl, (lo, hi) in SHIT_THRESHOLDS.items():
            if lo <= avg_score < hi:
                level = lvl
                break

        emoji = {"CLEAN": "✅", "MILD_SHIT": "🟡", "SHIT_OVERFLOW": "🟠", "DEEP_SHIT": "💩"}.get(level, "")
        color = get_score_color(avg_score)

        # 大字分数
        self.query_one("#score-big", Static).update(
            f"[{color}]{'':>2}{avg_score:>5.1f}%[/{color}]"
        )
        self.query_one("#score-bar", Static).update(make_bar(avg_score, 22))
        self.query_one("#score-level", Static).update(
            f"[{color}]{emoji} {level}[/{color}]"
        )

        # 统计数字
        total_input  = sum(r["stoi"]["input_tokens"] for r in records)
        total_read   = sum(r["stoi"]["cache_read"] for r in records)
        total_wasted = sum(r["stoi"]["wasted_tokens"] for r in records)
        total_out    = sum(r["stoi"]["output_tokens"] for r in records)
        avg_hit = sum(r["stoi"]["cache_hit_rate"] for r in scored) / max(len(scored), 1)

        stats_text = (
            f"[dim]总轮次[/dim]  [white]{len(records):>6}[/white]\n"
            f"[dim]有效轮[/dim]  [white]{len(scored):>6}[/white]\n"
            f"[dim]缓存命中[/dim] [{get_score_color(100-avg_hit)}]{avg_hit:>5.1f}%[/{get_score_color(100-avg_hit)}]\n"
            f"[dim]总输入[/dim]  [white]{total_input/1e6:>5.1f}M[/white] tokens\n"
            f"[dim]总输出[/dim]  [white]{total_out/1e3:>5.1f}K[/white] tokens\n"
            f"[dim]浪费量[/dim]  [red]{total_wasted/1e6:>5.1f}M[/red] tokens"
        )
        self.query_one("#stats-content", Static).update(stats_text)

        # 改进建议
        suggestions = self._gen_suggestions(avg_score, avg_hit, records)
        sug_text = "[bold #FFB800]改进建议[/bold #FFB800]\n" + "\n".join(suggestions[:4])
        self.query_one("#suggestions-box", Static).update(sug_text)

        # Sparkline 趋势
        all_scores = [r["stoi"]["stoi_score"] for r in records]
        spark = make_sparkline(all_scores, 40)
        self.query_one("#sparkline-display", Static).update(
            f"[#FFB800]{spark}[/#FFB800]"
        )
        if len(all_scores) >= 2:
            trend = all_scores[-1] - all_scores[0]
            trend_str = f"[red]↑ +{trend:.1f}%[/red]" if trend > 5 else f"[green]↓ {trend:.1f}%[/green]" if trend < -5 else "[white]→ 稳定[/white]"
            self.query_one("#sparkline-stats", Static).update(
                f"[dim]最新:[/dim] [{get_score_color(all_scores[-1])}]{all_scores[-1]:.1f}%[/{get_score_color(all_scores[-1])}]  "
                f"[dim]均值:[/dim] [{get_score_color(avg_score)}]{avg_score:.1f}%[/{get_score_color(avg_score)}]  "
                f"[dim]趋势:[/dim] {trend_str}"
            )

        # 轮次明细表
        table = self.query_one("#turns-table", DataTable)
        table.clear()
        for r in records[-15:]:  # 最近15轮
            s = r["stoi"]
            ts = datetime.fromtimestamp(r["ts"]/1000).strftime("%H:%M:%S") if r["ts"] else "--"
            score_str = f"{s['stoi_score']:.1f}%"
            hit_str   = f"{s['cache_hit_rate']:.1f}%"
            inp_str   = f"{s['input_tokens']/1000:.1f}K"
            out_str   = f"{s['output_tokens']/1000:.1f}K"
            note      = s.get("note", "") or {"CLEAN": "✅", "MILD_SHIT": "🟡", "SHIT_OVERFLOW": "🟠", "DEEP_SHIT": "💩"}.get(s["level"], "")
            if s.get("is_baseline"):
                note = "[dim]基准[/dim]"
            table.add_row(str(r["turn"]+1), ts, score_str, hit_str, inp_str, out_str, note)

        # 底部状态栏
        self.query_one("#bottom-bar", Static).update(
            f"  [dim]{session.get('name','')[:40]}[/dim]  "
            f"[bold]共 {len(records)} 轮[/bold]  "
            f"含屎量均值: [{get_score_color(avg_score)}]{avg_score:.1f}%[/{get_score_color(avg_score)}]"
        )

    def _gen_suggestions(self, avg_score: float, avg_hit: float, records: list) -> list[str]:
        """基于分析结果生成改进建议"""
        suggestions = []

        # 缓存命中率低
        if avg_hit < 30:
            suggestions.append("⚠️  [yellow]缓存命中率过低[/yellow] → 运行 stoi blame 找出动态字段")
        elif avg_hit < 60:
            suggestions.append("🟡 [yellow]缓存命中率偏低[/yellow] → 检查 System Prompt 是否有时间戳/UUID")

        # 含屎量高
        if avg_score > 70:
            suggestions.append("💩 [red]含屎量严重超标[/red] → 优先修复 Cache Miss 问题")
        elif avg_score > 50:
            suggestions.append("🟠 [dark_orange]含屎量偏高[/dark_orange] → 考虑压缩上下文或清理 System Prompt")

        # 轮次多且输入 token 增长快
        if len(records) > 10:
            inputs = [r["stoi"]["input_tokens"] for r in records if not r["stoi"].get("is_baseline")]
            if len(inputs) > 5:
                growth = (inputs[-1] - inputs[0]) / max(inputs[0], 1) * 100
                if growth > 200:
                    suggestions.append(f"📈 [yellow]上下文膨胀[/yellow] {growth:.0f}% → 建议在第 {len(records)//2} 轮后压缩历史")

        if not suggestions:
            suggestions.append("✅ [green]整体含屎量正常，继续保持[/green]")

        suggestions.append("[dim]按 S 键语音播报结果，按 B 键分析造屎元凶[/dim]")
        return suggestions

    def action_refresh_data(self) -> None:
        self._load_data()

    def action_speak_result(self) -> None:
        avg = self.avg_score
        if avg >= 75:   level = "DEEP_SHIT"
        elif avg >= 50: level = "SHIT_OVERFLOW"
        elif avg >= 30: level = "MILD_SHIT"
        else:           level = "CLEAN"
        msg = TTS_MESSAGES.get(level, "")
        if msg:
            try:
                subprocess.Popen(["say", "-v", "Ting-Ting", msg])
            except Exception:
                pass

    def action_show_blame(self) -> None:
        self.app.push_screen(BlameScreen())

    def action_go_back(self) -> None:
        self.app.pop_screen()


# ── 屏幕4：Blame 分析 ─────────────────────────────────────────────────────────
class BlameScreen(Screen):

    BINDINGS = [
        Binding("q", "go_back", "返回"),
        Binding("escape", "go_back", "返回"),
    ]

    CSS = """
    BlameScreen {
        background: #0D0D0D;
        align: center middle;
    }
    #blame-panel {
        width: 80;
        height: 30;
        border: solid #FF4444;
        background: #110000;
        padding: 1 2;
    }
    #blame-title {
        color: #FF4444;
        text-style: bold;
        margin-bottom: 1;
    }
    #blame-content {
        height: 1fr;
        color: #CCCCCC;
    }
    """

    def compose(self) -> ComposeResult:
        with Vertical(id="blame-panel"):
            yield Label("🔍 stoi blame — Cache 造屎元凶分析", id="blame-title")
            yield Rule()
            yield Static(self._analyze_blame(), id="blame-content")
            yield Rule()
            yield Label("[dim]按 Q 或 Esc 返回[/dim]")

    def _analyze_blame(self) -> str:
        """分析最近 session 的 system prompt（从 Claude Code session 文件提取）"""
        from stoi_engine import l3_cache_blame

        session = self.app.selected_session
        if not session:
            return "[dim]未选择会话文件[/dim]"

        path = Path(session.get("path", ""))
        if not path.exists():
            return "[dim]文件不存在[/dim]"

        # 找 system prompt
        system_prompt = ""
        try:
            with open(path, encoding="utf-8") as f:
                for line in f:
                    obj = json.loads(line.strip())
                    msg = obj.get("message", {})
                    if isinstance(msg, dict):
                        content = msg.get("content", [])
                        if isinstance(content, list):
                            for c in content:
                                if isinstance(c, dict) and c.get("type") == "tool_result":
                                    pass
                        # 检查 system 字段
                        if "system" in obj:
                            system_prompt = obj["system"]
                            break
        except Exception:
            pass

        if not system_prompt:
            # 分析缓存模式代替
            records = parse_session_file(path, session.get("agent", "claude_code"))
            if not records:
                return "[dim]无法提取 System Prompt，请通过 proxy 模式获取更详细分析[/dim]"

            miss_turns = [r for r in records if r["stoi"]["cache_hit_rate"] < 5 and not r["stoi"].get("is_baseline")]
            hit_turns  = [r for r in records if r["stoi"]["cache_hit_rate"] > 50]

            return (
                f"[bold white]缓存模式分析[/bold white]\n\n"
                f"总轮次：{len(records)}\n"
                f"缓存完全失效轮：[red]{len(miss_turns)}[/red]\n"
                f"缓存命中良好轮：[green]{len(hit_turns)}[/green]\n\n"
                f"[yellow]提示[/yellow]：完整 Blame 分析需要 System Prompt 内容。\n"
                f"使用 STOI Proxy 模式（stoi start）可获取更详细的元凶分析。\n\n"
                f"[dim]常见造屎元凶：\n"
                f"• 时间戳注入（Claude Code 已知问题）\n"
                f"• 随机 UUID\n"
                f"• 绝对路径\n"
                f"• 动态切换 tools 列表[/dim]"
            )

        result = l3_cache_blame(system_prompt)
        culprits = result["culprits"]

        if not culprits:
            return "[green]✅ 未发现造屎元凶，System Prompt 结构干净[/green]"

        lines = [f"[bold red]发现 {len(culprits)} 个造屎元凶[/bold red]\n"]
        for c in culprits:
            sev_color = "red" if c["severity"] == "HIGH" else "yellow"
            lines.append(f"[{sev_color}]▸ {c['desc']}[/{sev_color}]  ({c['severity']})")
            lines.append(f"  原因：{c['detail']}")
            lines.append(f"  修复：[dim]{c['fix']}[/dim]")
            lines.append("")

        return "\n".join(lines)

    def action_go_back(self) -> None:
        self.app.pop_screen()


# ── 主 App ────────────────────────────────────────────────────────────────────
class STOIApp(App):
    """STOI — Shit Token On Investment"""

    TITLE = "STOI 含屎量分析"
    SCREENS = {}

    selected_agent: str = "claude_code"
    selected_session: Optional[dict] = None
    session_list: list = []

    def on_mount(self) -> None:
        self.push_screen(AgentSelectScreen())


def run_tui():
    app = STOIApp()
    app.run()


if __name__ == "__main__":
    run_tui()
