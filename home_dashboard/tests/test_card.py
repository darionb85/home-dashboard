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
    assert res == {"ok": True, "needs_restart": True, "reason": None}  # new www -> HA must restart once
    assert (tmp_path / "www/home-dashboard/ai-usage-card.js").read_text().startswith("/* AI Usage card")
    assert ha.sent[-1] == {"type": "lovelace/resources/create", "res_type": "module",
                           "url": f"/local/home-dashboard/ai-usage-card.js?v={card_installer.CARD_VERSION}"}


async def test_install_updates_old_version_and_skips_current(tmp_path, monkeypatch):
    monkeypatch.setenv("HA_CONFIG_DIR", str(make_config(tmp_path, with_www=True)))
    ha = FakeHA([{"id": "abc", "url": "/local/home-dashboard/ai-usage-card.js?v=0.0.1", "type": "module"}])
    res = await card_installer.install(ha)
    assert res["ok"] and not res["needs_restart"]
    assert ha.sent[-1]["type"] == "lovelace/resources/update" and ha.sent[-1]["resource_id"] == "abc"
    current = FakeHA([{"id": "abc", "url": f"/local/home-dashboard/ai-usage-card.js?v={card_installer.CARD_VERSION}"}])
    await card_installer.install(current)
    assert [c["type"] for c in current.sent] == ["lovelace/resources"]


async def test_install_without_config_mount_fails_soft(monkeypatch, tmp_path):
    monkeypatch.setenv("HA_CONFIG_DIR", str(tmp_path / "nope"))
    monkeypatch.setattr(card_installer, "CONFIG_ROOTS", ())
    res = await card_installer.install(FakeHA())
    assert res["ok"] is False and "mapped" in res["reason"]


def test_widget_uses_card_only_when_installed(fixture):
    found = builder.discover(fixture("ha_states.json"), fixture("ha_registry.json"), builder.load_rules())
    def ai_cards(extras):
        cfg = builder.render(builder.load_template("catppuccin"), found, extras)
        cards = [c for s in cfg["views"][0]["sections"] for c in s["cards"]]
        return [c["card"]["type"] for c in cards if c["type"] == "conditional"]
    assert ai_cards({"ai_card": True}) == ["custom:ai-usage-card"] * len(found["ai_usage"])
    assert ai_cards({}) == ["gauge"] * len(found["ai_usage"])
