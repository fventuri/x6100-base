# Controlled shutdown

## Scope

This document records the complete BASE 1.1.9 controlled-shutdown path
from its Linux-visible request through GPIO rail sequencing and the
final Cortex-M reset.

## Protocol entry

The Linux-visible request is bit 16 (`power_off`) of protocol register
`0x0030`, historically named `sple_atue_trx`.

`FUN_0802AF0C` tests:

```text
uptime_counter > 1999 || (register_0x0030 & 0x00010000) != 0
```

When either condition is true, it returns true. In normal runtime,
setting `power_off` therefore terminates the superloop in
`FUN_08034178`. The bit does not directly write a GPIO. The test,
return value, and superloop edge are VERIFIED.

The uptime condition participates in the startup transition into the
same main-loop region; it must not be interpreted as an unconditional
two-second power-off timer without reconstructing the surrounding
startup state.

## Ordered shutdown

After the superloop exits, `FUN_08034178` executes this sequence:

1. stop or quiesce the protocol, tuner/control, USART, saved-state, PA,
   charger-backend, and audio-related paths;
2. clear PG0, PG1, and PG11;
3. clear PE7, PE8, PE9, PE14, and related PA outputs;
4. clear PD4;
5. set PF11 high;
6. wait 5000 delay units;
7. clear PD3;
8. wait 3000 delay units;
9. clear PD2;
10. clear PE11;
11. mask interrupts through PRIMASK;
12. wait until GPIOG input PG4 is high;
13. clear PE11 again;
14. wait 100 delay units;
15. execute a data synchronization barrier;
16. preserve AIRCR priority-group bits and write the `0x5FA` key with
    `SYSRESETREQ`;
17. execute another barrier and wait forever for reset.

The GPIO pins, levels, delays, ordering, interrupt mask, and AIRCR reset
request are VERIFIED. Existing timing-helper use supports interpreting
5000 and 3000 as approximately five and three seconds: HIGH CONFIDENCE.

PE11 is already included in the earlier GPIOE clear mask and is cleared
again after PG4 becomes high. Both writes are present in the firmware:
VERIFIED.

## Power-control interpretation

| Signal | Recovered behavior | Interpretation | Confidence |
|---|---|---|---|
| PD4 | low before the five-second delay | `+5T` transmit-rail disable | HIGH CONFIDENCE role; VERIFIED level |
| PD3 | low after the five-second delay | power/charge LED off at power-down (PD3 = power LED, VERIFIED on hardware; supersedes the `+5R` rail reading) | VERIFIED level |
| PD2 | low after the additional three-second delay | remaining support-power or power-hold disable | HIGH CONFIDENCE role; exact net unresolved |
| PG4 | input awaited high before final reset | power/status feedback | HIGH CONFIDENCE role; exact source unresolved |
| PE11 | cleared before and after the PG4 wait | member of PA/power shutdown state | VERIFIED behavior; exact individual net unresolved |

The sequence is therefore an ordered rail shutdown, not a single
`power_off` GPIO write: HIGH CONFIDENCE. PD2 is the strongest candidate
for the final MCU-controlled power-hold output, but a final semantic
symbol name requires continuity or voltage evidence.

## Independent implementation contract

- Treat register `0x0030` bit 16 as a request, not an immediate pin
  assignment.
- Quiesce transmit, PA bias, DMA/audio, buses, and saved-state handling
  before removing rails.
- Preserve the PD4 → five-second delay → PD3 → three-second delay →
  PD2 ordering until the board nets are measured.
- Wait for PG4 in the same polarity before requesting system reset.
- Keep all TX and PA controls inactive throughout the sequence.
- Provide a timeout or fail-safe policy only as an explicitly
  documented deviation from OEM behavior; the recovered firmware waits
  indefinitely for PG4.
