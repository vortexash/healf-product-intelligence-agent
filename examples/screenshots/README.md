# Screenshots

Capture these from a running instance (`docker compose up`, then open http://localhost:3000):

1. `01-empty-state.png` — the intro/empty state with example URL and suggested prompts.
2. `02-product-card.png` — first answer with the rich product card (LMNT Recharge).
3. `03-ingredient-answer.png` — "Does it contain Vitamin D?" → not-listed wording + ingredient card.
4. `04-evaluation.png` — "What can I improve?" → scorecard + recommendations.
5. `05-evidence-drawer.png` — the evidence drawer open, showing source/field/excerpt/confidence.
6. `06-content-draft.png` — a rewrite draft card with claims-preserved / claims-not-introduced.

Suggested command (macOS): use the browser's built-in screenshot, or run the app and use
your OS capture tool. Keep images ~1400px wide.

The real, unedited text of these responses is in [`../example_outputs.md`](../example_outputs.md),
captured live from the backend — so a reviewer can verify outputs without running the app.
