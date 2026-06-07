#!/bin/bash
# ============================================================
# Wall Street AI 股票分析系統 - 一鍵啟動腳本 (Mac 專用)
# ============================================================

set -e

APP_URL="http://127.0.0.1:8080"

echo "啟動 Wall Street AI 股票分析系統..."

# 切換到腳本所在目錄的 backend 資料夾
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

if [ -n "${PYTHON_BIN:-}" ]; then
    BASE_PYTHON="$PYTHON_BIN"
elif [ -x "$DIR/.venv/bin/python" ]; then
    BASE_PYTHON="$DIR/.venv/bin/python"
elif [ -x "/opt/homebrew/bin/python3.13" ]; then
    BASE_PYTHON="/opt/homebrew/bin/python3.13"
elif [ -x "/opt/homebrew/bin/python3.12" ]; then
    BASE_PYTHON="/opt/homebrew/bin/python3.12"
elif [ -x "/opt/homebrew/bin/python3.11" ]; then
    BASE_PYTHON="/opt/homebrew/bin/python3.11"
elif [ -x "/opt/homebrew/bin/python3" ]; then
    BASE_PYTHON="/opt/homebrew/bin/python3"
else
    BASE_PYTHON="$(command -v python3)"
fi

PYTHON_VERSION="$("$BASE_PYTHON" - <<'PY'
import sys
print(f"{sys.version_info.major}.{sys.version_info.minor}")
PY
)"

if [ -x "$DIR/.venv/bin/python" ]; then
    PYTHON_BIN="$DIR/.venv/bin/python"
elif "$BASE_PYTHON" - <<'PY'
import sys
raise SystemExit(0 if sys.version_info >= (3, 11) else 1)
PY
then
    echo "建立本機虛擬環境：$DIR/.venv（Python $PYTHON_VERSION）"
    "$BASE_PYTHON" -m venv "$DIR/.venv"
    PYTHON_BIN="$DIR/.venv/bin/python"
else
    echo "警告：目前 Python $PYTHON_VERSION 低於建議版本 3.11，可能出現 Google 套件支援警告。"
    echo "建議安裝 Homebrew Python，或用 PYTHON_BIN 指定 Python 3.11+。"
    PYTHON_BIN="$BASE_PYTHON"
fi

echo "使用 Python：$PYTHON_BIN"
"$PYTHON_BIN" "$DIR/scripts/check_runtime.py" --strict

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

# 確認 Python 套件版本；每次執行 requirements 可避免舊版 google-genai / pydantic 留在環境中。
echo "正在確認 Python 套件版本..."
"$PYTHON_BIN" -m pip install -r requirements.txt

# 如果 8080 已有舊服務，先停止，避免啟動後立刻因 port 被占用而失敗。
OLD_PIDS="$(lsof -ti tcp:8080 2>/dev/null || true)"
if [ -n "$OLD_PIDS" ]; then
    echo "偵測到 8080 連接埠已有舊服務，正在停止..."
    kill $OLD_PIDS 2>/dev/null || true
    sleep 1
fi

echo "啟動伺服器..."
PYTHONUNBUFFERED=1 "$PYTHON_BIN" -u -m uvicorn api:app --host 0.0.0.0 --port 8080 &
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
