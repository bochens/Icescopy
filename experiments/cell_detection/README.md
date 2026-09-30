# Example-guided cell detection experiment

This is a separate research prototype. Icescopy does not import it or package its dependencies. It operates on one original picture and requires at least one marked example. It writes proposed circles to a new directory; it never edits a session or adds cells to the application.

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

The output directory must not exist. Results include `suggestions.json` and a colored overlay. Green circles are input examples, gray circles are other existing cells, and yellow circles are suggestions.

## Evaluate

`benchmark.py` reads a local label manifest, extracts proposals and fixed model features, trains the small comparison classifier only on scenes marked `development`, and chooses thresholds on those development scenes. Other recordings are evaluated afterward with the model and thresholds fixed. It tries ten choices of one example and five pairs, where enough reference cells exist. The first reference example fixes the measurement radius for each picture in this pilot.

Each manifest scene contains `id`, `recording`, `source`, `sha256`, `width`, `height`, `split`, `targets`, `complete_labels`, and `label_status`. Each target has `x`, `y`, `radius`, and optionally `id`. Allowed split descriptions are `development`, `held_out_recording`, and `external_stage_evaluation`.

```sh
python experiments/cell_detection/benchmark.py \
  --labels path/to/private-labels.json --output output/new-benchmark
python experiments/cell_detection/make_review.py output/new-benchmark/report.json
python -m unittest discover -s experiments/cell_detection -p 'test_*.py' -v
```

Open the resulting `review.html` locally to compare methods and example choices. Images, labels, features, model outputs, and reports belong in ignored `output/` directories. Do not commit private recordings or saved sessions.

## Interpretation and limits

- Supplied examples are excluded from detection scores. Matching is one-to-one within one measurement radius; position errors are also reported.
- Complete reference annotations are required to label unmatched proposals as errors. With partial annotations, unmatched proposals remain unknown and precision is not reported.
- A saved session supplies marked locations, not proof that every unmarked object is empty. The prototype does not offer session-based training or customization.
- A candidate-location stage can miss cells before classification. Candidate coverage is reported separately from final detection accuracy.
- Separate recordings and physical arrays must stay in separate training/evaluation groups. Adjacent frames and augmented versions are not independent recordings.
- The first pilot has limited training variety. Development performance is not evidence of generalization to unfamiliar stages, empty wells, or severe blur.
- Duplicate exclusion protects circles by center and scale. Closely spaced cells and poorly centered suggestions need additional real-image validation.
- Image preprocessing preserves 16-bit contrast; source files are read only. Synthetic or altered pictures must never replace the original data.
- Cross-image tracking, automatic keyframes, application integration, and personalized training are out of scope.
