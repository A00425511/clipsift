# Backup demo recordings

Two screen recordings of ClipSift, kept here in case the live demo cannot be run. Neither has audio.

Both were recorded on 8 Nov 2026 from ClipSift v1.3.0, driving the real app in a browser. The footage is a short test clip cut from Coastal Action's T1-STAT2 411 video. Permission to show that footage publicly is still open.

## demo-backup.mp4 (65 s, 7.6 MB)

The one-count-point path, from the home page to the Report:

- open the video and go to Step 3, Count points
- pick the point at 2:10, play the count seconds at quarter speed, and try the Silhouette and Movement views
- mark 3 fish on that one point, remove one mark, then tick how the fish were seen
- save the point and open the Report

The Report in the recording is a draft. Only 1 of the 11 points was counted, so its numbers are not a result for the video.

## setup-fast.mp4 (21 s, 0.9 MB)

Adding a new video and letting ClipSift prepare it without anyone watching: choose the file, pick when the sediment has settled, enter a video ID and year, press Start, and the video opens when processing finishes. The real run took about 57 seconds. The recording is sped up 3x.

## Running the live demo

```
python -m app.server --runs <runs> --port 8791
```

Then open http://127.0.0.1:8791/ in a browser.
