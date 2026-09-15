"""公网部署相关的安全配置。"""

from django.urls import reverse


def test_static_served_without_debug(client, settings):
    """关闭调试模式后，静态文件仍由 WhiteNoise 提供，页面不会丢样式。"""
    settings.DEBUG = False
    resp = client.get("/static/css/app.css")
    assert resp.status_code == 200
    assert "text/css" in resp["Content-Type"]


def test_404_does_not_leak_debug_info(client, settings):
    settings.DEBUG = False
    resp = client.get("/.env")
    assert resp.status_code == 404
    assert b"DEBUG = True" not in resp.content
    assert b"URLconf" not in resp.content


def test_repeated_login_failures_lock_the_account(client, staff):
    url = reverse("login")
    for _ in range(5):
        client.post(url, {"username": staff.username, "password": "wrong"})
    # 锁定后即使密码正确也无法登录
    resp = client.post(url, {"username": staff.username, "password": "pw"})
    assert resp.status_code == 429
    assert "暂时锁定" in resp.content.decode()


def test_security_headers(client):
    resp = client.get(reverse("login"))
    assert resp["X-Frame-Options"] == "DENY"
    assert resp["X-Content-Type-Options"] == "nosniff"
