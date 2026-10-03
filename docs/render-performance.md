# Render performance

The renderer runs offline at the score's full sample rate. Performance work must
preserve the synthesis equations, mode counts, seeded excitation, envelopes and
floating-point operation order. There is no reduced-quality rendering mode.

## Measure a change

From the repository root:

```sh
uv run python examples/benchmark_render.py --workload solo --repeats 3
uv run python examples/benchmark_render.py --workload polyphonic --repeats 3
uv run python examples/benchmark_render.py --workload first-light --repeats 3
uv run python examples/benchmark_render.py --workload full-song --repeats 3
```

The solo case contains four piano notes. The chamber case contains 56 overlapping
piano, violin, harp and marimba notes over eight seconds. First Light checks the
original electronic arrangement. The full-song case renders all 546 notes and
102.86 seconds of the original *Lanterns on the Water* arrangement at 44.1 kHz.
The benchmark writes JSON, not WAV files; use `--output output/benchmark.json`
to retain results.

Each repetition starts a fresh subprocess. CPU and wall time cover only
`render_audio`, including its validation, synthesis, effects and metrics.
Imports, score construction, hashing, process launch and JSON serialization are
outside that interval. Peak resident memory is the operating system's process
high-water mark, including imports; it is not the sum of allocations or an
isolated DSP memory measurement. Windows uses `PeakWorkingSetSize`; Linux and
macOS use `ru_maxrss` with their respective units. NumPy buffer memory is included.

For a comparison, put a reference `audio_as_code` package in an isolated
directory, then pass its parent with `--engine-root`:

```sh
uv run python examples/benchmark_render.py --workload polyphonic \
  --engine-root output/before --output output/before.json
uv run python examples/benchmark_render.py --workload polyphonic \
  --engine-root src --output output/after.json
```

Use the same Python, NumPy, score builder and machine, keep other render/test
processes idle, and alternate before/after run order. Compare medians and ranges,
not one favorable run. The JSON includes source path, runtime versions, sample
rate, note count and a SHA-256 of the float32 stereo output. `identical_audio`
checks repeated runs of one invocation; compare the hashes across invocations
as well to establish before/after equality. A different NumPy version or platform
may produce different hashes.

For profiling:

```sh
uv run python examples/benchmark_render.py --workload polyphonic \
  --profile output/render.prof
uv run python -c "import pstats; pstats.Stats('output/render.prof').sort_stats('cumtime').print_stats(25)"
```

Profile mode runs once. Its timings include profiling overhead and should not be
compared to ordinary benchmark timings.

## Implemented allocation and computation reductions

Piano modal tails reuse their complex output buffer for the pole product,
exponential, released amplitude and contact normalization. Applying the complex
residue reuses that buffer as well. Operand order is preserved: even exchanging
the operands of a complex multiply can change the last bits on some NumPy builds.
The exact-response regression covers empty and short notes, sub-sample hammer
contacts, contacts longer than the note, and a full-second decay.

Held voices calculate the common bloom envelope once per note. Harmonics twelve
and higher reuse the same capped pressure response. The original multiplication
order and harmonic summation order remain unchanged. Marimba no longer computes
the sine and exponential arrays used only by the bell branch.

These changes remove repeated calculations and temporary arrays; they do not
approximate the complex exponential, shorten tails, skip quiet partials or cache
seeded voices. Peak process memory may remain similar because complete stereo
tracks, the mix and its metrics can dominate it. Runtime gains depend on the
instrument and score: piano and bowed strings benefit more than the original
electronic First Light arrangement. Timing and numerical equality do not
establish perceptual realism; no listening claim follows from these benchmarks.
