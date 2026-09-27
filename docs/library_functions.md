# Third-party library functions and build environment

## Summary

96 of the 456 recovered firmware functions are **byte-for-byte** identical to
functions in stock prebuilt libraries, so they are not application code and need
no behavioural reverse engineering. They were identified with
`tools/identify_lib_functions.py` (relocation-aware exact matching; the method is
described in `docs/dsp_primitives.md`).

Matching them also pins the firmware's build environment:

| Component | Identity | Confidence |
| --- | --- | --- |
| CMSIS-DSP | STM32Cube_FW_F4 **V1.23.0** prebuilt `libarm_cortexM4lf_math.a` (CMSIS-DSP V1.4.5) | VERIFIED |
| C library | **newlib-nano** from **ST `gnu-tools-for-stm32` GCC 12.3.1** (bundled with STM32CubeIDE) | VERIFIED (nano); HIGH CONFIDENCE (exact GCC point release) |
| Compiler runtime | **libgcc** from the same ST GCC 12.3.1 | VERIFIED |

The firmware was therefore built in ST's STM32CubeIDE toolchain, not with an
upstream GNU Arm / xpack build, and links **newlib-nano** (`-specs=nano.specs`).

## Toolchain determination

`libc`, `libc_nano`, `libm`, and `libgcc` (Cortex-M4F `v7e-m+fp/hard` multilib)
were swept across every arm-none-eabi toolchain on hand. Exact non-trivial
matches (confidence ≥ 0.99):

| Toolchain | full `libc` | **`libc_nano`** | `libm` | `libgcc` |
| --- | ---: | ---: | ---: | ---: |
| xpack GCC 7.3.1 | 0 | 7 | 0 | – |
| xpack GCC 8.3.1 | 0 | 7 | 0 | 9 |
| xpack GCC 9.3.1 | 0 | 11 | 0 | 11 |
| xpack GCC 10.3.1 | 0 | 13 | 0 | 11 |
| xpack GCC 11.3.1 | 0 | 19 | 0 | 11 |
| xpack GCC 13.3.1 | 0 | 42 | 0 | 11 |
| **ST gnu-tools 12.3.1** | **27** | **52** | **5** | **12** |

Only ST's toolchain matches full `libc`/`libm` at all, and it wins every
column: VERIFIED that the C runtime is ST's newlib build, not a generic GNU Arm
one. The C runtime is **newlib-nano**, not full newlib: the nano archive matches
far more (52 vs 27) and adds the high-level stdio/heap routines that differ
between the two (`_printf_float`, `_vfprintf_r`, `_malloc_r`, ...). `_dtoa_r`
matches byte-exact over 2508 bytes.

Only ST 12.3.1 was available for the run; a neighbouring ST `gnu-tools` release
could be byte-identical for these functions, so the exact GCC point release is
HIGH CONFIDENCE rather than VERIFIED. There were essentially no near-miss
(0.90–0.99) matches, i.e. no "one version off" gradient — consistent with 12.3.1
being the actual build or byte-equivalent to it.

## Identified functions

Full machine-readable list (96 functions, confidence ≥ 0.99):
`analysis/library_functions/runtime_library_matches.csv`. Highlights:

### newlib-nano `libc` (62)

- float `printf`/`scanf` and stdio: `_printf_float`, `_scanf_float`,
  `_vfprintf_r`, `_svfprintf_r`, `_printf_i`, `_printf_common`, `__cvt`,
  `__exponent`, `snprintf`/`sniprintf`/`siprintf`, `setvbuf`, `__sflush_r`,
  `__swsetup_r`, `__swbuf_r`, `__smakebuf_r`, `__ssputs_r`;
- David-Gay float conversion (`dtoa`/`strtod`): `_dtoa_r` (2508 B), `__gethex`,
  `__hexnan`, `__multiply`, `__multadd`, `__mdiff`, `__mcmp`, `quorem`,
  `__lshift`, `rshift`, `__d2b`, `__b2d`, `__ulp`, `__ratio`, `__copybits`,
  `__any_on`, `__hi0bits`, `__lo0bits`, `_strtol_l`;
- heap: `_malloc_r`, `_free_r`.

### `libm` (5)

`__kernel_rem_pio2f` (1222 B), `powf`, `cosf`, `log10f`,
`sqrtf`/`__ieee754_sqrtf`.

### `libgcc` (13)

soft-float **double** and integer helpers: `__adddf3` (630 B), `__udivmoddi4`,
`__truncdfsf2`, `__cmpdf2`, `__unorddf2`, `__fixdfsi`, `__fixunsdfsi`,
`__fixdfdi`, `__fixunsdfdi`, `__floatsidf`, `__floatunsidf`, `__floatdidf`,
`__extendsfdf2`, `__aeabi_dcmp{eq,lt,le}`, `__aeabi_cdcmpeq`. This confirms the
firmware performs `double`-precision math through the ARM EABI soft-float path.

### CMSIS-DSP (16)

See `docs/dsp_primitives.md`.

## Significance

- These 96 functions are stock library code; excluding them focuses the RE effort
  on the ~360 application functions.
- Because the matches are exact, they can be renamed with their library symbol
  names at VERIFIED confidence (the two `_init` type-suffix ambiguities noted in
  `docs/dsp_primitives.md` excepted).
- A compatible reimplementation may link the same libraries rather than
  reimplementing these functions.

## Reproducing

```sh
python3 tools/identify_lib_functions.py \
    --image X6100_BBFW_V1.1.9_251127001.bin \
    --functions analysis/memory/function_ranges.csv \
    --lib <path to the prebuilt library> \
    --min-confidence 0.99 --min-invariant 24
```

Libraries are proprietary/toolchain files and are not committed; they are the
CubeF4 V1.23.0 CMSIS-DSP archive (SHA-256 in `docs/dsp_primitives.md`) and the
`thumb/v7e-m+fp/hard` `libc_nano.a` / `libm.a` / `libgcc.a` from ST
`gnu-tools-for-stm32` 12.3.1.
