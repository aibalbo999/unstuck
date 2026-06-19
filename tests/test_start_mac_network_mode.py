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
