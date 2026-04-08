#!/usr/bin/env python3
"""
STOI TUI - Apple Design Terminal UI
使用 Textual 构建的苹果风格终端界面
简约、优雅、现代
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from datetime import datetime
from typing import Optional
from importers import BaseImporter, Conversation, Message, list_supported_importers
from importers.claude import ClaudeImporter

from config import ConfigManager, get_openai_client
from stoi import STOIDatabase, STOIAnalyzer, LLMJudge, Speaker

try:
    from textual.app import App, ComposeResult
    from textual.containers import Container, Horizontal, Vertical, Grid
    from textual.widgets import (
        Header, Footer, Static, ListView, ListItem, Label,
        Button, ProgressBar, Markdown, TabbedContent, TabPane,
        Select, Input, Checkbox
    )
    from textual.reactive import reactive
    from textual.binding import Binding
    from textual.screen import Screen
    TEXTUAL_AVAILABLE = True
except ImportError:
    TEXTUAL_AVAILABLE = False


class SessionListItem(ListItem):
    """会话列表项"""

    def __init__(self, conversation: Conversation):
        self.conversation = conversation
        time_str = ""
        if conversation.updated_at:
            time_str = conversation.updated_at.strftime("%m-%d %H:%M")
        elif conversation.created_at:
            time_str = conversation.created_at.strftime("%m-%d %H:%M")

        title = conversation.title or conversation.id[:12]
        label = f"{title:20s} │ {time_str:12s} │ {conversation.message_count:3d} msgs"
        super().__init__(Label(label))


class SessionList(Static):
    """会话列表面板"""

    sessions = reactive([])
    current_importer = reactive("claude")

    def compose(self) -> ComposeResult:
        with Vertical(classes="panel"):
            yield Label("SOURCE", classes="section-header")
            yield Select(
                [("Claude Code", "claude"), ("Kimi (Export)", "kimi"), ("OpenAI", "openai")],
                value="claude",
                id="importer-select"
            )
            yield Label("SESSIONS", classes="section-header")
            yield ListView(id="session-list")

    def on_mount(self):
        self.load_sessions()

    def on_select_changed(self, event: Select.Changed) -> None:
        """切换导入源"""
        if event.select.id == "importer-select":
            self.current_importer = event.value
            self.load_sessions()

    def load_sessions(self):
        """加载会话列表"""
        list_view = self.query_one("#session-list", ListView)
        list_view.clear()

        importer = None
        if self.current_importer == "claude":
            importer = ClaudeImporter()

        if importer and importer.is_available():
            self.sessions = importer.get_conversations(limit=20)
            for conv in self.sessions:
                list_view.append(SessionListItem(conv))
        else:
            list_view.append(ListItem(Label("No sessions found")))

    def get_selected_session(self) -> Optional[Conversation]:
        """获取选中的会话"""
        list_view = self.query_one("#session-list", ListView)
        if list_view.index is not None and 0 <= list_view.index < len(self.sessions):
            return self.sessions[list_view.index]
        return None


class GradeDisplay(Static):
    """等级显示组件"""

    grade = reactive("S")
    purity = reactive(95.0)
    waste = reactive(5.0)

    GRADE_COLORS = {
        "S": "#007AFF",  # 苹果蓝
        "A": "#34C759",  # 苹果绿
        "B": "#FF9500",  # 苹果橙
        "C": "#FF3B30",  # 苹果红
        "D": "#AF52DE",  # 紫色
        "F": "#5856D6",  # 靛蓝
    }

    def compose(self) -> ComposeResult:
        with Horizontal(classes="grade-container"):
            with Static(classes="grade-circle"):
                yield Label(self.grade, classes="grade-letter")
                yield Label("GRADE", classes="grade-label")
            with Vertical(classes="stats-container"):
                with Horizontal(classes="stat-row"):
                    yield Label("Purity", classes="stat-name")
                    yield Label(f"{self.purity:.0f}/100", classes="stat-value")
                with Horizontal(classes="stat-row"):
                    yield Label("Waste", classes="stat-name")
                    yield Label(f"{self.waste:.1f}%", classes="stat-value waste" if self.waste > 50 else "stat-value")

    def watch_grade(self, grade: str):
        """等级变化时更新颜色"""
        try:
            circle = self.query_one(".grade-circle", Static)
            color = self.GRADE_COLORS.get(grade, "#007AFF")
            circle.styles.background = color
        except Exception:
            pass  # 组件可能还未挂载


class DimensionBar(Static):
    """维度进度条"""

    def __init__(self, name: str, score: int):
        self.dim_name = name
        self.score = score
        super().__init__()

    def compose(self) -> ComposeResult:
        with Horizontal(classes="dimension-row"):
            yield Label(self.dim_name, classes="dim-name")
            yield ProgressBar(total=5, value=self.score, classes="dim-bar")
            yield Label(f"{self.score}/5", classes="dim-score")


class AnalysisPanel(Static):
    """分析面板"""

    def compose(self) -> ComposeResult:
        with Vertical(classes="panel"):
            yield Label("ANALYSIS", classes="section-header")

            with Horizontal(classes="button-row"):
                yield Button("Analyze", id="btn-analyze", variant="primary")
                yield Button("Analyze + Speak", id="btn-speak", variant="primary")
                yield Button("Refresh", id="btn-refresh", variant="default")

            with Vertical(classes="result-area"):
                yield GradeDisplay(id="grade-display")

                yield Label("DIMENSIONS", classes="section-header")
                with Vertical(id="dimensions-container"):
                    yield DimensionBar("Problem Solving", 4)
                    yield DimensionBar("Code Quality", 4)
                    yield DimensionBar("Information Density", 5)
                    yield DimensionBar("Context Efficiency", 3)

                yield Label("AI EVALUATION", classes="section-header")
                yield Static("Select a session and click Analyze to see results.", id="ai-summary")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """处理按钮点击"""
        btn_id = event.button.id

        if btn_id == "btn-refresh":
            self.app.query_one(SessionList).load_sessions()
        elif btn_id in ["btn-analyze", "btn-speak"]:
            self.run_analysis(dramatic=(btn_id == "btn-speak"))

    async def run_analysis(self, dramatic: bool = False):
        """运行分析"""
        session_list = self.app.query_one(SessionList)
        conv = session_list.get_selected_session()

        if not conv:
            self.query_one("#ai-summary", Static).update("❌ Please select a session first.")
            return

        self.query_one("#ai-summary", Static).update("🔄 Analyzing...")

        # 导入到数据库
        db = STOIDatabase()
        self._import_conversation(db, conv)

        try:
            client, model = get_openai_client()
            judge = LLMJudge(client, model)

            # 获取最后一条用户消息和模拟的助手回复
            user_msg = ""
            for msg in reversed(conv.messages):
                if msg.role == "user":
                    user_msg = msg.content
                    break

            # 评估
            evaluation = judge.evaluate(user_msg, "Analysis of conversation efficiency.")

            # 更新显示
            grade_display = self.query_one("#grade-display", GradeDisplay)
            grade_display.grade = evaluation.grade
            grade_display.purity = evaluation.stoi_index
            grade_display.waste = evaluation.waste_ratio * 100

            # 更新维度
            dims_container = self.query_one("#dimensions-container", Vertical)
            dims_container.remove_children()
            dims_container.mount(DimensionBar("Problem Solving", evaluation.problem_solving))
            dims_container.mount(DimensionBar("Code Quality", evaluation.code_quality))
            dims_container.mount(DimensionBar("Information Density", evaluation.information_density))
            dims_container.mount(DimensionBar("Context Efficiency", evaluation.context_efficiency))

            # 更新总结
            advice_text = "Clean and efficient!" if evaluation.waste_ratio < 0.2 else "Getting bloated, consider optimization."
            self.query_one("#ai-summary", Static).update(f"""{evaluation.summary}

💡 Advice: {advice_text}""")

            if dramatic:
                speaker = Speaker()
                speaker.speak(f"Analysis complete! Grade {evaluation.grade}")

        except Exception as e:
            self.query_one("#ai-summary", Static).update(f"❌ Error: {str(e)}")

    def _import_conversation(self, db: STOIDatabase, conv: Conversation):
        """导入会话到数据库"""
        try:
            db.create_session(conv.id)
        except:
            pass  # 可能已存在

        for msg in conv.messages:
            try:
                db.add_message(conv.id, msg.role, msg.content, len(msg.content))
            except:
                pass


class StoiApp(App):
    """STOI TUI 主应用 - Apple Design"""

    CSS = """
    Screen { align: center middle; }

    /* Apple Design Colors */
    $apple-bg: #F5F5F7;
    $apple-card: #FFFFFF;
    $apple-text: #1D1D1F;
    $apple-secondary: #86868B;
    $apple-blue: #007AFF;
    $apple-green: #34C759;
    $apple-orange: #FF9500;
    $apple-red: #FF3B30;

    /* Layout */
    .panel {
        height: 100%;
        padding: 1 2;
    }

    .section-header {
        text-style: bold;
        color: $apple-secondary;
        padding: 1 0;
        text-align: left;
    }

    /* Grade Display */
    .grade-container {
        height: auto;
        padding: 1 0;
    }

    .grade-circle {
        width: 16;
        height: 8;
        background: $apple-blue;
        border: none;
        content-align: center middle;
    }

    .grade-letter {
        text-style: bold;
        color: white;
        text-align: center;
    }

    .grade-label {
        color: white;
        text-align: center;
        text-style: none;
    }

    .stats-container {
        width: 1fr;
        padding: 0 2;
    }

    .stat-row {
        height: 3;
    }

    .stat-name {
        width: 1fr;
        color: $apple-secondary;
    }

    .stat-value {
        color: $apple-text;
        text-style: bold;
    }

    .stat-value.waste {
        color: $apple-red;
    }

    /* Dimensions */
    .dimension-row {
        height: 3;
        padding: 0 0;
    }

    .dim-name {
        width: 20;
        color: $apple-text;
    }

    .dim-bar {
        width: 1fr;
    }

    .dim-score {
        width: 8;
        text-align: right;
        color: $apple-secondary;
    }

    /* Buttons */
    .button-row {
        height: auto;
        padding: 1 0;
    }

    Button {
        margin-right: 1;
    }

    /* Result Area */
    .result-area {
        padding: 1 0;
    }

    /* List */
    ListView {
        border: none;
        height: 1fr;
    }

    ListView:focus {
        border: none;
    }

    ListItem {
        padding: 0 1;
    }

    ListItem:hover {
        background: rgba(0, 122, 255, 0.1);
    }

    ListItem.--highlight {
        background: $apple-blue;
        color: white;
    }

    /* Select */
    Select {
        height: 3;
        margin-bottom: 1;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("r", "refresh", "Refresh"),
        Binding("a", "analyze", "Analyze"),
        Binding("s", "speak", "Speak"),
    ]

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)

        with Horizontal():
            yield SessionList()
            yield AnalysisPanel()

        yield Footer()

    def action_refresh(self):
        self.query_one(SessionList).load_sessions()

    def action_analyze(self):
        self.query_one(AnalysisPanel).run_analysis(dramatic=False)

    def action_speak(self):
        self.query_one(AnalysisPanel).run_analysis(dramatic=True)


def main():
    if not TEXTUAL_AVAILABLE:
        print("请先安装 Textual: pip3 install textual")
        sys.exit(1)

    app = StoiApp()
    app.run()


if __name__ == "__main__":
    main()
