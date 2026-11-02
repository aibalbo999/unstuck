import os,socket
import pytest


def test_isolated_rq_option_never_opens_formal_tcp_or_foreign_unix():
    with socket.socket(socket.AF_INET,socket.SOCK_STREAM)as sock:
        with pytest.raises(OSError):sock.connect(('127.0.0.1',6379))
    with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM)as sock:
        with pytest.raises(OSError):sock.connect('/var/run/foreign-redis.sock')
    with pytest.raises(OSError):socket.create_connection(('127.0.0.1',8080),timeout=.01)
