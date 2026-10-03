# Piano and bowed-string refinement

This refinement changes the generated `piano`, `violin`, `viola`, `cello`, and
`double_bass` voices. Existing instrument IDs, score schema, tone controls, and
control ranges stay the same. The eleven original electronic/physical voices
remain unchanged. These are still designed models, not reproductions of a
particular instrument or claims of perceptual realism.

## Piano: shared unison losses

Previously, the two- and three-string registers summed independently detuned
strings. Each had the same prescribed mixture of fast and slow decay. That can
produce beating, but does not represent energy exchange between strings through
their shared bridge. Coupled-string models distinguish rapidly radiating common
motion from weakly radiating differential motion; slight mistuning connects
them. See Julius O. Smith's [coupled strings discussion](https://www.dsprelated.com/freebooks/pasp/Coupled_Strings.html)
and [bridge coupling eigenanalysis](https://www.dsprelated.com/freebooks/pasp/Two_Coupled_Strings.html).

The new model represents each partial's unison amplitudes by a small complex
linear system. Its diagonal contains the individual angular frequencies and
intrinsic loss; a shared rank-one damping term represents a resistive bridge.
The intrinsic loss is 28% of the designed damping and the common bridge loss
72%. These are design coefficients, not measurements of a piano. The Hermitian
part is negative definite, so free string energy cannot grow. Eigenmodes are
evaluated analytically; the same finite raised-cosine hammer pulse excites the
coupled system, starting from rest. Complex modal residues retain both response
quadratures instead of treating the strings as independent oscillators.

Unison spread is deliberately narrow: ±0.6 cents for two strings and
−0.9/0/+0.9 cents for three. It produces differential decay while keeping the
measured fundamental centered; upper partials naturally have wider separation in
hertz. Partial stiffness, hammer contact/position filtering, brightness and
velocity response, generated contact noise, and the existing driven soundboard
filter remain. Below 65 Hz the existing single-string two-component decay is
preserved. The `decay_seconds` control still sets a nominal decay scale, not an
exact silence time or a measured whole-instrument T60.

This is a narrow-band approximation with resistive coupling, not a full nonlinear
hammer/string/bridge/soundboard solver. It omits reactive bridge tuning, sympathetic
cross-note resonance, physical pedal mechanics, longitudinal waves, and explicit coupling
between the two vibration planes. Those are distinct phenomena in more complete
[piano models](https://dsprelated.com/freebooks/pasp/Piano_Synthesis.html).

The renderer separately supports [binary piano sustain gates](piano-sustain.md).
They control note damping without adding sympathetic resonance to this model.

## Bowed strings: excitation bandwidth and body phase

The existing bowed voices already had a long harmonic series, evolving pressure,
delayed vibrato, pitch-synchronous friction noise, and hand-designed body bands.
Their brightness rolloff was attached to harmonic number, which suppressed the
upper body bands disproportionately in lower registers. Their body-band gains
also had no phase response.

The new rolloff uses absolute frequency with a designed corner bandwidth of
`900 + 6500 * brightness²` Hz, where brightness already includes the existing
velocity contribution. It represents a rounded bridge-force waveform while
retaining each instrument's partial weights, body bands, onset, and noise.
Helmholtz bridge motion has a sawtooth-like force waveform; corner rounding and
bow force affect its upper spectrum. This motivates the model but does not make
it a nonlinear stick/slip solver. See Jim Woodhouse's
[bowed-string overview](https://euphonics.org/11-3-0-summary-of-bowed-string-behaviour/)
and Woodhouse/Galluzzo's [bowed-string physics review](https://euphonics.org/wp-content/uploads/2022/03/BowedStringReview.pdf).

Body bands now use the complex response of damped bandpass resonances, each
specified by center, half-power bandwidth, and peak gain. Both magnitude and
phase color each harmonic. This is a steady-state response evaluated at each
nominal partial, with the existing played onset; it does not integrate a coupled
body transient or use measured admittance. It also does not simulate bow position,
force-dependent friction, wolf notes, articulation changes, or ensembles.

Wind and brass models were left unchanged in this refinement: the probes did not
establish a specific defect warranting another shared held-voice change.

## Validation and listening comparison

Run the focused checks from the checkout root:

```console
uv run pytest tests/test_instrument_refinement.py tests/test_finite_strikes.py tests/test_acoustics.py tests/test_orchestra.py
```

The checks include an independent time-domain integration of three coupled piano
strings, passive modal damping, pole-frequency bounds, FFT fundamental estimates
across registers, brightness/velocity behavior, fixed-seed/default-tone equivalence,
one-sample notes, eight-second holds, and the existing tuning/control/extreme-pitch
regressions. No numerical result establishes realism or listener preference.

Development comparison artifacts live under ignored
`output/instrument-round/existing/`. `before/` and `after/` contain identically
scored register clips for all five voices and a piano velocity/chord comparison.
Use the same playback gain when comparing them; no peak normalization was applied.
The development `probe.py` reproduces clips and spectral/RMS measurements, and
`benchmark.py` compares the saved prior implementation with the new per-note cost.
Those generated assets and the saved source snapshot are local review artifacts,
not package resources. The project example `uv run python examples/first_light.py`
remains available as the standard synthesis smoke render.

The implementation was assessed numerically and through exported comparison
files. No perceptual audition was performed during this refinement. A listener
should judge attack, decay, register balance, and fatigue before describing the
result as a more realistic instrument.
