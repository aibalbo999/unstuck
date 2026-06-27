from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_start_mac_supports_explicit_lan_access_mode():
    script = (ROOT / "start_mac.command").read_text(encoding="utf-8")
    lan_script = (ROOT / "start_mac_lan.command").read_text(encoding="utf-8")

    assert 'SERVER_HOST="127.0.0.1"' in script
    assert 'LAN_ACCESS="${LAN_ACCESS:-0}"' in script
    assert 'SERVER_HOST="0.0.0.0"' in script
    assert 'ipconfig getifaddr en0' in script
    assert '--host "$SERVER_HOST"' in script
    assert '手機請開啟' in script
    assert 'LAN_ACCESS=1' in lan_script
    assert 'exec "$DIR/start_mac.command"' in lan_script


def test_start_mac_lan_launches_full_local_runtime_stack():
    script = (ROOT / "start_mac.command").read_text(encoding="utf-8")

    assert 'export TASK_QUEUE_BACKEND="${TASK_QUEUE_BACKEND:-rq}"' in script
    assert 'export REDIS_URL="${REDIS_URL:-redis://localhost:6379/0}"' in script
    assert 'redis-server' in script
    assert 'redis_ping()' in script
    assert 'REDIS_PID=$!' in script
    assert '(trap \'\' INT; exec "$PYTHON_BIN" -u worker_main.py --role all)' in script
    assert 'WORKER_PID=$!' in script
    assert 'kill "$WORKER_PID"' in script
    assert 'kill "$REDIS_PID"' in script
    assert 'Worker 已啟動' in script


def test_start_mac_offers_homebrew_redis_install_when_missing():
    script = (ROOT / "start_mac.command").read_text(encoding="utf-8")

    assert 'install_redis_server()' in script
    assert 'command -v brew' in script
    assert 'brew install redis' in script
    assert '是否要現在用 Homebrew 安裝 Redis' in script
    assert 'Redis 安裝完成。' in script


def test_start_mac_children_ignore_terminal_ctrl_c_and_are_cleaned_up_by_parent():
    script = (ROOT / "start_mac.command").read_text(encoding="utf-8")

    assert "(trap '' INT; exec redis-server" in script
    assert '(trap \'\' INT; exec "$PYTHON_BIN" -u worker_main.py --role all)' in script
    assert '(trap \'\' INT; exec "$PYTHON_BIN" -u -m uvicorn api:app --host "$SERVER_HOST" --port 8080)' in script
    assert script.index('kill "$WORKER_PID"') < script.index('kill "$REDIS_PID"')
