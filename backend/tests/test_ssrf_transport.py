import json
import socket

import pytest
from fastapi import HTTPException


class FakeResponse:
    status = 200
    reason = "OK"

    def __init__(self, chunks):
        self._chunks = list(chunks)
        self.headers = {"content-type": "application/json"}

    def read(self, _size):
        return self._chunks.pop(0) if self._chunks else b""


def test_public_request_connects_to_the_validated_ip_and_keeps_tls_hostname(monkeypatch):
    from qingqing_v1 import security

    captured = {}

    def fake_getaddrinfo(host, port, **kwargs):
        assert host == "api.example.com"
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", port))]

    class FakeConnection:
        def __init__(self, hostname, port, pinned_ip, timeout):
            captured.update(hostname=hostname, port=port, pinned_ip=pinned_ip, timeout=timeout)

        def request(self, method, path, body=None, headers=None):
            captured.update(method=method, path=path, body=body, headers=headers)

        def getresponse(self):
            return FakeResponse([json.dumps({"ok": True}).encode()])

        def close(self):
            captured["closed"] = True

    monkeypatch.setattr(security.socket, "getaddrinfo", fake_getaddrinfo)
    monkeypatch.setattr(security, "_PinnedHTTPSConnection", FakeConnection)

    response = security.request_public_https(
        "POST",
        "https://api.example.com/v1/run?q=1",
        headers={"Content-Type": "application/json"},
        json_body={"prompt": "hello"},
    )

    assert captured["pinned_ip"] == "93.184.216.34"
    assert captured["hostname"] == "api.example.com"
    assert captured["headers"]["Host"] == "api.example.com"
    assert captured["path"] == "/v1/run?q=1"
    assert response.json() == {"ok": True}
    assert captured["closed"] is True


def test_public_request_rejects_any_private_dns_answer(monkeypatch):
    from qingqing_v1 import security

    monkeypatch.setattr(
        security.socket,
        "getaddrinfo",
        lambda *args, **kwargs: [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443)),
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 443)),
        ],
    )

    with pytest.raises(HTTPException, match="public addresses"):
        security.request_public_https("GET", "https://api.example.com/data")


def test_public_request_stops_reading_at_the_response_limit(monkeypatch):
    from qingqing_v1 import security

    monkeypatch.setattr(
        security.socket,
        "getaddrinfo",
        lambda *args, **kwargs: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))],
    )

    class FakeConnection:
        def __init__(self, *args, **kwargs):
            pass

        def request(self, *args, **kwargs):
            pass

        def getresponse(self):
            return FakeResponse([b"1234", b"5678"])

        def close(self):
            pass

    monkeypatch.setattr(security, "_PinnedHTTPSConnection", FakeConnection)

    with pytest.raises(HTTPException, match="exceeds"):
        security.request_public_https("GET", "https://api.example.com/data", max_bytes=6)
