"""
Claude Code Importer - 从 Claude Code 导入会话
"""

import json
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from .base import BaseImporter, Conversation, Message


class ClaudeImporter(BaseImporter):
    """Claude Code 会话导入器"""

    NAME = "claude"
    DISPLAY_NAME = "Claude Code"
    DESCRIPTION = "从 Claude Code 的 ~/.claude/history.jsonl 导入会话"
    SUPPORTED_EXTENSIONS = [".jsonl"]

    def _get_default_path(self) -> Optional[Path]:
        return Path.home() / ".claude" / "history.jsonl"

    def is_available(self) -> bool:
        return self.data_path and self.data_path.exists()

    def get_conversations(self, limit: int = 20) -> List[Conversation]:
        """从 history.jsonl 读取会话"""
        if not self.is_available():
            return []

        sessions = {}

        try:
            with open(self.data_path, 'r', encoding='utf-8') as f:
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
                                'messages': [],
                            }

                        sessions[session_id]['last_seen'] = max(
                            sessions[session_id]['last_seen'],
                            entry.get('timestamp', 0)
                        )

                        # 添加消息
                        if entry.get('display'):
                            sessions[session_id]['messages'].append(Message(
                                role='user',
                                content=entry['display'],
                                timestamp=datetime.fromtimestamp(entry.get('timestamp', 0) / 1000) if entry.get('timestamp') else None,
                            ))

                    except json.JSONDecodeError:
                        continue

        except Exception as e:
            print(f"读取 Claude 历史失败: {e}")
            return []

        # 转换为 Conversation 对象
        conversations = []
        for sid, data in sessions.items():
            conv = Conversation(
                id=sid,
                title=data['project'],
                messages=data['messages'],
                created_at=datetime.fromtimestamp(data['first_seen'] / 1000) if data['first_seen'] else None,
                updated_at=datetime.fromtimestamp(data['last_seen'] / 1000) if data['last_seen'] else None,
                source='claude',
                metadata={'project': data['project']},
            )
            conversations.append(conv)

        # 按时间排序
        conversations.sort(key=lambda x: x.updated_at or datetime.min, reverse=True)

        return conversations[:limit]

    def get_conversation(self, conversation_id: str) -> Optional[Conversation]:
        """获取单个会话"""
        conversations = self.get_conversations(limit=100)
        for conv in conversations:
            if conv.id == conversation_id:
                return conv
        return None
