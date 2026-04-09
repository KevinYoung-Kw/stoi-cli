#!/usr/bin/env bash
set -e

REPO_URL="https://github.com/KevinYoung-Kw/stoi-cli.git"
INSTALL_DIR=""

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

info() { echo -e "${GREEN}[INFO]${NC} $1"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
err() { echo -e "${RED}[ERROR]${NC} $1"; }

# 检测是否在仓库目录内运行
if [ -f "pyproject.toml" ] && grep -q 'name = "stoi"' pyproject.toml 2>/dev/null; then
    INSTALL_DIR="."
    info "检测到本地仓库目录，直接安装..."
else
    INSTALL_DIR=$(mktemp -d)
    info "正在克隆仓库到临时目录..."
    git clone --depth 1 "$REPO_URL" "$INSTALL_DIR"
    cd "$INSTALL_DIR"
fi

# 检测首选安装工具
if command -v uv &> /dev/null; then
    info "检测到 uv，使用 uv tool install 安装..."
    uv tool install .
elif command -v pipx &> /dev/null; then
    info "检测到 pipx，使用 pipx install 安装..."
    pipx install .
else
    warn "未检测到 uv 或 pipx，回退到 pip3 install --user..."
    pip3 install --user .

    # 尝试定位 stoi 可执行文件
    STOI_BIN=""
    USER_BASE=$(python3 -m site --user-base 2>/dev/null || echo "")

    if [ -f "$USER_BASE/bin/stoi" ]; then
        STOI_BIN="$USER_BASE/bin/stoi"
    elif [ -f "$HOME/.local/bin/stoi" ]; then
        STOI_BIN="$HOME/.local/bin/stoi"
    elif [ -f "$HOME/Library/Python/3.9/bin/stoi" ]; then
        STOI_BIN="$HOME/Library/Python/3.9/bin/stoi"
    elif [ -f "$HOME/Library/Python/3.11/bin/stoi" ]; then
        STOI_BIN="$HOME/Library/Python/3.11/bin/stoi"
    elif [ -f "$HOME/Library/Python/3.12/bin/stoi" ]; then
        STOI_BIN="$HOME/Library/Python/3.12/bin/stoi"
    fi

    if [ -n "$STOI_BIN" ]; then
        info "找到 stoi 安装位置: $STOI_BIN"
        TARGET_DIR="$HOME/.local/bin"
        mkdir -p "$TARGET_DIR"

        if [ -L "$TARGET_DIR/stoi" ] || [ -e "$TARGET_DIR/stoi" ]; then
            rm -f "$TARGET_DIR/stoi"
        fi
        ln -sf "$STOI_BIN" "$TARGET_DIR/stoi"
        info "已创建软链接: $TARGET_DIR/stoi → $STOI_BIN"

        if ! command -v stoi &> /dev/null; then
            warn "命令仍不可用，请把 $TARGET_DIR 加入 PATH："
            echo "  export PATH=\"\$HOME/.local/bin:\$PATH\""
            echo "  建议将上行加入 ~/.zshrc 或 ~/.bash_profile"
        fi
    else
        err "无法自动定位 stoi 安装路径，请手动检查 pip3 安装日志。"
    fi
fi

# 验证
if command -v stoi &> /dev/null; then
    info "✅ 安装成功！"
    stoi help
else
    warn "安装完成，但 'stoi' 命令似乎不在 PATH 中。"
    echo ""
    echo "请尝试以下方式运行："
    echo "  export PATH=\"\$HOME/.local/bin:\$PATH\""
    echo "  # macOS 系统 Python 也可能是："
    echo "  export PATH=\"\$HOME/Library/Python/3.9/bin:\$PATH\""
    echo ""
    echo "或直接运行："
    echo "  python3 -m stoi help"
fi
