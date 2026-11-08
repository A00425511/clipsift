# ClipSift â€” Experimental Fine-tuned Fish Detector (GitHub-ready add-on)

**Standalone, non-disruptive component.** Keeps existing ClipSift V6 and Jacob's main app untouched.

This package supports an RF-DETR Small fine-tuned checkpoint from a DIGI4ECO pilot. Checkpoints are **NOT** included (large files). See the [Model card](docs/MODEL_CARD.md) for model lineage and limitations, and the [Experimental results](docs/EXPERIMENT_RESULTS.md) for verified evaluation and Windows integration results.

## 1. Obtain trained weights

Authorized team members should obtain `checkpoint_best_total.pth` (~121.6 MB) from the approved shared training location. The checkpoint is excluded from GitHub. The original Windows test used:

`F:\SMU\ClipSift_Training\models\digi4eco_best.pth`

Do not remove the original `F:\SMU\ClipSift\community-fish-detector\models\cfd-small.pth`.

## 2. Locate the add-on package

For a GitHub checkout, the package is in `experiments/digi4eco-finetuned/`. The PowerShell examples below use the original Windows test paths. Update `$pkg`, `$py`, and the model/video paths for your computer.

## 3. Preflight in PowerShell (no model inference)

```powershell
$py = 'F:\SMU\ClipSift_GitHub\.venv\Scripts\python.exe'
$pkg = 'F:\SMU\ClipSift_Training\ClipSift_Finetuned_Experimental'
& $py "$pkg\scripts\preflight.py" --checkpoint 'F:\SMU\ClipSift_Training\models\digi4eco_best.pth' --baseline 'F:\SMU\ClipSift\community-fish-detector\models\cfd-small.pth' --image 'F:\SMU\ClipSift_Training\coastal_test\T1_1320s.jpg'
```

Original V6 was pinned to `rfdetr==1.11.2`; fine-tuned in Colab with `rfdetr==1.12.0`. If model load fails, DO NOT upgrade the working V6 environment. Instead make an isolated venv with Python >=3.10:

```powershell
py -m venv F:\SMU\ClipSift_Training\.venv
& 'F:\SMU\ClipSift_Training\.venv\Scripts\python.exe' -m pip install --upgrade pip
& 'F:\SMU\ClipSift_Training\.venv\Scripts\python.exe' -m pip install -r 'F:\SMU\ClipSift_Training\ClipSift_Finetuned_Experimental\requirements.txt'
```

CPU inference may take time. An MX130 with 2 GB VRAM is not a suitable RF-DETR GPU; use `--device cpu`.

## 4. First inference â€” compare one whole frame

```powershell
$py = 'F:\SMU\ClipSift_GitHub\.venv\Scripts\python.exe'
$pkg = 'F:\SMU\ClipSift_Training\ClipSift_Finetuned_Experimental'
& $py "$pkg\scripts\compare_image.py" --image 'F:\SMU\ClipSift_Training\coastal_test\T1_1320s.jpg' --baseline 'F:\SMU\ClipSift\community-fish-detector\models\cfd-small.pth' --checkpoint 'F:\SMU\ClipSift_Training\models\digi4eco_best.pth' --device cpu --mode whole --output 'F:\SMU\ClipSift_Training\local_test\whole'
```

Outputs: `comparison_whole.jpg` (side by side), individual overlays, CSV candidate bounding boxes, JSON summary. These outputs are NOT verified fish counts.

## 5. Optional tiled inference (slower CPU)

Run the same command with `--mode tiled --tile-size 1024 --overlap 256 --output 'F:\SMU\ClipSift_Training\local_test\tiled'`. Tiling increases candidate visibility but may also increase false positives, as seen in prior tests.

## 6. Check compatibility with original V6 without changes

```powershell
& $py "$pkg\scripts\check_v6_compatibility.py" --v6-source 'F:\SMU\ClipSift_Release_Test\ClipSift_Source' --checkpoint 'F:\SMU\ClipSift_Training\models\digi4eco_best.pth' --image 'F:\SMU\ClipSift_Training\coastal_test\T1_1320s.jpg'
```

If this passes, original V6 can use the alternative checkpoint via `CLIPSIFT_MODEL_PATH` in a **new terminal**. Do not overwrite the running V6 instance:

```powershell
cd F:\SMU\ClipSift_Release_Test\ClipSift_Source
$env:CLIPSIFT_MODEL_PATH = 'F:\SMU\ClipSift_Training\models\digi4eco_best.pth'
& 'F:\SMU\ClipSift_GitHub\.venv\Scripts\python.exe' -m uvicorn app.local_api:app --host 127.0.0.1 --port 8767
```

`http://127.0.0.1:8767/videos` uses the experimental checkpoint for any **new** analysis process. Results from prior runs do not automatically change. If local RF-DETR 1.11.2 cannot load this checkpoint, use the standalone package inside an isolated 1.12.0 environment rather than modifying V6.

## 7. GitHub handoff

- Add folder `experiments/digi4eco-finetuned/` as its own commit/PR after review.
- Commit **code and documentation only**, not weights, video or test data (see `.gitignore`).
- Link licensed dataset, include training methodology and limitations; don't claim scientifically validated counting.
- Do not replace Jacob's / Adrien's model or merge into root automatically.

## Reproducing unit tests

```powershell
& $py -m unittest discover -s "$pkg\tests" -v
```
