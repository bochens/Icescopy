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
