# PA bias and RX/TX hardware control

<!-- Maintenance-manual cross-reference: the OEM manual confirms +5R (RX)
and +5T (TX) are complementary RX/TX-switched 5 V rails. The complementary
PA tuple (PE8/PG11 high in TX, PE9 high in RX) is the candidate enable for
+5T / +5R respectively -- HYPOTHESIS, benchable at rail test points 5/6.
"+5T must read 5 V during TX" (manual p.16) ties the PA to the +5T rail.
See docs/maintenance_manual_findings.md. -->

## Scope and evidence

This document describes the hardware-facing PA control recovered from
BASE firmware 1.1.9. It deliberately does not attempt to reproduce the
OEM control policy.

Primary evidence:

- `analysis/pa/pa_control_decompilation.txt`;
- `analysis/pa/bias_device_init_decompilation.txt`;
- `analysis/pa/pre_main_bias_init_decompilation.txt`;
- `analysis/pa/bias_device_object_refs.csv`;
- `analysis/pa/bias_device_object.csv`;
- `analysis/pa/gpio_odr_refs.csv`;
- disassembly and decompilation under `analysis/pa/callbacks/`.

Firmware SHA-256:

`3fa11293e06951c21c9cfda04ea08adad85eaadda26b77a8e8bbcca8820c53c4`

## External two-channel bias-control device

The object at `0x20000334` has the following initialized layout:

| Offset | Value | Meaning | Confidence |
| ---: | ---: | --- | --- |
| `+0x00` | `0xC6` | I2C address byte; conventional 7-bit address `0x63` | VERIFIED |
| `+0x04` | `2` | accepted channel count | VERIFIED |
| `+0x08` | `5000` | object constant, also used as write timeout | VERIFIED value |
| `+0x0C` | `0x0400` initially | overwritten by startup readback | VERIFIED |
| `+0x10`, `+0x14` | `0` | cached values for channels 0 and 1 | VERIFIED |
| `+0x20` | `0x08030F25` | Thumb I2C1 write callback | VERIFIED |
| `+0x24` | `0x08030FE5` | Thumb I2C1 read callback | VERIFIED |
| `+0x28` | `0x08030FC5` | Thumb PE10 pulse/delay callback | VERIFIED |

`FUN_0803062c(object, channel, value)` ignores channels greater than
or equal to two. If the requested value differs from the cached value,
it sends exactly three bytes:

```
byte 0 = channel << 3
byte 1 = value >> 8
byte 2 = value
```

It then invokes the PE10 callback with argument `10`. The callback
drives PE10 low, calls the firmware delay function, and drives PE10
high. Transaction bytes, cache behavior, bus, address, and GPIO pulse:
VERIFIED. PE10 being the device's update/latch signal is HIGH
CONFIDENCE; the schematic net name remains unknown.

The I2C callbacks serialize access to I2C1 (`0x40005400`). Writes use a
timeout of 5000 and reads use 2500; either failure invokes the common
I2C1 recovery path: VERIFIED.

### Startup transaction sequence

`FUN_080305ac` clears all four cached slots in the generic object and
sends these three-byte frames to address `0xC6`:

```
00 00 00
40 00 00
48 00 00
50 00 00
```

It pulses PE10 low/high, then performs a two-byte read associated with
command/register `0x10` and stores the result at object offset `+0x0C`:
VERIFIED.

The exact IC is unresolved. An MCP4728 identification is specifically
not supported: that device is four-channel and its documented command
framing does not match this two-channel object and runtime
channel-select byte. Device identity: unknown.

## Channel roles

The firmware uses only channels 0 and 1:

| Channel | Firmware use | Confidence |
| ---: | --- | --- |
| 0 | drive-stage quiescent-current control | HIGH CONFIDENCE |
| 1 | final-stage quiescent-current control | HIGH CONFIDENCE |

The association comes from diagnostic strings
`PA_drive_stage_current` and `PA_final_stage_current`, their calibration
order, and the use of ADC2 channel 7 / PA7 as current feedback. The
electrical DAC transfer function and the final current units are not
yet known.

Protocol register 41 supplies the normal operating codes. Its low
16-bit half is sent to channel 0 and its high 16-bit half to channel 1:
VERIFIED for BASE 1.1.9.

## RX/TX hardware sequence

`FUN_0802aaf4` is the central hardware transition. The table records
the order visible in the function; all GPIO levels are direct ODR
levels.

### Enter RX / disable TX

1. PE12 high.
2. Board-variant PA-control callback called with `0`.
3. Bias channel 0 set to zero.
4. Bias channel 1 set to zero.
5. PE9 high.
6. PE8 low.
7. PG11 low.
8. PE2 low.
9. Internal DSP/control state is changed by `FUN_08023f20(0)`.
10. PD3 high.
11. PD4 low.
12. Internal state bit `0x2` is cleared by `FUN_08033974`.

### Enter TX / enable PA

After the mode-dependent audio/DSP preparation:

1. Bias channel 0 receives the cached drive-stage code.
2. Bias channel 1 receives the cached final-stage code.
3. Board-variant PA-control callback called with `1`.
4. PE9 low.
5. PE8 high.
6. PG11 high.
7. PE2 high.
8. PD3 low.
9. PD4 high.
10. Internal state bit `0x2` is set by `FUN_08033974`.

The order, levels, and bias-channel writes are VERIFIED. Treating the
GPIO group as PA/RF enable and routing controls is HIGH CONFIDENCE, but
assigning individual relay, gate-bias, or supply-enable net names is
still a HYPOTHESIS without schematic or measurements.

### PA-calibration subset

The startup current-calibration procedure does not assert the complete
TX group. Before applying either bias code it performs:

1. board-variant PA-control callback = `1`;
2. PE9 low;
3. PE8 high;
4. PG11 high.

After testing both stages it restores:

1. board-variant PA-control callback = `0`;
2. PE8 low;
3. PE9 high;
4. PG11 low.

PE2, PD3, PD4, and PE12 are not changed by this calibration enable
window. Therefore the callback plus PE8/PE9/PG11 form the directly
PA-related enable/bias-measurement subset: HIGH CONFIDENCE. PE2 and
the complementary PD3/PD4 pair are more likely RX/TX routing or
support-power controls, but their exact roles remain HYPOTHESIS.

The later ACC correlation narrows PE2 further: the published ACC
connector contains an MCU-controlled `TRX` signal, and PE2 has the
matching RX=`0`, TX=`1` behavior. PE2 as ACC `TRX` is HIGH CONFIDENCE;
the firmware levels are VERIFIED. See `docs/acc.md`.

### PA enable tuple

An exhaustive audit of the known startup, normal RX/TX, PA-calibration,
post-calibration, and shutdown paths gives:

| State | PE8 | PE9 | PG11 | PCA9535 bit 0 / PD14 |
| --- | ---: | ---: | ---: | ---: |
| startup/RX safe | 0 | 1 | 0 | 0 |
| normal RX | 0 | 1 | 0 | 0 |
| normal TX | 1 | 0 | 1 | 1 |
| PA bias calibration | 1 | 0 | 1 | 1 |
| post-calibration RX | 0 | 1 | 0 | 0 |
| shutdown | 0 | 1 | 0 | 0 |

The levels in every listed path are VERIFIED. PE8 and PG11 always
share one level, PE9 is always their complement, and the
PCA9535-bit-0/PD14 callback follows the asserted/deasserted state of
PE8 and PG11. No recovered path independently stages these four
logical controls.

This establishes a single firmware-level PA enable tuple:

`disabled = {PE8=0, PE9=1, PG11=0, callback=0}`

`enabled  = {PE8=1, PE9=0, PG11=1, callback=1}`

Treating the tuple as the PA bias-measurement/TX enable condition is
HIGH CONFIDENCE because exactly the same asserted state is required
during both ordinary TX and bias-current calibration. Assigning
individual schematic names remains unsafe without continuity evidence.
The lifecycle table is exported in
`analysis/pa/pa_gpio_lifecycle.csv`.

### PD3/PD4 receive/transmit supply correlation

The X6100 service manual identifies separate middle-board rails:

- `+5R`, present in receive and zero in transmit;
- `+5T`, present in transmit and theoretically zero in receive.

Firmware drives PD3 high/PD4 low in RX and PD3 low/PD4 high in TX.
The levels are an exact match for active-high enables of `+5R` and
`+5T`, respectively. Therefore:

| GPIO | Candidate physical role | Confidence |
| --- | --- | --- |
| PD3 | front-panel power/charge LED (active-high) — supersedes the earlier `+5R` receive-rail reading | VERIFIED on hardware |
| PD4 | `+5T` transmit-rail enable | HIGH CONFIDENCE |

The external rail behavior is documented by the
[X6100 service manual](https://www.manualslib.com/guide/3740642/xiegu-x6100-hf-transceiver-series-manual.html);
the GPIO levels and ordering are VERIFIED from firmware. Final net
names still require continuity measurement or schematic evidence.

The shutdown sequence is consistent with this interpretation: PD4 is
cleared first, then PD3 after five seconds, and the remaining PD2
support-power signal after another three seconds. PD2's exact rail is
still unknown.

The early charger/service loop independently toggles PD3 while charging
and forces it high when its full condition is reached: VERIFIED. This
does not change the service-manual correlation during normal RX/TX, but
the reason for the early reuse is unresolved. Charge indication,
temporary `+5R` cycling, and an incomplete physical interpretation
remain HYPOTHESIS alternatives. See `docs/charger.md`.

### PE12 CW hardware output

PE12 is not simply a static member of the RX/TX group. In CW/CWR modes
the fast DMA1 Stream 3 handler compares the current RF-envelope sample
with zero on every generated sample:

```
sample > 0  -> PE12 low
sample <= 0 -> PE12 high
```

When TX is disabled or a non-CW mode is selected, the same path forces
PE12 high. The comparison, per-sample update, mode restriction, and
safe-high state are VERIFIED. PE12 being an active-low hardware CW/RF
key output is HIGH CONFIDENCE; the external net and destination remain
unknown. PE12 remains high throughout PA bias calibration and is not
part of the PA enable tuple: VERIFIED.

## Board-variant PA-control callback

`FUN_0803131c` assigns the callback stored at `0x2000C6CC` according to
the detected hardware variant:

| Variant implementation | Effect of argument `0` / `1` | Confidence |
| --- | --- | --- |
| `FUN_08031120` | clear/set output bit 0 in the PCA9535-compatible I2C2 expander at 7-bit address `0x20`, then commit the output word | VERIFIED |
| `FUN_080312bc` | clear/set GPIOD ODR bit 14 (PD14) directly | VERIFIED |

Thus this callback is one logical board signal implemented either as
PCA9535 output bit 0 or PD14: VERIFIED. Its participation in every RX/TX
transition makes a PA/RF enable or routing role HIGH CONFIDENCE. Its
exact physical net and active semantics beyond the observed RX=`0`,
TX=`1` remain unknown.

This callback is one member of a seven-slot board-abstraction table.
The complete recovered backend correspondence is:

| Slot | PCA9535 backend | Direct-GPIO backend |
| --- | --- | --- |
| `0x2000C6BC` | bit 2, active-low | PG2, polarity selected by a board flag |
| `0x2000C6C0` | bit 10 | PG3 |
| `0x2000C6C4` | bit 14 | PG5 |
| `0x2000C6C8` | bit 1, active-low | PF12 |
| `0x2000C6CC` | bit 0 | PD14 |
| `0x2000C6D0` | bit 15 | PD15 |
| `0x2000C6D4` | one-hot RF mask | binary RF code on PD9/PD10/PD11/PD13 |

Callback addresses, affected bits, and GPIOs: VERIFIED. The logical
signal names remain unknown. This wider table confirms that
PCA9535-bit-0/PD14 is a board-revision abstraction rather than two
unrelated operations. Machine-readable mappings and reusable Ghidra
exports are under `analysis/pa/variant_callback_map.csv` and
`analysis/pa/variant_callbacks/`.

`FUN_08023f20` and `FUN_08033974`, although adjacent to the GPIO writes,
only update RAM state/dirty bits; they are not direct hardware
operations: VERIFIED.

The startup safe state in `FUN_0802a5d0` agrees with the RX sequence:
both bias values are zero, PE12/PE9/PD3 are high, and
PE8/PG11/PD4 are low. PE2 is additionally driven low by the explicit
RX transition. This correspondence is VERIFIED.

## Independent implementation requirements

- Initialize I2C1 and the external bias device before any PA enable.
- Preserve the three-byte channel-write framing and PE10 low/high
  update pulse.
- Keep both bias channels at zero in startup and RX safe states.
- Apply the stored channel-0 and channel-1 codes before asserting the
  remaining TX GPIO group, matching the recovered order.
- Preserve the complete PE8/PE9/PG11/variant-callback tuple. There is no
  firmware evidence that any member may be omitted or combined with
  another output electrically.
- In CW/CWR, reproduce the active-low PE12 update from the current RF
  envelope rather than treating PE12 as a once-per-transition signal.
- On return to RX, disable the board-level path before zeroing both
  bias channels, matching the recovered order.
- Keep all unknown GPIOs and the variant callback under provisional
  names until board-level evidence identifies their nets.
