"""AI usage card: install into HA config, resource registration, widget choice."""
from app import builder, card_installer


class FakeHA:
    def __init__(self, resources=None):
        self.resources = resources or []
        self.sent = []

    async def ws_commands(self, cmds):
        out = []
        for c in cmds:
            self.sent.append(c)
            out.append(self.resources if c["type"] == "lovelace/resources" else None)
        return out


def make_config(tmp_path, with_www):
    (tmp_path / "configuration.yaml").write_text("default_config:\n")
    if with_www:
        (tmp_path / "www").mkdir()
    return tmp_path


async def test_install_creates_www_and_registers(tmp_path, monkeypatch):
    monkeypatch.setenv("HA_CONFIG_DIR", str(make_config(tmp_path, with_www=False)))
    ha = FakeHA()
    res = await card_installer.install(ha)
    assert res == {"copied": True, "created_www": True, "registered": True, "reason": None}  # new www -> restart once
    assert (tmp_path / "www/home-dashboard/ai-usage-card.js").read_text().startswith("/* AI Usage card")
    assert ha.sent[-1] == {"type": "lovelace/resources/create", "res_type": "module",
                           "url": f"/local/home-dashboard/ai-usage-card.js?v={card_installer.CARD_VERSION}"}


async def test_install_updates_old_version_and_skips_current(tmp_path, monkeypatch):
    monkeypatch.setenv("HA_CONFIG_DIR", str(make_config(tmp_path, with_www=True)))
    ha = FakeHA([{"id": "abc", "url": "/local/home-dashboard/ai-usage-card.js?v=0.0.1", "type": "module"}])
    res = await card_installer.install(ha)
    assert res["copied"] and res["registered"] and not res["created_www"]
    assert ha.sent[-1]["type"] == "lovelace/resources/update" and ha.sent[-1]["resource_id"] == "abc"
    current = FakeHA([{"id": "abc", "url": f"/local/home-dashboard/ai-usage-card.js?v={card_installer.CARD_VERSION}"}])
    await card_installer.install(current)
    assert [c["type"] for c in current.sent] == ["lovelace/resources"]


async def test_install_without_config_mount_fails_soft(monkeypatch, tmp_path):
    monkeypatch.setenv("HA_CONFIG_DIR", str(tmp_path / "nope"))
    monkeypatch.setattr(card_installer, "CONFIG_ROOTS", ())
    res = await card_installer.install(FakeHA())
    assert res["copied"] is False and "mapped" in res["reason"]


class FailingHA(FakeHA):
    async def ws_commands(self, cmds):
        raise RuntimeError("unauthorized")


async def test_registration_failure_is_reported(tmp_path, monkeypatch):
    monkeypatch.setenv("HA_CONFIG_DIR", str(make_config(tmp_path, with_www=True)))
    res = await card_installer.install(FailingHA())
    assert res["copied"] and not res["registered"] and "resource" in res["reason"]


def test_widget_uses_card_only_when_installed(fixture):
    found = builder.discover(fixture("ha_states.json"), fixture("ha_registry.json"), builder.load_rules())
    def ai_cards(extras):
        cfg = builder.render(builder.load_template("catppuccin"), found, extras)
        cards = [c for s in cfg["views"][0]["sections"] for c in s["cards"]]
        return [c["card"]["type"] for c in cards if c["type"] == "conditional"]
    assert ai_cards({"ai_card": True}) == ["custom:ai-usage-card"] * len(found["ai_usage"])
    assert ai_cards({}) == ["gauge"] * len(found["ai_usage"])


# ---- build decision: when does the dashboard use the custom card? ----
import pytest
from aiohttp import ClientSession
from app.main import DEFAULTS, Service
from app.store import Store


class BuildHA(FakeHA):
    available = True
    def __init__(self, fail_register=False):
        super().__init__()
        self.fail_register = fail_register
        self.saved = None
    async def get_states(self):
        return [{"entity_id": "sensor.ai_usage_claude", "state": "64"}]
    async def entity_registry(self):
        return []
    async def addon_info(self):
        return {"slug": "abc_home_dashboard"}
    async def save_dashboard(self, url_path, title, config):
        self.saved = config
    async def ws_commands(self, cmds):
        if self.fail_register and any(c["type"] != "lovelace/resources" for c in cmds):
            raise RuntimeError("unauthorized")
        return await super().ws_commands(cmds)


def ai_card_types(config):
    cards = [c for s in config["views"][0]["sections"] for c in s["cards"]]
    return [c["card"]["type"] for c in cards if c["type"] == "conditional"]


@pytest.mark.parametrize("with_www,served,fail_register,expect_state,expect_card", [
    (True, True, False, "active", "custom:ai-usage-card"),           # normal
    (False, False, False, "restart_needed", "gauge"),                # fresh www: restart first
    (False, True, False, "active", "custom:ai-usage-card"),          # already served
    (True, True, True, "failed", "gauge"),                           # resource registration refused
])
async def test_build_card_decision(tmp_path, monkeypatch, with_www, served, fail_register, expect_state, expect_card):
    monkeypatch.setenv("HA_CONFIG_DIR", str(make_config(tmp_path, with_www)))
    async def fake_served(_s):
        return served
    monkeypatch.setattr(card_installer, "served", fake_served)
    async with ClientSession() as session:
        ha = BuildHA(fail_register)
        svc = Service(Store(tmp_path / "data"), dict(DEFAULTS), session, ha)
        await svc.build_dashboard()
        assert svc.card_status["state"] == expect_state
        assert ai_card_types(ha.saved) == [expect_card]
        if expect_state != "active":  # the manual override always wins
            svc.store.set_flag("card_force", True)
            await svc.build_dashboard()
            assert ai_card_types(ha.saved) == ["custom:ai-usage-card"]
