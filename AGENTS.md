# Project direction

- Build instrument sounds from code: procedural synthesis and physical/modal models. Do not introduce recorded samples, SoundFonts, sample-library backends, or measured impulse responses as instrument sources.
- Use the musical families and shared engine groups in `docs/instrument-foundation.md` as the foundation. Keep discovery metadata in `src/audio_as_code/instruments.py`.
- Keep planned instruments separate from playable voices. Never substitute a generic synth while reporting an unimplemented instrument as supported.
- Preserve existing score IDs and deterministic seeded rendering. Make the actual synthesis limits clear in documentation and examples.
- For instrument changes, validate tuning, stability, control behavior, and output audio as appropriate. Numerical checks do not establish perceptual realism.
- Follow `CONTRIBUTING.md` for the repository's checks and schema updates.
