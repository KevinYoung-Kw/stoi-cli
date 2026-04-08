#!/bin/bash
# STOI Skill 安装脚本

set -e

echo "🚀 安装 STOI Skill..."

# 检查 Python
if ! command -v python3 &> /dev/null; then
    echo "❌ 错误：需要 Python 3"
    exit 1
fi

# 检查环境变量
if [ -z "$DASHSCOPE_API_KEY" ]; then
    echo "⚠️ 警告：未设置 DASHSCOPE_API_KEY"
    echo "请先设置环境变量: export DASHSCOPE_API_KEY=your_key"
fi

# 安装依赖
echo "📦 安装依赖..."
pip install dashscope -q

# 创建目录
mkdir -p ~/.stoi

# 添加别名（可选）
echo ""
echo "✅ 安装完成！"
echo ""
echo "使用方式:"
echo "  python3 $(pwd)/stoi.py analyze    # 分析"
echo "  python3 $(pwd)/stoi.py tts \"test\" # 测试语音"
echo ""
echo "添加到 Claude Code:"
echo "  claude skill add $(pwd)"
