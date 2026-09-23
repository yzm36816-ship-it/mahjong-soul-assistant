# Project instructions

- Keep all project changes inside this directory.
- Separate domain rules, window/filesystem adapters, vision, application state and UI.
- Never use game memory, network interception, hidden hands, or automatic input.
- The user-approved capture scope is the explicitly selected Mahjong Soul window.
- Store private screenshots/video frames/templates under ignored `data/`; never commit them.
- Display unknowns and stale states explicitly. Similarity and heuristic scores are not probabilities.
- Any change affecting tile safety must run domain and session regression tests.
- Manual confirmations belong to a single session and observed river. Do not retain them across reset/source switches.
- Keep known limitations and validation evidence in docs/; do not advertise benchmark accuracy from training screenshots.
- Do not make paid network calls without an agreed provider and budget.

