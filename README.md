# SNJ Mesh Weather Bot

A Discord bot that posts live weather conditions, NWS alerts, tides, air quality, and hurricane tracking for Southern New Jersey — Atlantic, Burlington, Camden, Cape May, Cumberland, Gloucester, and Salem counties.

Conditions are pulled from a personal weather station (PWS) via the Aeris/Xweather API. Alerts, forecasts, tides, air quality, and tropical storm data come from NWS, NOAA CO-OPS, EPA AirNow, and the National Hurricane Center.

## Features

- **Live conditions** that update in place on a single pinned message — temperature, feels-like, humidity/dewpoint, wind, barometric trend, rain, UV, and sunrise/sunset — with a manual Refresh button
- **NWS alerts** posted automatically as they're issued, updated, or cancelled, filtered to Southern NJ by an explicit set of 10 NWS forecast zones and 7 county codes (see below) — not a heuristic — with a configurable severity threshold and a per-type suppression list
- **Weekly outlook** auto-posted on a configurable day/time — forecast, tides, air quality, and active alert count
- **Slash commands** for on-demand conditions, alerts, forecasts, tides, AQI, hurricane status, radar links, and bot health
- **Built to stay up** — per-service circuit breakers and exponential-backoff retries mean one flaky upstream API degrades gracefully instead of taking the bot down, state is written atomically so a crash mid-write can't corrupt it, and an NWS outage is never mistaken for "no active alerts" (so it can't trigger false all-clears)

## Coverage area

Alerts are matched against the 7 Southern NJ counties by NWS UGC code — Atlantic, Burlington, Camden, Cape May, Cumberland, Gloucester, and Salem — using the specific forecast zones NWS Mount Holly issues for them:

| Zone | County | Zone | County |
|---|---|---|---|
| NJZ016 | Salem | NJZ022 | Atlantic |
| NJZ017 | Gloucester | NJZ023 | Cape May |
| NJZ018 | Camden | NJZ024 | Atlantic Coastal Cape May |
| NJZ019 | NW Burlington | NJZ025 | Coastal Atlantic |
| NJZ021 | Cumberland | NJZ027 | SE Burlington |

Ocean, Mercer, Middlesex, Monmouth, and every other NJ county are intentionally excluded. An alert only needs to touch *one* of the zones/counties above to post — a storm spanning both Southern and Central NJ will still show up.

## Commands

| Command | Description |
|---|---|
| `/conditions [station_id]` | Latest PWS reading; optionally query any Xweather station |
| `/alerts` | Active NWS alerts for the 7 Southern NJ counties |
| `/forecast [zipcode]` | NWS 7-day forecast; optionally for any US zip code |
| `/tides [station_id]` | High/low tide schedule; optionally any NOAA CO-OPS station |
| `/aqi` | Current + forecast EPA AirNow air quality (needs an API key) |
| `/hurricane` | NHC Atlantic tropical storm / hurricane status |
| `/radar` | Links to live NWS KDIX radar |
| `/status` | Bot uptime, last update times, circuit-breaker health |
| `/help` | Command list |

## Requirements

- Python 3.10+
- A Discord application with a bot user ([discord.com/developers/applications](https://discord.com/developers/applications)), invited with the `bot` and `applications.commands` scopes
- An Aeris/Xweather account for your PWS station ([xweather.com](https://www.xweather.com/))
- Optional: an EPA AirNow API key for `/aqi` — free at [docs.airnowapi.org](https://docs.airnowapi.org/)
- Optional: `astral` for sunrise/sunset times

No privileged Gateway Intents are needed — the bot runs on `discord.Intents.default()`. In the server it's invited to, it needs View Channel, Send Messages, Embed Links, Read Message History, and (if you want the conditions message pinned) Manage Messages.

## Setup

```bash
git clone https://github.com/<you>/<repo>.git
cd <repo>
pip install -r requirements.txt
cp config.example.json config.json
```

Fill in `config.json` with your credentials (see reference below), then run:

```bash
python weather_bot.py
```

Startup validates `config.json` and exits with a specific, readable error for anything missing or malformed, so a bad config fails fast instead of failing quietly later.

## Configuration reference

| Key | Default | Notes |
|---|---|---|
| `pws_station_id` | — | **Required.** Your Aeris/Xweather PWS station ID |
| `pws_client_id` / `pws_client_secret` | — | **Required.** Aeris/Xweather API credentials |
| `discord_bot_token` | — | **Required.** From the Discord Developer Portal |
| `discord_channel_id` | — | Channel the bot posts conditions and alerts to |
| `discord_guild_id` | none | Optional — enables near-instant slash-command sync for one server instead of the ~1 hour global sync |
| `location_name` | "Southern NJ" | Display name used in embeds |
| `conditions_update_mins` | 30 | How often the conditions message refreshes |
| `conditions_repost_hours` | 4 | Repost as a new message (instead of editing) after this long |
| `pin_conditions_message` | true | Pin the conditions message |
| `alert_interval_secs` | 300 | How often NWS alerts are polled |
| `alert_post_threshold` | "all" | `all` / `watch` / `warning` — minimum severity auto-posted to the channel |
| `alert_suppress_types` | [] | Specific event names to never auto-post, e.g. `"Small Craft Advisory"` |
| `forecast_lat` / `forecast_lon` | 39.455 / -74.722 | Default forecast location |
| `tide_station_id` / `tide_station_name` | 8534720 / "Atlantic City, NJ" | Default NOAA CO-OPS tide station |
| `airnow_api_key` | none | Optional — enables `/aqi` and AQI threshold alerts |
| `aqi_alert_threshold` | 3 | AQI category (1–6) that triggers an alert |
| `weekly_summary_day` / `weekly_summary_hour` | 6 / 8 | When the weekly outlook posts (0=Mon … 6=Sun, hour in ET) |

Suppressed or below-threshold alerts still show up in `/alerts` — they're just not auto-posted to the channel.

## Running continuously

This is a single long-running process with no built-in daemonization. Run it under `systemd`, `tmux`/`screen`, `pm2`, or your process supervisor of choice so it restarts if it ever exits. Logs go to `weather-bot.log`, with the previous run kept as `weather-bot.log.1`. `state.json` self-trims resolved alert entries older than 48 hours, so it won't grow without bound.

## Data sources

- Conditions: [Aeris/Xweather](https://www.xweather.com/)
- Alerts & forecasts: [National Weather Service](https://www.weather.gov/)
- Tides: [NOAA CO-OPS](https://tidesandcurrents.noaa.gov/)
- Air quality: [EPA AirNow](https://www.airnow.gov/)
- Tropical systems: [National Hurricane Center](https://www.nhc.noaa.gov/)

Independent project — not affiliated with or endorsed by NOAA, NWS, EPA, or NHC.

## License

[GNU General Public License v3.0](LICENSE) or later. You're free to run, study, modify, and share this. If you distribute a modified version (share the code, publish a fork, etc.), it must also be GPLv3 with source available. Note that GPLv3 doesn't require this for running a modified copy privately as a hosted bot without distributing the code — only AGPLv3 covers that case, and this project doesn't use it.

---

*Built by compy / KD2QED.*
