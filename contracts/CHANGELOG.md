# API contract changes

## 2026-10-01

- Added optional `mock_mode` to `HealthStatus` so the UI can display the backend's actual processing mode.
- Made `EvalCondition.faithfulness` nullable when an evaluation run does not measure generated-claim faithfulness.
