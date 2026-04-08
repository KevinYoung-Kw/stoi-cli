#!/bin/bash
# STOI Skill 安装脚本

set -e

echo "💩 安装 STOI Skill..."

# 检查 Python
if ! command -v python3 &> /dev/null; then
    echo "❌ 错误：需要 Python 3"
    exit 1
fi

# 获取脚本所在目录
STOI_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# 安装依赖
echo "📦 安装依赖..."
pip3 install -q openai rich questionary || {
    echo "⚠️  依赖安装可能需要 sudo，尝试手动安装:"
    echo "  pip3 install openai rich questionary"
}

# 创建 stoi 命令
mkdir -p ~/.local/bin

cat > ~/.local/bin/stoi << EOF
#!/bin/bash
# STOI CLI wrapper
python3 "$STOI_DIR/stoi.py" "\$@"
EOF

chmod +x ~/.local/bin/stoi

# 检查 ~/.local/bin 是否在 PATH 中
if [[ ":$PATH:" != *":$HOME/.local/bin:"* ]]; then
    echo ""
    echo "⚠️  ~/.local/bin 不在 PATH 中"
    echo "请添加以下行到你的 ~/.zshrc 或 ~/.bash_profile:"
    echo 'export PATH="$HOME/.local/bin:$PATH"'
    echo ""
    echo "然后运行: source ~/.zshrc"
else
    echo "✅ stoi 命令已安装"
fi

# 创建目录
mkdir -p ~/.stoi

echo ""
echo "✅ 安装完成！"
echo ""
echo "使用方法:"
echo "  stoi config           # 打开配置面板（支持上下键导航）"
echo "  stoi init             # 初始化"
echo "  stoi analyze <id>     # 分析会话"
echo "  stoi tts \"test\"       # 测试语音"
echo ""
echo "或者直接用 Python:"
echo "  python3 $STOI_DIR/stoi.py config"
