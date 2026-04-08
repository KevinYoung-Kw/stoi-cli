#!/usr/bin/env python3
"""
Claude Code 会话导入器
自动从 ~/.claude/ 目录读取会话历史并导入到 STOI 数据库
"""

import json
import sqlite3
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional


class ClaudeImporter:
    """从 Claude Code 导入会话数据"""

    CLAUDE_DIR = Path.home() / ".claude"
    HISTORY_FILE = CLAUDE_DIR / "history.jsonl"

    def __init__(self, db_path: str = "~/.stoi/stoi.db"):
        self.db_path = Path(db_path).expanduser()

    def get_recent_sessions(self, limit: int = 10) -> List[Dict]:
        """获取最近的会话列表"""
        if not self.HISTORY_FILE.exists():
            return []

        sessions = {}

        try:
            with open(self.HISTORY_FILE, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue

                    try:
                        entry = json.loads(line)
                        session_id = entry.get('sessionId')
                        if not session_id:
                            continue

                        if session_id not in sessions:
                            sessions[session_id] = {
                                'id': session_id,
                                'first_seen': entry.get('timestamp', 0),
                                'last_seen': entry.get('timestamp', 0),
                                'project': entry.get('project', 'Unknown'),
                                'message_count': 0,
                            }

                        sessions[session_id]['last_seen'] = max(
                            sessions[session_id]['last_seen'],
                            entry.get('timestamp', 0)
                        )
                        sessions[session_id]['message_count'] += 1

                    except json.JSONDecodeError:
                        continue

        except Exception as e:
            print(f"读取历史文件失败: {e}")
            return []

        # 转换为列表并按时间排序
        session_list = list(sessions.values())
        session_list.sort(key=lambda x: x['last_seen'], reverse=True)

        return session_list[:limit]

    def get_session_messages(self, session_id: str) -> List[Dict]:
        """获取指定会话的消息历史"""
        if not self.HISTORY_FILE.exists():
            return []

        messages = []

        try:
            with open(self.HISTORY_FILE, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue

                    try:
                        entry = json.loads(line)
                        if entry.get('sessionId') == session_id:
                            messages.append({
                                'role': 'user',
                                'content': entry.get('display', ''),
                                'timestamp': entry.get('timestamp', 0),
                            })
                    except json.JSONDecodeError:
                        continue

        except Exception as e:
            print(f"读取消息失败: {e}")

        return messages

    def import_to_stoi(self, session_id: str, stoi_db) -> bool:
        """将会话导入到 STOI 数据库"""
        messages = self.get_session_messages(session_id)

        if not messages:
            return False

        # 检查会话是否已存在
        existing = stoi_db.get_session(session_id)
        if existing:
            # 已存在，跳过导入
            return True

        # 创建会话
        try:
            stoi_db.create_session(session_id)
        except Exception:
            # 可能已存在，忽略错误
            pass

        # 添加消息（由于 history.jsonl 只有用户输入，我们需要模拟对话）
        for msg in messages:
            try:
                stoi_db.add_message(
                    session_id,
                    msg['role'],
                    msg['content'],
                    len(msg['content'])  # 简单的 token 估算
                )
            except Exception:
                # 可能已存在，忽略
                pass

        return True

    def format_session_info(self, session: Dict) -> str:
        """格式化会话信息"""
        # 转换时间戳
        last_time = datetime.fromtimestamp(session['last_seen'] / 1000)
        time_str = last_time.strftime("%Y-%m-%d %H:%M")

        # 缩短项目路径
        project = session['project']
        if len(project) > 40:
            project = "..." + project[-37:]

        return f"{session['id'][:8]}... | {time_str} | {session['message_count']:3d} msgs | {project}"


def list_claude_sessions(limit: int = 10):
    """列出最近的 Claude 会话"""
    importer = ClaudeImporter()
    sessions = importer.get_recent_sessions(limit)

    if not sessions:
        print("未找到 Claude 会话历史")
        print(f"检查文件是否存在: {importer.HISTORY_FILE}")
        return []

    print(f"\n💬 最近的 {len(sessions)} 个 Claude 会话:\n")
    print(f"{'ID':<12} | {'时间':<16} | {'消息':<5} | 项目")
    print("-" * 80)

    for i, session in enumerate(sessions, 1):
        info = importer.format_session_info(session)
        marker = "👉 " if i == 1 else "   "
        print(f"{marker}{i}. {info}")

    return sessions


def import_session(session_id: str, stoi_db) -> bool:
    """导入指定会话到 STOI"""
    importer = ClaudeImporter()

    # 验证会话存在
    messages = importer.get_session_messages(session_id)
    if not messages:
        print(f"未找到会话: {session_id}")
        return False

    # 导入
    success = importer.import_to_stoi(session_id, stoi_db)

    if success:
        print(f"✅ 已导入 {len(messages)} 条消息")

    return success


if __name__ == "__main__":
    # 测试
    sessions = list_claude_sessions()

    if sessions:
        print("\n要导入并分析最新会话，运行:")
        print(f"  stoi analyze {sessions[0]['id']}")
