# BASE firmware update from Linux

## Scope and evidence

The complete Linux-side update path was recovered from the unstripped
`x6100_ui_v100` ELF:

| Function | Address | Role |
| --- | ---: | --- |
| `UiFwUpgrade::upgradeFirmware` | `0x00070FBC` | read selected image and start worker |
| `XMWorker::slot_start` | `0x0006FEC4` | IAP orchestration |
| `_comm_send_cmd` | `0x0006FB78` | one-byte command/response |
| `xradio_start_xmodem` | `0x000933EC` | GPIO boot entry and UART greeting |
| `Xmodem::sendFile` | `0x0007A75C` | 1K XMODEM sender |

Names and addresses come from the preserved OEM ELF symbol table:
VERIFIED. The descriptions are behavioral documentation, not proposed
renames for BASE firmware symbols.

The application selects a file below `/usr/firmware`, reads its entire
contents into a byte array, and passes those bytes unchanged to the
worker: VERIFIED. No image header, signature, checksum, target-address,
or size validation occurs in the recovered Linux path: VERIFIED.

## Entry into BASE IAP

The normal `/dev/ttyS1` receive worker is suspended, the input is
drained, and the following exact GPIO sequence is executed:

| Step | Command/effect |
| ---: | --- |
| 1 | export GPIO 203 |
| 2 | set GPIO 203 direction to output |
| 3 | drive GPIO 203 low |
| 4 | export GPIO 204 |
| 5 | set GPIO 204 direction to output |
| 6 | drive GPIO 204 high |
| 7 | wait 100 ms and drain UART |
| 8 | drive GPIO 204 low |
| 9 | unexport GPIO 204 |
| 10 | wait for ASCII `A` or `a` from BASE |
| 11 | drive GPIO 203 high |
| 12 | unexport GPIO 203 |

Command order and levels: VERIFIED. GPIO 203 is the shared active-low
CW/IAP-strap line; GPIO 204 is the BASE reset line with HIGH
CONFIDENCE. See `docs/linux_hardware_interface.md`.

The greeting reader polls for up to about one second at a time. An
unexpected nonzero byte consumes one of 51 outer attempts, separated
by 100 ms; a per-attempt timeout aborts immediately. Acceptance test
`byte & 0xDF == 'A'` permits `A` and `a`: VERIFIED.

GPIO 203 is restored high and both temporary sysfs exports are removed
even if the greeting fails: VERIFIED.

## IAP commands before transfer

After the `A`/`a` greeting:

1. Linux transmits ASCII `r`.
2. It waits as long as 60 seconds for any nonzero byte.
3. Linux transmits ASCII `p`.
4. It waits as long as one second for any nonzero byte.

Bytes `r` and `p`, ordering, and timeouts: VERIFIED. String evidence
labels the first phase as flash erase and the second as XMODEM start,
so the meanings are:

- `r`: erase/prepare application flash — HIGH CONFIDENCE;
- `p`: begin programming/XMODEM receive — HIGH CONFIDENCE.

The helper returns only whether it received a nonzero byte. Although it
stores the byte, the caller does not check a particular ACK value:
VERIFIED. An independent updater should initially preserve this
compatibility behavior while logging the actual responses.

## 1K XMODEM dialect

Before the first packet, Linux waits up to ten seconds for an exactly
two-byte read whose second byte is ASCII `C` or `c`: VERIFIED. The
first byte is not validated.

Every data packet is written in one `write()` call:

| Field | Bytes | Value |
| --- | ---: | --- |
| start | 1 | `0x02` (STX, 1K packet) |
| packet number | 1 | starts at 1 |
| complement | 1 | bitwise complement of packet-number byte |
| payload | 1024 | image data |
| CRC | 2 | CRC-16, high byte then low byte |

CRC initialization is zero and the polynomial is `0x1021`: VERIFIED.
The last packet is padded with `0xFF`: VERIFIED. Packet numbering uses
the low byte of a counter and therefore wraps naturally after 255:
VERIFIED.

After each packet Linux waits up to ten seconds for one byte:

- `0x06` ACK: continue;
- `0x15` NAK: abort;
- `0x18` CAN: abort;
- timeout or any other byte: abort.

There is no packet retry path after NAK or timeout: VERIFIED. This is a
notable limitation of the OEM sender rather than standard robust
XMODEM behavior.

After the last acknowledged packet, Linux sends `0x04` EOT and requires
`0x06` ACK within ten seconds: VERIFIED.

## Completion behavior

On transfer completion or failure, the application resumes the normal
BASE UART worker and updates only the GUI result state: VERIFIED. No
explicit Linux-side reset, jump-to-application command, power cycle, or
image-verification request follows XMODEM in this code path: VERIFIED.

Consequently, the BASE IAP implementation itself must decide how and
when to leave the bootloader after the final ACK: HIGH CONFIDENCE.

The supplied decrypted BASE file is not a complete flash dump. Its
first word is the application initial MSP and its second word is the
application reset vector. Ghidra maps that first byte at `0x08020000`,
and the application itself installs `0x08020000` in `SCB->VTOR`:
VERIFIED. The file therefore contains only
`0x08020000`–`0x0807FB70`; it contains no bytes for
`0x08000000`–`0x0801FFFF`: VERIFIED.

The older 1.1.6 reverse-engineering project independently maps its
application vector table at the same `0x08020000`: VERIFIED. The
encrypted `.xgf` and decrypted `.bin` supplied for 1.1.9 also have the
same 392048-byte extent. The container does not carry an appended copy
of the omitted flash range: VERIFIED extent.

The missing 128 KiB range is the expected location of the custom code
that runs after the GPIO-strap reset and selects the application vector
table. It also contains separately addressed persistent blocks at
`0x08004000` and `0x08008000`, so the whole omitted range must not be
labelled as executable bootloader code. Presence of boot-resident
entry/exit code somewhere in that range: HIGH CONFIDENCE; its exact
boundaries: unknown.

No BASE-side XMODEM receiver or final-EOT control path can therefore be
traced in the supplied application image. The observable software
contract ends as follows:

1. BASE acknowledges EOT with `0x06`.
2. The Linux updater issues no further BASE command or reset.
3. Linux immediately returns ownership of the UART to the normal
   packet worker.

Steps 1–3: VERIFIED from the Linux updater. Automatic return to the
normal BASE application is required by the OEM workflow and is
therefore HIGH CONFIDENCE. Whether the omitted code uses
`SYSRESETREQ`, a direct vector-table jump, a watchdog, or another
mechanism remains unknown. The application's own verified
`SYSRESETREQ` path is the controlled power-off path and is not evidence
for IAP completion.

Recovering the exact mechanism requires a dump or executable image of
`0x08000000`–`0x0801FFFF`. It is not recoverable from either supplied
application binary or the Linux ELF: VERIFIED evidence boundary.

**UPDATE (2026-10-07): this region has now been dumped from live hardware** —
see `analysis/iap/base_bootloader_0x08000000-0x0801FFFF.bin` (128 KiB, reset
handler `0x08001990`) and `analysis/iap/README_bootloader_dump.md` for
provenance. The boot-resident greeting/XMODEM/app-entry code can now be
analysed directly rather than left as an evidence boundary.

## Independent updater checklist

1. Open the BASE UART and stop its normal packet consumer.
2. Drain pending input.
3. Apply the exact GPIO 203/204 boot/reset sequence.
4. Require `A` or `a`.
5. Send `r`; allow 60 seconds for erase response.
6. Send `p`; allow one second for response.
7. Require the two-byte XMODEM start ending in `C` or `c`.
8. Send 1024-byte, `0xFF`-padded CRC packets and require ACK.
9. Send EOT and require ACK.
10. Resume normal UART handling after the final ACK; tolerate the
    application startup interval before requiring normal packets.

Steps 1–10 reproduce the recovered OEM Linux behavior: VERIFIED. An
independent BASE bootloader must define and test its own post-EOT
validation and application-entry policy because the OEM mechanism is
not present in the available artifacts.
