# Example-guided cell detection experiment

This is a separate research prototype. Icescopy does not import it or package its dependencies. It selects cells on one current frame, supplied as an image file or a decoded video array, and requires at least one marked example. Freezing detection remains a separate downstream brightness-convolution calculation. No other image, tracking, or automatic keyframe enters cell selection. The prototype writes a new directory and never edits an application session.

The experiment compares image matching, a fixed MobileNetV3-Small image model, and a small trained classifier that combines neural similarity with image-matching measurements. The pretrained model recognizes general visual patterns; it was not originally trained to distinguish filled and empty experimental wells. Scores are rankings, not calibrated occupancy probabilities.

## Run locally

Create a separate Python 3.11 environment. Install `numpy scipy pillow opencv-python-headless torch torchvision` in that environment, not in the application environment. Set `TORCH_HOME` to a private model-cache directory. The first neural-network run downloads the official TorchVision MobileNetV3-Small weights; subsequent runs use the local copy.

Save example circles in JSON, using original-image pixels:

```json
{
  "examples": [{"x": 200, "y": 150, "radius": 10}],
  "existing": [{"x": 260, "y": 150, "radius": 10}]
}
```

All existing circles are protected, including those not selected as examples. The radius describes the intended brightness-measurement circle, not necessarily the outer edge of a well.

```sh
python experiments/cell_detection/run_detection.py picture.png examples.json \
  --method template --threshold 0.75 --output output/new-detection-run
```

For the neural methods, use `--method embedding` or `--method learned --model path/to/pair-model.json`. Use the threshold recorded by the benchmark for that method. The example threshold above is not a validated default for every setup.

The output directory must not exist. Results include `suggestions.json`, `state.json`, and a colored overlay. Green circles are input examples, gray circles are other known cells, and yellow circles are newly selected cells. The saved state automatically includes all input and new cells with stable nonnegative integer IDs. There is no mandatory review step. Explicit manual additions and deletions are supported; the review page is an optional developer diagnostic.

Pass the preceding `state.json` with `--state-in` on the next run. The example
JSON can then select saved cells with `{"example_ids": [0, 2]}` instead of
repeating their coordinates. All earlier cells remain protected, including
ones not chosen as examples. `remove_ids` explicitly deletes user-rejected
circles, and their IDs are never reused.

`single_frame.detect_current_frame(raw, example_ids=[0], state=state)` is the
equivalent pure Python interface for one decoded video frame. `raw` can be
uint8/uint16 grayscale or RGB; BGR arrays require `color_order='BGR'`. Both file
and array paths use `preprocess_image`. Coordinates and radii are original
frame pixels, independent of display zoom. Input state is never modified.

For a moving frame, the caller can supply `current_positions`, a complete list
of `{"id": 0, "circle": {"x": 200, "y": 150, "radius": 10}}` records for all
retained IDs. Later application integration should resolve those positions
using its existing keyframes. The prototype does not estimate movement.
Without updates it assumes saved positions are valid for the current frame.
Offscreen known cells retain their IDs, but examples must be visible. A changed
frame size requires explicit complete position updates; it never rescales
coordinates silently. Bad or incompatible state fails before a new output is
created, and the input state file remains unchanged.

## Separate fast tree experiment

`fast_model.py` adds a selectable alternative without changing the original
models. It measures 32-pixel patches directly and uses a small tree classifier:
100 successive decision trees, each with at most 15 final outcomes. The trees
learn combinations of image measurements instead of evaluating a neural
network on every candidate crop. CPU calculations are limited to four threads.
It does not import Torch. Install `scikit-learn==1.9.1 threadpoolctl joblib` only
in the separate experiment environment if running this alternative.

The measurements retain signed brightness matching, quarter-turn-tolerant
matching, radial brightness and texture, and the difference between each
candidate and example. Absolute radial profiles keep the central surface and
surrounding well distinguishable; brightness polarity is preserved. A similar
circular holder by itself is insufficient evidence of a filled well.

```sh
python experiments/cell_detection/fast_benchmark.py \
  --real-labels path/to/private-real-labels.json \
  --structured-labels path/to/structured-scenes-v3/labels.json \
  --output output/new-fast-tree-experiment
python experiments/cell_detection/run_detection.py picture.png examples.json \
  --method fast --model output/new-fast-tree-experiment/fast-model.joblib \
  --output output/new-fast-detection
```

The fast CLI uses the model's recorded threshold unless `--threshold` is
explicitly supplied. `--state-in` and manual state edits work identically for
all methods. The joblib file is a locally generated Python model; use only a
trusted experiment's model file and its recorded scikit-learn version.

The one fixed experiment fits only real recording A and independent rendered
training groups. Separate rendered groups choose a threshold targeting 99%
aggregate precision (the fraction of proposed additions that match references),
then the model and threshold are frozen before evaluation. Each holder family
also has its own calibration counts. Clear, glare and blur images with the
same family and seed remain in the same group. The existing structured test
seeds and their variants are excluded from training and calibration. Real
recordings already inspected during development remain exploratory tests.
Simulations approximate appearance and cannot establish real liquid occupancy.

Results include a model bundle, readable feature/training metadata, input
hashes, and `evaluation/report.json`. `single_frame_timings` measure current
frame normalization, proposals, candidate patches, one or two example patches,
classification and duplicate exclusion. File and model loading are excluded.
Cached benchmark preparation also measures every reference patch and is
reported separately. Use the original baseline report alongside this report
to assess speed and accuracy; a faster alternative is not automatically a
better cell selector.

One controlled follow-up uses `--feature-mode relative --reuse path/to/fast-tree-v1`.
It retains the five matching correlations and 38 candidate/example differences,
and removes the separate absolute candidate and example profiles. This tests
whether the first tree relied on holder appearance instead of example matching.
It uses exactly the first run's cached proposals, patches, labels, grouping,
sampling and tree settings. Both label manifests must have unchanged content.
The first model bundle remains usable; the new bundle records its feature mode.
Reused preparation time is recorded as zero because features are not recalculated;
actual current-frame calls are still measured separately.

```sh
python experiments/cell_detection/fast_benchmark.py \
  --real-labels path/to/private-real-labels.json \
  --structured-labels path/to/structured-scenes-v3/labels.json \
  --feature-mode relative --reuse output/first-fast-tree-experiment \
  --output output/new-relative-tree-experiment
```

The first fixed tree run (`fast-tree-v1`) measured roughly 0.58–1.16 seconds
per current-frame call on this Mac. It improved the rendered PCR clear case
from a mean 43.4 of 68 remaining targets with 20.8 extra circles to 68 of 68
with zero extras across five two-example choices. Real transfer was worse:
recording B frame 50 found a mean 15.6 of 48 remaining targets with 9.8 extras,
versus the original learned model's 39.8 with 0.4 extras. For TAMU-A frame 0,
the original examples 0 and 8 recovered the missed target at (424, 230), but
also added 13 false circles. These exploratory results support keeping the
tree as an alternative, not replacing the original learned model. Synthetic
calibration precision was 99.12% overall but only 96.33% for small pockets;
the aggregate number does not describe every holder or any real recording.

The relative-feature comparison (`fast-relative-v1`) reduced the TAMU-A frame
0 mean extra circles from 13.6 to 0.6 with two examples, but it missed the target
at (424, 230) again with examples 0 and 8. It improved recording B frame 50
to 35.2 of 48 remaining targets with 2.6 extras, still below the original
learned model's 39.8 with 0.4 extras. Two-example IS reference recovery fell
from 181.6 to 170.0 in frame 0 and from 180.8 to 164.4 in frame 295; unmatched
IS circles remain unclassified because those annotations are incomplete.
Both tree variants take roughly 0.6–1.2 seconds per current-frame call on this
Mac. These differences include separately calibrated thresholds and do not
prove that absolute candidate appearance alone caused the regression. Neither
tree variant is a reliable replacement for the original learned model.

## Evaluate

`benchmark.py` reads a local label manifest, extracts proposals and fixed model features, trains the small comparison classifier only on scenes marked `development`, and chooses thresholds on those development scenes. Other recordings are evaluated afterward with the model and thresholds fixed. It tries ten choices of one example and five pairs, where enough reference cells exist. The first reference example fixes the measurement radius for each picture in this pilot.

Each manifest scene contains `id`, `recording`, `source`, `sha256`, `width`, `height`, `split`, `targets`, `complete_labels`, and `label_status`. Each target has `x`, `y`, `radius`, and optionally `id`. Use `development` only for training scenes; other split descriptions are for evaluation. Optional `negatives` circles identify explicitly reviewed empty holes or other non-target objects. They allow known errors to be counted even when the positive annotations are incomplete. Never infer empty holes from missing saved circles.

```sh
python experiments/cell_detection/benchmark.py \
  --labels path/to/private-labels.json --output output/new-benchmark
python experiments/cell_detection/make_review.py output/new-benchmark/report.json
python -m unittest discover -s experiments/cell_detection -p 'test_*.py' -v
```

Open the resulting `review.html` locally to compare methods and example choices. Images, labels, features, model outputs, and reports belong in ignored `output/` directories. Do not commit private recordings or saved sessions.

To evaluate another recording without fitting or choosing new thresholds, add
`--reference-report output/previous-benchmark/report.json` to the benchmark
command. Use the same detector revision that produced that reference report.
The report records a hash of the reference report used.

`stress_images.py --output output/new-artificial-pictures` creates controlled
diagnostic scenes containing filled spots, empty rings, and smaller dark holes.
Variants add blur, uneven lighting, color, and dark interiors. Evaluate the
generated `labels.json` with `--reference-report`; these variants are not used
for training by default. They share one layout and must stay together in any
training/evaluation split. They cannot validate real filled-versus-empty accuracy.

`structured_scenes.py` generates PCR tube trays, rectangular grids, perforated
holders, and broad pockets containing small droplets. Filled and empty positions
are explicitly labeled before rendering. Clear, glare and blurred views test
occupancy errors, including completely empty tray rows; they use approximate
optics and do not validate real liquid occupancy.

```sh
python experiments/cell_detection/structured_scenes.py \
  --output output/new-structured-scenes
```

## Interpretation and limits

- Supplied examples are excluded from detection scores. Matching is one-to-one within one measurement radius; position errors are also reported.
- Complete reference annotations are required to label unmatched proposals as errors. With partial annotations, unmatched proposals remain unknown and precision is not reported.
- A saved session supplies marked locations, not proof that every unmarked object is empty. The prototype does not offer session-based training or customization.
- A candidate-location stage can miss cells before classification. Candidate coverage is reported separately from final detection accuracy.
- The location search combines brightness changes, circular edges, and agreement of edge directions around a rim. The comparison model examines a small area around each location. A circle-shaped object is not necessarily a filled well.
- Separate recordings and physical arrays must stay in separate training/evaluation groups. Adjacent frames and augmented versions are not independent recordings.
- The first pilot has limited training variety. Development performance is not evidence of generalization to unfamiliar stages, empty wells, or severe blur.
- Once a recording has been inspected to refine the method, call subsequent results exploratory. Keep a separate untouched recording for a later confirmation test.
- Duplicate exclusion protects circles by center and scale. Closely spaced cells and poorly centered suggestions need additional real-image validation.
- The review page displays recorded example choices, not an annotation editor. Full-size display means the saved preview size. Use `run_detection.py` for arbitrary manually supplied example circles. Its timing excludes model loading; benchmark preparation also computes features for all reference circles.
- Image preprocessing preserves 16-bit contrast; source files are read only. Synthetic or altered pictures must never replace the original data.
- Cross-image tracking, automatic keyframes, application integration, and personalized training are out of scope.
