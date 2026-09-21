# ICT Geometry Lock — Gap Closure H

**Version:** `H-2026-09-21`  
**Status:** FROZEN for this pass (validate → one freeze hash → no OOS)

## Locks

| Law | Choice |
|-----|--------|
| FVG | **B** — wick gap + middle-candle displacement |
| Killzones | **C** — default `mentorship_2017` |
| OTE | **B** — `require_ote=true`, `ote_mode=soft_score` |
| Liquidity model default | `session_pools` (do not switch without validate evidence) |

## FVG=B

- 3-candle pattern at bar close `i` (candles `i-2`, `i-1`, `i`).
- Bullish: `low[i] > high[i-2]` → gap `[high[i-2], low[i]]`.
- Bearish: `high[i] < low[i-2]` → gap `[high[i], low[i-2]]`.
- Middle candle (`i-1`) **must** be displacement (`fvg_require_displacement_candle=True`).
- `fvg_ce = (top + bottom) / 2`.
- **Mitigation** = first CE touch (wick or body). Event: `FVG_MITIGATED`.
- **Invalidation** = body close through far side (not mitigation). Event: `SETUP_INVALIDATED` reason `fvg_far_side_close`.
- Post-raid displacement remains a separate narrative gate (not conflated with FVG middle-candle rule).

## Order blocks / breakers

- Breaker created when price closes through OB extreme (existing causal rule).
- `BREAKER_RETESTED` = price revisits breaker CE after creation.

## Sweeps / raids

- Causal session pools only (ASH/ASL shifted by 1 for same-bar safety).
- Grades A/B/C from quality + linked displacement + MSS.

## MSS vs CHoCH

- **CHoCH**: first break against prior structure (no raid+disp required).
- **MSS**: body close beyond opposing swing **after** linked raid + displacement.

## Killzone tables (NY clock)

### mentorship_2017 (default)

| Window | Hours (NY) |
|--------|------------|
| Asia / ASH-ASL | 20:00–00:00 |
| London KZ | 01:00–05:00 |
| NY KZ | 07:00–10:00 |
| Silver Bullet | 03–04 / 10–11 / **14–15** |

### public_2016_2022

| Window | Hours (NY) |
|--------|------------|
| Asia | 20:00–00:00 |
| London KZ | 02:00–05:00 |
| NY KZ | 07:00–10:00 |
| SB | 10–11 / 14–15 |

### legacy_hybrid (attribution / regression only)

| Window | Hours (NY) |
|--------|------------|
| Asia | 00:00–06:00 |
| London KZ | 02:00–05:00 |
| NY KZ | 07:00–10:00 |
| SB | 03–04 / 10–11 / 15–16 |

## OTE

- Rolling lookback OTE (61.8–78.6) remains.
- Soft score: missing OTE reduces `soft_score` / confluence; **never hard-rejects** under `ote_mode=soft_score`.
- Future improvement (noted): prefer dealing-range OTE from raid/MSS — not this pass.

## Liquidity models (validate attribution only)

- `session_pools` (default)
- `eqh_eql_cluster`
- `window_extremes`

Do **not** change default without evidence in `LIQUIDITY_MODEL_ATTRIBUTION.md`.

## Explicit disagreements vs SMC lookahead

- No future-confirmed pivots for live decisions.
- No body-gap-only FVG without middle displacement under FVG=B.
- No hard OTE reject without later validate evidence.
- Timezone: source EET/EEST → America/New_York before KZ tags (SB 14–15 under mentorship).

## Config hash fields

Freeze candidate must include: `geometry_lock_version`, `kz_table`, `fvg_require_displacement_candle`, `require_ote`, `ote_mode`, `liquidity_model`.
