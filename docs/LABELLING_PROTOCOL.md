# ClipSift labelling protocol

One page for teammates using the label page (`/label.html`). Two people label every frame on their own. Your marks teach the detector and also show how well two people agree.

## How to work through a frame

1. Look at the frame.
2. Play the clip (Space). Use 0.25x if it helps.
3. Switch to Movement view (M).
4. Then finish marking.

Mark what is in this frame, not what appears somewhere else in the clip. Movement counts as evidence: an animal that is hard to see in the still but moves in the clip is a confident mark. Mark every animal you are confident about. You are confident when you can see at least two of: shape, anatomy, colour or a flash, movement.

## The five mark types

| Mark | Key | Use it for | Example |
| --- | --- | --- | --- |
| Fish | F | An animal you are confident is a fish | A clear cod, or a fish in a school that you can follow in the clip |
| Invertebrate | I | A crab, urchin, sea star or similar you are confident about | A crab on the seabed that only shows itself when it moves |
| Unsure | U | Might be an animal but does not meet the rule | A faint shape at the edge of a school that you cannot follow in the clip |
| Not fish | X | Something that truly looks like a fish but is not. At most 3 per frame | A drifting scrap of white tape that looks like a fish in the still |
| No animals | N | The frame has no animals. Use it only after checking the clip and Movement view | Empty seabed, nothing moves in the clip or the Movement view |

Unsure shows as a dashed ring with a question mark, so it is clear in any colour. Right-click a dot to change it to or from Unsure.

Not fish is for real look-alikes only. Skip the pipe and ordinary seabed: static pipe and seabed are handled in software, so marking them adds noise.

## Calibration

Before normal frames, every labeller gets the same set of calibration frames, in the same order. They are marked "Calibration frame 2 of 5" on screen. Everyone labels all of them, whatever the usual two-label limit says. They are there to compare how each of us marks, so we can agree on the rules and fix any drift. Nobody sees anyone else's marks while labelling. After the calibration frames, normal frames follow.

## What Unsure means for training

An Unsure mark is neither an animal nor background. When a detector is trained, the area around an Unsure mark is ignored: it is not a positive example and not a negative one. The exports mark these as ignore regions. We also check how often one person's Unsure matches another person's fish, which tells us whether the rule is being read the same way.

## Why missed fish matter

Anything you do not mark is treated as background. If a real fish is left unmarked, the detector is told "this is not a fish" and learns the wrong lesson, which makes it miss fish like that one. When in doubt between leaving it out and marking Unsure, mark Unsure.

## Worked example: crabs in T1 STAT 2

At 1:00 and at 24:20 in T1 STAT 2, there are crabs that look ambiguous in a single still. Playing the clip and checking Movement view showed them moving, which confirmed them. One of the two was found by using the contrast control. Both are confident marks, even though neither is easy to see in the still. A detector trained on single frames may miss animals that are identified only by movement, so these examples are worth knowing about when we read the results.

## Counting rule

Coastal Action's counting rule stays conservative. Only Fish and Invertebrate marks count towards a total. Unsure marks do not count, and neither do Not fish marks.

## Ground rules

- Use your own name only.
- Do not discuss a frame until both people have saved it.
- Frames labelled in the same "school block" are close together in time and are alike, so they stay together on one side of any train and test split.
