# Comparative analysis: Xiegu G90 schematics vs. X6100 BASE MCU

## Purpose and status

The X6100 schematics are not available, so several BASE GPIO roles are
recovered only from firmware behavior. The publicly circulated schematics
for the related Xiegu **G90** transceiver *are* available and were used
here as an **external reference** to test and extend the X6100 pin
hypotheses.

This is cross-reference analysis, not a measurement of the X6100 board.
No claim in this document opens or probes the physical X6100. Where the
G90 raises or lowers confidence in an X6100 pin role, that is stated
explicitly; where the firmware evidence already governs, the G90 only
corroborates vocabulary.

Source files (user-provided, under `~/X6100/g90/`, not committed):

- `G90-SSIGBD-2.0.6-GAI03.pdf` — small-signal board, carries the main MCU
- `G90-BASEBD-V2.0.6.pdf` — PA / power / band-relay board
- `G90-DISPBD-V2.0.6.pdf` — display board
- `G90_Microphone_Schematic.pdf`

Extraction script and the recovered pin map:

- `analysis/g90/extract_g90_mcu_pinmap.py`
- `analysis/g90/g90_ssig_mcu_pinmap.csv`

## Key finding: same MCU, same package, same pinout

The G90 SSIG main MCU is an **STM32F4 in the 144-pin LQFP package** — the
same package/pinout family as the X6100 BASE **STM32F427**. The schematic
labels every MCU pad with both its **pin number** and its **port name**,
and the two are internally consistent with the canonical
STM32F40x/41x/42x/43x Zx LQFP144 pinout. Three independent checks anchor
this: VERIFIED.

| G90 pin | Port | G90 net | STM32F4 LQFP144 | X6100 BASE firmware use |
| ---: | --- | --- | --- | --- |
| 99 | PC9 | I2C3_SDA | PC9 / I2C3_SDA AF4 | I2C3 slave SDA, PC9 AF4 |
| 100 | PA8 | I2C3_SCL | PA8 / I2C3_SCL AF4 | I2C3 slave SCL, PA8 AF4 |
| 101 | PA9 | USART1_TX | PA9 / USART1_TX AF7 | USART1, PA9 AF7 |
| 102 | PA10 | USART1_RX | PA10 / USART1_RX AF7 | USART1, PA10 AF7 |
| 96 | PC6 | USART6_TX | PC6 / USART6_TX AF8 | USART6, PC6 AF8 |
| 97 | PC7 | USART6_RX | PC7 / USART6_RX AF8 | USART6, PC7 AF8 |
| 136/137 | PB6/PB7 | I2C1_SCL/SDA | PB6/PB7 I2C1 AF4 | I2C1 master, PB6/PB7 AF4 |
| 69/70 | PB10/PB11 | CODEC_SCL/SDA | PB10/PB11 I2C2 AF4 | I2C2 master, PB10/PB11 AF4 |

Because the housekeeping/bus pins land on identical ports in both radios,
Xiegu clearly reused the same base pin assignment across the two designs.
That is what makes the G90 schematic a usable reference for the X6100.

## How to read the correlation

The two radios share the MCU and the housekeeping/bus wiring, but they are
**different RF architectures** (the G90 is a superheterodyne with an
SPI-driven LO PLL; the X6100 is a direct-sampling SDR). So the G90 is
authoritative for the X6100 only on the pins it demonstrably shares, and
is otherwise useful as a *naming dictionary* for Xiegu's house nets. Four
categories follow.

### 1. Confirmed shared assignments (same pin, same function)

These X6100 firmware results are independently reproduced by the G90
schematic on the identical STM32 pin. Confidence for the X6100 rises to
VERIFIED-by-cross-reference.

| Pin(s) | Function | X6100 evidence | G90 net |
| --- | --- | --- | --- |
| PA8 / PC9 | I2C3 (Linux control link) | VERIFIED | I2C3_SCL / I2C3_SDA |
| PA9 / PA10 | USART1 | VERIFIED | USART1_TX / USART1_RX |
| PC6 / PC7 | USART6 | VERIFIED | USART6_TX / USART6_RX |
| PB6 / PB7 | I2C1 (fuel gauge + LO) | VERIFIED | I2C1_SCL / I2C1_SDA |
| PB10 / PB11 | **I2C2 = audio-codec bus** | VERIFIED | **CODEC_SCL / CODEC_SDA** |
| PA13 / PA14 | SWD debug | implied | SWDIO / SWCLK |
| PB12–PB15 | I2S2 (full-duplex) | VERIFIED | I2S2 LRCK/SCLK/SDOUT/SDIN |
| PC10–PC12 | I2S3 | VERIFIED (AF5/AF6) | I2S3 SCLK/SDIN/SDOUT |
| **PG12 / PG13 / PG14** | **24-bit board-control shift image** | VERIFIED (SPI6 latch/SCK/MOSI) | **B_LATCH / B_SCK / B_DATA** |

The last row is the strongest new structural result. The X6100 firmware
drives a shared 24-bit output image out of SPI6 (PG13 SCK, PG14 MOSI)
latched by PG12 (`docs/rf_switching.md`, `docs/atu.md`). On the G90 those
exact pins are `B_SCK` / `B_DATA` / `B_LATCH`, and on the G90 BASE board
they clock **three cascaded SN74HC595** shift registers (3 x 8 = 24 bits)
that drive band relays, the `TRX` antenna switch, and filter selects. This
makes the X6100 "24-bit image -> external latch" almost certainly the same
**74HC595 relay/filter chain** topology. The `B_` prefix reads as
*Board*/*Band* control. HIGH CONFIDENCE for the X6100 topology.

Also confirmed: PB10/PB11 is explicitly the **codec** I2C bus on the G90,
which independently supports the X6100 identification of I2C2 as the
TLV320AIC3204 / CS4272 audio bus.

### 2. Vocabulary confirmed (function present in both; pin may differ)

The G90 uses Xiegu's house net names. These confirm that the X6100
firmware's hypothesized *functions* are real Xiegu concepts, even where
the G90 puts them on a different pin:

- `TRX` — RX/TX antenna-switch control (X6100 PE2 ACC-TRX hypothesis; G90
  places TRX on PD0 and on the BASE-board HC595 chain, so it confirms the
  concept but **not** the PE2 pin).
- `PO_FWD`, `PO_REV`, `VIN_SMP` — forward/reflected power and supply-voltage
  sensing (X6100 ADC detector + voltage cluster).
- `SEND`, `PTT_RD`, `PTT_WR`, `#PRE_EN` (preamp enable, active-low),
  `ATT_EN` (attenuator enable), `BPF0/1/2` (band-pass-filter select).
- `KEYER_DOT` / `KEYER_DSH` — CW paddle dot/dash (X6100 maps these to
  PF14/PF13; G90 uses PD8/PD9).
- `MUTE`, `SPK_SEL`, `BEEP` — audio mute / speaker select / sidetone.
- `PWR_KEY`, `PWR_EN2`, `PDRON` — power key and power-rail control.

### 3. New or strengthened X6100 hypotheses from shared pins

| X6100 pin | X6100 firmware status | G90 net (same pin) | Resulting X6100 hypothesis |
| --- | --- | --- | --- |
| PA5 / DAC2 | band/freq-dependent DAC = ACC `BAND_V`, HIGH CONFIDENCE | **PRESELV** (preselector tuning V) | Corroborated: PA5 is a band-dependent analog tuning voltage. HIGH CONFIDENCE. |
| PA4 / DAC1 | initialized to 0, no runtime write found | **BV_DRV** (bias-voltage drive) | PA4/DAC1 is likely a PA **bias-voltage drive** output left unused by fw 1.1.9. HYPOTHESIS. |
| PA0/PA1/PA2 (ADC1) | fwd detector / reflected detector / ALC_V, HIGH CONFIDENCE | VIN_SMP / PO_FWD / PO_REV | Same *sensing cluster* (power/SWR/voltage), but the pin-to-signal mapping differs; X6100 firmware evidence governs. No confidence change; vocabulary only. |

### 4. Discrepancies and X6100-specific pins (G90 does NOT explain these)

Some pins are used differently on the two radios, or are simply unused on
the G90 MCU. The G90 cannot resolve them, and this is stated so the
comparison is not over-read:

- **PG0 / PG1** — X6100 internal-speaker/HPR enable + loudness
  (bench-VERIFIED). Unused on the G90 MCU; the G90 drives audio out via
  `SPK_SEL`/`MUTE` + an LM386. The X6100 bench finding stands alone and
  was *necessary* — the G90 does not contain it.
- **PB9** — X6100 TX-source/`HPTT` input; on the G90 PB9 is `PWR_KEY`.
- **PD12** (X6100 TIM4 hardware-key waveform), **PG15** (X6100 TIM2-sampled
  input; G90 `1LO_FSYNC`) — different roles.
- **Power/charger rails**: the X6100's open pins **PF11, PE13, PD4
  (+5T?), PE2 (TRX?), PG4 (power feedback), PB2, PG11** land on G90 pins
  that are either unused or carry G90-specific superhet signals. The G90
  therefore does **not** resolve the X6100 charger/power-rail block.
- No `+5R` / `+5T` rail names appear anywhere in the G90 schematic; that
  X6100 guess is not supported or refuted here. G90 power rails are
  `+13.8`, `+9`, `+5`, `+3.3`.

## Still unresolved after this comparison

- PF11, PE13, PF12 charger/battery pins (X6100-specific block).
- PD4 `+5T` / PD3 power-LED / PD2 power-hold rail identities.
- PE2 ACC `TRX` pin (G90 confirms the TRX *concept*, not the PE2 pin).
- PG4 power/status feedback net.
- PB2 DSP-marker electrical destination.
- The mapping from individual shifted 74HC595 bits to specific
  relays/filters (needs the X6100 band plan, not the G90 bit order).

## Reproducibility

```
pdftotext -bbox-layout G90-SSIGBD-2.0.6-GAI03.pdf ssig.bbox.html
python3 -I analysis/g90/extract_g90_mcu_pinmap.py ssig.bbox.html
```

The script locates the MCU by clustering `P[A-G]n` port tokens, reads each
pin number as the nearest in-range integer, and assigns each net label to
its single nearest pin-number token by coordinates. All pin numbers it
recovers match the canonical LQFP144 pinout, which is the self-check that
the port/pin alignment is correct.
