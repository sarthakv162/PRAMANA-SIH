# API contract changes

## 2026-10-01

- Added optional `mock_mode` to `HealthStatus` so the UI can display the backend's actual processing mode.
- Made `EvalCondition.faithfulness` nullable when an evaluation run does not measure generated-claim faithfulness.

## 2026-10-02

- Added an optional `language` multipart field to `/v1/speech/asr`; the response reports Sarvam's detected language.
- `/v1/speech/tts` now returns WAV audio (`audio/wav`) from Sarvam and limits text to 2,500 characters.

## 2026-10-04

- ABS results expose `assessment_status` and nullable `required` / `exempt` flags for unassessed applicability. Classification requires the defining clause. Patent indicators expose draft assessment status. Classification and ABS dates validate as dates; ABS requires an activity.

- Added authorized shared conversations, saved request results and case-file references. `QueryRequest` accepts an optional conversation UUID. Saved content expires after 30 days.
- Added `generation_unavailable` refusals with real source excerpts; unavailable local generation cannot return verified synthesis.
- Added grouped fields to classification questions, preserving the existing result contract.
- Added corpus coverage and real local model readiness / embedding-compatibility health fields. PDF downloads accept a pinned corpus version.
- Removed remote speech providers. ASR and TTS endpoints report local generation-unavailable errors until a local audio engine is configured.

### Sarvam TTS restoration

- Restored `/v1/speech/tts` using Sarvam Bulbul v3, server-side credentials and the current REST `language_code` field. The response is validated PCM WAV (`audio/wav`); blank/over-limit input and invalid audio are rejected.
- Read-aloud calls the backend, chunks long answers and supports stop/cancel cleanup. Provider failures are explicit, without browser speech substitution.
- ASR stays unavailable; generation, translation and embeddings stay local.
