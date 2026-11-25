"""Dashboard builder: discover entities -> render a template -> Lovelace config.

Widgets never change when you swap looks; a template only picks which widgets
go in which section, the view type and the theme. See docs/templates.md.
"""
from __future__ import annotations

import copy
import re
from pathlib import Path

import yaml

HERE = Path(__file__).parent / "dashboard"
PLACEHOLDER = re.compile(r"\{\{\s*([a-z0-9_]+)\s*\}\}")


# --------------------------------------------------------------------------
# Loading
# --------------------------------------------------------------------------
def load_yaml(path: Path):
    with open(path) as fh:
        return yaml.safe_load(fh) or {}


def load_rules(path: Path | None = None) -> dict:
    return load_yaml(path or HERE / "discovery.yaml")


def template_dirs(extra: list[Path] | None = None) -> list[Path]:
    return [HERE / "templates", *(extra or [])]


def list_templates(extra: list[Path] | None = None) -> list[str]:
    names = set()
    for d in template_dirs(extra):
        if d.is_dir():
            names.update(p.stem for p in d.glob("*.yaml"))
    return sorted(names)


def load_template(name: str, extra: list[Path] | None = None) -> dict:
    if not re.fullmatch(r"[a-z0-9_-]+", name or ""):
        raise ValueError("template names are lowercase letters, digits, - and _")
    # user templates (in /share) win over bundled ones with the same name
    for d in reversed(template_dirs(extra)):
        p = d / f"{name}.yaml"
        if p.is_file():
            return load_yaml(p)
    raise FileNotFoundError(f"template {name!r} not found")


def load_widget(name: str) -> dict:
    if not re.fullmatch(r"[a-z0-9_]+", name):
        raise ValueError(f"bad widget name {name!r}")
    return load_yaml(HERE / "widgets" / f"{name}.yaml")


# --------------------------------------------------------------------------
# Discovery
# --------------------------------------------------------------------------
def discover(states: list[dict], registry: list[dict] | None, rules: dict,
             overrides: dict[str, str] | None = None) -> dict:
    """Map rule keys -> entity_id (or list of entity_ids for `multiple` rules)."""
    live = {s["entity_id"] for s in states if s.get("state") not in (None, "unavailable")}
    known = {s["entity_id"] for s in states}
    platform_of = {}
    disabled = set()
    for e in registry or []:
        platform_of[e["entity_id"]] = e.get("platform")
        if e.get("disabled_by") or e.get("hidden_by"):
            disabled.add(e["entity_id"])
    have_registry = bool(registry)

    found: dict = {}
    for key, rule in rules.items():
        domain = rule.get("domain")
        pats = [re.compile(p) for p in rule.get("match", [])]
        excl = [re.compile(p) for p in rule.get("exclude", [])]
        platforms = set(rule.get("platforms", []))
        hints = [h.lower() for h in rule.get("hints", [])]

        def ok(eid: str) -> bool:
            if eid in disabled:
                return False
            if domain and not eid.startswith(domain + "."):
                return False
            if pats and not any(p.search(eid) for p in pats):
                return False
            if any(p.search(eid) for p in excl):
                return False
            if platforms:
                if have_registry and eid in platform_of:
                    return platform_of[eid] in platforms
                # no registry info: fall back to name hints
                return not hints or any(h in eid for h in hints)
            return True

        # prefer entities that are currently reporting a value
        candidates = sorted((e for e in known if ok(e)), key=lambda e: (e not in live, e))
        if rule.get("multiple"):
            if candidates:
                found[key] = candidates
        elif candidates:
            found[key] = candidates[0]

    for key, value in (overrides or {}).items():
        if not value or value in ("-", "none"):
            found.pop(key, None)  # explicit "hide this"
        elif rules.get(key, {}).get("multiple"):
            found[key] = [v.strip() for v in value.split(",") if v.strip()]
        else:
            found[key] = value.strip()
    return found


def parse_overrides(lines: list[str] | None) -> dict[str, str]:
    """Add-on option lines like 'thermostat=climate.living_room'."""
    out = {}
    for line in lines or []:
        if "=" in line:
            k, v = line.split("=", 1)
            out[k.strip()] = v.strip()
    return out


# --------------------------------------------------------------------------
# Rendering
# --------------------------------------------------------------------------
def _sub(value, ctx: dict):
    if isinstance(value, str):
        whole = PLACEHOLDER.fullmatch(value.strip())
        if whole:
            return ctx[whole.group(1)]
        return PLACEHOLDER.sub(lambda m: str(ctx[m.group(1)]), value)
    if isinstance(value, list):
        return [_sub(v, ctx) for v in value]
    if isinstance(value, dict):
        return {k: _sub(v, ctx) for k, v in value.items()}
    return value


def _present(keys, ctx) -> bool:
    return all(ctx.get(k) not in (None, [], "") for k in keys or [])


def render_cards(cards: list, ctx: dict) -> list:
    out = []
    for card in cards:
        card = copy.deepcopy(card)
        needs = card.pop("_requires", [])
        unless = card.pop("_unless", [])
        repeat = card.pop("_repeat", None)
        if not _present(needs, ctx):
            continue
        if unless and _present(unless, ctx):
            continue
        if repeat:
            items = ctx.get(repeat["over"]) or []
            for item in items:
                out.append(_sub(card, {**ctx, repeat["as"]: item}))
        else:
            out.append(_sub(card, ctx))
    return out


def render_widget(name: str, ctx: dict) -> list:
    w = load_widget(name)
    if not _present(w.get("requires"), ctx):
        return []
    return render_cards(w.get("cards", []), ctx)


def render(template: dict, found: dict, extras: dict | None = None) -> dict:
    ctx = {**(extras or {}), **found}
    title = template.get("title", "Home")
    view_type = template.get("view_type", "sections")
    sections = []
    for sec in template.get("sections", []):
        cards = []
        for widget in sec.get("widgets", []):
            cards.extend(render_widget(widget, ctx))
        if cards:
            sections.append((sec.get("title"), cards))

    view = {"title": title, "path": "home"}
    if template.get("theme"):
        view["theme"] = template["theme"]
    if view_type == "sections":
        view["type"] = "sections"
        view["max_columns"] = template.get("max_columns", 4)
        view["sections"] = [
            {"type": "grid", "cards": ([{"type": "heading", "heading": t}] if t else []) + c}
            for t, c in sections
        ]
    else:  # masonry / panel-free classic layout
        view["cards"] = [
            {"type": "vertical-stack", "title": t, "cards": c} if t else {"type": "vertical-stack", "cards": c}
            for t, c in sections
        ]
    return {"title": title, "views": [view]}


def build(states, registry, template_name, overrides=None, extras=None, extra_template_dirs=None):
    rules = load_rules()
    found = discover(states, registry, rules, overrides)
    template = load_template(template_name, extra_template_dirs)
    return render(template, found, extras), found
