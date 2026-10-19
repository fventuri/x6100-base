# X6100 Maintenance Manual — pin/net evidence

## Source

Xiegu *X6100 Portable HF Transceiver — Product Maintenance Manual*,
Version V1.0 (30 content pages), supplied by the user at
`~/X6100/X6100_Maintenance_manual.pdf` (not committed). It is an OEM
service document: block diagrams, board photos, fault tables, and
**test-point / rail voltage tables with signal names**. That naming and
the stated RX/TX behavior are what make it useful for interpreting the
BASE firmware GPIO map; it does not give an MCU pinout.

The manual confirms the architecture already recovered from firmware:
zero-IF (ZIF), **STM32F429** main control (block diagram p.2; the chip
photo reads STM32F427 — same F42x 144-pin LQFP family, consistent with
`docs/g90_comparison.md`), **CS4272** I/Q converter, **TLV320AIC3204**
("IC3204") audio codec, with KEY / MIC / S/P / ACC / DC-battery blocks.

## Power rails and their RX/TX behavior (p.8) — VERIFIED (OEM table)

The small-signal-board measurement points are named:

| Pt | Rail | Name | State |
| --- | --- | --- | --- |
| 2 | **+5A** | utility 5 V | always on |
| 3 | **+3.3A** | baseband-unit supply | always on |
| 4 | **+3.3LO** | local-oscillator-unit supply | always on |
| 5 | **+5R** | receiving 5 V supply | **5 V in RX, 0 V in TX** |
| 6 | **+5T** | transmitting 5 V supply | **5 V in TX, 0 V in RX** |
| D2 | +3.3 | MCU-unit supply | always on |

So **`+5R` and `+5T` are real, complementary, RX/TX-switched rails** —
not a guess. This is the single most useful fact in the manual for the
GPIO work. It also settles that `+5R` is *not* PD3: PD3 is the
front-panel power/charge LED (bench-VERIFIED, on when idle), whereas
`+5R` is a receive-only rail — different signals.

Related: LO1 = 26.000 MHz TCXO reference (3.6 Vpp), LO2 = 14.270 MHz LO
output (5.9 Vpp) (p.8/p.10). Power-module connector pins are
`+6 / GND / VSW / 3.3V / PSYNC`, and **PSYNC is the "power-supply
synchronizing" square wave** (p.10) — the firmware's `PSYNC` / LO-output-4
harmonic-avoidance signal (`docs/rf_switching.md`,
`docs/frequency_control.md`). VERIFIED net name.

## What this adds to specific firmware pins

### +5R / +5T enable ↔ the PA enable tuple (NEW hypothesis)

`docs/pa_control.md` / `docs/gpio.md` established a complementary RX/TX
tuple: in TX **PE8 = PG11 = 1 and PE9 = 0**; in RX the reverse, with the
hardware-variant callback following PE8/PG11. The manual now gives two
complementary rails with exactly that polarity:

- **PE8 / PG11** (high in TX) → candidate **`+5T` enable** (transmit rail / PA)
- **PE9** (high in RX) → candidate **`+5R` enable** (receive rail / RX front end)

This is a natural candidate mapping, **HYPOTHESIS / MEDIUM CONFIDENCE**:
the manual proves the rails and their polarity, the firmware proves the
GPIO polarity, but the wire between them is not shown. It is directly
benchable — probe test points 5 (`+5R`) and 6 (`+5T`) while a dev
firmware toggles PE8/PE9/PG11 (the same bisection method that resolved
PD3 and PG0/PG1). It also means the earlier "**PD4 = +5T** candidate"
should be treated with caution: the tuple pins are now the stronger
candidates, and PD4's role is re-opened (`docs/gpio.md`,
`docs/charger.md`).

### PE2 = ACC `TRX` (T/R switch) — corroborated

p.15 documents the ACC interface (a 4-core 3.5 mm stereo plug) and directs
the technician to verify the **T/R switching level** and the **band
voltage**. This independently supports `docs/acc.md`'s PE2 = ACC `TRX`
(RX = 0, TX = 1) and the band-voltage output below. HIGH CONFIDENCE
role unchanged; now backed by the OEM service text, not only the user
manual.

### PA5 / DAC2 = ACC `BAND_V` — corroborated

The ACC "band voltage" (p.15) is the band-dependent analog voltage that
`docs/analog.md` traced to DAC2 / PA5 (ACC `BAND_V`, HIGH CONFIDENCE).
The G90 labels the same pin `PRESELV`; the manual confirms the X6100
exposes it as the ACC band voltage.

### External-supply sense = `VEXT` (p.20) — net name recovered

The battery-charge fault section names the **`VEXT` input protection
diode**. `VEXT` (external DC input) is the quantity `docs/charger.md` /
`docs/analog.md` measure on **ADC2 ch6 / PA6** (`× 4.835165` → mV). The
manual gives the OEM net name for that sense. The charging-control
check-points (A1 = 3.28 V charging / 0 off; A2 = 0 / 0.68 V; A3 = 6.23 V /
0 off, p.20) are analog nodes of the charger circuit the MCU gates via
PF12; the manual does **not** name the MCU charger pins (PF12 / PE13 /
PF11 / PG4), so those remain as in `docs/charger.md`.

### Preamp enable = `#PRE_EN` (p.14) — net name confirmed

"Check whether the PRE control signal **`#PRE_EN`** and AS179 controlled
voltage turn normally." Confirms `#PRE_EN` (active-low preamp enable)
as a real X6100 net — the same name the G90 uses (G90 PC2). The X6100
RX front end uses an **AS179** RF switch for the preamp.

### Internal-speaker path uses an LM386 + `S/P` (p.13)

The internal speaker is driven by an **LM386** audio power amp (test
point P2 = LM386 pin 5 output); the **`S/P`** (speaker/phone) seat
switches internal speaker vs. headphone. This frames the bench-verified
**PG1 = internal-speaker / HPR enable** and **PG0 = loudness**
(`docs/gpio.md`): the codec HPR feeds the LM386 speaker amp, gated/jack-
switched by `S/P` (jack detect = PF15). Roles unchanged; the amp topology
is now known.

### PA bias (p.16)

PA quiescent-current tuning sets the grid voltages of MOS tubes A/B via a
**"DAC conversion chip at point C"** — the external I2C1 bias device at
`0x63` (`docs/analog.md`, `docs/pa_control.md`,
`PA_drive_stage_current` / `PA_final_stage_current`). "`+5T` must read 5 V
during TX" ties the PA to the `+5T` rail above. MIC supply `VH` = 8 V
(p.18).

### Front-panel indicator LED(s)

p.25 documents a **bi-color power/indicator LED (common anode), green in
RX / red in TX**, measured on the **control board (R16 side)**. This is
distinct from the BASE **PD3** power/charge LED (bench-VERIFIED). Noted so
the two are not conflated: the T/R color indicator is control-board
driven; PD3 is the BASE charge LED.

## Net-name vocabulary recovered (for reuse in the docs)

`+5A`, `+3.3A`, `+3.3LO`, `+5R`, `+5T`, `VEXT`, `VSW`, `PSYNC`, `TRX`
(ACC T/R), `BAND_V` (ACC band voltage), `#PRE_EN`, `VH` (mic 8 V),
`S/P` (speaker/phone), `LO1`/`LO2`. These align with and extend the
Xiegu house names seen in `docs/g90_comparison.md`.

## Benchable follow-ups this opens

1. **+5R/+5T ↔ GPIO**: toggle PE8 / PE9 / PG11 in a read-safe dev
   firmware and watch test points 5/6. Confirms or refutes the tuple
   mapping and re-tests PD4.
2. **Charger pins**: fold the `VEXT`/charging-control nodes (A1–A3) into
   the planned `bms-status-readout` bench run (see
   `x6100-base-experiments/claude/PLAN-bms-status-readout.md`) when
   probing PE13 / PG4.

## Confidence summary

- Rail names, RX/TX behavior, PSYNC, VEXT, #PRE_EN, LM386, ACC T/R +
  band voltage, PA bias DAC: **VERIFIED** as stated in the OEM manual.
- `+5R`/`+5T` → PE9 / PE8+PG11 mapping: **HYPOTHESIS / MEDIUM
  CONFIDENCE** (rails and GPIO polarity each proven; the connection is
  inferred and benchable).
- PE2 = ACC TRX, PA5 = BAND_V: **HIGH CONFIDENCE** (now corroborated by
  the service manual).
