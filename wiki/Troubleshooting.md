# Troubleshooting

This page lists common failure modes and the first checks that matter.

## Session opens but images are missing

Likely cause:

- the image folder moved
- the session was opened on another machine

Action:

- use the relink-images workflow and point the session to the correct image folder

## A session was shared with another computer

The most common issue is path mismatch.

Action:

- move the image folder and session together when possible
- relink images if the stored paths are no longer valid

## The built app does not launch

Check:

- whether the build is signed correctly for the platform
- whether bundled dependencies are complete
- whether the app is blocked by platform security checks

In this repo, build issues have previously included packaged dependency issues such as OpenCV bundle path problems.

## Packaging fails with cache or permission errors

Check:

- whether the build process is trying to write into a protected location
- whether cached build artifacts are stale
- whether the packaging environment is using the expected Python environment

## Temperature import looks wrong

Check:

- image order
- timestamps
- sample assignment
- reset threshold
- whether freeze results are stale and need rerunning

## A new cycle appears at the wrong time

Check:

- reset-after-warmed-to threshold
- hysteresis behavior
- whether the temperature timeseries really crossed the threshold in the expected way

## Result tables look stale

Check whether you changed any analysis inputs after the last run:

- cell geometry
- keyframes
- crop
- image adjustments
- analysis settings

If so, rerun analysis.

## Cells drift off droplets during the run

Use keyframes.

If drift is global or stage-related, keyframes are the correct abstraction.
Do not try to manually patch every frame unless the sequence is extremely short.

## Freeze finding misses events or calls too many

Check:

- detection polarity
- width
- prominence
- convolution settings
- whether the image cadence is high enough for the event timing you expect

## The packaged app is large

That is usually a packaging/dependency question, not an analysis question.

Common contributors are:

- Qt libraries
- OpenCV
- packaged Python runtime dependencies
