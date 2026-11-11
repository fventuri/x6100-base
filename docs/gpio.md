# GPIO topology and control paths

## Scope and evidence

The central GPIO initializer is `FUN_0803158c`. Direct register
references were exported to `analysis/gpio/gpio_refs.csv`; selected
functions were also exported under `analysis/gpio/`.

Firmware SHA-256:

`3fa11293e06951c21c9cfda04ea08adad85eaadda26b77a8e8bbcca8820c53c4`

All seven ports GPIOA through GPIOG are clocked by the application:
VERIFIED.

## Central pin configuration

The compact initialization structure used by the firmware contains a
pin mask followed by byte-sized mode, speed, output-type, and pull
fields. Decoding its mode field gives the following groups.

| Mode | GPIO pins | Confidence |
| --- | --- | --- |
| output | PD2, PD3, PD4 | VERIFIED |
| output | PE2, PE7, PE8, PE9, PE11, PE12, PE14, PE15 | VERIFIED |
| output | PG12 | VERIFIED |
| input | PG0, PG1, PG6, PG8, PG11 | VERIFIED |
| output, high speed | PB0, PB1 | VERIFIED |
| output, high speed | PC5 | VERIFIED |
| output | PE10 | VERIFIED |
| output | PG6, PG12 | VERIFIED |
| output | PA3 | VERIFIED |
| input | PA11, PA12 | VERIFIED |
| input | PB8, PB9 | VERIFIED |
| input | PE3, PE13 | VERIFIED |
| input | PF13, PF14, PF15 | VERIFIED |
| input | PG4 | VERIFIED |
| input | PD0 | VERIFIED |
| analog | PA0, PA1, PA2, PA6, PA7 | VERIFIED |
| analog | PC4 | VERIFIED |
| analog | PA4, PA5 | VERIFIED |
| alternate function 2 | PD12 | VERIFIED |

PG0 and PG8 are configured with pull-downs; PG1 and PG11 with pull-ups:
VERIFIED. Other pull and output-type details should be checked pin by
pin before being copied into an independent implementation.

**PG0 and PG1 are later reconfigured from inputs to outputs and driven
high** by the startup sequence (`FUN_08034178` step 3; see
`docs/startup.md`). Their function is now known from an external bench
bisection (dev firmware drove individual GPIOs while listening to the
internal speaker, 2026-10-16): **PG1 = internal-speaker / HPR output
enable** (required — PG1 alone restores sound; the BASE codec's HPR
analog output stays silent without it even when every codec register
matches the OEM), and **PG0 = speaker loudness** (a gain / second-stage /
rail: PG0 alone gives no sound, but PG0+PG1 is markedly louder than PG1
alone). HIGH CONFIDENCE roles; VERIFIED on hardware (bench). This names two
startup GPIO writes whose purpose was previously unrecovered.

`FUN_080244b4` clears and later sets GPIOG ODR bit 8 around audio/IQ
startup. PG8 remains configured as an input throughout this sequence,
and no later output-mode configuration was found: VERIFIED. These ODR
writes therefore update only the latent output latch and do not
constitute verified physical reset control.

PE15 has a different and electrically effective lifecycle. It is an
output, is driven low early in main startup, driven low again before
audio initialization, held across a 1-ms delay, then driven high
immediately before TLV320AIC3204 programming. It is not written again:
VERIFIED. PE15 is the TLV320AIC3204 active-low hardware-reset line:
HIGH CONFIDENCE.

Some pins appear in more than one group because the initializer
deliberately reconfigures them during its sequence. PG6 and PG12 are
first included in an input/output setup and later explicitly configured
as outputs. PG11 is initially configured as a pulled-up input, but the
direct-GPIO hardware-variant path later configures PG10 and PG11 as
outputs before installing its callbacks: VERIFIED. Runtime PA/TX writes
to PG11 therefore do not conflict with the initial table.

## Peripheral alternate functions

Additional subsystem initializers establish these mappings:

| Peripheral | Pins | Alternate function | Confidence |
| --- | --- | ---: | --- |
| I2C3 | PA8, PC9 | AF4 | VERIFIED |
| USART1 | PA9, PA10 | AF7 | VERIFIED |
| USART6 | PC6, PC7 | AF8 | VERIFIED |
| TIM4 channel input | PD12 | AF2 | VERIFIED |
| Full-duplex I2S sample interfaces | PA15, PB12–PB15, PC10–PC12 | AF5/AF6 | VERIFIED |

PD12 remains configured for TIM4 AF2 and carries the encoded
hardware-key waveform: VERIFIED acquisition, HIGH CONFIDENCE external
hand-microphone/headset role. Exact I2S direction and clock roles are
documented in `docs/spi_i2s.md`.

The analog assignments are:

| Function | Pins | Confidence |
| --- | --- | --- |
| ADC1 channels 0, 1, 2 | PA0, PA1, PA2 | VERIFIED |
| ADC2 channels 6, 7, 14 | PA6, PA7, PC4 | VERIFIED |
| DAC channels 1, 2 | PA4, PA5 | VERIFIED |

See `docs/analog.md` for acquisition and filtering behavior.

## Serial GPIO shift chains

Three output pins implement software-clocked serial control:

- PC5 is serial data;
- PB0 is the serial clock;
- PB1 or PG6 is asserted around a completed transfer, depending on the
  selected chain.

`FUN_0802cf88` shifts six bits through PC5/PB0 and pulses PB1.
`FUN_0802d310` shifts two eight-bit arguments, most-significant bit
first, through PC5/PB0 while PG6 is low, then raises PG6.
`FUN_0802d15c` sends a fixed startup pattern through the same
PC5/PB0/PG6 path.

Pin roles, bit counts, order, and latch behavior: VERIFIED.

These routines are called by frequency/band configuration code.

The six-bit `FUN_0802cf88` chain (PB1-latched) is the **TX power
attenuator**, not an RX band filter (VERIFIED 2026-11-02). Its only
per-tune caller, `FUN_0802af0c`, computes the word from the TX power
setting, not frequency: `word = 0x64 - power` (power < 0x25 -> 0x3F;
0x25..0x64 -> 0x64 - power; >= 0x65 -> 0); the gate `FUN_0803147c` is
`return 1`, so that branch always runs. Earlier captures that looked
band-indexed (0x25 @ 1410 kHz, 0x3F @ 9.4 MHz) were per-band default TX
power reloads. Hardware confirms it: sweeping this chain 0x00..0x3F does
not change RX, and driving it blinks the TX LED. RX band selection is
done entirely by the primary index (direct GPIO), the secondary SPI6
image bit, and the DAC2 BAND_V staircase; the RX front-end enable is
PG2. `FUN_0802d15c`/`FUN_0802d310` (PG6-latched) are never called on
this build (gated off). The mapping of the remaining shifted bits to
physical parts is otherwise unresolved.

## Direct runtime controls

The following direct operations are established, but most physical net
names are not yet known:

| Pin or group | Observed use | Confidence |
| --- | --- | --- |
| PB2 | toggled at entry/exit of the fast DMA1 DSP handler | VERIFIED |
| PG15 | sampled and debounced by TIM2 | VERIFIED |
| PG4 | sampled during normal operation and awaited high during final shutdown | VERIFIED behavior; HIGH CONFIDENCE power/status feedback role |
| PE8, PE9, PE14 | changed during startup, PA calibration, DSP operation, or shutdown | VERIFIED |
| **PE11** | **battery MCU-rail power-hold / keep-alive** — held HIGH throughout the run; together with PD2 (also high) it latches the battery→STM32 rail. Driving PE11 LOW browns out the STM32 rail 2–6 s after the power button is released on battery (R16/Linux rides on; only the MCU drops). Cleared together with PD2 during the shutdown sequence to release the rail. Bench-proven with an independent BASE firmware (`x6100-bbfw` bms-keepalive, 2026-11-10); see below | VERIFIED on hardware (bench) |
| PE15 | low during early startup, high immediately before TLV320AIC3204 initialization | VERIFIED levels; HIGH CONFIDENCE codec reset |
| PE10 | low-delay-high pulse after external PA-bias device writes | VERIFIED |
| PE8, PE9, PG11 and variant callback | PA calibration and normal TX enable subset | HIGH CONFIDENCE role; VERIFIED levels |
| PE12 | per-sample active-low CW/RF envelope output; otherwise forced high | HIGH CONFIDENCE role; VERIFIED behavior |
| PD3 | **`+5R` receive-rail enable / RX-state line**: high in RX, low in TX. Lights the **green** side of the single bi-color front-panel LED (green in RX; early charge loop blinks it for charge status) | VERIFIED levels + LED behavior; HIGH CONFIDENCE `+5R` role |
| PD4 | **`+5T` transmit-rail enable**: low in RX, high in TX. Lights the **red** side of the bi-color LED in TX / ATU-tune | HIGH CONFIDENCE `+5T` role; VERIFIED levels + LED behavior |
| PE2 | candidate ACC `TRX`; low in RX and high in TX | HIGH CONFIDENCE role; VERIFIED levels |
| PD2 | final output cleared after PD4/PD3 delays when register `0x0030` bit 16 requests shutdown | VERIFIED behavior; HIGH CONFIDENCE support-power/power-hold role |
| PD3, PD4 | both sequenced low during shutdown (`+5R`/`+5T` off, LED off) | VERIFIED levels |
| PF11 | configured as output and held high by the charger/battery startup loop; exact net unknown | VERIFIED behavior |
| PF12 | active-high runtime charger enable; also mirrors the expander-backed variant | HIGH CONFIDENCE role; VERIFIED levels |
| PE13 | sampled by the charger/battery startup loop as part of its full/charging decision | VERIFIED behavior; physical net unresolved |
| PF15 | sampled with S/P mode; stable low state enables 0.05 receive-audio gain | VERIFIED behavior; HIGH CONFIDENCE S/P jack detect |
| **PG2** | **RX front-end enable** — the receive signal-path enable. Live OEM config (`oem-afedump`, 2026-11-02) drives it **open-drain + internal pull-up, released high, in every band** (constant RX enable); it is **not** in the central init table, so it is configured on the direct-GPIO variant path. Bench-proven (phase3-rx, 2026-11-02): driving PG2 high is **necessary and sufficient** to open the receiver (see below) | HIGH CONFIDENCE role; VERIFIED on hardware (bench) |
| PG8 | **output driven high at runtime** — the live OEM config dump (`oem-afedump`, 2026-11-02: MODER output, push-pull, pull-up, ODR=1/IDR=1, constant across bands) supersedes the earlier "stays input, ODR latch does not drive the pad" reading, which missed a later output reconfiguration outside the central table. Bench test: driving PG8 high does **not** affect the receive path, so it is not the RX enable | VERIFIED levels (live dump); physical role unresolved |
| PG1 | reconfigured input→output and driven high at startup; **internal-speaker / HPR output enable** — HPR analog output is silent without it even when codec registers match the OEM | HIGH CONFIDENCE role; VERIFIED on hardware (bench bisection 2026-10-16) |
| PG0 | reconfigured input→output and driven high at startup alongside PG1; **speaker loudness** (gain/2nd-stage/rail) — PG0 alone = no sound, PG0+PG1 markedly louder than PG1 alone | HIGH CONFIDENCE role; VERIFIED on hardware (bench) |
| PG11, PG12 | changed by startup, peripheral-reset, PA, or power-management paths | VERIFIED |

PB2 is a timing/debug marker candidate because it brackets the complete
DSP interrupt body: HIGH CONFIDENCE. Its electrical destination is
unknown.

### PG2 is the RX front-end enable (bench-resolved 2026-11-02)

PG2 gates the entire receive signal path. It was found by diffing the
**live** OEM GPIO configuration (not just the ODR latch) against an
independent from-scratch receive firmware (`x6100-bbfw/firmwares/phase3-rx`).
The `oem-afedump` instrument — a memory-only code cave on stock BASE 1.1.9
that dumps the complete GPIO config banks (MODER/OTYPER/OSPEEDR/PUPDR/IDR/
ODR/AFRL/AFRH) for every port A–G on each tune — showed the OEM, tuned to
1410 kHz AM and again at 9.4 MHz, holds **PG2 as an open-drain output with
an internal pull-up, released high**, identically in both bands. PG2 is not
in the central init table (`FUN_0803158c`); it is driven on the direct-GPIO
hardware-variant path.

The independent receiver reproduced the OEM's digital RF switching, LO
divider and I2S transport exactly yet sat at the I/Q noise floor
(`iq_rms ≈ 25 ×1e-6`). A live per-pin GPIO sweep over the config deltas
isolated the cause unambiguously: **driving PG2 high — and PG2 alone —
lifts `iq_rms` on WDOV 1410 kHz AM to ≈ 80, with a clean station/empty
contrast** (station `iq_rms ≈ 73`, carrier magnitude `env_dc ≈ 90–130`;
empty channel `iq_rms ≈ 40`, `env_dc ≈ 20`), matching the OEM baseline
(WDOV `iq_rms ≈ 79`, empty ≈ 40). The neighbouring config deltas
(PG8, PE11, PG6, PG3, PD15) had no effect on the receive path — for PE11
this is consistent with its later-resolved role as the **battery power-hold**
(a power pin, not an RX control; see "PE11 is the battery MCU-rail power-hold"
below). The
open-drain + pull-up detail matters: an open-drain "high" without the
pull-up floats (IDR reads 0) and does not assert, so a push-pull high, or
open-drain plus pull-up, is required.

The physical net is not yet tied to the schematic; the maintenance manual's
active-low preamp enable `#PRE_EN` (AS179 RF switch, see
`docs/maintenance_manual_findings.md`) is the leading candidate for what PG2
ultimately controls. This also identifies one of the previously
"physical names unresolved" auxiliary GPIOG controls in
`docs/hardware_map.md`. Whether PG2 is receive-only (deasserted in TX) is
not yet established, since all captures were in RX.

### PE11 is the battery MCU-rail power-hold (bench-resolved 2026-11-10)

PE11 is the firmware-asserted keep-alive that holds the STM32's own power
rail up on battery. It was resolved the same way as PG2 — by diffing the
**live** OEM GPIO state against an independent from-scratch BASE firmware
(`x6100-bbfw`) and bench-testing the single-pin difference — but it answers
a different puzzle: why a bare firmware that reproduces the OEM's steady
GPIO otherwise still **browns out on battery** a few seconds after boot.

Power topology (R16 SSH recon + firmware): battery → bq24715 NVDC charger
(BASE side) → VSYS, which feeds both the STM32 rail and R16's AXP PMIC. The
power **button** engages the battery→VSYS path in hardware and bridges it
only while held (and briefly after, via hold-up); firmware must then latch
the STM32 rail or it collapses. R16's AXP independently holds VSYS once
alive, so **R16/Linux always survives; only the STM32 drops** if the latch
is not taken over.

Bench result (`x6100-bbfw` bms-keepalive, 2026-11-10, battery-only, adapter
disconnected):

- With PE11 **low**, a bare telemetry firmware — already driving PD2 high
  (the documented power-hold) and matching the OEM's other steady levels —
  **browns out 2–6 s after the power button is released** (lifetime scales
  with how long the button is held). R16 rides on; only the MCU rail drops.
- Replicating the OEM's full steady GPIO (`GPIOE ODR = 0xDE80`, which
  includes PE11 high) **survives indefinitely** on battery.
- Bisection isolated the cause to **PE11 alone**: a build identical to the
  dying one except PE11 driven **high** survives the full discharge; PF11
  level is irrelevant (it varied across surviving builds). Confirmed through
  the production path (an unmodified telemetry firmware rebuilt with only the
  PE11-high change) running standalone on battery with external power
  disconnected **and R16 fully powered down** — proving the hold is entirely
  BASE-firmware, independent of R16, the I2C3/USART6 link, and the charger
  (the bq24715 is SMBus-unpowered on battery: "can't write bq24715").

So the MCU-controlled battery power-hold is **PD2 together with PE11** —
both must be high to keep the battery→STM32 rail latched; the shutdown
sequence clears both to release it (`docs/shutdown.md`). PE11 has no effect
on the receive path, consistent with a power rather than RF role. The exact
schematic net is still untied (resolvable with continuity/voltage at the
STM32 rail); a hard reset (GPIO Hi-Z for ~100 ms) also drops the rail, which
matches a firmware-driven latch rather than a self-holding hardware latch.

The earlier assignment of charger control to PF13 was incorrect. The
battery path at `FUN_08032500` reads GPIOE IDR mask `0x2000`, which is
PE13, not PF13: VERIFIED. PF13 remains the active-low KEY ring/`DA`
input serviced by TIM3: HIGH CONFIDENCE connector role, VERIFIED GPIO
consumer. No charger role is assigned to PF13.

The charger interface is now recovered at firmware level. Runtime
enable uses active-high PF12 and board callback `0x2000C6C8`; the
callback selects active-low PCA9535 bit 1 or active-high PF12 according
to hardware variant: HIGH CONFIDENCE role; VERIFIED levels and
backends. Full ordering and thresholds are in `docs/charger.md`.

**PD3 = `+5R`, PD4 = `+5T` (resolved).** The single front-panel LED is a
bi-color indicator: **green in RX, red in TX / ATU-tune** (VERIFIED on
hardware by the user). This matches the two RX/TX rails one-to-one — the
green element is lit by `+5R` (PD3, high in RX) and the red element by
`+5T` (PD4, high in TX) — and matches the firmware's PD3/PD4 RX/TX levels,
the maintenance manual's rail table (`docs/maintenance_manual_findings.md`),
and SP5TLS's independent reference. So PD3 is the `+5R` enable, not a
dedicated "power/charge LED" line; the LED is the visible sign of which
rail is live. The early battery loop's toggle-while-charging /
high-when-full use of PD3 simply flashes the green LED (via `+5R`) for
charge status. The earlier bench conclusion "PD3 = power LED, not `+5R`"
was the over-interpretation and is now itself superseded. Remaining
nuance, benchable with a multimeter at rail test points 5/6: confirm PD3
switches the whole receive rail versus only the LED element.

The precise RX/TX levels and ordering of the PA-related group, and the
I2C1 bias-control device associated with PE10, are documented in
`docs/pa_control.md`. Individual physical net names remain unresolved.
The hardware-variant PA callback is now resolved to PCA9535 output bit
0 on one variant and PD14 on the other: VERIFIED.

Across all recovered lifecycle paths, PE8 and PG11 have identical
levels, PE9 is their complement, and the variant callback follows their
asserted/deasserted state. The firmware-level four-signal PA enable
tuple is VERIFIED; its individual schematic nets remain unknown.

Protocol register `0x0030` bit 16 enters an ordered GPIO shutdown
rather than writing one pin directly. The GPIO sequence, delays,
power-control interpretation, and final reset are centralized in
`docs/shutdown.md`. Initial GPIO configuration and safe levels are in
`docs/startup.md`.

## Linux-board GPIO correlation

The current OEM Linux application uses `gpiochip0` line 203 as an
active-low software CW output and also holds legacy sysfs GPIO 203 low
while resetting BASE into IAP: VERIFIED. It pulses sysfs GPIO 204 high
then low for IAP entry; identification as BASE reset is HIGH
CONFIDENCE, with exact levels and sequence VERIFIED.

This establishes a shared inter-board CW/IAP-strap signal for Linux
GPIO 203 at HIGH CONFIDENCE. It does not by itself identify which
STM32 input pin receives that signal; the existing PF13/PF14 KEY-jack
mapping remains a separate, BASE-side result. Full Linux evidence and
the update sequence are in `docs/linux_hardware_interface.md` and
`docs/base_firmware_update.md`.

The user manual exposes an ACC `TRX` contact, and the service manual
directs technicians to check its MCU-controlled switching level. PE2 is
the only remaining direct GPIO in the central RX/TX transition with
RX=`0` and TX=`1`. Identifying PE2 as the ACC `TRX` control is HIGH
CONFIDENCE; continuity through the external interface circuit remains
to be measured. See `docs/acc.md`.

GPIO-backed callbacks selected by `FUN_0803131c` provide two hardware
variants for several power and RF-control operations. The callback
addresses and affected pins are VERIFIED, but final semantic names
should not be assigned until the hardware variant and nets are
identified.

The primary RF-band callback has now been resolved. One implementation
uses a PCA9535-compatible I2C2 expander; the other writes the index as
a binary value on PD9, PD10, PD11, and PD13. A secondary one-hot RF
index and all ATU controls share a 24-bit SPI6 output image. PG13 is
SCK, PG14 is MOSI, and PG12 is the output latch. Exact mappings are
documented in `docs/rf_switching.md` and `docs/atu.md`.

## Inputs serviced by TIM3

TIM3 debounces seven active-low GPIO-backed input descriptors:

| Pin | Mask | Debounce reload | Stable flag |
| --- | ---: | ---: | ---: |
| PB9 | `0x0200` | 10 | `0x20000182` |
| PE3 | `0x0008` | 10 | `0x20000196` |
| PF14 | `0x4000` | 1 | `0x200001AA` |
| PF13 | `0x2000` | 1 | `0x200001BE` |
| PA11 | `0x0800` | 1 | `0x200001D2` |
| PA12 | `0x1000` | 1 | `0x200001E6` |
| PD0 | `0x0001` | 1 | `0x200001FA` |

Descriptor values, active level, debounce state machine, and stable
destinations: VERIFIED.

PB9 directly controls TX-source bit `0x2`; its historical `HPTT`
interpretation is HIGH CONFIDENCE. PF14 and PF13 feed the two CW paddle
inputs. Correlation with the
published KEY-plug diagram and keyer element lengths maps PF14 to
tip/`DI`/dot and PF13 to ring/`DA`/dash: HIGH CONFIDENCE. PA11 and PD0
feed the aggregated immediate-CW-key path only in CW/CWR modes:
VERIFIED software routing. Their exact external or internal sources,
and PB9's exact physical PTT control, remain unresolved. See
`docs/tx_pipeline.md`.

## Reimplementation implications

- Reproduce the output-safe states before enabling RF or peripheral
  subsystems.
- Preserve the MSB-first PC5/PB0 shift timing and the distinct
  PB1/PG6 latch signals.
- Keep the PD4 → PD3 → PD2 shutdown delays until the controlled rails
  are identified.
- Do not assign semantic GPIO names from port masks alone.

## Maintenance-manual cross-reference

The OEM X6100 maintenance manual (`docs/maintenance_manual_findings.md`)
confirms `+5R` and `+5T` are real, complementary RX/TX-switched 5 V rails
(`+5R` on in RX, `+5T` on in TX). The firmware drives **PD3 = 1 in RX /
0 in TX** and **PD4 = 0 in RX / 1 in TX**, exactly that polarity, so the
convergent reading (firmware + the SP5TLS reference + the manual) is
**PD3 = `+5R`, PD4 = `+5T`**. The PA tuple (PE8/PG11 high in TX, PE9 high
in RX) is the *separate* PA-stage enable, not the rail switch. The PD3
bench result (toggling PD3 toggled a front-panel LED, radio idle) stays a
VERIFIED fact but its interpretation is now open: PD3 tracking RX/TX is
evidence it is the `+5R` enable with the LED powered from that rail,
rather than a dedicated power-LED line — benchable at rail test points
5/6 across a real RX→TX transition. The manual further corroborates PE2 =
ACC `TRX`, PA5/DAC2 = ACC `BAND_V`, `#PRE_EN` as the preamp-enable net,
and the LM386 speaker amp behind PG0/PG1. See
`docs/maintenance_manual_findings.md`.

## G90 schematic cross-reference

An external comparison with the public Xiegu G90 schematics (same
STM32F4 LQFP144 pinout) is documented in `docs/g90_comparison.md`. It
confirms the shared I2C1/I2C2/I2C3, USART1/USART6, codec-I2C, and
PG12/PG13/PG14 board-control (74HC595) assignments, and corroborates the
PA5 band-voltage role. It does **not** resolve the BASE-specific
charger/power-rail pins (PF11, PE13, PD4, PE2, PG4, PB2, PG11) or the
bench-verified PG0/PG1 speaker pins.

## Remaining work

- Correlate shifted RF-control bits with frequency ranges and hardware
  filters.
- Document initial and shutdown levels for every output pin.
