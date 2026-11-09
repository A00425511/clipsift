# Integrating the separate V6 review prototype

This addition is deliberately **non-invasive**: place `experiments/v6-human-review/` into the team repository. There are no overwritten files in the existing `clipsift2-main` snapshot.

Use `experiments/v6-human-review/README_TEAM_INTEGRATION.md` for setup and local run instructions.

## Why not merge Flask and FastAPI right before the hackathon?

The team app and V6 use different JSON formats, analysis pipelines, review state, and deployment. Keeping the tested V6 prototype in a self-contained folder preserves both implementations for judge code review. The demo on Cloudflare Pages is **not** executing V6 inference.

## Before public publication

1. Review source and materials for permission and sensitive information.
2. Exclude checkpoint weights, videos, generated evidence/outputs, local environments, secrets and private review decisions.
3. Confirm licensing of model implementation and dependencies.
4. Test the team's application and V6 independently after branch insertion.
5. If V6 is demonstrated Monday, run it locally on your laptop and preload an authorized sample; do not promise internet inference.

## GitHub workflow

- Create a feature branch from team `main` (for example `feature/v6-human-review`).
- Copy the **two top-level paths from this add-on archive**: `experiments/v6-human-review/` and `docs/V6_INTEGRATION.md`.
- Review staged changes; they should only be *new files* under these two paths.
- Commit and open a Pull Request for Jacob to review.
- Do not replace or modify the team's root README, root requirements, Flask app, or Cloudflare deployment.
