# CLAUDE.md

## Project overview

Swedish DAB+ radio metadata collector. Polls "now playing" song metadata from three operators (Sveriges Radio, Viaplay Radio, Bauer Media) and stores it in Azure Table Storage. The goal is to test the hypothesis that Viaplay Radio's metadata pipeline occasionally emits corrupt bytes (C1 control chars, trailing bidi-format characters) that crash the MG Marvel car radio's DAB+ receiver.

## Architecture

- **Azure Functions** (Python 3.12, Linux Consumption plan) in resource group `mg-radio`, subscription `Labs` (`f65aae7b-5c8a-46aa-b3a1-fe5a51c2e552`), region `swedencentral`.
- **Azure Table Storage** (`mgradiostorage`, table `plays`): PartitionKey = channel slug, RowKey = `{starts_at}_{hash(artist|title)}`.
- **Two timer triggers** in `function_app.py`:
  - `poll_channels` (every 1 min): SR via `api.sr.se` + Bauer via `listenapi.planetradio.co.uk`.
  - `collect_khz` (every 10 min): Viaplay via Socket.IO at `wss://beat.khz.se`, holds WS ~9m20s per invocation.

## Key files

- `function_app.py` — Azure Functions entry point (two timer triggers).
- `radio_watermarks/channels.py` — SR + Bauer channel registry (polled per-channel).
- `radio_watermarks/sources/khz_socketio.py` — Viaplay Socket.IO client + full 23-channel ID → station name map.
- `radio_watermarks/sources/sr.py` — Sveriges Radio API fetcher.
- `radio_watermarks/sources/bauer_planetradio.py` — Bauer Planet Radio API fetcher.
- `radio_watermarks/storage.py` — Azure Table Storage writer with dedup.
- `radio_watermarks/analyze.py` — local CLI for char-level analysis.
- `findings.md` — analysis results and hypothesis status.

## Commands

```bash
# Local smoke test
python -c "from radio_watermarks.poller import poll_all; print(poll_all())"

# Deploy
az functionapp deployment source config-zip --resource-group mg-radio --name mg-radio-func --src deploy.zip --build-remote true

# Analyze
python -m radio_watermarks.analyze --group suspect
python -m radio_watermarks.analyze --channel khz_star_fm

# Start / stop function app
az functionapp start --name mg-radio-func --resource-group mg-radio
az functionapp stop --name mg-radio-func --resource-group mg-radio
```

## Notes

- SR's Akamai WAF occasionally blocks IPs that poll too aggressively. The Azure Function IP currently works; local IP may be blocked. User-Agent header is set but doesn't help once blocked — just wait for the block to expire.
- The `deploy.zip` is built manually (see commit history for the Python zip-builder one-liner). Exclude `.venv`, `local.settings.json`, `pass*_*.txt`, `findings.md`, `.claude/`.
- `local.settings.json` contains the Azure Storage connection string and is gitignored.
