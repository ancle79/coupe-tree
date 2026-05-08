#!/bin/bash

# 获取脚本所在目录
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$DIR"

echo "======================================================"
echo "          Starting Tree Coupe Server (Linux/Pi)"
echo "======================================================"

# 检查 Python3
if ! command -v python3 &> /dev/null
then
    echo "[ERROR] python3 could not be found. Please install it."
    exit 1
fi

# 安装依赖
echo "[1/2] Checking dependencies..."
pip3 install -r requirements.txt --quiet

# 启动服务器
echo "[2/2] Starting server..."
echo "------------------------------------------------------"
echo "[TIPS] "
echo "1. Server is running on http://0.0.0.0:5000"
echo "2. Use 'screen' or 'systemd' to keep it running 24/7."
echo "------------------------------------------------------"
echo ""

python3 app.py
