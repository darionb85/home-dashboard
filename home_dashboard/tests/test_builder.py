"""Dashboard discovery + template rendering."""
import yaml
import pytest

from app import builder


@pytest.fixture
def found(fixture):
    return builder.discover(fixture("ha_states.json"), fixture("ha_registry.json"), builder.load_rules())


def test_discovery_picks_the_right_entities(found):
    assert found["weather"] == "weather.forecast_home"
    assert found["calendars"] == ["calendar.darion_gmail_com"]  # holidays excluded
    assert found["thermostat"] == "climate.living_room"
    assert found["cameras"] == ["camera.front_door_live_view", "camera.garage_c110_hd_stream"]
    assert found["ecoflow_battery"] == "sensor.delta_3_ultra_plus_main_battery_level"
    assert found["wall_connector_power"] == "sensor.tesla_wall_connector_power"
    assert found["grow_temp"] == "sensor.growhub_e42a_temperature"  # not outside temp
    assert found["net_clients"] == "sensor.gl_be9300_connected_clients"
    assert found["plugs"] == ["switch.office_plug"]  # no camera switches, no disabled
    assert found["ai_usage"] == ["sensor.ai_usage_claude", "sensor.ai_usage_copilot"]
    assert "solar_power" not in found  # Tesla Fleet not set up yet


def test_discovery_without_registry_uses_hints(fixture):
    found = builder.discover(fixture("ha_states.json"), None, builder.load_rules())
    assert found["ecoflow_battery"] == "sensor.delta_3_ultra_plus_main_battery_level"
    assert found["grow_vpd"] == "sensor.growhub_e42a_vpd"


def test_overrides_replace_and_hide(fixture):
    o = builder.parse_overrides(["thermostat=climate.hall", "plugs=-", "cameras=camera.a, camera.b"])
    found = builder.discover(fixture("ha_states.json"), fixture("ha_registry.json"), builder.load_rules(), o)
    assert found["thermostat"] == "climate.hall"
    assert "plugs" not in found
    assert found["cameras"] == ["camera.a", "camera.b"]


def test_render_catppuccin(found):
    cfg = builder.render(builder.load_template("catppuccin"), found, {"addon_ingress": "/hassio/ingress/x"})
    view = cfg["views"][0]
    assert view["type"] == "sections" and view["theme"] == "Catppuccin Auto Latte Mocha"
    cards = [c for s in view["sections"] for c in s["cards"]]
    types = [c["type"] for c in cards]
    assert "thermostat" in types and "weather-forecast" in types
    cal = next(c for c in cards if c["type"] == "calendar")
    assert cal["entities"] == ["calendar.darion_gmail_com"]  # list substituted, not stringified
    cams = [c["entity"] for c in cards if c["type"] == "picture-entity"]
    assert cams == found["cameras"]
    assert not any("{{" in yaml.safe_dump(c) for c in cards)
    assert not any("_requires" in c or "_repeat" in c for c in cards)
    assert "Solar" not in [c.get("name") for c in cards]  # optional card dropped


def test_empty_sections_are_dropped():
    cfg = builder.render(builder.load_template("catppuccin"), {"weather": "weather.home"})
    secs = cfg["views"][0]["sections"]
    assert len(secs) == 1 and secs[0]["cards"][0] == {"type": "heading", "heading": "Today"}


def test_minimal_template_is_masonry(found):
    view = builder.render(builder.load_template("minimal"), found)["views"][0]
    assert "sections" not in view and view["cards"][0]["title"] == "Cameras"


def test_every_template_uses_real_widgets():
    for name in builder.list_templates():
        for sec in builder.load_template(name)["sections"]:
            for w in sec["widgets"]:
                assert "cards" in builder.load_widget(w), w


def test_user_template_dir_overrides(tmp_path):
    (tmp_path / "mine.yaml").write_text("title: Mine\nview_type: sections\nsections:\n  - title: X\n    widgets: [weather]\n")
    assert "mine" in builder.list_templates([tmp_path])
    cfg = builder.render(builder.load_template("mine", [tmp_path]), {"weather": "weather.a"})
    assert cfg["title"] == "Mine"


@pytest.mark.parametrize("bad", ["../x", "A", "a/b", ""])
def test_template_names_are_safe(bad):
    with pytest.raises(ValueError):
        builder.load_template(bad)
