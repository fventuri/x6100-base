# BASE bootloader (IAP) flash dump

`base_bootloader_0x08000000-0x0801FFFF.bin` — the 128 KiB boot-resident region of
the X6100 BASE STM32F427 internal flash, captured from live hardware.

| Property | Value |
| --- | --- |
| Covers | `0x08000000`–`0x0801FFFF` (131072 bytes) |
| md5 | `c3221064e14fe1fd473bdcafdd9fe2c6` |
| sha256 | `d82fa5a40e3ab021285567c423bf861d82abd1bd30d4a3c3f96278b5c7903285` |
| Captured | 2026-10-07, from fventuri's X6100 BASE MCU |

## Why this matters

`docs/base_firmware_update.md` established that this region is **not recoverable**
from either supplied application binary or the Linux `x6100_ui` ELF, yet it holds
the boot-resident code that runs after the GPIO-strap reset: it emits the IAP
greeting (`A`/`a`), implements the 1K-XMODEM receiver, erases/programs the
application flash, selects the application vector table, and decides how/when to
enter the application after the final EOT. This dump makes that code available for
analysis for the first time.

## How it was captured

On-hardware, Linux-side, via the `base-flasher` toolkit (not part of this repo):

1. `dump_fw/dumper` (a tiny STM32 app linked at `0x08020000`) was flashed into the
   application region through the IAP bootloader using the Linux flasher
   (`x6100_base_flash.py`, GPIO strap/reset + 1K-XMODEM).
2. The dumper reads internal flash `0x08000000`–`0x0807FFFF` and streams it as
   CRC-32-checked `XDMP` frames over `USART6` (PC6) → the R16's `/dev/ttyS1`
   @115200.
3. `capture_dump.py` on the R16 reassembled the stream by address: **2048/2048
   blocks, no gaps**, CRC-verified.

## Scope / caveats

- This file is **only** the `0x08000000`–`0x0801FFFF` bootloader region. The full
  512 KiB capture's application region (`0x08020000`+) contained the **dumper
  itself** at capture time (that is what was running), **not** the stock
  application, so only the bootloader region is preserved here as the meaningful
  artifact. The stock `V1.1.9` application is available separately as the
  decrypted `.xgf` / the `1.1.9` image already analysed in this project.
- This is the **raw on-chip flash** (already plaintext). The `.xgf` AES-256-ECB
  encryption applies only to the IAP *wire* transfer, not to what is stored in
  flash.

## Loading in Ghidra

- Format: Raw Binary
- Language: ARM Cortex little-endian (Cortex-M4F; STM32F427)
- Base / image address: `0x08000000`
- Vector table at `0x08000000`: initial MSP `0x20030000`, reset vector
  `0x08001991` → **reset handler `0x08001990`** (Thumb). The region tail up to
  `0x0801FFFF` is `0xFF`-erased.
