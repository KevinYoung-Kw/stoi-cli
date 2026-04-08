#!/usr/bin/env python3
"""
Kimi Importer - 从 Kimi 导入会话

Kimi 目前不提供直接的本地存储文件访问。
支持以下导入方式:
1. 从浏览器导出 JSON
2. 从 Kimi API 获取（需要 API Key）
3. 从剪贴板粘贴
"""

import json
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from .base import BaseImporter, Conversation, Message


class KimiImporter(BaseImporter):
    """Kimi 会话导入器"""

    NAME = "kimi"
    DISPLAY_NAME = "Kimi"
    DESCRIPTION = "从 Kimi 导出文件或 API 导入会话"
    SUPPORTED_EXTENSIONS = [".json", ".md"]

    def __init__(self, data_path: Optional[Path] = None, api_key: Optional[str] = None):
        super().__init__(data_path)
        self.api_key = api_key

    def _get_default_path(self) -> Optional[Path]:
        # Kimi 没有默认本地存储路径
        # 需要用户手动导出
        return None

    def is_available(self) -> bool:
        return self.data_path and self.data_path.exists()

    def import_from_export(self, export_path: Path) -> List[Conversation]:
        """从 Kimi 导出文件导入

        Kimi 导出格式示例:
        {
            "title": "会话标题",
            "messages": [
                {"role": "user", "content": "..."},
                {"role": "assistant", "content": "..."}
            ],
            "created_at": "2024-01-01T00:00:00"
        }
        """
        conversations = []

        try:
            with open(export_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # 处理单一会话或会话列表
            if isinstance(data, list):
                for item in data:
                    conv = self._parse_conversation(item)
                    if conv:
                        conversations.append(conv)
            else:
                conv = self._parse_conversation(data)
                if conv:
                    conversations.append(conv)

        except Exception as e:
            print(f"导入 Kimi 会话失败: {e}")

        return conversations

    def _parse_conversation(self, data: dict) -> Optional[Conversation]:
        """解析单个会话"""
        try:
            messages = []
            for msg in data.get('messages', []):
                messages.append(Message(
                    role=msg.get('role', 'user'),
                    content=msg.get('content', ''),
                    timestamp=self._parse_timestamp(msg.get('timestamp')),
                ))

            created_at = self._parse_timestamp(data.get('created_at'))
            updated_at = self._parse_timestamp(data.get('updated_at'))

            return Conversation(
                id=data.get('id', str(hash(data.get('title', '')))),
                title=data.get('title', 'Untitled'),
                messages=messages,
                created_at=created_at,
                updated_at=updated_at,
                source='kimi',
            )

        except Exception as e:
            print(f"解析会话失败: {e}")
            return None

    def _parse_timestamp(self, ts) -> Optional[datetime]:
        """解析时间戳"""
        if not ts:
            return None

        if isinstance(ts, str):
            try:
                return datetime.fromisoformat(ts.replace('Z', '+00:00'))
            except:
                return None

        if isinstance(ts, (int, float)):
            return datetime.fromtimestamp(ts)

        return None

    def get_conversations(self, limit: int = 20) -> List[Conversation]:
        """获取会话列表"""
        if not self.is_available():
            return []
        return self.import_from_export(self.data_path)[:limit]

    def get_conversation(self, conversation_id: str) -> Optional[Conversation]:
        conversations = self.get_conversations(limit=100)
        for conv in conversations:
            if conv.id == conversation_id:
                return conv
        return None
