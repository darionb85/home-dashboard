# Layouts (templates) and themes

Three layers, each swappable on its own:

| Layer | What it is | Where |
|---|---|---|
| **Widgets** | What each device shows (cards + which entities) | `home_dashboard/app/dashboard/widgets/*.yaml` |
| **Template** | Which widgets go in which section, view type, column count, theme name | `…/dashboard/templates/*.yaml` or `/share/home_dashboard/templates/*.yaml` |
| **Theme** | Colors/fonts (e.g. Catppuccin) | installed via Marketplace or `/config/themes/` |

Switching looks never touches widgets or device setup.

## Switch template

**Dashboard setup** → pick from the dropdown → **Build dashboard**. To make it the default after a reboot, set the add-on's `template` option to the same name.

Bundled:
- `catppuccin` (default): Catppuccin *Auto Latte Mocha* (light/dark follows your device), 4-column sections.
- `minimal`: stock theme, classic masonry, cameras first. A starting point for your own.

## Make your own (5 minutes)

1. With File editor or Samba, create `/share/home_dashboard/templates/mylook.yaml`:
   ```yaml
   title: Home
   theme: Catppuccin Macchiato        # any installed theme name, or "default"
   view_type: sections                # sections (modern grid) | masonry (classic)
   max_columns: 3                     # sections only
   sections:
     - title: Now
       widgets: [weather, thermostat, ecoflow]
     - title: Cameras
       widgets: [cameras]
     - title: Everything else
       widgets: [calendar, tesla, grow, network, plugs, ai_usage]
   ```
2. Dashboard setup → reload the page → choose `mylook` → Build.

A template file with the same name as a bundled one replaces it. Widgets with no matching devices drop out, and so do empty sections.

Available widgets: `weather, calendar, thermostat, ecoflow, tesla, cameras, grow, network, plugs, ai_usage`.

## Using a layout you found online

Most shared HA dashboards are either **a theme** (colors only; Catppuccin is one) or **a full dashboard YAML**.
- **Theme:** install it, then put its name in `theme:` of a template. Done.
- **Full dashboard YAML:** send it to me, or copy its section order and card style into a template. If it relies on custom cards (Mushroom, bubble-card, etc.), install those from the Marketplace and add a widget variant that uses them. Widgets are plain Lovelace cards with `{{placeholders}}`, so `widgets/thermostat.yaml` can become a `custom:mushroom-climate-card` in a few lines.

## Widget file format (for edits)

```yaml
requires: [thermostat]             # widget is skipped unless all of these were found
cards:
  - type: thermostat               # any Lovelace card
    entity: "{{thermostat}}"       # placeholder = a key from discovery.yaml
  - _requires: [ecoflow_in]        # just this card is optional
    type: tile
    entity: "{{ecoflow_in}}"
  - _repeat: {over: cameras, as: cam}   # one card per item in a list key
    type: picture-entity
    entity: "{{cam}}"
```

## Bypass the builder entirely

Dashboard setup → **Download YAML** → in HA create a new dashboard → ⋮ → *Raw configuration editor* → paste. From then on you hand-edit it.
