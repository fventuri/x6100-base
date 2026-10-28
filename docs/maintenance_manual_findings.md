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

### +5R / +5T enable = PD3 / PD4 (corrected)

> Correction (2026-10-28): an earlier draft of this section mapped the
> rails onto the PA tuple (PE8/PG11/PE9). SP5TLS's independent firmware
> reference (`~/X6100/x6100-base-SP5TLS/docs/mcu_reference.md`) and our
> own RX/TX GPIO sequences show the better fit is **PD3 / PD4**; the PA
> tuple is a separate signal. The corrected mapping follows.

The firmware drives **PD3 = 1 in RX / 0 in TX** and **PD4 = 0 in RX /
1 in TX** — exactly the manual's `+5R` (on in RX) / `+5T` (on in TX)
polarity. SP5TLS assigns **PD3 = `+5R`, PD4 = `+5T`** on that basis, which
matches the original firmware reading before our PD3 bench test.

- **PD3** (high in RX, low in TX) → **`+5R` receive-rail enable**
- **PD4** (low in RX, high in TX) → **`+5T` transmit-rail enable**

The **PA tuple** PE8/PG11 (high in TX) and PE9 (high in RX), with the
variant callback, is the **PA-stage enable** — a *distinct* signal that
co-asserts with `+5T`/`+5R` because the PA needs the transmit rail, not
the rail switch itself (`docs/pa_control.md`).

**Decisive confirmation (user, 2026-10-28):** the radio has a **single**
front-panel LED, and it is **green normally (RX) and red when transmitting
or while the ATU is tuning**. ATU tuning keys a carrier, i.e. TX. This is
a bi-color LED whose two elements map one-to-one onto the rails:

- **green element** lit by **`+5R`** (PD3, high in RX)
- **red element** lit by **`+5T`** (PD4, high in TX / tune)

That explains the PD3 bench result (driving PD3 high lit the LED, low
turned it off, radio idle = RX → green) without a dedicated "power LED"
line: PD3 is the `+5R` enable and the LED is the visible sign of the live
rail. A plain power LED would not track RX/TX. The earlier "PD3 = power
LED, not `+5R`" conclusion is therefore superseded.

Confidence: **PD3 = `+5R`, PD4 = `+5T` — HIGH CONFIDENCE**, convergent
across the firmware RX/TX levels, the LED colour behaviour, the manual's
rail table, and the SP5TLS reference. The only residual check is whether
PD3/PD4 switch the full receive/transmit rails or only the LED elements —
a multimeter at rail test points 5 (`+5R`) / 6 (`+5T`) across an RX→TX
transition settles it.

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

## SP5TLS independent reference cross-check

Michael Zabielski (SP5TLS) shared a single-page MCU reference
(`~/X6100/x6100-base-SP5TLS/docs/mcu_reference.md`) summarising his own
BASE 1.1.9 analysis. It is largely **independent corroboration** of this
project — same firmware hash, same core/clock/memory/IRQ/DMA/peripheral
facts — and it is the source that prompted the PD3/PD4 = `+5R`/`+5T`
correction above. Points of note when reconciling with our docs:

- **Corroborates** (independently reached the same result): bq24715
  charger at I2C1 `0x09` (`docs/charger.md`), 250 MHz SYSCLK /
  `RCC_PLLCFGR = 0x04403C0C` (`docs/clocks.md`), the shift-chain roles,
  the PCA9535/direct-GPIO variant callback table, PE2 = ACC `TRX`,
  PA5 = ACC `BAND_V`, PE15 = codec reset, the bias-DAC at `0x63`, and the
  SPI6 24-bit image on PG12/13/14.
- **Advances our PD3/PD4 reading**: he keeps PD3 = `+5R`, PD4 = `+5T`
  from the firmware RX/TX pattern — see the corrected section above.
- **One discrepancy to re-check (likely a slip in his summary)**: his
  table lists the PCA9535 expander (`0x20`) on **I2C1**; our evidence
  (`docs/i2c.md`, address byte `0x40`) places it on **I2C2**. The
  bq24715 (`0x09`) is the I2C1 device; the RF-control PCA9535 is I2C2.
- **Open items he flags that we also hold open or assign differently**:
  jack-detect PF15-vs-PG15 (we assign PF15), ADC2 on DMA2 S2-vs-S3 (we
  note S2 with the same caveat), `PWR_CR` VOS-vs-overdrive, I2C1 ~390 kHz
  after the clock switch. None contradict a VERIFIED result here.

Net: his document adds **no new verified facts** beyond ours, but it is
valuable as a second independent pass that agrees on the hard-won results
and sharpens the PD3/PD4 rail interpretation.

## Confidence summary

- Rail names, RX/TX behavior, PSYNC, VEXT, #PRE_EN, LM386, ACC T/R +
  band voltage, PA bias DAC: **VERIFIED** as stated in the OEM manual.
- `+5R`/`+5T` → **PD3 / PD4** mapping: **HIGH CONFIDENCE**, convergent
  across the firmware RX/TX levels, the single bi-color LED's green-RX /
  red-TX behaviour (user-VERIFIED on hardware), the manual's rail table,
  and the SP5TLS reference. Only the rail-vs-LED-only nuance remains (a
  multimeter check at rail test points 5/6).
- PE2 = ACC TRX, PA5 = BAND_V: **HIGH CONFIDENCE** (now corroborated by
  the service manual).
