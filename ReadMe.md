# Description

Download, store and anlyze radio channel song meta data.

## The problem

In my car (MG Marvel) I listen to radio via DAB in Sweden. For some radio channels the radio crashes, I can't restart it or change to "regular" radio etc.

## Hypothesis

This happens only on some channels, I believe from the same operator. The hyopthesis I want to test is that this operator sends metadata on songs which somehow crashes the MG radio player. Either via charactrers which aren't supported or something else.

## DAB metadata protocols

DAB+ carries metadata through several standardized ETSI channels:

- **DLS (Dynamic Label Segment)** — scrolling "Artist - Title" text, max 128 chars per segment, chainable to ~256. Defined in **ETSI EN 300 401**.
- **DLS+ (Dynamic Label Plus)** — structured tags inside the DLS bytes: `ITEM.TITLE`, `ITEM.ARTIST`, `STATIONNAME`, etc. **ETSI TS 102 980**.
- **SLS (Slideshow)** — images (typically album art) transported via MOT. **ETSI TS 101 499**.
- **EPG / SPI** — programme schedule, XML. **ETSI TS 102 818 / 102 371**.

### Character encoding — likely crash vector

DLS text can be carried in any of four charsets, selected by a header byte:

| Byte  | Charset              |
|-------|----------------------|
| `0x00`| ISO/IEC 6937 (ITU Latin, default) |
| `0x01`| ISO 8859-1           |
| `0x04`| ISO 10646-2 (UCS-2 / UTF-16BE) |
| `0x0F`| UTF-8                |

If the encoder signals one charset but sends bytes in another, or emits a malformed UTF-8/UCS-2 sequence, cheap receivers regularly mishandle it — display garbage at best, crash at worst. Other known triggers: overrunning the 128-byte segment, truncating mid-codepoint, zero-length DLS+ tag content.

## What's in this repo

Collection is split by source:

- **Sveriges Radio** (public broadcaster, control group): polled per-channel via `https://api.sr.se/api/v2/playlists/rightnow` — `radio_watermarks/sources/sr.py`.
- **Commercial stations incl. Star FM** (suspect group): captured from the Socket.IO stream at `wss://beat.khz.se/socket.io/` — `radio_watermarks/sources/khz_socketio.py`. Channel `94` = Star FM (confirmed).
- Storage: Azure Table Storage `plays` table — `radio_watermarks/storage.py`.
- Hosting: Azure Functions on Consumption plan (`function_app.py`) with two timers:
  - `poll_channels` — every 1 min (SR).
  - `collect_khz` — every 10 min, holds WebSocket for ~9m20s.
- Analysis: `radio_watermarks/analyze.py` — char histogram, control-char scan, compares suspect vs control groups.

### Azure resources (subscription: Labs)

- Resource group `mg-radio` in `swedencentral`
- Storage account `mgradiostorage`
- Function App `mg-radio-func`
- Application Insights `mg-radio-insights`

### Caveat on web-sourced data

The web APIs normalize text to UTF-8 server-side. The DLS bytes the car radio actually receives may differ. If the web-data hypothesis survives, the next step is capturing real DAB+ bytes with an RTL-SDR.

## Next step: capture real DAB+ DLS bytes

### Phase A — Hardware (~€30–50, one-time)

1. **RTL-SDR Blog v4** dongle (~€30). Avoid unbranded clones.
2. **Antenna for Band III (174–240 MHz).** Telescopic VHF whip for bench testing; outdoor DAB antenna for reliable reception near the location where the crash occurs.
3. Optional USB extension so the dongle doesn't block other ports.

### Phase B — Software

- **welle.io** (https://welle.io/) — open-source DAB+ receiver, Windows/Mac/Linux. Shows DLS + DLS+ tags live, saves slideshow images, has raw-log mode. Primary tool.
- **dablin** (Linux CLI) — useful for scripting captures.

### Phase C — Find the right multiplex

Sweden's DAB+ topology:

- **SR Rikstäckande** (public) — carries P1/P2/P3/P4 on its own mux. Typically blocks 11C/11D.
- **Teracom Rikstäckande** (commercial trial mux) — where Viaplay's Star FM rides. Block depends on region (typically 12A–12D).

**TODO:** next time in the car during/near a crash, note the MG Marvel's ensemble name / frequency / block (e.g. "12B 225.648 MHz" or "Teracom Riks"). That pins down the mux for welle.io.

### Phase D — Capture workflow

1. Plug in RTL-SDR, install welle.io, scan for ensembles in your area.
2. Tune the ensemble carrying Star FM, select the service.
3. Enable **"Save DLS"** in welle.io — writes raw DLS bytes with timestamps.
4. Enable slideshow saving (SLS) in case the crash is an image-decoder issue.
5. Leave it running alongside a car listening session where the crash actually happens, so timestamps can be lined up.

### Phase E — Compare

- DLS bytes (SDR) vs. API text (Azure Table Storage).
- Check the charset header byte of each DLS segment (`0x00` / `0x01` / `0x04` / `0x0F`).
- Scan for truncated codepoints, zero-length DLS+ tags, oversized segments.
- Correlate crashes against specific bytes / tags / encoding switches.

## Local dev

```
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
# Set AzureWebJobsStorage from local.settings.json
python -c "from radio_watermarks.poller import poll_all; print(poll_all())"
```

## Deploy

```
az functionapp deployment source config-zip \
    --resource-group mg-radio --name mg-radio-func \
    --src deploy.zip --build-remote true
```

## Analyze

```
python -m radio_watermarks.analyze --group suspect
python -m radio_watermarks.analyze --channel khz_star_fm
```
