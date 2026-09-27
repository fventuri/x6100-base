# Recovered DSP primitives

## Scope

The large DMA1 Stream 3 handler calls a small set of optimized
floating-point primitives. Their algorithms and state layouts allow
candidate CMSIS-DSP identities to be assigned without yet renaming
symbols.

All names in this document are candidates unless explicitly marked
otherwise. The CMSIS-DSP identities have now been confirmed by exact
object-code identity against a specific library build; see
[CMSIS-DSP library identification](#cmsis-dsp-library-identification-verified).

## Direct calls from the DMA handler

The complete call graph contains 26 unique direct callees from
`FUN_08024528`. Many are runtime arithmetic, memory, or DMA helpers.
The following functions implement reusable signal-processing kernels.

| Address | Current symbol | Candidate identity | Evidence | Confidence |
| ---: | --- | --- | --- | --- |
| `0x08035364` | `FUN_08035364` | `candidate_arm_fir_interpolate_f32` | polyphase FIR, interpolation factor in instance, produces multiple outputs per input | HIGH CONFIDENCE |
| `0x080357C0` | `FUN_080357c0` | `candidate_arm_fir_f32` | FIR instance with tap count, coefficient pointer, state pointer, block processing | HIGH CONFIDENCE |
| `0x08035C88` | `FUN_08035c88` | `candidate_arm_fir_decimate_f32` | block size divided by instance factor; one output per factor-sized input group | HIGH CONFIDENCE |
| `0x08036000` | `FUN_08036000` | `candidate_arm_biquad_cascade_df1_f32` | stages use five coefficients and four state floats | HIGH CONFIDENCE |
| `0x080361A0` | `FUN_080361a0` | `candidate_arm_cmplx_mag_f32` | computes `sqrt(real² + imag²)` for interleaved complex input | HIGH CONFIDENCE |
| `0x08036478` | `FUN_08036478` | `candidate_arm_scale_f32` | multiplies each source float by one scalar | HIGH CONFIDENCE |

The mathematical behavior in the final column is VERIFIED from the
instructions. Exact library symbol identity is now also VERIFIED: every
function in this table is byte-identical to the corresponding symbol in the
STM32Cube_FW_F4 V1.23.0 prebuilt CMSIS-DSP library. See
[CMSIS-DSP library identification](#cmsis-dsp-library-identification-verified)
below.

## Rate-conversion evidence

The DMA handler calls both the candidate decimator and interpolator.
Firmware initialization also establishes rate constants of 100 kHz,
12.5 kHz, and 25 kHz.

Together these establish that the signal path contains explicit
multi-rate FIR processing: VERIFIED.

The RX call sites are now separated. SSB/CW use a direct factor-8
complex decimator. AM/NFM use factor 4 before demodulation and factor 2
after it. All modes therefore produce 16 audio samples at the
12.5-kHz-domain rate from each 128-sample input block, and a factor-8
interpolator returns 128 samples to the output domain. The call topology
and integer factors are VERIFIED; interpreting the initialization
constants as physical sample rates still requires a hardware clock
measurement. See `docs/rx_pipeline.md`.

All RX rate-conversion FIR coefficient sets are exported and
independently checked for symmetry and representative response. Runtime
RX biquad table selection remains to be completed. See
`docs/rx_pipeline.md`.

## Biquad processing

`FUN_08036000` iterates over a stage count. Each stage consumes:

- five coefficients;
- four persistent state values;
- a caller-provided float block.

The output of each stage becomes the input to the next stage. This is a
direct-form-I floating-point biquad cascade: VERIFIED.

Multiple state objects are passed to this primitive from different
branches of the DMA handler, so one final semantic name cannot yet be
assigned to every filter instance.

## TX filter instances

| Object | Primitive | Parameters | Confidence |
| ---: | --- | --- | --- |
| `0x20007244` | FIR decimator | factor 8, 64 taps | VERIFIED |
| `0x20007728` | biquad cascade | 5 stages, generated for 300 Hz at 12.5 kHz | VERIFIED parameters |
| `0x200077F4` | biquad cascade | 5 stages, generated for 3000 Hz at 12.5 kHz | VERIFIED parameters |
| `0x200078D8` | FIR | 101-tap antisymmetric quadrature coefficients | VERIFIED structure |
| `0x20007490` | FIR interpolator | factor 8, 64 taps | VERIFIED |
| `0x200075DC` | FIR interpolator | factor 8, 64 taps | VERIFIED |

The decimator and both interpolators share the flash coefficient array
at `0x0803E3E4`. The quadrature FIR uses `0x0803E130`. Both arrays are
exported under `analysis/tx_filters/`. Its exact antisymmetry, zero
center tap, and use with a 50-sample delay establish a Hilbert role:
HIGH CONFIDENCE.

The 300/3000 Hz biquad entries have also been exported. Each contains
five six-float source sections plus an overall gain. The runtime loader
converts each section into the five-float CMSIS-style DF1 layout and
applies the two overall gains after cascading both objects: VERIFIED.
See `docs/tx_pipeline.md` for the selection formula and addresses.

## Complex magnitude

`FUN_080361a0` consumes interleaved real/imaginary float pairs and emits
one magnitude per pair:

```text
magnitude = sqrt(real * real + imag * imag)
```

Algorithm: VERIFIED. Its DMA-handler call site is a candidate signal
level/envelope stage; the downstream consumer must be traced before
that semantic label is finalized.

## CMSIS-DSP library identification (VERIFIED)

The optimized floating-point primitives are byte-for-byte identical to the
prebuilt CMSIS-DSP library shipped in **STM32Cube_FW_F4 V1.23.0**:

| Property | Value |
| --- | --- |
| Source package | STM32Cube_FW_F4 **V1.23.0** |
| Archive member | `Drivers/CMSIS/Lib/GCC/libarm_cortexM4lf_math.a` |
| SHA-256 | `23585b33cc55776a0c395a164ea1519e1ecde26f0910bbad5d86dd0b0fa1fdf7` |
| CMSIS-DSP version | V1.4.5 (per bundled `arm_math.h`) |
| ABI | Cortex-M4, little-endian, hard-float (`lf`) |

ST **rebuilt** this archive in later releases: STM32Cube_FW_F4 V1.24.0
through V1.27.1 all ship a single, different binary
(SHA-256 `73e7c4f8...`) whose float functions no longer match the firmware
(for example `arm_fir_f32` falls to ratio 0.65), and V1.28.0+ omit the
prebuilt archive entirely. Only the V1.23.0 build matches. The firmware's
CMSIS-DSP is therefore specifically this build: VERIFIED by exact
object-code identity.

### Verified function identities

Each firmware function below is byte-identical to the named library symbol
over every position-independent byte (relocation-affected bytes masked),
i.e. confidence 1.000. Load base `0x08020000`.

| Firmware address | Library symbol | Invariant / masked bytes |
| ---: | --- | ---: |
| `0x08036550` | `arm_radix8_butterfly_f32` | 1476 / 0 |
| `0x080357c0` | `arm_fir_f32` | 1224 / 0 |
| `0x08034d7c` | `arm_cfft_radix8by4_f32` | 1194 / 16 |
| `0x08035364` | `arm_fir_interpolate_f32` | 1080 / 0 |
| `0x08035c88` | `arm_fir_decimate_f32` | 888 / 0 |
| `0x08036000` | `arm_biquad_cascade_df1_f32` | 414 / 0 |
| `0x080361a0` | `arm_cmplx_mag_f32` | 444 / 20 |
| `0x08034bd8` | `arm_cfft_radix8by2_f32` | 412 / 8 |
| `0x08035238` | `arm_cfft_f32` | 226 / 16 |
| `0x08034b08` | `arm_max_f32` | 208 / 0 |
| `0x08036478` | `arm_scale_f32` | 108 / 0 |
| `0x080364e4` | `arm_abs_f32` | 108 / 0 |
| `0x08034aa8` | `arm_copy_f32` | 94 / 0 |
| `0x08034a6c` | `arm_fill_f32` | 60 / 0 |
| `0x0803532c` | `arm_fir_interpolate_init_f32` * | 50 / 4 |
| `0x0803579c` | `arm_fir_init_f32` * | 30 / 4 |

`*` The two `_init` routines are byte-identical across the CMSIS `_f32`,
`_q31`, and `_q15` type variants (they only fill an instance struct), so
object code alone cannot select the suffix. The `_f32` variant is named
because the surrounding path is float: function body VERIFIED, type suffix
HIGH CONFIDENCE.

This confirms and extends the earlier candidate table: `arm_fir_*`,
`arm_biquad_cascade_df1_f32`, `arm_cmplx_mag_f32`, and `arm_scale_f32` are
now VERIFIED, and the CFFT/radix-8 kernels, `arm_abs/copy/fill/max_f32`,
and the FIR init routines are newly identified.

Full machine-readable results are in
`analysis/dsp_primitives/cmsis_dsp_v1230_matches.csv`.

### Identification tool

`tools/identify_lib_functions.py` performs relocation-aware signature
matching between an analyzed image and a static `.a` library, scoring each
firmware function against every library symbol in the interval [0, 1]:

```sh
python3 tools/identify_lib_functions.py \
    --image X6100_BBFW_V1.1.9_251127001.bin \
    --functions analysis/memory/function_ranges.csv \
    --lib .../STM32Cube_FW_F4_V1.23.0/Drivers/CMSIS/Lib/GCC/libarm_cortexM4lf_math.a
```

For each library symbol it reads the exact `.text.<name>` bytes and the ELF
relocations inside them, masks the four-byte field at every code relocation
(BL/B.W targets, MOVW/MOVT address halves, ABS32 literal-pool words), and
compares the remaining invariant bytes against `N` bytes at each firmware
function entry. Confidence is the invariant-byte match ratio; matches with
fewer than `--min-invariant` invariant bytes are gated out as trivial, and
ambiguous ties are flagged. The method is sound because the same GCC/linker
produced both sides, so instruction encodings and literal-pool layout are
identical apart from the relocated fields; a positive control that
synthesises an image from the library's own bytes matches every function at
1.000. The proprietary ST library is not committed; it is identified above
by SHA-256.

## Call-graph tooling

`ghidra_scripts/ExportCallGraph.java` exports every direct call as:

```text
caller_address,caller,call_site,callee_address,callee
```

Run it with:

```text
./tools/run_headless_callgraph.sh analysis/callgraph.csv
```

The export is deterministic for the current analyzed Ghidra project and
does not rename or modify the program.

## Reproducible evidence

- `analysis/callgraph.csv`;
- `analysis/interrupts/irq_14_DMA1_Stream3_08024528_disassembly.txt`;
- `ghidra_scripts/ExportCallGraph.java`;
- `analysis/dsp_primitives/cmsis_dsp_v1230_matches.csv`;
- `tools/identify_lib_functions.py` (against the SHA-256-identified V1.23.0 library).
