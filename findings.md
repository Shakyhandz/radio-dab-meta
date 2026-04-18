# Findings

Analysis of metadata collected into the `plays` Azure Table, across 29 channels: 6 Sveriges Radio (control, public broadcaster) and 23 `beat.khz.se` Socket.IO channels — **all Viaplay Radio** (suspect).

## Dataset summary

| Group   | Rows  | Channels | Total chars | Non-ASCII | Non-ASCII % |
|---------|-------|----------|-------------|-----------|-------------|
| suspect | 5,827 | 23       | 153,757     | 968       | 0.63 %      |
| control | 707   | 6        | 23,684      | 242       | 1.02 %      |

Note: the control group (SR) has *more* non-ASCII density than the suspect group — Nordic diacritics are common in SR's Swedish-language programming. Raw non-ASCII rate is not the discriminator; the *kind* of non-ASCII is.

## Channel identification

All 23 channels on the `beat.khz.se` Socket.IO stream are Viaplay Radio stations. IDs were confirmed by matching `now playing` data on viaplayradio.se/radiokanaler/ against the collected table in two passes 15 minutes apart (a match on both passes = confirmation).

| khz ID | Station             | khz ID | Station             |
|--------|---------------------|--------|---------------------|
| 2      | Bandit Rock         | 21     | Electro Lounge      |
| 3      | Rix FM              | 22     | Go Country          |
| 4      | Lugna Favoriter     | 25     | Skärgårdsradion     |
| 6      | Power Hit Radio     | 31     | Julkanalen          |
| 7      | Bandit Classic Rock | 32     | Sonic               |
| 8      | Bandit Metal        | 56     | Radio Rainbow       |
| 9      | Rix FM Fresh        | 64     | Bandit Ballads      |
| 10     | Bandit Alternative  | 72     | Guldkanalen         |
| 11     | Power Club          | 73     | Dansbandskanalen    |
| 12     | Power Street        | 94     | Star FM             |
| 13     | Soul Classics       | 95     | HitMix 90's         |
| 14     | Gamla Favoriter     |        |                     |
| 20     | Disco 54            |        |                     |

Note: an earlier draft of this document inferred `khz_11 = NRJ Fresh` and `khz_13 = Soul Classics (Bauer)` via playlist fingerprinting against onlineradiobox.com. The NRJ Fresh inference was wrong — coincidental current-hits overlap between Viaplay's Power Club and Bauer's NRJ Fresh. The Soul Classics inference was right on *station name* but wrong on *operator* — both Viaplay and Bauer happen to run a station called "Soul Classics"; the one on `beat.khz.se` is Viaplay's.

## Anomaly 1 — C1 control codepoints in a title (channel khz_13 = Soul Classics, Viaplay)

```
"There'\x80\x99s Nothing Like This"
```

- Positions: between `'` and `s`, i.e. where a curly apostrophe should be.
- Codepoints: **U+0080** and **U+0099** — both in the C1 control range (U+0080..U+009F), reserved as non-printable.
- Zero occurrences in the control group.

### Interpretation
Classic mojibake. A curly apostrophe `’` is U+2019; in UTF-8 it's three bytes `E2 80 99`. Some upstream step stripped the leading `E2` byte, leaving the bytes `80 99`, which were then interpreted as literal Unicode codepoints U+0080 and U+0099 rather than as the tail of a UTF-8 sequence. When this text is re-serialized — particularly when emitted as DLS/DLS+ bytes with any of the four ETSI-permitted charsets — the receiver parser encounters bytes it is not specified to handle. Plausible crash trigger on cheap DAB+ head units.

## Anomaly 2 — trailing U+202C (POP DIRECTIONAL FORMATTING) on khz_11 (= Power Club, Viaplay)

```
"Be Your Friend\u202c\u202c"
"Friday Night\u202c\u202c\u202c"
```

- U+202C is an invisible Unicode bidi format character (category `Cf`).
- Appears 5 times across khz_11 titles, always trailing the visible text.
- Zero occurrences in the control group.

### Interpretation
A title was copy-pasted from an editor that inserted RTL/LTR override markers; the "pop" terminators stuck. Less likely to crash than Anomaly 1, but a receiver that expects DLS+ `ITEM.TITLE` to terminate cleanly could behave oddly.

## Star FM (khz_94) — clean in this sample

188 rows of Star FM. Non-ASCII inventory: only ordinary Nordic diacritics (`å ä ö é`, uppercase equivalents) plus one U+2019 curly quote. No C1 chars, no format chars, no overlong fields.

### Hypothesis refinement

All anomaly-carrying channels (Soul Classics and Power Club) are Viaplay Radio, same as Star FM. The anomalies are consistent with the original hypothesis: **something in Viaplay's metadata pipeline occasionally emits corrupt bytes** (stripped UTF-8 leads, trailing bidi-format characters). It's not Star FM specifically — it's any Viaplay station whose current track's metadata happens to be dirty when the car radio is tuned in.

This is also consistent with the user report that the crash occurs "on some channels" and feels operator-correlated: the operator is Viaplay, but which channel crashes depends on which track Viaplay's pipeline recently mangled.

### Live observation — 2026-04-18 crash on Star FM

User crash report: MG Marvel DAB+ died at ~15:40 local (CEST = UTC+2) on Star FM. Radio recovered ~15 minutes later while Gyllene Tider was playing. Matched against `khz_star_fm` rows for 2026-04-18 13:00Z–14:30Z (17 rows in window):

| Local | Artist — Title | Anomaly |
|-------|----------------|---------|
| 15:30:19 | Wham! — Freedom | — |
| **15:34:50** | **Snap — Rhythm Is A Dancer** | **— (crash during this track, `run_length=221s` → ~15:38:31)** |
| 15:41:24 | Tina Turner — What's Love Got To Do With It | — |
| 15:51:46 | Gyllene Tider — ` Leva Livet` | leading 0x20 space (harmless) |
| 15:55:17 | Kim Wilde — Cambodia | — |
| 16:04:30 | Kate Ryan — Désenchantée | `é` = `c3 a9`, valid UTF-8 |

Full-payload scan (all 17 rows, entire Socket.IO envelope including `album_name`, `cover_art`, `genre`, `search_title`, ids): zero C1 controls, zero bidi-format chars, zero lone surrogates, zero malformed UTF-8.

**Interpretation.** The khz.se API row for the track playing at crash time was clean. That is a genuine counter-data-point: the hypothesis that every crash correlates with Anomaly-1-style C1 corruption in the captured metadata is not supported by this incident. Either (a) corruption entered downstream of khz.se, (b) the trigger is in a metadata channel we do not capture, or (c) the trigger is not metadata at all. See **Future research** below.

## Field lengths

All channels stay within the ETSI DLS ceiling (≤256 chars). Longest artist field observed: 133 chars on `sr_p2` (classical multi-composer credit). No length-based suspects.

## Top non-ASCII chars per group

### Suspect (khz)
| Codepoint | Char | Count | Name |
|-----------|------|-------|------|
| U+00E4 | ä | 261 | LATIN SMALL LETTER A WITH DIAERESIS |
| U+00F6 | ö | 217 | LATIN SMALL LETTER O WITH DIAERESIS |
| U+00E5 | å | 193 | LATIN SMALL LETTER A WITH RING ABOVE |
| U+00E9 | é | 119 | LATIN SMALL LETTER E WITH ACUTE |
| U+2019 | ’ | 40 | RIGHT SINGLE QUOTATION MARK |
| U+0117 | ė | 15 | LATIN SMALL LETTER E WITH DOT ABOVE |
| U+202C |   | 5 | POP DIRECTIONAL FORMATTING |
| U+0080 |   | 1 | (C1 control) |
| U+0099 |   | 1 | (C1 control) |

### Control (SR)
| Codepoint | Char | Count | Name |
|-----------|------|-------|------|
| U+00F6 | ö | 71 | LATIN SMALL LETTER O WITH DIAERESIS |
| U+00E4 | ä | 55 | LATIN SMALL LETTER A WITH DIAERESIS |
| U+00E5 | å | 47 | LATIN SMALL LETTER A WITH RING ABOVE |
| U+00E9 | é | 29 | LATIN SMALL LETTER E WITH ACUTE |

## Takeaways

1. **Concrete differentiator found:** C1 control codepoints and Unicode format characters appear in the Viaplay/khz data and not in the SR control data.
2. **Most likely crash vector:** Anomaly 1 (C1 chars from stripped UTF-8 leading bytes), because the resulting byte stream is malformed regardless of which of the four ETSI DLS charsets the encoder signals.
3. **Operator attribution confirmed:** all 23 khz channels are Viaplay Radio; Bauer is not represented in the suspect dataset. The anomalies are Viaplay-side.
4. **Which Viaplay channel crashes is opportunistic:** the current hypothesis says the crash depends on which track's metadata happens to be mangled at the moment the car tunes in — not on which station. Soul Classics and Power Club happened to ship dirty titles during our sample; any Viaplay station could in principle.
5. **Next step remains the SDR capture** (see `ReadMe.md` Phase D) — the web API data shows the upstream metadata has C1 char corruption; the DAB+ DLS capture is what confirms these bytes actually reach the receiver in the broadcast stream.

## Caveats

- Sample size modest: ~7k rows, ~24 hours of Viaplay data. One C1-char occurrence proves the pipeline *can* emit corrupt metadata; estimating frequency requires a longer run.
- Bauer collection is now active (10 stations via `listenapi.planetradio.co.uk`) as a secondary control group. Once enough Bauer rows accumulate, re-run the analysis with three groups (SR / Bauer / Viaplay) to test whether C1-char and bidi-char anomalies are Viaplay-specific or common to commercial operators.
- The current hypothesis predicts the crash can occur on any Viaplay station, not just Star FM. Next real-world crash: note the station on the display and check whether the just-played track on that channel carried a C1 char or other anomaly in the Azure table.

## Future research

The 2026-04-18 live observation — a real crash on a row with no detectable corruption in our capture — means the C1-character story covers at most *some* crashes. Alternatives worth investigating, in priority order:

### 1. Corruption enters downstream of the khz.se API

khz.se's Socket.IO feed and the DAB+ broadcast encoder are two branches off Viaplay's upstream metadata. Stages that could introduce malformed bytes after the API fork:

- **Charset-flag mismatch.** DLS declares one of ISO 6937 / ISO 8859-1 / UCS-2 / UTF-8 in its header byte (see ReadMe.md §"Character encoding"). If the encoder declares UTF-8 but ships Latin-1 (or vice versa), valid source bytes become malformed on-air while looking clean in our capture.
- **Mid-codepoint chunking.** A multi-byte UTF-8 character split across two 128-byte DLS segments leaves each segment internally malformed even when the source string is fine.
- **Malformed DLS+ tag headers.** A tag whose declared length exceeds the payload, or a zero-length `ITEM.TITLE`, could crash a strict parser.

Directly addressed by the RTL-SDR path already scoped in **ReadMe.md §"Next step: capture real DAB+ DLS bytes"** (Phases A–E). After today's observation this is the priority next step — it is the only way to compare on-air bytes against API bytes for the same track.

### 2. Trigger is in a metadata stream we don't capture

DAB+ carries more than DLS:

- **MOT Slideshow (SLS).** Album art shipped over MOT. A bad JPEG header, oversized file, or unexpected MIME type can crash an image decoder. We only record a `cover_art` *filename*; the broadcast ships the actual binary, which we never see.
- **Journaline / EPG / SPI.** Structured sidebands, often XML.
- **PAD framing.** Byte-level PAD headers around DLS and SLS — corruption here never touches a text field.

welle.io can dump SLS binaries and raw PAD alongside DLS — extend Phase D to save both.

### 3. Not metadata at all — audio codec

DAB+ audio is HE-AAC v2 (AAC-LC + SBR + PS). Specific frames — SBR parameter switches, PS mode changes, DSE payloads — have crashed decoder implementations in the field. A test: if the *same specific recording* of "Rhythm Is A Dancer" crashes the MG Marvel again on its next playout (on any Viaplay station), the audio chain becomes a stronger suspect than the metadata chain.

### 4. Signal / environmental

MG Marvel firmware could crash on low SNR, a multiplex reconfiguration event, or out-of-order frame sequences. Partial check without SDR hardware: do crashes correlate with specific road stretches / times of day independent of station and track?

### Evidence to collect on the next crash

- **Ensemble name / frequency / block** shown on the MG display (pins the mux for welle.io — ReadMe.md §Phase C).
- **Station name** as displayed (confirms operator).
- **Time to the minute** (for table-storage lookup and SDR log alignment).
- **Location and signal bars** if visible (for hypothesis 4).
