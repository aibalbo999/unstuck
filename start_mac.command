#!/bin/bash
# ============================================================
# Wall Street AI 股票分析系統 - 一鍵啟動腳本 (Mac 專用)
# ============================================================

set -e
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"

LAN_ACCESS="${LAN_ACCESS:-0}"
SERVER_HOST="127.0.0.1"
APP_HOST="127.0.0.1"
if [ "$LAN_ACCESS" = "1" ] || [ "$LAN_ACCESS" = "true" ] || [ "$LAN_ACCESS" = "yes" ]; then
    SERVER_HOST="0.0.0.0"
    LAN_IP="$(ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1 2>/dev/null || true)"
    if [ -n "$LAN_IP" ]; then
        APP_HOST="$LAN_IP"
    else
        APP_HOST="$(hostname)"
    fi
fi
APP_URL="http://$APP_HOST:8080"

echo "啟動 Wall Street AI 股票分析系統..."

# 切換到腳本所在目錄的 backend 資料夾
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
export TASK_QUEUE_BACKEND="${TASK_QUEUE_BACKEND:-rq}"
export REDIS_URL="${REDIS_URL:-redis://localhost:6379/0}"
export TASK_QUEUE_NAME="${TASK_QUEUE_NAME:-stock-analysis}"
export PYTHONUNBUFFERED="${PYTHONUNBUFFERED:-1}"

SERVER_PID=""
WORKER_PID=""
REDIS_PID=""
WORKER_PID_FILE="$DIR/backend/cache/start_mac_worker.pid"
TARGET_NOFILE_LIMIT="${TARGET_NOFILE_LIMIT:-4096}"

raise_file_descriptor_limit() {
    case "$TARGET_NOFILE_LIMIT" in
        ""|*[!0-9]*)
            TARGET_NOFILE_LIMIT=4096
            ;;
    esac

    current_limit="$(ulimit -n 2>/dev/null || echo 0)"
    if [ "$current_limit" = "unlimited" ]; then
        echo "檔案描述符上限：unlimited"
        return 0
    fi

    if [ "$current_limit" -lt "$TARGET_NOFILE_LIMIT" ] 2>/dev/null; then
        if ulimit -n "$TARGET_NOFILE_LIMIT" 2>/dev/null; then
            :
        elif ulimit -n 1024 2>/dev/null; then
            :
        else
            echo "提醒：無法提高檔案描述符上限，目前為 $current_limit。"
        fi
    fi
    echo "檔案描述符上限：$(ulimit -n 2>/dev/null || echo "$current_limit")"
}

raise_file_descriptor_limit

cleanup() {
    if [ -n "${SERVER_PID:-}" ]; then
        kill "$SERVER_PID" 2>/dev/null || true
        wait "$SERVER_PID" 2>/dev/null || true
    fi
    if [ -n "${WORKER_PID:-}" ]; then
        kill "$WORKER_PID" 2>/dev/null || true
        wait "$WORKER_PID" 2>/dev/null || true
        rm -f "$WORKER_PID_FILE" 2>/dev/null || true
    fi
    if [ -n "${REDIS_PID:-}" ]; then
        kill "$REDIS_PID" 2>/dev/null || true
        wait "$REDIS_PID" 2>/dev/null || true
    fi
}
trap cleanup INT TERM EXIT

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
    echo "請貼上 Gemini API key；若有多組 key，請用逗號分隔，系統會寫成一行一把的序號格式。"
    echo "若先不設定，直接按 Enter，伺服器仍會啟動，但分析會被擋下並提示缺少 API key。"
    read -r -p "Gemini API keys: " GEMINI_KEYS_INPUT
    if [ -n "$GEMINI_KEYS_INPUT" ]; then
        cp "$DIR/backend/.env.example" "$DIR/backend/.env"
        "$PYTHON_BIN" - "$DIR/backend/.env" "$GEMINI_KEYS_INPUT" <<'PY'
from pathlib import Path
import re
import sys

path = Path(sys.argv[1])
keys = [item.strip() for item in sys.argv[2].replace("\n", ",").split(",") if item.strip()]
lines = path.read_text(encoding="utf-8").splitlines()
managed = re.compile(r"^(GEMINI_API_KEYS|GOOGLE_API_KEYS|GEMINI_API_KEY_\d+|GOOGLE_API_KEY_\d+)\s*=")
insert_at = None
kept = []
for i, line in enumerate(lines):
    if managed.match(line.strip()):
        if insert_at is None:
            insert_at = len(kept)
        continue
    kept.append(line)
if insert_at is None:
    insert_at = len(kept)
block = ["# LLM API key rotation (numeric order)"]
block.extend(f"GEMINI_API_KEY_{index}={key}" for index, key in enumerate(keys, 1))
updated = kept[:insert_at] + block + [""] + kept[insert_at:]
path.write_text("\n".join(updated).rstrip() + "\n", encoding="utf-8")
PY
        chmod 600 "$DIR/backend/.env" 2>/dev/null || true
        echo "已建立 backend/.env。"
    fi
    echo ""
fi

# 確認 Python 套件版本；每次執行 requirements 可避免舊版 google-genai / pydantic 留在環境中。
echo "正在確認 Python 套件版本..."
"$PYTHON_BIN" -m pip install -r requirements.txt

redis_ping() {
    "$PYTHON_BIN" - <<'PY' >/dev/null 2>&1
import os
import sys

from redis import Redis

try:
    client = Redis.from_url(
        os.environ.get("REDIS_URL", "redis://localhost:6379/0"),
        socket_connect_timeout=0.5,
        socket_timeout=0.5,
    )
    sys.exit(0 if client.ping() else 1)
except Exception:
    sys.exit(1)
PY
}

wait_for_redis() {
    for _ in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20
    do
        if redis_ping; then
            return 0
        fi
        sleep 0.5
    done
    return 1
}

redis_server_bin() {
    if [ -x "/opt/homebrew/bin/redis-server" ]; then
        printf '%s\n' "/opt/homebrew/bin/redis-server"
        return 0
    fi
    if [ -x "/usr/local/bin/redis-server" ]; then
        printf '%s\n' "/usr/local/bin/redis-server"
        return 0
    fi
    command -v redis-server 2>/dev/null || return 1
}

print_redis_install_guide() {
    echo "找不到 redis-server，無法啟動任務佇列。"
    echo "請先安裝 Redis 後再重跑："
    echo "  brew install redis"
    echo "或改用既有 Redis："
    echo "  REDIS_URL=redis://<host>:6379/0 ./start_mac.command"
}

REDIS_HOST="$("$PYTHON_BIN" - <<'PY'
import os
from urllib.parse import urlparse

parsed = urlparse(os.environ.get("REDIS_URL", "redis://localhost:6379/0"))
print(parsed.hostname or "localhost")
PY
)"
REDIS_PORT="$("$PYTHON_BIN" - <<'PY'
import os
from urllib.parse import urlparse

parsed = urlparse(os.environ.get("REDIS_URL", "redis://localhost:6379/0"))
print(parsed.port or 6379)
PY
)"

start_redis_if_needed() {
    if redis_ping; then
        echo "Redis 已在運行：$REDIS_URL"
        return 0
    fi
    if [ "$REDIS_HOST" != "localhost" ] && [ "$REDIS_HOST" != "127.0.0.1" ] && [ "$REDIS_HOST" != "::1" ]; then
        echo "無法連線到 Redis：$REDIS_URL"
        echo "REDIS_URL 指向非本機主機（$REDIS_HOST），請先手動啟動該 Redis。"
        exit 1
    fi

    REDIS_SERVER_BIN="$(redis_server_bin || true)"
    if [ -z "$REDIS_SERVER_BIN" ]; then
        print_redis_install_guide
        exit 1
    fi

    mkdir -p "$DIR/backend/cache"
    echo "啟動 Redis：$REDIS_URL"
    (trap '' INT; exec "$REDIS_SERVER_BIN" --bind 127.0.0.1 --port "$REDIS_PORT" --save "" --appendonly no > "$DIR/backend/cache/redis-start_mac.log" 2>&1) &
    REDIS_PID=$!
    if ! wait_for_redis; then
        echo "Redis 啟動逾時，請檢查：$DIR/backend/cache/redis-start_mac.log"
        tail -40 "$DIR/backend/cache/redis-start_mac.log" 2>/dev/null || true
        exit 1
    fi
    echo "Redis 已啟動。"
}

start_redis_if_needed

# 如果 8080 已有舊服務，先停止，避免啟動後立刻因 port 被占用而失敗。
OLD_PIDS="$(lsof -ti tcp:8080 2>/dev/null || true)"
if [ -n "$OLD_PIDS" ]; then
    echo "偵測到 8080 連接埠已有舊服務，正在停止..."
    kill $OLD_PIDS 2>/dev/null || true
    sleep 1
fi

project_worker_pids() {
    ps -axo pid=,command= | while read -r pid command
    do
        case "$command" in
            *"worker_main.py --role all"*|*"worker_main.py --role queue"*|*"worker_main.py --role schedulers"*|*"worker_main.py --role maintenance"*|*"multiprocessing.spawn"*|*"multiprocessing.resource_tracker"*)
                if [ "$pid" = "$$" ] || [ "$pid" = "${WORKER_PID:-}" ]; then
                    continue
                fi
                worker_cwd="$(lsof -a -p "$pid" -d cwd -Fn 2>/dev/null | sed -n 's/^n//p' | head -1)"
                if [ "$worker_cwd" = "$DIR/backend" ]; then
                    printf '%s\n' "$pid"
                fi
                ;;
        esac
    done
}

stop_existing_project_workers() {
    EXISTING_WORKER_PIDS="$(project_worker_pids || true)"
    if [ -z "$EXISTING_WORKER_PIDS" ]; then
        return 0
    fi
    echo "偵測到同專案殘留 Worker，正在停止..."
    for pid in $EXISTING_WORKER_PIDS
    do
        kill -TERM "$pid" 2>/dev/null || true
    done
    sleep 1
    for pid in $EXISTING_WORKER_PIDS
    do
        if kill -0 "$pid" 2>/dev/null; then
            kill -INT "$pid" 2>/dev/null || true
        fi
    done
    sleep 1
    for pid in $EXISTING_WORKER_PIDS
    do
        if kill -0 "$pid" 2>/dev/null; then
            echo "提醒：Worker PID $pid 尚未停止，若持續出現舊模型或排程錯誤，請手動檢查。"
        fi
    done
}

if [ -f "$WORKER_PID_FILE" ]; then
    OLD_WORKER_PID="$(cat "$WORKER_PID_FILE" 2>/dev/null || true)"
    if [ -n "$OLD_WORKER_PID" ] && kill -0 "$OLD_WORKER_PID" 2>/dev/null; then
        echo "偵測到舊 Worker，正在停止..."
        kill "$OLD_WORKER_PID" 2>/dev/null || true
        sleep 1
    fi
    rm -f "$WORKER_PID_FILE" 2>/dev/null || true
fi
stop_existing_project_workers

echo "啟動 Worker..."
(trap '' INT; exec "$PYTHON_BIN" -u worker_main.py --role all) &
WORKER_PID=$!
echo "$WORKER_PID" > "$WORKER_PID_FILE"
sleep 1
if ! kill -0 "$WORKER_PID" 2>/dev/null; then
    echo "Worker 啟動失敗，請檢查上方錯誤訊息。"
    wait "$WORKER_PID" 2>/dev/null || true
    exit 1
fi
echo "Worker 已啟動。"

echo "啟動伺服器..."
(trap '' INT; exec "$PYTHON_BIN" -u -m uvicorn api:app --host "$SERVER_HOST" --port 8080) &
SERVER_PID=$!

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
if [ "$SERVER_HOST" = "0.0.0.0" ]; then
    echo "區網存取已啟用，手機請開啟：$APP_URL"
    echo "提醒：僅在可信任 Wi-Fi 使用 LAN_ACCESS=1。"
fi
echo "請保持這個終端機視窗開啟；按下 Ctrl+C 可停止伺服器。"
echo "============================================================"

wait "$SERVER_PID"
