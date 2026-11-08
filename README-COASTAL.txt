ClipSift - Coastal Action handoff
==================================

What this is
------------
ClipSift is a local tool for counting fish and invertebrates in
stationary, unbaited GoPro video, using Coastal Action's MeanCount
protocol. Everything runs on your own computer - no footage or
results are sent anywhere. After the one-time setup, it works
fully offline.

What you need
-------------
- Windows 10 or 11
- Internet once, for the setup (about 500 MB of downloads)
- About 500 MB of free disk space

How to use it (3 steps)
------------------------
1. Double-click 1-Setup.bat
   Checks Python and ffmpeg, then installs everything ClipSift
   needs. Run this once. If it asks you to install Python, get
   Python 3.11 or newer from python.org and tick "Add Python to
   PATH" during install, then run 1-Setup.bat again.

2. Drag a video file onto 2-Process-Video.bat
   The app watches the video and suggests a fish count at each
   sampling point (every 60 seconds, using the MeanCount protocol).
   A 35-minute video takes about 10 minutes to process.

3. Double-click 3-Open-ClipSift.bat
   Opens the review app in your browser. This is where a human
   counts each point and checks the model's suggestions.

How counting works
------------------
Count first, then look at the model. The review app is designed
so the counter counts each point blind, then the model's
suggestion is revealed to compare against. The model is a second
opinion, not the answer.

What MeanCount means
--------------------
MeanCount is the average number of fish seen per sampled point.
It is a relative index for comparing videos and conditions - not
a census of how many fish are in the video. A mean of 23 means
that on a typical look, about 23 fish are visible.

Honest limits - please read
---------------------------
- The detector was trained on Brackish, a dataset of cold,
  turbid Danish water - not Nova Scotia water. Its measured
  numbers (about 68% recall, about 71% precision) are on Danish
  test photos, not your footage.
- The sensitivity has not been fine-tuned for your water, and
  the model undercounts by design rather than overcounting.
- Retraining on your own labelled footage is the unlock: label
  frames using the guide in docs/LABELLING_PROTOCOL.md, and the
  model can be retrained for Nova Scotia conditions.

Troubleshooting
---------------
- "Python not found": install Python 3.11+ from python.org with
  "Add Python to PATH" ticked, then run 1-Setup.bat again.
- "ffmpeg not found": 1-Setup.bat installs it with winget; if it
  still fails, install FFmpeg from https://ffmpeg.org and make
  sure it is on your PATH.
- "Missing models\clipsift-yolov8n.onnx": the model file is not
  in this folder. It ships with this package - re-extract the zip
  or ask the team for the file.
- The review app won't open: make sure 3-Open-ClipSift.bat is
  running, then go to http://127.0.0.1:8765 in your browser.

What is in this folder
----------------------
1-Setup.bat, 2-Process-Video.bat, 3-Open-ClipSift.bat - the three
steps above.
config/yolo.yaml - the settings the app runs with (YOLO detector,
tiled detection, fish + small_fish).
models/clipsift-yolov8n.onnx - the trained detector.
app/, clipsift/, config/, docs/, species/, tests/, tools/ - the
application code and documentation.

Licence
-------
The app code is under the MIT licence in the LICENSE file. The
team is confirming the licence for the model component before
wider use.
