# X6100 BASE hardware resource map

## Purpose and scope

This is the implementation-oriented index of hardware resources used by
BASE firmware 1.1.9. It consolidates proven interfaces and lifecycle
requirements; detailed algorithms remain in the linked subsystem
documents.

The machine-readable companion is
`analysis/hardware/hardware_resources.csv`.

This is a consumer-oriented map: resources appear when firmware gives
them a usable role or contract. The complete raw GPIO mode inventory,
including pins whose board functions remain unknown, stays in
`docs/gpio.md`.

Confidence labels apply to each role:

- VERIFIED: directly established by firmware, protocol, vector, or
  independent register-map correlation;
- HIGH CONFIDENCE: physical role is strongly correlated but still
  lacks a schematic net or continuity measurement;
- MEDIUM CONFIDENCE: best current subsystem-level interpretation;
- HYPOTHESIS: must not be used as a final hardware name.

## Core and clock domains

| Resource | Configuration | Implementation consequence | Confidence |
| --- | --- | --- | --- |
| MCU | STM32F427, Cortex-M4, Thumb-2, little-endian | application image begins at `0x08020000` | VERIFIED |
| HSE | 25 MHz expected | source of the application PLL | VERIFIED firmware assumption |
| SYSCLK/HCLK | intended 250 MHz | apparent overclock; replacement may use a safe clock with recalculated timing | VERIFIED configuration; HIGH CONFIDENCE physical rate |
| PCLK1 / APB1 timers | 62.5 / 125 MHz | I2C and TIM2/3/4 timing basis | VERIFIED |
| PCLK2 / APB2 timers | 125 / 250 MHz | USART and high-speed peripheral basis | VERIFIED |

The OEM clock tree is not a mandatory hardware contract. Peripheral
rates and DSP deadlines are the contract; a replacement should
recalculate divisors if it does not reproduce the 250-MHz setting. See
`docs/clocks.md`.

## Communication buses and external devices

| Bus | Pins and mode | Attached device or service | Firmware-visible role | Confidence |
| --- | --- | --- | --- | --- |
| I2C1 | PB6/PB7 AF4, 100-kHz master | MAX17205 at `0x36` | fuel-gauge registers and battery telemetry | VERIFIED |
| I2C1 | same | five-output LO generator at `0x6A` | VFO/LO synthesis | HIGH CONFIDENCE 5P49V60 identification |
| I2C1 | same | two-channel controller at `0x63` | drive/final PA bias; PE10 commit pulse | HIGH CONFIDENCE role; exact IC unresolved |
| I2C2 | PB10/PB11 AF4, 100-kHz master | CS4272 at `0x10` | primary zero-IF I/Q ADC/DAC | VERIFIED |
| I2C2 | same | TLV320AIC3204 at `0x18` | microphone, line, speaker/phone, and board-audio codec | VERIFIED |
| I2C2 | same | PCA9535-compatible device at `0x20` | board-variant RF and PA/charger outputs | HIGH CONFIDENCE family; VERIFIED protocol |
| I2C2 | same | device at `0x4A` | unconditional fixed audio/IQ support startup | VERIFIED contract; MEDIUM CONFIDENCE support role |
| I2C2 | same | device at `0x4C` | fallback for the CS4272 I/Q backend | HIGH CONFIDENCE role; exact IC unresolved |
| I2C3 | PA8/PC9 AF4, 400-kHz slave at `0x72`; OEM Linux `/dev/i2c-0` | Linux control service | register writes, STOP-separated reads, boot handshake, calibration windows | VERIFIED on both sides |
| USART1 | PA9/PA10 AF7, 115200 8-N-1 | diagnostic endpoint | formatted debug/stdio traffic | HIGH CONFIDENCE |
| USART6 | PC6/PC7 AF8; OEM Linux `/dev/ttyS1` | Linux flow and IAP endpoint | 4136-byte IQ/telemetry packets and firmware transfer | VERIFIED role; unresolved 1.5M/1.152M rate conflict |
| SPI6 | PG13 SCK, PG14 MOSI AF5; PG12 GPIO latch | output-only 24-bit chain | ATU and secondary RF relay image | VERIFIED |

I2C address notation in this table is conventional 7-bit notation.
Exact command sequences are in `docs/i2c.md`, `docs/charger.md`,
`docs/frequency_control.md`, and `docs/pa_control.md`.

## Sample interfaces

| Interface | STM32 mode | Data role | DMA | Confidence |
| --- | --- | --- | --- | --- |
| SPI2/I2S2 + I2S2ext | 32-bit stereo slave receive/transmit | real audio pair | DMA1 Streams 3/4 | VERIFIED |
| SPI3/I2S3 + I2S3ext | 32-bit stereo slave receive/transmit | complex I/Q pair | DMA1 Streams 0/5 | VERIFIED |

The TLV320AIC3204 supplies BCLK/WCLK for its interface and both STM32
I2S pairs are configured as slaves: VERIFIED. Whether those codec clocks
are physically shared with the I/Q pair requires board tracing. Each
double-buffer bank contains 512 halfwords, or 128 stereo 32-bit frames.
The firmware constants indicate 100-kHz raw framing and a 1.28-ms bank
deadline: HIGH CONFIDENCE. See `docs/spi_i2s.md` and `docs/dma.md`.

Configured alternate-function pins are PA15, PB12–PB15, and PC10–PC12.
Exact signal-to-pin names should be taken from `docs/spi_i2s.md`; they
must not be inferred merely from the peripheral role.

## Analog resources

| Resource | Pins/channels | Acquisition or output | Role | Confidence |
| --- | --- | --- | --- | --- |
| ADC1 | PA0/ch0, PA1/ch1, PA2/ch2 | DMA2 Stream 0, three halfwords | forward RF, reflected RF, ACC ALC | HIGH CONFIDENCE roles; VERIFIED acquisition |
| ADC2 | PA6/ch6, PA7/ch7, PC4/ch14 | DMA2 Stream 2, five interleaved triplets | external voltage, PA current, unresolved input | mixed; see below |
| DAC1 | PA4 | initialized and held at zero | no runtime consumer recovered | HIGH CONFIDENCE |
| DAC2 | PA5 | frequency-dependent 12-bit staircase | ACC `BAND_V` | HIGH CONFIDENCE role; VERIFIED codes |

The external-voltage path is explicitly:

```
PA6 / ADC2 ch6
  -> DMA2 Stream 2
  -> filtered getter 0
  -> * 4.835165
  -> state 0x200000F0
  -> * 0.01
  -> Linux flow offset 0x100C
```

Software path and constants: VERIFIED. External-supply interpretation:
HIGH CONFIDENCE. Full transfer functions and RF calibration are in
`docs/analog.md`.

## Timers, DMA, and active interrupts

| Resource | Configuration | Responsibility | Confidence |
| --- | --- | --- | --- |
| TIM2 | about 1487.72-Hz update | UART-flow scheduler, ADC2 filtering, PG15 debounce | VERIFIED |
| TIM3 | about 199.96-Hz update | input debounce and TX-power/VSWR/ALC telemetry | VERIFIED |
| TIM4 | PD12/AF2 PWM-input capture, approximately 72-ns tick | encoded external hardware-key capture/reporting | HIGH CONFIDENCE headset role; VERIFIED acquisition and decoding |
| DMA1 Streams 0/3/4/5 | circular double-buffer I2S | synchronized audio/IQ transport | VERIFIED |
| DMA2 Streams 0/2 | ADC1/ADC2 scans | analog acquisition | VERIFIED |
| DMA2 Streams 1/5/6/7 | USART6/USART1 RX/TX | Linux flow and diagnostics | VERIFIED |

Only these external interrupts are active:

| IRQ | Handler role | Confidence |
| ---: | --- | --- |
| 14 | DMA1 Stream 3 sample-bank/DSP handler | VERIFIED |
| 28 | TIM2 service | VERIFIED |
| 29 | TIM3 input/telemetry service | VERIFIED |
| 30 | TIM4 capture | VERIFIED |
| 72 | I2C3 slave event | VERIFIED |
| 73 | I2C3 slave error | VERIFIED |

All other external vectors point to the default loop. The application
does not use IWDG or WWDG: VERIFIED. See `docs/interrupts.md`,
`docs/timers.md`, and `docs/watchdog.md`.

## Direct GPIO control groups

| Function | Resource and active behavior | Lifecycle | Confidence |
| --- | --- | --- | --- |
| ACC `TRX` | PE2: RX low, TX high | RX/TX | HIGH CONFIDENCE role; VERIFIED levels |
| power/charge LED | PD3 high = on (toggled while charging, solid when full) | charge indication | VERIFIED on hardware |
| transmit rail? | PD4 (complement of PD3): RX `0`, TX `1` | RX/TX/shutdown | HIGH CONFIDENCE `+5T`; VERIFIED levels. PD3's old `+5R` role superseded by the LED finding — pair mapping needs re-examination |
| PA enable tuple | PE8/PE9/PG11/callback: enabled `1/0/1/1` | TX and calibration | VERIFIED tuple; HIGH CONFIDENCE aggregate role |
| CW RF envelope | PE12 active-low per sample | CW transmit | HIGH CONFIDENCE role; VERIFIED behavior |
| codec reset | PE15 active-low | audio startup | HIGH CONFIDENCE role; VERIFIED lifecycle |
| internal-speaker / HPR enable | PG1 high (reconfigured input→output at startup step 3) | audio | HIGH CONFIDENCE role; VERIFIED on hardware (bench bisection 2026-10-16) — HPR silent without it despite OEM-identical codec regs |
| speaker loudness | PG0 high (with PG1) | audio | HIGH CONFIDENCE role; VERIFIED on hardware — PG0 alone silent, PG0+PG1 much louder than PG1 alone |
| PA-bias commit | PE10 low-delay-high | changed bias write | HIGH CONFIDENCE role; VERIFIED waveform |
| charger enable | PF12 high or PCA9535 bit 1 low | startup/runtime | HIGH CONFIDENCE role; VERIFIED levels |
| shutdown request | register `0x0030` bit 16 exits superloop; PD4 low, 5 s, PD3 low, 3 s, PD2 low; wait PG4 high | controlled shutdown | VERIFIED sequence; HIGH CONFIDENCE PD2 power-hold and PG4 feedback roles |
| primary RF index | PCA9535 one-hot mask or PD9/10/11/13 binary | frequency change | VERIFIED |
| secondary RF/ATU | SPI6 24-bit word; PG12 high-to-low latch | frequency/tune | VERIFIED |
| software RF chains | PC5 data, PB0 clock, PB1 or PG6 latch | startup/frequency | VERIFIED protocol; HIGH CONFIDENCE relay role |

The ordered RX/TX transition must be copied from `docs/pa_control.md`;
this summary table does not imply that simultaneous GPIO writes are
equivalent.

## Direct and debounced inputs

| Input | Behavior | Recovered role | Confidence |
| --- | --- | --- | --- |
| PB9 | active-low, TIM3 debounce | hardware PTT | HIGH CONFIDENCE |
| PF14 | active-low, TIM3 debounce | KEY tip / `DI` / dot | HIGH CONFIDENCE |
| PF13 | active-low, TIM3 debounce | KEY ring / `DA` / dash | HIGH CONFIDENCE |
| PF15 | stable-low changes RX audio gain | speaker/phone jack detection | HIGH CONFIDENCE |
| PE13 | active-low early sample | early charge `FULL/status` condition | VERIFIED behavior; net unresolved |
| PA11, PA12, PD0, PE3 | TIM3 debounce | partial key/PTT/control consumers | VERIFIED behavior; physical sources incomplete |
| PG15 | TIM2 debounce | unknown | VERIFIED behavior |
| PG4 | boot/runtime/shutdown polling | power/status condition | VERIFIED behavior; physical source unresolved |

PF13 is not a charger signal. It belongs to the telegraph-key path:
VERIFIED separation.

## Board variants

`FUN_0803131C` installs one of two callback sets:

| Function class | Expander backend | Direct-GPIO backend | Confidence |
| --- | --- | --- | --- |
| primary RF index | PCA9535 one-hot outputs | PD9/PD10/PD11/PD13 binary | VERIFIED |
| PA control | PCA9535 bit 0 | PD14 | VERIFIED |
| charger | PCA9535 bit 1 active-low | PF12 active-high | VERIFIED levels; HIGH CONFIDENCE role |
| other auxiliary controls | PCA9535 bits 2/10/14/15 | GPIOG/PD15 alternatives | VERIFIED mapping; physical names unresolved |

The selected board revision and physical net names remain unresolved.
The complete callback table is
`analysis/pa/variant_callback_map.csv`.

## Complete direct peripheral-reference export

`analysis/hardware/peripheral_accesses.csv` contains every Ghidra data
reference originating from an instruction and targeting the STM32
peripheral, external-control, or Cortex-M system-register address
ranges. The current export contains:

- 777 references from 69 functions;
- 136 exact target addresses;
- 361 direct writes and 280 direct reads;
- 126 parameter/address constructions and 10 generic data references.

These counts and rows are VERIFIED properties of the current Ghidra
analysis. All 542 peripheral-reference rows previously exported into
subsystem-specific `*_refs.csv` files are present in the consolidated
table: VERIFIED by exact `(site, target, reference type)` comparison.
The consolidated export adds 235 rows that were not in those earlier
targeted tables.

`READ` and `WRITE` rows are direct register accesses. `PARAM` and
`DATA` rows mean that an instruction constructs, passes, or otherwise
refers to a peripheral address; they must not independently be
described as a bus transaction. Conversely, generic drivers can
receive a base address through a register without Ghidra recovering a
direct reference at every call site. The table is therefore a complete
export of recovered instruction references, not a proof that every
dynamic peripheral access has been statically resolved.

The audit exposed one previously under-documented active peripheral:
the STM32 CRC engine. It resets `CRC_CR`, streams all `0x409` words of
the Linux UART-flow packet through `CRC_DR`, and stores the resulting
word at packet offset `0x1024`: VERIFIED. See `docs/protocol.md`.

Reproduce the export with:

```sh
GHIDRA_INSTALL=ghidra-directory \
JAVA_HOME=jdk-directory \
./tools/run_headless_peripheral_accesses.sh \
    analysis/hardware/peripheral_accesses.csv
```

## Lifecycle checklist

### Startup

1. Run early power/charger service and load persistent charger policy.
2. Establish the application clock tree and central GPIO modes.
3. Initialize I2C1/I2C2 and choose the expander or direct-GPIO board
   backend.
4. Initialize MAX17205, PA bias control, LO generator, DAC/ADC, and
   timer services.
5. Reset and program TLV320AIC3204, run the fixed `0x4A` sequence,
   then configure CS4272 or its `0x4C` fallback.
6. Enable the four synchronized I2S DMA streams and Linux transports.

This is a subsystem ordering summary, not a replacement for the exact
call sequence in `docs/startup.md` and `docs/i2c.md`.

### Runtime

- TIM2 services ADC2 filtering and Linux flow scheduling.
- TIM3 services inputs and RF telemetry.
- DMA1 Stream 3 owns sample-block DSP timing.
- The foreground loop applies Linux control changes, RF frequency
  transitions, charger state, and RX/TX hardware state.

Execution is bare-metal; no RTOS scheduler or synchronization objects
were found: HIGH CONFIDENCE architecture.

### Shutdown

Register `0x0030` bit 16 enters the ordered PD4/PD3/PD2 rail shutdown,
PG4 feedback wait, and final system reset. The complete authoritative
sequence and confidence assignments are in `docs/shutdown.md`.

## Implementation boundary

An independent firmware can implement the known contracts without
identifying every package or schematic net. The following still require
board measurements and must remain descriptive:

- PF11 and PE13 physical nets;
- PD3/PD4 `+5R/+5T` pair mapping, now that PD3 is confirmed as the power/charge
  LED (its early-loop "reuse" is the LED's charge indication);
- exact functions of the `0x4A` support device and `0x4C` hardware;
- individual PA-enable and RF-relay net names;
- PC4/ADC2 channel 14 and several debounced input sources.

These unknowns do not invalidate the recovered bus transactions,
active levels, timing, or state-machine behavior.
