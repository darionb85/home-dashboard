# iCloud Reminders & Notes: later build (plan)

Apple has no sign-in that other apps can use for Reminders or Notes, and Notes has no API at all. The reliable route is your iPhone pushing the data to Home Assistant.

## Plan
1. **HA side (I'll add to the add-on):** a `POST /ingest/reminders` endpoint protected by the write token. It stores the list and exposes it as `sensor.icloud_reminders` (count as the state, items as an attribute), plus a `reminders` widget.
2. **iPhone side:** a Shortcut that runs **Find Reminders** (not completed, due in the next 7 days, a chosen list) → builds JSON (title, due date, list) → **Get contents of URL** (POST over Tailscale, `Authorization: Bearer <write token>`).
3. **Automation:** Shortcuts → Automation → *Time of Day* every hour, and *When Reminders app is closed* → run the Shortcut, with *Ask before running* off.
4. **Notes:** the same pattern, but only for one pinned note: **Find Notes** with name = "Dashboard" → send its text. A full Notes sync isn't realistic.

Read-only to start. Ticking a reminder off from the dashboard would need a second Shortcut fired by HA's iOS app notifications. That's possible later.
