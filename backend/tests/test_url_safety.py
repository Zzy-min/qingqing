import os
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

os.environ.setdefault("MINIMAX_API_KEY", "test-image-key")

from services.minimax import _is_url_safe


def test_is_url_safe_allows_https_whitelisted_domains():
    assert _is_url_safe("https://api.minimaxi.com/v1/ok") is True
    assert _is_url_safe("https://filecdn.minimaxi.com/path/file.png") is True
    assert _is_url_safe(
        "https://hailuo-image-algeng-data.oss-cn-wulanchabu.aliyuncs.com/path/image.jpg"
    ) is True


def test_is_url_safe_rejects_http_and_non_whitelist_domains():
    assert _is_url_safe("http://api.minimaxi.com/v1/ok") is False
    assert _is_url_safe("https://example.com/file.png") is False


def test_is_url_safe_rejects_private_or_reserved_ip_targets():
    assert _is_url_safe("https://127.0.0.1/a") is False
    assert _is_url_safe("https://10.0.0.1/a") is False
    assert _is_url_safe("https://172.16.0.1/a") is False
    assert _is_url_safe("https://192.168.1.5/a") is False
