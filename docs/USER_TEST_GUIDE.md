# Live application checks

Start the app using the root README with `MOCK_MODE=0`. Open http://localhost:8080 and check that `/v1/health` reports the requested Qwen models and a real corpus version.

1. Ask “Summarize section 3(p) of the Patents Act and its introductory section.” Inspect each surviving claim's status and citation. Open a source and verify the highlighted cited page. Verify the receipt. Also try “Can traditional knowledge be patented in India?”; the current live keyword index may refuse broad wording for low confidence. A refusal must not be presented as verified synthesis.
2. Exercise an unavailable local Ollama endpoint in an isolated test process and retry an answerable question. An unavailable-generation/extractive message must never show a verified synthesized answer. Restore the normal endpoint afterward.
3. Ask an unrelated weather question, then an in-scope question about a missing source. Their refusal reasons must distinguish domain from evidence coverage.
4. Connect the demo workspace key under Saved conversations. Ask a supported question and a follow-up. Reload, resume, and delete the conversation. Another authorized demo user sees the same workspace history.
5. Add a saved answer to the case file. Reload and export a dossier; it must contain the actual stored result and evidence. Unavailable/expired IDs remain explicitly missing.
6. Run the classification wizard for each category. Missing/unknown and conflicting inputs must ask for clarification, never guess.
7. Inspect official-source coverage. Missing documents must be labelled. Source checks stage changes; unapproved promotion must fail.
8. Scroll a long answer on desktop: sidebar position remains unchanged. At 360 px, navigation and evidence drawers fit the viewport.
9. Change “As of” to a historical date and confirm a new tool request uses that date. Reload or reopen: it must default to today's local date, including for browsers with the old saved preference. Other preferences such as theme remain saved. In default today mode, returning after midnight advances the date; historical research remains selected within the current session. Saved answers and corpus versions keep their original dates. The current query date does not certify that every official amendment has been reviewed.

10. Configure `SARVAM_API_KEY` in the root `.env` and recreate the backend with `docker compose up -d --force-recreate backend`. Press Listen on an actual answer. Read-aloud sends the displayed answer text to Sarvam Bulbul v3; verify a WAV response from `/v1/speech/tts` and audible playback. Stop during loading and playback, and test an answer longer than 2,500 characters to check sequential chunks and cleanup. Missing credentials, timeouts, invalid audio and provider failures must show clear errors without substituting a browser voice. The key must remain on the backend, outside Git and frontend bundles.

Speech recognition remains unavailable. Answer generation, translation and embeddings stay on local Ollama. Sarvam TTS is the user-requested speech exception; provider-backed audio must not be described as verified until a real keyed request succeeds.

See [the verification report](VERIFICATION_REPORT.md) for measured acceptance, corpus extraction findings and the unapproved staged Qwen index. Complete source repair, re-ingestion, quality review and named reviewer approval before promotion.
