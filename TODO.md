# TODO

## Scope

Only software artifacts are in scope: BASE firmware, Linux binaries,
Ghidra databases, exported analysis data, and documentation automation.
PCB/schematic study, continuity tracing, signal measurements, component
identification from board markings, and other physical-board work are
explicitly out of scope. Known physical uncertainties remain documented
only as evidence boundaries, not as planned tasks.

## High priority

### Startup

-   [x] Recover complete Reset_Handler
-   [x] Identify startup_call_1 (`candidate_SystemInit`, HIGH CONFIDENCE)
-   [x] Identify startup_call_2 (`candidate_libc_init_array`, HIGH CONFIDENCE)
-   [x] Identify startup_call_3 (`candidate_main`, HIGH CONFIDENCE)
-   [x] Confirm SystemInit() (VERIFIED)
-   [x] Confirm \_\_libc_init_array() (VERIFIED)
-   [x] Locate `candidate_main` at `0x08034178` (HIGH CONFIDENCE)

### Interrupts

-   [x] Recover complete vector table
-   [x] Identify all active IRQ handlers
-   [x] Apply the seven VERIFIED interrupt-handler names through an
    idempotent CSV-driven Ghidra script

### Memory

-   [x] Document recovered executable region
-   [x] Bound combined read-only data/runtime-table region
-   [x] Document startup-derived `.data` range (HIGH CONFIDENCE)
-   [x] Document startup-derived `.bss` range (HIGH CONFIDENCE)
-   [x] Confirm no application CCMRAM accesses (HIGH CONFIDENCE)

## Hardware

-   [x] RCC / clocks
-   [x] GPIO modes, peripheral pins, shift chains, and shutdown sequence
-   [x] Trace register `0x0030` bit 16 (`power_off`) into the ordered
    PD4/PD3/PD2 shutdown and PG4 feedback wait
-   [x] DMA
-   [x] ADC topology, DMA acquisition, and ADC2 filtering
-   [x] DAC initialization and frequency-dependent DAC2 control
-   [x] SPI / full-duplex I2S
-   [x] I2C1/I2C2 masters, codec, variants, and I2C3 slave
-   [x] Identify I2C2 address `0x10` as CS4272 and decode its startup
-   [x] Recover complete startup-only control contract for `0x4A`/`0x4C`
-   [x] Identify TLV320AIC3204 as 32-bit I2S BCLK/WCLK master
-   [x] Recover PE15 TLV320AIC3204 reset lifecycle (HIGH CONFIDENCE role)
-   [x] Export complete ordered TLV320AIC3204 startup contract and
    decode its power, routing, mute, and gain phases
-   [x] Map TLV320AIC3204 control helpers to analog routing, gain,
    MICBIAS, and ADC/DAC mute semantics
-   [x] Correlate codec IN1L/IN2L/IN2R and gain controls with built-in
    microphone, hand microphone, and line input (HIGH CONFIDENCE)
-   [x] Trace speaker/phone mode through PF15 to the DMA audio-gain
    selector (HIGH CONFIDENCE jack-detect role)
-   [x] Assign IN3R/HPL to the MAIN/Linux-board audio path and
    IN2R/LOL/LOR to the C-Media/USB-card path (HIGH CONFIDENCE)
-   [x] Recover SPI2 audio and SPI3 I/Q signal roles from DMA processing
-   [x] Verify CS4272 as zero-IF I/Q converter and assign SPI3/I2S3
-   [x] Assign `0x4C` fallback to the same I/Q interface (HIGH CONFIDENCE)
-   [x] Export exact `0x4A`/`0x4C` startup bytes, both fallback delays,
    branch condition, and ignored transfer results
-   [x] Audit PG8 around converter startup; it remains an input and is
    not a verified reset line
-   [x] USART
-   [x] Timers
-   [x] Confirm no application IWDG/WWDG use and document software reset
-   [x] Recover firmware-visible charger control, I2C telemetry,
    hysteresis, and ordered PF12/PCA9535 actuation; exclude PF13
-   [x] Recover early MAX17205 capacity/voltage reads and ordered
    reset/hibernate/pack-configuration recovery writes
-   [x] Map the runtime `0x36`/512-byte MAX17205 snapshot, its four
    consumed registers, failure behavior, cadence, and Linux fields

## RTOS

-   [x] Identify bare-metal superloop; no RTOS scheduler (HIGH CONFIDENCE)
-   [x] Confirm no RTOS task objects are present
-   [x] Confirm no RTOS queues/semaphores are present
-   [x] Confirm timers are hardware-driven rather than RTOS timers

## Linux ↔ BASE protocol

-   [x] I2C3 control transport and framing
-   [x] Verify UART IQ/telemetry flow against BASE 1.1.9
-   [x] Recover BASE 1.1.9 explicit USART6 1,500,000-baud initializer
-   [x] Audit current OEM Linux 1.2 hardware layer (`x6100_ui_v100`)
-   [x] Confirm current OEM `/dev/i2c-0` address `0x72` and
    STOP-separated read framing
-   [x] Confirm current OEM `/dev/ttyS1` BASE flow endpoint
-   [x] Recover Linux GPIO 203 software-CW/IAP-strap sharing and GPIO
    204 reset sequence
-   [x] Recover BASE IAP commands and complete 1K XMODEM sender contract
-   [x] Bound BASE IAP post-transfer behavior: Linux sends no command
    after EOT ACK, and the exact jump/reset path resides in the missing
    `0x08000000`–`0x0801FFFF` boot-resident range
-   [x] Dump the `0x08000000`–`0x0801FFFF` boot-resident range from live
    hardware (`analysis/iap/base_bootloader_0x08000000-0x0801FFFF.bin`)
-   [ ] Analyse the dumped IAP bootloader (reset handler `0x08001990`):
    greeting emission, 1K-XMODEM receiver, erase/program, and the
    post-EOT application-entry mechanism
-   [x] Verify ATU tune flag and Linux boot handshake
-   [x] Recover UART flow packet layout and metadata producers
-   [x] Trace `vfoa_freq`/`vfob_freq` through LO synthesizer programming
-   [x] Resolve the BASE 1.1.9 frequency-path selector (constant 1)
-   [x] Recover output-4 harmonic-avoidance algorithm (`PSYNC`, HIGH CONFIDENCE)
-   [x] Recover RF-band indices and frequency-dependent DAC2 table
-   [x] Map primary RF index to PCA9535 and direct-GPIO backends
-   [x] Map secondary RF index to SPI6 output-image bits
-   [x] Recover exact secondary RF-index frequency boundaries
-   [x] Recover frequency-change DSP reset and four-block countdown
-   [x] Correlate all 56 control-register slots with BASE 1.1.9
    consumers, including explicit unused/decoded-only slots
    - [x] Recover register 15 RF-gain serial output, DSP gain split,
      and TX-power target scaling
    - [x] Recover every consumed register 12 operation bit and the
      ATU-tune request/clear handshake
    - [x] Recover register 13 active-VFO selection, calibration-band
      table effects, and required index bound
    - [x] Audit all register 21 fields, including persistent charger
      control, variant output behavior, and squelch threshold
    - [x] Recover register 35 signed RX complex shift and active-low
      bypass, including its shared CW-oscillator gate
    - [x] Audit registers 22/25 as decoded-only VOX/compressor controls
      with no recovered runtime effect
    - [x] Recover register 24 DNF and registers 27/28 AGC field behavior
    - [x] Audit all unnamed slots and register 16 cached-only behavior
-   [x] Recover I2C read responses and calibration-window framing
-   [x] Recover telemetry physical units and used calibration-block
    field semantics
-   [x] Recover `hkey` acquisition through PD12/TIM4 PWM-input capture,
    frame decoding, validation, and release timeout

## DSP

-   [x] Identify the exact CMSIS-DSP build: STM32Cube_FW_F4 **V1.23.0**
    prebuilt `libarm_cortexM4lf_math.a` (CMSIS-DSP V1.4.5); VERIFY 16 float
    primitives (FIR/decimate/interpolate, biquad DF1, CFFT + radix-8,
    cmplx_mag, scale/abs/copy/fill/max, FIR init) by exact object-code
    identity. See `docs/dsp_primitives.md`.
-   [x] Identify the build toolchain and remaining library code: **ST
    `gnu-tools-for-stm32` GCC 12.3.1 + newlib-nano** (swept vs GCC 7/8/9/10/11/13;
    only ST matches full libc/libm). VERIFY 96/456 firmware functions as stock
    library code (16 CMSIS-DSP + 62 newlib-nano libc + 5 libm + 13 libgcc),
    isolating ~360 application functions. See `docs/library_functions.md`.
-   [x] Add locality (address-block) classification to `identify_lib_functions.py`
    (multi-library; derives library blocks from confident matches to promote
    trivial/ambiguous matches and flag version-variant library code). Classify all
    456 functions: **103 library / 52 likely-library / 301 application**. Evidence
    `analysis/library_functions/function_classification.csv`.
-   [x] Apply VERIFIED Ghidra renames for 92 of the 103 library functions
    (`analysis/library_functions/verified_library_renames.csv`, idempotent); 11
    byte-identical/ambiguous stubs left as `FUN_*`.

### RX

-   [x] IQ buffers and Q31 input conversion
-   [x] Audit converter-input DC removal
    (no dedicated complex-input stage found)
-   [x] Adaptive IQ imbalance correction
-   [x] Complex frequency shift
-   [x] Export and validate all RX rate-conversion FIR coefficients
-   [x] Map runtime-selected RX biquad tables, protocol edges, and
    mode-dependent cutoff rules
-   [x] Determine dedicated complex-input DC removal behavior
    (none found; later mode-dependent high-pass stages documented)
-   [x] AGC topology, look-ahead, bounds, and bypass
-   [x] SSB/CW/AM/NFM demodulation topology
-   [x] Recover optional RX block spectral noise-reduction transform,
    register control, FFT framing, estimator, and overlap-add
-   [x] Recover final RX audio mixer and fixed-point DMA output contract

### TX

-   [x] Recover mode-dependent modulation topology
-   [x] Export TX rate-conversion and quadrature-filter coefficients
-   [x] Recover runtime TX biquad selection and exact coefficients
-   [x] Verify combined TX audio-filter frequency response independently
-   [x] Correlate BASE mode numbers with historical Linux-facing names
-   [x] Recover CW RF/monitor envelope timing and tone/level fields
-   [x] Recover CW software key-state generator and register-33 fields
-   [x] Recover QSK hold units and audit key-ratio application
-   [x] Map CW input flags to STM32 GPIO pins
-   [x] Map PF13/PF14 to KEY tip/ring contacts
-   [x] Recover TX-request arbitration and hardware-PTT GPIO
-   [x] RX/TX block-boundary handoff and first digital input gain
-   [x] Recover TX ALC topology, limits, and final complex scaling
-   [x] Correlate ADC1 directional-detector inputs with TX-power/VSWR telemetry
-   [x] Recover absolute RF-power unit (`0.1 W` protocol field;
    watt-to-dBm target conversion)
-   [x] Identify ADC1 channel 2 / PA2 as the ACC ALC input
-   [x] Recover PA bias-device protocol and ordered RX/TX hardware controls
-   [x] Resolve hardware-variant PA callback to PCA9535 bit 0 / PD14
-   [x] Export the complete PCA9535/direct-GPIO variant callback table
-   [x] Audit the PA enable GPIO tuple across startup, RX/TX, calibration, and shutdown
-   [x] Separate PA calibration-enable subset and recover PE12 CW output
-   [x] Correlate PD3/PD4 with service-manual +5R/+5T rails
-   [x] Recover ACC TRX, BAND_V, and ALC_V MCU mappings
-   [x] Trace VSWR measurement into the antenna-tuner search
-   [x] Recover ATU state packing, relay-bit permutation, and search phases
-   [x] Recover ATU result publication and register-17 reapplication path
-   [x] Recover physical ATU output through SPI6 and PG12 latch
-   [x] Audit direct VSWR consumers for a firmware hard-trip path

## Tooling

-   [x] Export complete function ranges from Ghidra
-   [x] Export call graph
-   [x] Export direct function callers
-   [x] Export raw interrupt table
-   [x] Export Ghidra global data labels with types, memory blocks, and
    exact reference counts
-   [x] Export all recovered instruction references to STM32
    peripheral and Cortex-M system-register ranges
-   [x] Generate a deterministic Markdown cross-index from preserved
    analysis CSV files, including an input SHA-256 manifest
-   [x] Add a relocation-aware static-library function identifier
    (`tools/identify_lib_functions.py`): masks ELF relocations, scores each
    firmware function against every library symbol in [0, 1], validated by a
    self-match positive control

## Documentation

-   [x] hardware_map.md and machine-readable hardware resource inventory
-   [x] implementation_readiness.md with driver inventory, safety gates,
    blockers, and staged bring-up
-   [x] startup.md
-   [x] shutdown.md
-   [x] interrupts.md
-   [x] memory_map.md
-   [x] gpio.md
-   [x] clocks.md
-   [x] timers.md
-   [x] usart.md
-   [x] dma.md
-   [x] spi_i2s.md
-   [x] dsp_primitives.md
-   [x] analog.md
-   [x] i2c.md
-   [x] frequency_control.md
-   [x] rf_switching.md
-   [x] watchdog.md
-   [x] protocol.md (transport and historical 1.1.6 register map)
-   [x] linux_hardware_interface.md
-   [x] base_firmware_update.md
-   [x] rtos.md
-   [x] rx_pipeline.md (input, correction, mode demodulation, AGC,
    rate conversion, and documented remaining work)
-   [x] tx_pipeline.md (initial mode handoff and input-gain stages)

## Milestone 1

Recover complete firmware startup.

Completion criteria:

-   Reset_Handler understood
-   SystemInit identified
-   Runtime identified
-   main() identified
-   Startup documented
-   Ghidra project updated
