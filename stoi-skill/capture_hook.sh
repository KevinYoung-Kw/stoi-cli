#!/bin/bash
# STOI Hook - 捕获 Claude Code 工具调用
# 这个脚本会被 Claude Code 的 PreToolUse Hook 调用

STOI_DIR="$HOME/.stoi"
SESSION_FILE="$STOI_DIR/current_session"
DB_FILE="$STOI_DIR/stoi.db"

# 读取 stdin（Hook 输入）
read -r INPUT

# 如果没有当前会话，创建一个新的
if [ ! -f "$SESSION_FILE" ]; then
    SESSION_ID="session_$(date +%Y%m%d_%H%M%S)"
    echo "$SESSION_ID" > "$SESSION_FILE"
    echo "{\"session_id\": \"$SESSION_ID\", \"messages\": []}" > "$STOI_DIR/${SESSION_ID}.json"
fi

SESSION_ID=$(cat "$SESSION_FILE")
SESSION_JSON="$STOI_DIR/${SESSION_ID}.json"

# 解析工具调用信息
TOOL_NAME=$(echo "$INPUT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('tool_name','unknown'))" 2>/dev/null || echo "unknown")

# 记录到 SQLite（如果可用）
if command -v sqlite3 &> /dev/null; then
    sqlite3 "$DB_FILE" "INSERT INTO messages (session_id, role, content) VALUES ('$SESSION_ID', 'tool', '$TOOL_NAME');" 2>/dev/null || true
fi

# 忽略错误，不影响 Claude Code 正常使用
exit 0
