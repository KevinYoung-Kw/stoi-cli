#!/usr/bin/env python3
"""
STOI CLI Skill - Shit Token On Investment
一个让 Claude Code 能分析自己 Token 效率的 CLI 工具，带 TTS 语音播报

Usage:
    stoi analyze <session_id>    # 分析会话并语音播报结果
    stoi analyze <session_id> --dashboard  # 使用仪表盘模式
    stoi blame                   # 找出 Token 刺客
    stoi stats                   # 查看统计
    stoi tts "message"           # 测试 TTS 播报
"""

import os
import sys
import json
import sqlite3
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, List
from dataclasses import dataclass

# DashScope for LLM evaluation
try:
    import dashscope
except ImportError:
    print("请先安装 dashscope: pip3 install dashscope")
    sys.exit(1)

# Rich UI 支持
try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.text import Text
    from rich.table import Table
    from rich import box
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False
    print("提示: 安装 rich 获得更好的界面体验: pip3 install rich")

# TTS - 使用系统 say 命令 (macOS) 或 espeak (Linux)
class Speaker:
    """语音播报器"""

    def __init__(self):
        self.enabled = True
        self.platform = sys.platform

    def speak(self, text: str, voice: str = "default"):
        """播报文本"""
        if not self.enabled:
            return

        # 清理文本，移除表情和特殊字符
        clean_text = self._clean_text(text)

        if self.platform == "darwin":  # macOS
            voices = {
                "default": "Ting-Ting",
                "dramatic": "Bad",
                "whisper": "Whisper",
            }
            selected_voice = voices.get(voice, "Ting-Ting")
            cmd = ["say", "-v", selected_voice, clean_text]
        elif self.platform == "linux":
            cmd = ["espeak", clean_text]
        else:
            return

        try:
            subprocess.run(cmd, check=True, capture_output=True)
        except subprocess.CalledProcessError:
            pass

    def _clean_text(self, text: str) -> str:
        """清理文本用于语音"""
        import re
        text = re.sub(r'[^\u4e00-\u9fa5a-zA-Z0-9，。！？,.!?\s]', '', text)
        return text[:200]


@dataclass
class Session:
    """会话数据"""
    id: str
    start_time: datetime
    messages: List[Dict]
    total_input_tokens: int = 0
    total_output_tokens: int = 0


@dataclass
class Evaluation:
    """评估结果"""
    problem_solving: int
    code_quality: int
    information_density: int
    context_efficiency: int
    stoi_index: float
    waste_ratio: float
    grade: str
    summary: str
    advice: str = ""


class STOIDatabase:
    """STOI 数据库"""

    def __init__(self, db_path: str = "~/.stoi/stoi.db"):
        self.db_path = Path(db_path).expanduser()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.init_db()

    def init_db(self):
        """初始化数据库"""
        with sqlite3.connect(self.db_path) as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS sessions (
                    id TEXT PRIMARY KEY,
                    start_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    end_time TIMESTAMP,
                    total_input_tokens INTEGER DEFAULT 0,
                    total_output_tokens INTEGER DEFAULT 0,
                    metadata TEXT
                );

                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT,
                    role TEXT,
                    content TEXT,
                    token_count INTEGER,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (session_id) REFERENCES sessions(id)
                );

                CREATE TABLE IF NOT EXISTS evaluations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT,
                    problem_solving INTEGER,
                    code_quality INTEGER,
                    information_density INTEGER,
                    context_efficiency INTEGER,
                    stoi_index REAL,
                    waste_ratio REAL,
                    grade TEXT,
                    summary TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (session_id) REFERENCES sessions(id)
                );
            """)

    def create_session(self, session_id: str) -> str:
        """创建新会话"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("INSERT INTO sessions (id) VALUES (?)", (session_id,))
        return session_id

    def add_message(self, session_id: str, role: str, content: str, token_count: int = 0):
        """添加消息"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """INSERT INTO messages (session_id, role, content, token_count)
                   VALUES (?, ?, ?, ?)""",
                (session_id, role, content, token_count)
            )

    def save_evaluation(self, session_id: str, eval_result: Evaluation):
        """保存评估结果"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """INSERT INTO evaluations
                   (session_id, problem_solving, code_quality, information_density,
                    context_efficiency, stoi_index, waste_ratio, grade, summary)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (session_id, eval_result.problem_solving, eval_result.code_quality,
                 eval_result.information_density, eval_result.context_efficiency,
                 eval_result.stoi_index, eval_result.waste_ratio, eval_result.grade,
                 eval_result.summary)
            )

    def get_session(self, session_id: str) -> Optional[Session]:
        """获取会话"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("SELECT * FROM sessions WHERE id = ?", (session_id,))
            row = cursor.fetchone()
            if not row:
                return None

            messages = conn.execute(
                "SELECT role, content, token_count FROM messages WHERE session_id = ?",
                (session_id,)
            ).fetchall()

            return Session(
                id=row[0],
                start_time=datetime.fromisoformat(row[1]) if row[1] else datetime.now(),
                messages=[{"role": m[0], "content": m[1], "tokens": m[2]} for m in messages],
                total_input_tokens=row[3] or 0,
                total_output_tokens=row[4] or 0
            )


class LLMJudge:
    """LLM 评估器"""

    EVAL_PROMPT = """你是一个严格的代码评估专家。请评估以下 AI 助手的回复质量。

评估维度（1-5分）：
1. 问题解决度：是否真正解决了用户的问题
2. 代码质量：代码是否正确、可读、符合最佳实践
3. 信息密度：是否有冗余废话，信噪比如何
4. 上下文效率：是否有效利用了上下文

请按以下格式输出：
问题解决度: X/5
代码质量: X/5
信息密度: X/5
上下文效率: X/5
总结: 一句话评价（不超过50字）
建议: 一句话改进建议
"""

    def __init__(self, api_key: str):
        dashscope.api_key = api_key
        self.model = "qwen-max"

    def evaluate(self, query: str, output: str) -> Evaluation:
        """评估对话"""
        messages = [
            {"role": "system", "content": self.EVAL_PROMPT},
            {"role": "user", "content": f"用户问题：{query[:500]}\n\nAI回复：{output[:1500]}"}
        ]

        try:
            response = dashscope.Generation.call(
                model=self.model,
                messages=messages,
                result_format="message"
            )

            result_text = response.output.choices[0].message.content
            return self._parse_evaluation(result_text)

        except Exception as e:
            print(f"评估失败: {e}", file=sys.stderr)
            return Evaluation(
                problem_solving=3, code_quality=3,
                information_density=3, context_efficiency=3,
                stoi_index=50, waste_ratio=0.5,
                grade="C", summary="评估失败，使用默认值", advice="请检查 API 配置"
            )

    def _parse_evaluation(self, text: str) -> Evaluation:
        """解析评估结果"""
        import re

        scores = {}
        patterns = {
            'problem_solving': r'问题解决度[:：]\s*(\d)',
            'code_quality': r'代码质量[:：]\s*(\d)',
            'information_density': r'信息密度[:：]\s*(\d)',
            'context_efficiency': r'上下文效率[:：]\s*(\d)',
        }

        for key, pattern in patterns.items():
            match = re.search(pattern, text)
            scores[key] = int(match.group(1)) if match else 3

        weights = {
            'problem_solving': 0.35,
            'code_quality': 0.25,
            'information_density': 0.20,
            'context_efficiency': 0.20
        }

        base_score = sum(scores[k] * weights[k] for k in scores) * 20

        summary_match = re.search(r'总结[:：]\s*(.+)', text)
        summary = summary_match.group(1)[:50] if summary_match else "无总结"

        advice_match = re.search(r'建议[:：]\s*(.+)', text)
        advice = advice_match.group(1)[:50] if advice_match else "无建议"

        grade = self._calculate_grade(base_score)

        return Evaluation(
            problem_solving=scores['problem_solving'],
            code_quality=scores['code_quality'],
            information_density=scores['information_density'],
            context_efficiency=scores['context_efficiency'],
            stoi_index=round(base_score, 1),
            waste_ratio=round(1 - base_score/100, 2),
            grade=grade,
            summary=summary,
            advice=advice
        )

    def _calculate_grade(self, score: float) -> str:
        """计算等级"""
        if score >= 90: return "S"
        if score >= 80: return "A"
        if score >= 60: return "B"
        if score >= 40: return "C"
        if score >= 20: return "D"
        return "F"


class RichUIRenderer:
    """Rich UI 渲染器 - 提供美观的终端界面"""

    def __init__(self):
        self.console = Console()

    def get_color(self, waste_ratio: float) -> str:
        """根据 waste_ratio 返回颜色"""
        if waste_ratio < 0.2: return "bright_cyan"
        elif waste_ratio < 0.4: return "bright_green"
        elif waste_ratio < 0.6: return "bright_yellow"
        elif waste_ratio < 0.8: return "yellow"
        else: return "orange3"

    def get_emoji(self, waste_ratio: float) -> str:
        """获取表情"""
        if waste_ratio < 0.1: return "💎"
        elif waste_ratio < 0.3: return "🌟"
        elif waste_ratio < 0.5: return "💩"
        elif waste_ratio < 0.7: return "💩💩"
        elif waste_ratio < 0.9: return "💩💩💩"
        else: return "💩💩💩💩💩"

    def get_advice(self, waste_ratio: float) -> str:
        """获取建议"""
        if waste_ratio < 0.2:
            return "🌸 太棒了！你的代码清新脱俗，继续保持！"
        elif waste_ratio < 0.4:
            return "💨 略有味道，可以稍微精简一下。"
        elif waste_ratio < 0.6:
            return "💩 开始有屎了！建议检查是否有废话。"
        elif waste_ratio < 0.8:
            return "💩💩 屎量可观！Token 浪费严重，请优化！"
        else:
            return "💩💩💩💩💩 史无前例的屎山！建议立即重构！"

    def render_compact(self, session_id: str, eval_data: Evaluation):
        """简洁模式"""
        color = self.get_color(eval_data.waste_ratio)
        emoji = self.get_emoji(eval_data.waste_ratio)

        # 头部
        header_text = Text()
        header_text.append(f"会话: ", style="dim")
        header_text.append(f"{session_id}\n", style="bright_black")
        header_text.append(f"等级: ", style="dim")
        header_text.append(f"{emoji} ", style="bold")
        header_text.append(f"{eval_data.grade} ", style=f"bold {color}")
        header_text.append("    ")
        header_text.append("纯净度: ", style="dim")
        header_text.append(f"{eval_data.stoi_index:.0f}/100", style="bold bright_cyan")

        self.console.print(Panel(header_text, title="[bold]💩 STOI 分析结果[/bold]", border_style="cyan"))

        # 进度条
        width = 40
        filled = int(eval_data.waste_ratio * width)
        bar = Text()
        bar.append("💩" * filled, style=f"bold {color}")
        bar.append("░" * (width - filled), style="dim")
        bar.append(f" {eval_data.waste_ratio * 100:.1f}%", style=f"bold {color}")
        self.console.print(Panel(bar, title="含屎量", border_style=color))

        # 维度评分
        dims = [
            ("问题解决度", eval_data.problem_solving),
            ("代码质量", eval_data.code_quality),
            ("信息密度", eval_data.information_density),
            ("上下文效率", eval_data.context_efficiency),
        ]

        table = Table(show_header=False, box=None, padding=(0, 2))
        table.add_column("维度", style="cyan", width=12)
        table.add_column("评分", width=20)
        table.add_column("数值", justify="right", width=8)

        for label, score in dims:
            bar_chars = "█" * score + "░" * (5 - score)
            score_color = "bright_cyan" if score >= 4 else "yellow" if score >= 3 else "orange3"
            table.add_row(label, f"[{score_color}]{bar_chars}[/{score_color}]", f"{score}/5")

        self.console.print(Panel(table, title="[bold]💩 维度评分[/bold]", border_style="green"))

        # 评价和建议
        advice = self.get_advice(eval_data.waste_ratio)
        content = Text()
        content.append("【🤖 AI 屎评】\n", style="bold bright_yellow")
        content.append(f"{eval_data.summary}\n\n", style="italic")
        content.append("【💡 建议】\n", style="bold")
        content.append(advice, style=color)

        self.console.print(Panel(content, border_style=color))
        self.console.print()

    def render_dashboard(self, session_id: str, eval_data: Evaluation):
        """仪表盘模式"""
        color = self.get_color(eval_data.waste_ratio)
        emoji = self.get_emoji(eval_data.waste_ratio)

        # 头部
        header = Text()
        header.append("💩 STOI 屎量分析仪", style="bold bright_white")
        header.append(f"    会话: {session_id}", style="dim")
        self.console.print(Panel(header, style="on blue", box=box.SIMPLE))

        # 左侧：等级信息
        left_text = Text(justify="center")
        left_text.append(f"\n{emoji}\n", style="bold")
        left_text.append(f"{eval_data.grade}\n", style=f"bold {color}")
        left_text.append(f"\n纯净度\n", style="dim")
        left_text.append(f"{eval_data.stoi_index:.0f}", style="bold bright_cyan")
        left_text.append("/100\n\n", style="dim")
        left_text.append(f"含屎量\n", style="dim")
        left_text.append(f"{eval_data.waste_ratio * 100:.1f}%\n", style=f"bold {color}")

        # 创建布局
        from rich.layout import Layout
        layout = Layout()
        layout.split_row(
            Layout(Panel(left_text, title="[bold]💩 屎量指数[/bold]", border_style="cyan"), ratio=1),
            Layout(self._make_dimensions_table(eval_data), ratio=2)
        )
        self.console.print(layout)

        # 建议
        advice = self.get_advice(eval_data.waste_ratio)
        content = Text()
        content.append("【🤖 AI 屎评】\n", style="bold bright_yellow")
        content.append(f"{eval_data.summary}\n\n", style="italic")
        content.append("【💡 建议】\n", style="bold")
        content.append(advice, style=color)

        self.console.print(Panel(content, border_style=color))
        self.console.print()

    def _make_dimensions_table(self, eval_data: Evaluation) -> Panel:
        """创建维度表格"""
        table = Table(show_header=True, header_style="bold bright_cyan")
        table.add_column("维度", style="cyan")
        table.add_column("得分", justify="center")
        table.add_column("权重", justify="center")
        table.add_column("可视化")

        dims = [
            ("问题解决度", eval_data.problem_solving, "35%"),
            ("代码质量", eval_data.code_quality, "25%"),
            ("信息密度", eval_data.information_density, "20%"),
            ("上下文效率", eval_data.context_efficiency, "20%"),
        ]

        for label, score, weight in dims:
            visual = "💎" * score + "💩" * (5 - score)
            color = "bright_cyan" if score >= 4 else "yellow" if score >= 3 else "orange3"
            table.add_row(label, f"{score}/5", weight, f"[{color}]{visual}[/{color}]")

        return Panel(table, title="[bold]📊 维度分析[/bold]", border_style="green")


class STOIAnalyzer:
    """STOI 分析器"""

    def __init__(self, db: STOIDatabase, judge: LLMJudge, speaker: Speaker, use_rich: bool = True):
        self.db = db
        self.judge = judge
        self.speaker = speaker
        self.use_rich = use_rich and RICH_AVAILABLE
        if self.use_rich:
            self.rich_ui = RichUIRenderer()

    def analyze_session(self, session_id: str, dramatic: bool = False, dashboard: bool = False) -> str:
        """分析会话"""
        session = self.db.get_session(session_id)
        if not session:
            return f"错误：找不到会话 {session_id}"

        if not session.messages:
            return "错误：会话没有消息"

        # 找出最后一条用户查询和助手回复
        user_query = ""
        assistant_output = ""

        for msg in reversed(session.messages):
            if msg["role"] == "assistant" and not assistant_output:
                assistant_output = msg["content"]
            elif msg["role"] == "user" and not user_query:
                user_query = msg["content"]
                break

        # 评估
        evaluation = self.judge.evaluate(user_query, assistant_output)

        # 保存评估结果
        self.db.save_evaluation(session_id, evaluation)

        # 使用 Rich UI 或文本输出
        if self.use_rich:
            if dashboard:
                self.rich_ui.render_dashboard(session_id, evaluation)
            else:
                self.rich_ui.render_compact(session_id, evaluation)
        else:
            # 回退到文本输出
            print(self._generate_text_report(session_id, evaluation))

        # 语音播报
        if dramatic:
            if evaluation.waste_ratio > 0.6:
                self.speaker.speak(f"警报！检测到屎山！等级{evaluation.grade}！建议立即清理！", voice="dramatic")
            else:
                self.speaker.speak(f"分析完成！等级{evaluation.grade}，相对清新！")

        return "分析完成"

    def _generate_text_report(self, session_id: str, eval: Evaluation) -> str:
        """生成文本报告（无 Rich 时回退）"""
        lines = [
            "=" * 50,
            "💩 STOI 屎量分析报告",
            "=" * 50,
            f"会话ID: {session_id}",
            f"等级: {eval.grade}",
            f"纯净度: {eval.stoi_index}/100",
            f"含屎量: {eval.waste_ratio * 100:.1f}%",
            "",
            f"问题解决度: {eval.problem_solving}/5",
            f"代码质量: {eval.code_quality}/5",
            f"信息密度: {eval.information_density}/5",
            f"上下文效率: {eval.context_efficiency}/5",
            "",
            f"评价: {eval.summary}",
            "=" * 50,
        ]
        return "\n".join(lines)


def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description="💩 STOI - Shit Token On Investment")
    parser.add_argument("command", choices=["analyze", "blame", "stats", "tts", "init", "demo"])
    parser.add_argument("--session", "-s", help="会话ID")
    parser.add_argument("--dramatic", "-d", action="store_true", help="戏剧化播报")
    parser.add_argument("--dashboard", action="store_true", help="仪表盘模式（需安装 rich）")
    parser.add_argument("--no-rich", action="store_true", help="禁用 Rich UI")
    parser.add_argument("--message", "-m", help="TTS消息")

    args = parser.parse_args()

    # 初始化组件
    db = STOIDatabase()
    speaker = Speaker()

    api_key = os.getenv("DASHSCOPE_API_KEY")
    if not api_key and args.command not in ["tts", "init", "demo"]:
        print("错误：请设置 DASHSCOPE_API_KEY 环境变量")
        print("export DASHSCOPE_API_KEY=your_key_here")
        sys.exit(1)

    if args.command == "init":
        print("✅ STOI 初始化完成")
        print(f"数据库位置: {db.db_path}")
        print(f"Rich UI: {'可用' if RICH_AVAILABLE else '未安装（pip3 install rich）'}")

    elif args.command == "demo":
        # 创建演示数据
        session_id = f"demo_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        db.create_session(session_id)
        db.add_message(session_id, 'user', '写一个Python函数，计算斐波那契数列', 20)
        db.add_message(session_id, 'assistant', '''这是一个高效的斐波那契函数：\n\ndef fib(n):\n    a, b = 0, 1\n    for _ in range(n):\n        yield a\n        a, b = b, a + b\n\n# 使用\nprint(list(fib(10)))\n\n时间复杂度 O(n)，空间复杂度 O(1)。''', 150)

        print(f"\n🎮 STOI 演示模式")
        print(f"会话ID: {session_id}\n")

        if api_key:
            judge = LLMJudge(api_key)
            use_rich = not args.no_rich and RICH_AVAILABLE
            analyzer = STOIAnalyzer(db, judge, speaker, use_rich=use_rich)
            analyzer.analyze_session(session_id, dashboard=args.dashboard)
        else:
            print("提示: 设置 DASHSCOPE_API_KEY 可查看完整分析")
            print("export DASHSCOPE_API_KEY=sk-xxxxx")

    elif args.command == "analyze":
        session_id = args.session
        if not session_id:
            print("错误：请指定会话ID (--session)")
            sys.exit(1)

        judge = LLMJudge(api_key)
        use_rich = not args.no_rich and RICH_AVAILABLE
        analyzer = STOIAnalyzer(db, judge, speaker, use_rich=use_rich)
        analyzer.analyze_session(session_id, dramatic=args.dramatic, dashboard=args.dashboard)

    elif args.command == "tts":
        message = args.message or "STOI 测试播报"
        print(f"🗣️ 播报: {message}")
        speaker.speak(message)

    elif args.command == "blame":
        print("🔍 Token 刺客分析功能开发中...")
        print("敬请期待 Phase 2！")

    elif args.command == "stats":
        print("📈 统计功能开发中...")
        print("敬请期待 Phase 2！")


if __name__ == "__main__":
    main()
