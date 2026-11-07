# GitHub Integration Checklist (Do Not Push Yet)

## Current verified situation
- Four local pages and clickable help were confirmed working on Windows after moving old backups out of `app/`.
- `app/` active files are `demo.html`, `gallery_routes.py`, `local_api.py`, `results.html`, `results_routes.py`, `subsamples.html`, `subsample_routes.py`, `videos.html`, and `__init__.py`.
- Active API/gallery code refers to `scripts/build_review_queue_v2.py`.
- The local worktree `<local ClipSift project folder>` has no `.git`; the team's repository `A00425511/clipsift` returned `Repository not found` before collaborator access was granted.
- Model path portability passed a single detector-frame inference test on the developer's machine (75 NMS proposals, output image saved); this is not yet a clean-machine test.

## Before transferring anything
- [ ] Obtain collaborator access and accept GitHub invitation.
- [ ] Clone the team's existing repository in a **different** directory.
- [ ] Compare branch, folder layout, framework and UI with working ClipSift version.
- [ ] Check `requirements.txt` against installed environment; pin compatible versions.
- [ ] Verify model path comes from environment or configurable relative location; remove literal personal Windows defaults from active app.
- [ ] Scan `app`, `src`, `scripts`, `tests`, `config`, `.env.example`, docs for secrets, personal addresses, absolute paths and confidential footage metadata.
- [ ] Ensure `.gitignore` excludes `*.pth`, `*.pt`, `*.onnx`, `.venv/`, videos, `outputs/`, secrets, local overrides, and backups.
- [ ] Confirm redistribution rights for any sample video, screenshot, weights or dataset. Do not upload restricted materials.
- [ ] Keep only required active install/run scripts; archive old `install_*` scripts privately.
- [ ] Re-test all four pages, review decision saving, evidence building, JSON/CSV export and analysis on approved data.
- [ ] Document that GitHub Pages cannot independently run a local Python/FastAPI backend.

## After access is granted

```powershell
# In a parent folder separate from the working prototype
cd F:\SMU
git clone https://github.com/A00425511/clipsift.git ClipSift_Team_Integration
cd ClipSift_Team_Integration
git checkout -b feature/local-ai-review-integration
```

**STOP and compare team repo before copying files.** Do not paste the complete prototype over teammates' files or force-push. Copy selectively after resolving conflicts, run tests, inspect `git status` and `git diff --cached`, then open a Pull Request for team review. Never add all files blindly if private assets may be present.

## Recommended team-facing artifacts
`README.md`, `docs/TEAM_WALKTHROUGH.md`, `docs/GITHUB_INTEGRATION_CHECKLIST.md`, existing architecture/validation guides, setup and environment-variable instructions, a clearly licensed small demo fixture (if available), test instructions, and explicit limitations.

## Local staging warning
This documentation ZIP is **not** the full application repository. The user's working Windows tree contains the source and runtime state. A code transfer requires inspecting that tree and the team repo, plus testing a new branch.
