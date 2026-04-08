"""
Base Importer - 所有会话导入器的基类
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, Dict, Any
from pathlib import Path


@dataclass
class Message:
    """消息数据类"""
    role: str  # 'user', 'assistant', 'system'
    content: str
    timestamp: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Conversation:
    """会话数据类"""
    id: str
    title: Optional[str] = None
    messages: List[Message] = field(default_factory=list)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    source: str = ""  # 来源：claude, kimi, openai
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def message_count(self) -> int:
        return len(self.messages)

    @property
    def last_message(self) -> Optional[Message]:
        if self.messages:
            return self.messages[-1]
        return None


class BaseImporter(ABC):
    """会话导入器基类"""

    # 子类需要覆盖这些属性
    NAME: str = ""
    DISPLAY_NAME: str = ""
    DESCRIPTION: str = ""
    SUPPORTED_EXTENSIONS: List[str] = []

    def __init__(self, data_path: Optional[Path] = None):
        self.data_path = data_path or self._get_default_path()

    @abstractmethod
    def _get_default_path(self) -> Optional[Path]:
        """获取默认数据路径"""
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """检查是否可用（数据是否存在）"""
        pass

    @abstractmethod
    def get_conversations(self, limit: int = 20) -> List[Conversation]:
        """获取会话列表"""
        pass

    @abstractmethod
    def get_conversation(self, conversation_id: str) -> Optional[Conversation]:
        """获取单个会话详情"""
        pass

    def format_conversation_info(self, conv: Conversation) -> str:
        """格式化会话信息用于显示"""
        time_str = ""
        if conv.updated_at:
            time_str = conv.updated_at.strftime("%m-%d %H:%M")
        elif conv.created_at:
            time_str = conv.created_at.strftime("%m-%d %H:%M")

        title = conv.title or conv.id[:8]
        return f"{title} | {time_str} | {conv.message_count} msgs"
