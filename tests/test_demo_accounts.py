import stat

from django.core.management import call_command
from django.urls import reverse


def test_login_page_hides_demo_accounts_by_default(client, settings):
    settings.ORDERPILOT_SHOW_DEMO_ACCOUNTS = False
    assert "huamei" not in client.get(reverse("login")).content.decode()


def test_login_page_can_show_demo_accounts(client, settings):
    settings.ORDERPILOT_SHOW_DEMO_ACCOUNTS = True
    assert "huamei" in client.get(reverse("login")).content.decode()


def test_rotate_demo_passwords(staff, tmp_path):
    out = tmp_path / "creds"
    call_command("rotate_demo_passwords", output=str(out))

    staff.refresh_from_db()
    assert not staff.check_password("pw")
    line = next(row for row in out.read_text(encoding="utf-8").splitlines() if row.startswith("zhang"))
    assert staff.check_password(line.split()[1])
    assert stat.S_IMODE(out.stat().st_mode) == 0o600
