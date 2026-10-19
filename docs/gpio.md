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
Interpretation as two RF relay/filter control shift chains is HIGH
CONFIDENCE. The mapping from individual shifted bits to physical
relays, filters, or attenuators remains unknown.

## Direct runtime controls

The following direct operations are established, but most physical net
names are not yet known:

| Pin or group | Observed use | Confidence |
| --- | --- | --- |
| PB2 | toggled at entry/exit of the fast DMA1 DSP handler | VERIFIED |
| PG15 | sampled and debounced by TIM2 | VERIFIED |
| PG4 | sampled during normal operation and awaited high during final shutdown | VERIFIED behavior; HIGH CONFIDENCE power/status feedback role |
| PE8, PE9, PE11, PE14 | changed during startup, PA calibration, DSP operation, or shutdown | VERIFIED |
| PE15 | low during early startup, high immediately before TLV320AIC3204 initialization | VERIFIED levels; HIGH CONFIDENCE codec reset |
| PE10 | low-delay-high pulse after external PA-bias device writes | VERIFIED |
| PE8, PE9, PG11 and variant callback | PA calibration and normal TX enable subset | HIGH CONFIDENCE role; VERIFIED levels |
| PE12 | per-sample active-low CW/RF envelope output; otherwise forced high | HIGH CONFIDENCE role; VERIFIED behavior |
| PD3 | drives the front-panel **power/charge LED**, active-high (externally driving PD3 high lit the LED, low turned it off; radio idle) — supersedes the earlier `+5R` rail-enable guess for PD3 | VERIFIED on hardware |
| PD4 | complementary partner of PD3; candidate `+5T` TX rail enable | HIGH CONFIDENCE role; VERIFIED levels |
| PE2 | candidate ACC `TRX`; low in RX and high in TX | HIGH CONFIDENCE role; VERIFIED levels |
| PD2 | final output cleared after PD4/PD3 delays when register `0x0030` bit 16 requests shutdown | VERIFIED behavior; HIGH CONFIDENCE support-power/power-hold role |
| PD3, PD4 | sequenced low during shutdown (PD3 = power LED off at power-down, VERIFIED; PD4 candidate `+5T`) | VERIFIED levels |
| PF11 | configured as output and held high by the charger/battery startup loop; exact net unknown | VERIFIED behavior |
| PF12 | active-high runtime charger enable; also mirrors the expander-backed variant | HIGH CONFIDENCE role; VERIFIED levels |
| PE13 | sampled by the charger/battery startup loop as part of its full/charging decision | VERIFIED behavior; physical net unresolved |
| PF15 | sampled with S/P mode; stable low state enables 0.05 receive-audio gain | VERIFIED behavior; HIGH CONFIDENCE S/P jack detect |
| PG8 | input; ODR latch changes during audio startup but does not drive the pad | VERIFIED |
| PG1 | reconfigured input→output and driven high at startup; **internal-speaker / HPR output enable** — HPR analog output is silent without it even when codec registers match the OEM | HIGH CONFIDENCE role; VERIFIED on hardware (bench bisection 2026-10-16) |
| PG0 | reconfigured input→output and driven high at startup alongside PG1; **speaker loudness** (gain/2nd-stage/rail) — PG0 alone = no sound, PG0+PG1 markedly louder than PG1 alone | HIGH CONFIDENCE role; VERIFIED on hardware (bench) |
| PG11, PG12 | changed by startup, peripheral-reset, PA, or power-management paths | VERIFIED |

PB2 is a timing/debug marker candidate because it brackets the complete
DSP interrupt body: HIGH CONFIDENCE. Its electrical destination is
unknown.

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

PD3 drives the front-panel **power/charge LED** (active-high): VERIFIED on
hardware by externally driving PD3 high (LED on) and low (LED off) with the
radio idle. The startup battery loop's toggle-while-charging / high-when-full
use of PD3 is therefore the LED's blink/solid charge indication. This supersedes
the earlier reading of PD3 as the `+5R` receive rail; the complementary PD3/PD4
RX/TX pattern seen in later code still needs re-examination (PD4 / `+5T`
untested): VERIFIED PD3 = power LED; HYPOTHESIS for the remaining +5R/+5T mapping.

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
(`+5R` on in RX, `+5T` on in TX). This yields a new **HYPOTHESIS**: the
complementary PA tuple drives them — **PE8/PG11 (high in TX) = `+5T`
enable, PE9 (high in RX) = `+5R` enable** — benchable at rail test points
5/6. It also means **PD4 is no longer a strong `+5T` candidate** (PD3 is
the power/charge LED, not `+5R`). The manual further corroborates PE2 =
ACC `TRX`, PA5/DAC2 = ACC `BAND_V`, `#PRE_EN` as the preamp-enable net,
and the LM386 speaker amp behind PG0/PG1.

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
