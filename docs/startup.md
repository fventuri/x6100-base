# Firmware startup

## Scope

This document records the reset path of
`X6100_BBFW_V1.1.9_251127001.bin`.

Firmware SHA-256:

`3fa11293e06951c21c9cfda04ea08adad85eaadda26b77a8e8bbcca8820c53c4`

The evidence was exported with Ghidra 12.1.2 using
`ghidra_scripts/ExportStartupEvidence.java`. Generated evidence is under
`analysis/startup/`.

## Vector entry

| Property | Value | Confidence |
| --- | --- | --- |
| Vector-table address | `0x08020000` | VERIFIED |
| Initial MSP | `0x20030000` | VERIFIED |
| Reset vector value | `0x08034A19` | VERIFIED |
| Reset code address | `0x08034A18` | VERIFIED |

The low bit of the vector value is the Cortex-M Thumb-state bit. It is
not part of the aligned code address.

## Reset function

Current Ghidra name: `FUN_08034a18`

Proposed name: `candidate_Reset_Handler`

Confidence: HIGH CONFIDENCE

The function performs these operations:

1. Loads `0x20030000` into `SP`.
2. Copies 32-bit words from `0x0807C5D0` to
   `[0x20000000, 0x20003570)`.
3. Clears 32-bit words in `[0x20003570, 0x2000EB00)`.
4. Calls `FUN_0803485c`.
5. Calls `FUN_08037ed0`.
6. Calls `FUN_08034178`.
7. Enters an infinite loop if the third call returns.

The copy, clear, call sequence, and final loop are VERIFIED by direct
disassembly. The interpretation as `.data` and `.bss` initialization is
HIGH CONFIDENCE pending correlation with a recovered linker layout.

## First startup call

Address: `0x0803485C`

Current name: `FUN_0803485c`

Proposed name: `candidate_SystemInit`

Final name justified by evidence: `SystemInit`

Confidence: VERIFIED

Observed behavior:

- enables CP10 and CP11 access through `SCB->CPACR` at `0xE000ED88`;
- writes RCC control/configuration registers in the
  `0x40023800` block;
- writes `0x08020000` to `SCB->VTOR` at `0xE000ED08`;
- returns to the reset function.

The register sequence and reset constants match the STM32F4 CMSIS
`SystemInit` implementation distributed in the official
[STM32CubeF4 package](https://github.com/STMicroelectronics/STM32CubeF4).
The function's position as the first reset-time call independently
supports the identification. The final name is therefore VERIFIED,
although it has not yet been applied to the persistent Ghidra project.

## Second startup call

Address: `0x08037ED0`

Current name: `FUN_08037ed0`

Proposed name: `candidate_libc_init_array`

Final name justified by evidence: `__libc_init_array`

Confidence: VERIFIED

Observed behavior:

- iterates over a first range of function pointers;
- calls `FUN_0803ced8`;
- iterates over a second range of function pointers;
- returns.

The four boundaries loaded by this function are:

| Linker-provided range | Start | End | Entries |
| --- | ---: | ---: | ---: |
| preinit array | `0x0807C5C8` | `0x0807C5C8` | 0 |
| init array | `0x0807C5C8` | `0x0807C5CC` | 1 |

The sole init-array entry is the Thumb address `0x080201D5`, whose code
address is `0x080201D4`.

The control flow is an exact match for newlib's `__libc_init_array`:
iterate the preinit array, call `_init`, then iterate the init array.
This comparison is based on the
[newlib `init.c` implementation](https://sourceware.org/pipermail/newlib/2022/018886.html)
and the recovered array boundaries. The final name is therefore
VERIFIED, although it has not yet been applied to the persistent Ghidra
project.

`FUN_0803ced8` contains only an ABI-compatible prologue, `nop`, and
epilogue. Its role as the `_init` stub is HIGH CONFIDENCE.

The init-array function at `0x080201D4` loads a null weak-function
literal and returns without invoking it. Its identity as a generated
frame-registration helper is MEDIUM CONFIDENCE; its effective no-op
behavior in this image is VERIFIED.

## Third startup call

Address: `0x08034178`

Current name: `FUN_08034178`

Proposed name: `candidate_main`

Confidence: HIGH CONFIDENCE

The function performs extensive application and peripheral
initialization, references the firmware version and build date strings,
performs PA calibration checks, and does not normally return. Its
position after the runtime initializer strongly supports the `main`
hypothesis. No final rename has been performed.

## GPIO initialization sequence

GPIO setup is not performed by one isolated call. `FUN_08034178`
first executes an early power/battery service phase and then calls the
main board initializer `FUN_080317B4`. The following call order is
VERIFIED:

1. `FUN_08032500` establishes the early power/charger GPIO state.
2. `FUN_080317B4` invokes `FUN_08031480`, followed by the central GPIO
   initializer `FUN_0803158C`.
3. `FUN_080317B4` initializes the DMA, protocol, USART, interrupt, ADC,
   DAC, ATU, and remaining board subsystems.
4. After `FUN_080317B4` returns, `FUN_08034178` applies explicit safe
   output levels before PA-bias validation and entry into the
   superloop.

### Early power and charger pins

`FUN_08032500` runs before the central GPIO table. Its ordered GPIO
contract is:

1. configure PF11 and PF12 as outputs;
2. configure PE13 and PG4 as inputs;
3. configure PD3 and PD4 as outputs;
4. drive PF11 high, PF12 low, and PD4 low;
5. initialize the selected charger backend and apply the saved charger
   policy;
6. during its service loop, toggle PD3 for charging samples or hold it
   high for the recovered full condition;
7. leave PF11 high when returning.

Pins, directions, levels, and ordering are VERIFIED. PF12 is the
runtime charger-enable output at HIGH CONFIDENCE. Exact PF11 and PE13
board nets and the reason for early PD3 reuse remain unresolved. The
complete battery behavior is in `docs/charger.md`.

### Central GPIO table

`FUN_0803158C` first enables the clocks for GPIOA through GPIOG and the
system-configuration block. It then configures pins in this port order:

1. debug pins PA13/PA14;
2. GPIOD output group;
3. GPIOE output/input groups;
4. GPIOF group;
5. GPIOG input/output groups;
6. high-speed PB0/PB1 and PC5 serial-control pins;
7. PE10 and the later GPIOG output group;
8. remaining GPIOA, GPIOB, GPIOC, GPIOE, GPIOF, GPIOG, and GPIOD
   control/input/analog groups.

The call order and register targets are VERIFIED. The resulting
direction map is:

| Direction or mode | Pins | Confidence |
|---|---|---|
| output | PD2, PD3, PD4 | VERIFIED |
| output | PE2, PE7, PE8, PE9, PE10, PE11, PE12, PE14, PE15 | VERIFIED |
| output retained from early phase | PF11, PF12 | VERIFIED |
| output | PG6, PG12 | VERIFIED |
| high-speed output | PB0, PB1, PC5 | VERIFIED |
| output | PA3 | VERIFIED |
| input | PA11, PA12, PB8, PB9, PD0, PE3, PE13 | VERIFIED |
| input | PF13, PF14, PF15, PG0, PG1, PG4, PG6, PG8, PG11 | VERIFIED |
| analog | PA0, PA1, PA2, PA4, PA5, PA6, PA7, PC4 | VERIFIED |
| alternate function 2 | PD12 | VERIFIED |

PG6 appears in both groups because it is deliberately reconfigured.
PG11 is initially an input and is later made an output by one
hardware-variant backend. Full pull, speed, output-type, and
reconfiguration evidence is retained in `docs/gpio.md`.

### Explicit safe levels after board initialization

After the board initializer returns, `FUN_08034178` performs additional
direct writes. The relevant ordered state is:

1. PE15 low and PG8 output latch low before audio/IQ startup;
2. initialize timers and main runtime state;
3. drive PG0 and PG1 high (both reconfigured from inputs to outputs here;
   external bench bisection 2026-10-16 identified **PG1 = internal-speaker /
   HPR output enable** and **PG0 = speaker loudness** — see `docs/gpio.md`.
   Without this write the BASE codec's HPR output is silent even with
   OEM-identical codec registers);
4. call the installed hardware-variant callback with argument `1`;
5. drive PD2 high and PF11 low;
6. set both PA-bias device channels to zero;
7. assert the PA-calibration control subset while validating both bias
   channels with temporary nonzero codes;
8. return both bias codes to zero and place the PA/RX-TX tuple into its
   normal RX-safe state before entering the superloop.

The direct GPIO writes, callback arguments, and bias values are
VERIFIED. Their aggregate purpose as safe startup/PA-validation states
is HIGH CONFIDENCE. The complete PA tuple and transition ordering are
documented in `docs/pa_control.md`; codec reset is documented in
`docs/i2c.md`.

The matching power-off path is intentionally documented separately in
`docs/shutdown.md`.

## Remaining work

- Recover the complete call graph rooted at `FUN_08034178`.
- Correlate RAM ranges with linker sections and global references.
- Apply candidate or final names in the persistent Ghidra project only
  after the evidence review.
