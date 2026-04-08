#!/usr/bin/env python3
"""
STOI CLI Skill - Shit Token On Investment
一个让 Claude Code 能分析自己 Token 效率的 CLI 工具，带 TTS 语音播报

Usage:
    stoi analyze <session_id>    # 分析会话并语音播报结果
    stoi blame                   # 找出 Token 刺客
    stoi stats                   # 查看统计
    stoi tts "message"           # 测试 TTS 播报
"""

import os
import sys
import json
import sqlite3
import tempfile
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, List
from dataclasses import dataclass

# DashScope for LLM evaluation
import dashscope

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
            # macOS say 命令，支持不同声音
            voices = {
                "default": "Ting-Ting",  # 中文女声
                "dramatic": "Bad",       # 戏剧化声音
                "whisper": "Whisper",    # 耳语
            }
            selected_voice = voices.get(voice, "Ting-Ting")
            cmd = ["say", "-v", selected_voice, clean_text]
        elif self.platform == "linux":
            cmd = ["espeak", clean_text]
        else:
            return  # Windows 暂不支持

        try:
            subprocess.run(cmd, check=True, capture_output=True)
        except subprocess.CalledProcessError:
            pass  # TTS 失败不影响主功能

    def _clean_text(self, text: str) -> str:
        """清理文本用于语音"""
        # 移除 emoji 和特殊字符
        import re
        # 保留中英文、数字、标点
        text = re.sub(r'[^\u4e00-\u9fa5a-zA-Z0-9，。！？,.!?\s]', '', text)
        return text[:200]  # 限制长度


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
    problem_solving: int  # 1-5
    code_quality: int     # 1-5
    information_density: int  # 1-5
    context_efficiency: int   # 1-5
    stoi_index: float     # 0-100
    waste_ratio: float    # 0-1
    grade: str            # S/A/B/C/D/F
    summary: str          # 文字总结


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
                    role TEXT,  -- user/assistant/tool
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
            conn.execute(
                "INSERT INTO sessions (id) VALUES (?)",
                (session_id,)
            )
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
            cursor = conn.execute(
                "SELECT * FROM sessions WHERE id = ?", (session_id,)
            )
            row = cursor.fetchone()
            if not row:
                return None

            # 获取消息
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
    """LLM 评估器 - 使用 DashScope"""

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
            # 返回默认评估
            return Evaluation(
                problem_solving=3, code_quality=3,
                information_density=3, context_efficiency=3,
                stoi_index=50, waste_ratio=0.5,
                grade="C", summary="评估失败，使用默认值"
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

        # 计算 STOI 指数
        weights = {
            'problem_solving': 0.35,
            'code_quality': 0.25,
            'information_density': 0.20,
            'context_efficiency': 0.20
        }

        base_score = sum(scores[k] * weights[k] for k in scores) * 20  # 转换为百分制

        # 提取总结
        summary_match = re.search(r'总结[:：]\s*(.+)', text)
        summary = summary_match.group(1)[:50] if summary_match else "无总结"

        # 计算等级
        grade = self._calculate_grade(base_score)

        return Evaluation(
            problem_solving=scores['problem_solving'],
            code_quality=scores['code_quality'],
            information_density=scores['information_density'],
            context_efficiency=scores['context_efficiency'],
            stoi_index=round(base_score, 1),
            waste_ratio=round(1 - base_score/100, 2),
            grade=grade,
            summary=summary
        )

    def _calculate_grade(self, score: float) -> str:
        """计算等级"""
        if score >= 90: return "S"
        if score >= 80: return "A"
        if score >= 60: return "B"
        if score >= 40: return "C"
        if score >= 20: return "D"
        return "F"


class STOIAnalyzer:
    """STOI 分析器"""

    def __init__(self, db: STOIDatabase, judge: LLMJudge, speaker: Speaker):
        self.db = db
        self.judge = judge
        self.speaker = speaker

    def analyze_session(self, session_id: str, dramatic: bool = False) -> str:
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

        # 生成报告
        report = self._generate_report(session, evaluation)

        # 语音播报 - 💩 特别版
        if dramatic:
            # 戏剧化播报 - 屎量警报
            if evaluation.waste_ratio > 0.6:
                intro = f"警报！检测到屎山！等级{evaluation.grade}！建议立即清理！"
                self.speaker.speak(intro, voice="dramatic")
                self.speaker.speak(f"纯净度{evaluation.stoi_index}分，含屎量{evaluation.waste_ratio * 100:.0f}%。注意，你的 Token 正在变成屎！")
            else:
                intro = f"分析完成！等级{evaluation.grade}，相对清新！"
                self.speaker.speak(intro)
                self.speaker.speak(f"纯净度{evaluation.stoi_index}分，含屎量{evaluation.waste_ratio * 100:.0f}%。继续保持！")
        else:
            # 普通播报 - 也带点 💩 味
            shit_comment = "清新脱俗" if evaluation.waste_ratio < 0.2 else "略有屎味" if evaluation.waste_ratio < 0.4 else "屎量可观"
            self.speaker.speak(f"分析完成。等级{evaluation.grade}，{shit_comment}。{evaluation.summary}")

        return report

    def _generate_report(self, session: Session, eval: Evaluation) -> str:
        """生成文字报告 - 💩 特别版"""
        shit_bar = self._shit_meter(eval.waste_ratio)

        lines = [
            "=" * 50,
            "💩 STOI 屎量分析报告",
            "=" * 50,
            "",
            f"会话ID: {session.id}",
            f"会话时长: {self._format_duration(session.start_time)}",
            "",
            "【💩 屎量指数】",
            f"  纯净度: {eval.stoi_index}/100 (越高越好)",
            f"  等级: {self._grade_emoji(eval.grade)} ({eval.grade})",
            f"  含屎量: {eval.waste_ratio * 100:.1f}%",
            f"  屎量评级: {shit_bar}",
            "",
            "【💩 维度分析】",
            f"  问题解决度: {'💎' * eval.problem_solving}{'💩' * (5-eval.problem_solving)} ({eval.problem_solving}/5)",
            f"  代码质量: {'💎' * eval.code_quality}{'💩' * (5-eval.code_quality)} ({eval.code_quality}/5)",
            f"  信息密度: {'💎' * eval.information_density}{'💩' * (5-eval.information_density)} ({eval.information_density}/5)",
            f"  上下文效率: {'💎' * eval.context_efficiency}{'💩' * (5-eval.context_efficiency)} ({eval.context_efficiency}/5)",
            "",
            "【🤖 AI屎评】",
            f"  {eval.summary}",
            "",
            self._generate_shit_advice(eval.waste_ratio),
            "",
            "=" * 50,
        ]

        return "\n".join(lines)

    def _grade_emoji(self, grade: str) -> str:
        """等级表情 - 💩 越多代表越屎（逆向表达）"""
        # 💩 越多 = 越屎 = 效率越低
        shit_scale = {
            "S": "💎",      # 钻石级（无屎，极致）
            "A": "🌟",      # 优秀（微量）
            "B": "💩",      # 良好（少量）
            "C": "💩💩",    # 一般（中量）
            "D": "💩💩💩",  # 较差（大量）
            "F": "💩💩💩💩💩"  # 失败（屎山）
        }
        return shit_scale.get(grade, "❓")

    def _generate_shit_advice(self, waste_ratio: float) -> str:
        """根据屎量给出建议"""
        if waste_ratio < 0.2:
            return "【💎 建议】\n  太棒了！你的代码清新脱俗，继续保持！"
        elif waste_ratio < 0.4:
            return "【💨 建议】\n  略有味道，可以稍微精简一下解释。"
        elif waste_ratio < 0.6:
            return "【💩 建议】\n  开始有屎了！建议检查是否有冗余代码或废话。"
        elif waste_ratio < 0.8:
            return "【💩💩 警告】\n  屎量可观！Token 浪费严重，请优化 Prompt！"
        else:
            return "【💩💩💩💩💩 警报】\n  史无前例的屎山！建议立即重构，否则钱包会哭！"

    def _shit_meter(self, waste_ratio: float) -> str:
        """屎量计 - 可视化屎量"""
        if waste_ratio < 0.1:
            return "🌸 清新脱俗"
        elif waste_ratio < 0.3:
            return "💨 略有味道"
        elif waste_ratio < 0.5:
            return "💩 开始有屎"
        elif waste_ratio < 0.7:
            return "💩💩 屎量可观"
        elif waste_ratio < 0.9:
            return "💩💩💩 屎山一座"
        else:
            return "💩💩💩💩💩 屎无前例"

    def _format_duration(self, start: datetime) -> str:
        """格式化时长"""
        delta = datetime.now() - start
        minutes = int(delta.total_seconds() / 60)
        return f"{minutes}分钟"


def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description="STOI - Shit Token On Investment")
    parser.add_argument("command", choices=["analyze", "blame", "stats", "tts", "init"])
    parser.add_argument("--session", "-s", help="会话ID")
    parser.add_argument("--dramatic", "-d", action="store_true", help="戏剧化播报")
    parser.add_argument("--message", "-m", help="TTS消息")
    parser.add_argument("--input", "-i", help="输入JSON文件（从Claude Hook接收）")

    args = parser.parse_args()

    # 初始化组件
    db = STOIDatabase()
    speaker = Speaker()

    api_key = os.getenv("DASHSCOPE_API_KEY")
    if not api_key:
        print("错误：请设置 DASHSCOPE_API_KEY 环境变量")
        sys.exit(1)

    judge = LLMJudge(api_key)
    analyzer = STOIAnalyzer(db, judge, speaker)

    if args.command == "init":
        print("✅ STOI 初始化完成")
        print(f"数据库位置: {db.db_path}")

    elif args.command == "analyze":
        session_id = args.session or f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        # 如果从 Hook 接收输入
        if args.input:
            with open(args.input) as f:
                data = json.load(f)
                db.create_session(session_id)
                for msg in data.get("messages", []):
                    db.add_message(session_id, msg["role"], msg["content"], msg.get("tokens", 0))

        report = analyzer.analyze_session(session_id, dramatic=args.dramatic)
        print(report)

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
