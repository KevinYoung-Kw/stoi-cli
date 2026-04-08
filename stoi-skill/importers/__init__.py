#!/usr/bin/env python3
"""
STOI Importers - 支持多种 AI 工具的会话导入
"""

from .base import BaseImporter, Conversation, Message
from .claude import ClaudeImporter

__all__ = [
    'BaseImporter',
    'Conversation',
    'Message',
    'ClaudeImporter',
]

# 注册所有导入器
IMPORTERS = {
    'claude': ClaudeImporter,
}


def get_importer(name: str):
    """获取导入器类"""
    return IMPORTERS.get(name.lower())


def list_supported_importers():
    """列出所有支持的导入器"""
    return [
        {
            'name': key,
            'display_name': cls.DISPLAY_NAME,
            'description': cls.DESCRIPTION,
        }
        for key, cls in IMPORTERS.items()
    ]
