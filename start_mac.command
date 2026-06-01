#!/bin/bash
# ============================================================
# Wall Street AI 股票分析系統 - 一鍵啟動腳本 (Mac 專用)
# ============================================================

set -e

APP_URL="http://127.0.0.1:8080"
PYTHON_BIN="${PYTHON_BIN:-python3}"

echo "啟動 Wall Street AI 股票分析系統..."

# 切換到腳本所在目錄的 backend 資料夾
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$DIR/backend" || {
    echo "找不到 backend 資料夾：$DIR/backend"
    read -r -p "按 Enter 關閉視窗..."
    exit 1
}

if [ ! -f "$DIR/backend/.env" ] && [ -z "${GEMINI_API_KEYS}${GOOGLE_API_KEYS}${GOOGLE_API_KEY_1}${GEMINI_API_KEY_1}" ]; then
    echo "提醒：尚未偵測到 Gemini API key。"
    echo "請貼上 Gemini API key；若有多組 key，請用逗號分隔。"
    echo "若先不設定，直接按 Enter，伺服器仍會啟動，但分析會被擋下並提示缺少 API key。"
    read -r -p "GEMINI_API_KEYS: " GEMINI_KEYS_INPUT
    if [ -n "$GEMINI_KEYS_INPUT" ]; then
        cp "$DIR/backend/.env.example" "$DIR/backend/.env"
        "$PYTHON_BIN" - "$DIR/backend/.env" "$GEMINI_KEYS_INPUT" <<'PY'
from pathlib import Path
import sys

path = Path(sys.argv[1])
keys = sys.argv[2].strip()
lines = path.read_text(encoding="utf-8").splitlines()
for i, line in enumerate(lines):
    if line.startswith("GEMINI_API_KEYS="):
        lines[i] = f"GEMINI_API_KEYS={keys}"
        break
else:
    lines.append(f"GEMINI_API_KEYS={keys}")
path.write_text("\n".join(lines) + "\n", encoding="utf-8")
PY
        chmod 600 "$DIR/backend/.env" 2>/dev/null || true
        echo "已建立 backend/.env。"
    fi
    echo ""
fi

# 檢查 Python 套件；使用 python3 -m 檢查可避免 PATH 找不到 uvicorn 指令的誤判。
if ! "$PYTHON_BIN" -c "import fastapi, uvicorn, sse_starlette; from google import genai" >/dev/null 2>&1
then
    echo "正在安裝必要的套件..."
    "$PYTHON_BIN" -m pip install --user -r requirements.txt
fi

# 如果 8080 已有舊服務，先停止，避免啟動後立刻因 port 被占用而失敗。
OLD_PIDS="$(lsof -ti tcp:8080 2>/dev/null || true)"
if [ -n "$OLD_PIDS" ]; then
    echo "偵測到 8080 連接埠已有舊服務，正在停止..."
    kill $OLD_PIDS 2>/dev/null || true
    sleep 1
fi

echo "啟動伺服器..."
"$PYTHON_BIN" -m uvicorn api:app --host 0.0.0.0 --port 8080 &
SERVER_PID=$!

cleanup() {
    kill "$SERVER_PID" 2>/dev/null || true
}
trap cleanup INT TERM EXIT

echo "等待伺服器啟動..."
READY=0
for _ in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20
do
    if curl -fsS "$APP_URL/api/reports" >/dev/null 2>&1; then
        READY=1
        break
    fi
    sleep 0.5
done

if [ "$READY" != "1" ]; then
    echo "伺服器啟動逾時，請檢查上方錯誤訊息。"
    wait "$SERVER_PID"
    exit 1
fi

echo "開啟瀏覽器..."
open "$APP_URL"

echo ""
echo "============================================================"
echo "伺服器已啟動：$APP_URL"
echo "請保持這個終端機視窗開啟；按下 Ctrl+C 可停止伺服器。"
echo "============================================================"

wait "$SERVER_PID"
