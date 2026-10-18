# Charger and battery-management contract

## Scope

This document describes the firmware-visible behavior needed for an
independent implementation. The fuel gauge is identified as MAX17205;
the separate charger IC does not need to be identified because firmware
controls it only through a binary enable line.

The two relevant routines are the early service loop
`FUN_08032500` and the runtime controller `FUN_0802d878`. The exact
state machine and GPIO lifecycle are exported in:

- `analysis/charger/charger_runtime_state_machine.csv`;
- `analysis/charger/charger_gpio_lifecycle.csv`;
- `analysis/charger/battery_telemetry_fields.csv`.

## Linux policy control

Linux register 21 bit 4, historically named `chge`, is copied into
state byte `0x2000003E` and bit 0 of persistent word `0x2000E984`.
The update handler itself performs no GPIO write: VERIFIED.

The bit is an enable policy, not an unconditional output level. The
runtime battery manager combines it with external-power detection,
capacity thresholds, and the current charger state before changing the
hardware: HIGH CONFIDENCE semantic role; VERIFIED data flow.

## Battery telemetry transaction

The runtime routine has two nested dividers. Every 5000 calls it
services its current phase. The read phase performs an I2C1 combined
write/repeated-start/read:

```
address byte = 0x6C (7-bit address 0x36)
register     = 0x00
destination  = 0x2000BF90
length       = 0x200 bytes
```

Transaction parameters and ordering are VERIFIED. The decoded fields
used by this routine are:

The 512 bytes are a contiguous snapshot of the 256 two-byte registers
on the MAX17205 primary `0x00`–`0xFF` page: VERIFIED by the device
address, embedded `max17205` strings, register numbers, and matching
scale factors. Buffer offset is therefore `register × 2`.

| Offset | Register | Firmware conversion and use | Confidence |
| ---: | --- | --- | --- |
| `0x0C` | `0x06 RepSOC` | unsigned × `0.0039`; 90/98 thresholds and Linux capacity | VERIFIED |
| `0x10` | `0x08 Temp` | signed ÷ `256`; stored but no downstream reader recovered | VERIFIED |
| `0x16` | `0x0B AvgCurrent` | signed × `0.15625`; stored but no downstream reader recovered | VERIFIED register/arithmetic; HIGH CONFIDENCE 10-mΩ sense scaling |
| `0x1B4` | `0xDA Batt` | unsigned × `1.25` mV; power detection and Linux battery voltage | VERIFIED |

External supply is measured independently of the MAX17205. PA6 is
ADC2 channel 6 and occupies getter index 0. The filtered getter result
is multiplied by `4.835165` and stored at `0x200000F0`: VERIFIED
hardware/software path and arithmetic; HIGH CONFIDENCE external-voltage
role. This value participates in external-power hysteresis and is
published to Linux at flow offset `0x100C` after multiplication by
`0.01`. The complete acquisition/filter path is documented in
`docs/analog.md`.

On a successful read the four values are decoded and the sample-valid
byte is set. On failure the failure counter at `0x200000DC` is
incremented, all four decoded values are cleared, and sample-valid is
cleared: VERIFIED.

The evaluate phase does not run on the next 5000-call tick. A secondary
modulo-20 counter delays it for 20 such ticks. Only then does firmware
publish capacity, sample ADC2, make charger/power decisions, and return
to the read phase. The next block read occurs on the following
5000-call tick: VERIFIED. Thus an exact implementation must preserve
the `5000 × 20` deferred evaluation, not model the phases as simple
alternation.

No other byte in the 512-byte buffer has a direct firmware read.
Specifically, BASE 1.1.9 does not inspect the MAX17205 Status register,
device/version identification, initialization-ready state, or any
checksum after the bulk transfer: VERIFIED direct-reference audit.
The I2C transaction return code is the only validation applied to this
snapshot.

The complete direct-reference audit is
`analysis/charger/max17205_block_refs.csv`.

### Linux telemetry path

`RepSOC` is converted to unsigned integer and its low byte is written to
flow offset `0x100E`: VERIFIED. For valid 0–100% data this is the
integer battery percentage.

The internal external- and battery-voltage values are each multiplied
by `0.01`, converted to unsigned integer, and truncated to one byte.
They are published at flow offsets `0x100C` and `0x100D` respectively:
VERIFIED. With the recovered millivolt internal scale, the bytes
represent tenths of a volt: HIGH CONFIDENCE.

`Temp` and `AvgCurrent` are decoded into globals but no downstream
reader or Linux-flow setter was recovered. They are not published by
the BASE 1.1.9 flow packet: VERIFIED direct-reference and call-path
audit.

## Runtime charger state machine

The following decisions are VERIFIED:

1. If `chge` is zero, disable charging.
2. If `chge` is one but external power is absent, disable charging.
3. If charging is inactive, external power is present, and capacity is
   below 90, enable charging.
4. Once active, retain charging below 98.
5. At capacity 98 or above, disable charging.

Thus 90/98 form start/stop hysteresis. Between 90 and 98 the previous
charger state is retained: VERIFIED.

External-power state has a separate 500-unit voltage hysteresis. When
the state is absent, `battery < external + 500` sets it present. When
the state is present, `external < battery + 500` clears it. The
comparisons and ordering are VERIFIED; identifying the two scaled
values as battery and external supply is HIGH CONFIDENCE.

The charger decision uses the existing external-power state and updates
that state afterward. A compatible implementation must preserve this
one-evaluation ordering if exact OEM transition timing matters:
VERIFIED.

## Physical actuation

Each enable or disable transition performs these operations:

1. call board-variant callback slot `0x2000C6C8` with the requested
   state;
2. call `FUN_08030140` with the same state;
3. directly set or clear PF12;
4. publish the charging-active flag through `FUN_08033974`.

The callback has two verified backends:

| Backend | Enabled | Disabled | Confidence |
| --- | --- | --- | --- |
| PCA9535-compatible expander bit 1 | low | high | VERIFIED |
| direct PF12 | high | low | VERIFIED |

PF12 and expander bit 1 therefore implement the board-variant charger
enable, with opposite electrical polarity: HIGH CONFIDENCE role;
VERIFIED operations and levels. The unconditional direct PF12 write
means that the expander-backed variant also updates the PF12 output
latch.

`FUN_08030140` is exactly a two-byte `bx lr` stub in BASE 1.1.9. It has
no hardware effect and must not be mistaken for a second charger
device command: VERIFIED. It appears to be a reserved hook:
HYPOTHESIS.

No charger-programming register writes were found in the runtime state
transition. The firmware-visible control contract is a binary enable
line, not a recovered current/voltage programming protocol: VERIFIED
within the analyzed call paths.

## Early boot/service loop

`FUN_08032500` temporarily establishes this charger-related state:

1. configure PF11 and PF12 as outputs, PE13 and PG4 as inputs, and PD3
   and PD4 as outputs;
2. drive PF11 high, PF12 low, and PD4 low;
3. load persistent policy bit 0, defaulting to enabled when the stored
   configuration is invalid;
4. when enabled, initialize the selected board backend, apply the
   policy to PF12 and callback `0x2000C6C8`, and enter the service loop;
5. periodically read an early battery object and report `CHARGING` or
   `FULL`;
6. classify full when the recovered capacity-like value is at least
   `1800.0` or PE13 is low;
7. toggle PD3 on charging samples and force PD3 high in the full state
   (PD3 drives the front-panel power/charge LED — blink while charging,
   solid when full);
8. leave PF11 high on exit.

GPIO configuration, levels, calls, comparisons, and ordering are
VERIFIED. PE13 is an input to the early full decision, not the charger
enable. Its exact electrical source is unresolved.

PF11 is written as an output; it is not read by this loop. Its physical
net remains HYPOTHESIS. PD3 drives the front-panel **power/charge LED**
(active-high): confirmed on hardware by externally driving PD3 high (LED
on) and low (LED off) with the radio idle. This resolves the early
toggle-while-charging / high-when-full behaviour as the LED's blink/solid
charge indication, and supersedes the earlier interpretation of PD3 as
the `+5R` receive rail. The complementary PD3/PD4 RX/TX pattern in normal
operation therefore needs re-examination (PD4 / `+5T` untested here): the
power LED tracking RX/TX would be unusual, so either the `+5R`-rail model
for PD3 was an overinterpretation of the toggling or the nets differ:
VERIFIED PD3=power LED; HYPOTHESIS for the remaining +5R/+5T mapping.

PF13 has no charger role. It is consumed by the TIM3 telegraph-key
input path: VERIFIED separation.

### Early MAX17205 transaction contract

The early object at `0x200002D0` is a MAX17205 fuel-gauge interface:
VERIFIED by the embedded error strings naming `max17205` and
`max172xx`, together with the accessed register addresses. This
identification is useful for interpreting the transactions but is not
required by an independent implementation.

The normal early reads are:

| Operation | Register | Conversion | Failure fallback | Confidence |
| --- | ---: | --- | ---: | --- |
| reported capacity | `0x1F` | unsigned 16-bit value converted directly to float | `1800.0` | VERIFIED |
| pack voltage | `0xDA` | unsigned 16-bit × `1.25` mV | `8000` mV | VERIFIED |

The early display percentage is
`clamp(capacity * 100 / 1800, 0, 100)`, and capacity `>= 1800` is one
of the two `FULL` conditions: VERIFIED.

If either read fails, `FUN_08030528` sends three three-byte writes in
this order:

```
60 0F 00    register 0x60 = 0x000F
BA 0B 09    register 0xBA = 0x090B
BD 22 32    register 0xBD = 0x3222
```

Byte ordering, values, and order are VERIFIED. Firmware strings
describe these writes as device reset, hibernate configuration, and
battery-pack configuration respectively: VERIFIED OEM descriptions.
There are no delays between the three writes and their individual
failures only produce diagnostic messages.

These operations configure and read the same register family used by
the runtime `0x36` bulk snapshot: VERIFIED protocol correlation. They
do not program charger current or voltage and must not be confused with
the separate
PF12/PCA9535 binary charger-enable path: VERIFIED separation.

The reusable Ghidra exports are stored beside the machine-readable
sequence in `analysis/charger/`.

## Battery-management pin cluster and G90 cross-reference

The battery-management subsystem is X6100-specific. It is built from the
MAX17205 fuel gauge on I2C1 (PB6/PB7) plus a discrete GPIO cluster that
the early service loop configures together:

| Pin | BMS role | Confidence | Open question |
| --- | --- | --- | --- |
| PB6/PB7 (I2C1) | MAX17205 fuel-gauge bus | VERIFIED | — |
| PF12 | charger enable (or PCA9535 bit 1 variant) | HIGH CONFIDENCE role | exact net |
| PE13 | input to the "battery full" decision (full when low) | VERIFIED behavior | likely charger status / CHG-done / DC-in; net unknown |
| PF11 | driven and held high across the loop, never read | VERIFIED behavior | candidate charger/battery power-path or load-switch enable; HYPOTHESIS |
| PG4 | sampled in run, awaited high before power-down handoff | HIGH CONFIDENCE power/status feedback | likely supply-present / power-good supervisor |
| PD3 | front-panel power/charge LED (blink/solid) | VERIFIED on hardware | — |
| PD4 | configured low with the cluster; `+5T` candidate | HIGH CONFIDENCE levels | rail identity |

The related Xiegu G90 has **no battery-management hardware at all** (no
fuel gauge, charger IC, or battery connector appears anywhere in its
schematics). On the shared STM32F4 pinout, PF11, PF12, PE13, and PG4 are
all unused/unconnected on the G90. That the exact pins the X6100 firmware
spends on battery management are the ones its BMS-less sibling leaves
blank is consistent with (though does not by itself prove) their BMS
role: the firmware call-path membership remains the primary evidence.
See `docs/g90_comparison.md`. PE13 and PG4 are good bench-probe
candidates against the charger IC's STAT/PG pins.

## Independent implementation guidance

A compatible implementation needs:

- the register-21 `chge` policy bit and persistent default;
- the I2C1 `0x36` block read and exact field scaling;
- the early MAX17205 `0x1F`/`0xDA` reads and ordered recovery writes
  when reproducing the pre-Linux service loop;
- external-power and 90/98 capacity hysteresis;
- the selected active-low expander-bit or active-high PF12 backend;
- charging-active telemetry publication.

Exact part names are unnecessary. PE13, PF11, and the early PD3 reuse
should remain descriptively named until board measurements establish
their nets.
