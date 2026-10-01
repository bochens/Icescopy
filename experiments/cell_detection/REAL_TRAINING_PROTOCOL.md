# Real-image training experiment

This extends the earlier synthetic-only experiment with authorized real-stage
training. It remains separate from Icescopy. The detector uses one current image
or decoded video frame, guided by one or two marked cells. Existing cells remain
excluded from new selections; freezing detection is unchanged.

## Fixed data split

The first real-data run reserves half the recording/source groups for training
and half for evaluation: five groups on each side. After including the complete
CIF folders, there are 621 training images and 557 reserved evaluation images.
The image counts differ because the two CIF recordings have different lengths.
All frames from any recording stay together. Crops, flips and other variants
inherit that same group; they never cross into the other partition.

The private manifest records source hashes, original locations, copied image
locations, group membership, labels and annotation provenance. Original files
and previous outputs are preserved. Private recordings, labels and trained
artifacts are not committed or uploaded.

Existing local images have already been inspected during earlier development.
Their evaluation is therefore exploratory, even though this run keeps them out
of training. Public images are inspected to establish reference labels before
training, without using detector predictions to choose those labels or splits.

## Additional public sources

| Source | Use and preparation | Attribution and reuse terms |
| --- | --- | --- |
| [CIF cold-stage example data, v0.2.0](https://github.com/CIF-Cold-Stage/DropFreezingDetection.jl/tree/v0.2.0/exampledata) | All 614 frames from Experiment 1 enter the training inventory; all 550 frames from Experiment 2 enter the evaluation inventory. Original photo bytes are retained. Supplied coordinates are converted from row/column order to image x/y, duplicate positions are removed, and missing visible droplets are annotated. | Petters and Yadav, [software archive](https://doi.org/10.5281/zenodo.7765097). The repository supplies a [GPL-3.0 license](https://github.com/CIF-Cold-Stage/DropFreezingDetection.jl/blob/v0.2.0/LICENSE). The downloaded files are checked against the tagged Git object hashes. |
| [FINC, Miller et al. (2021), Fig. 1d](https://amt.copernicus.org/articles/14/3131/2021/) | An unannotated photo crop containing 50 wells enters training. Other figure panels, text, highlighted circles and the scale bar are outside the crop. | CC BY 4.0. The source figure, crop coordinates and image hashes are recorded. |
| [DRINCZ, David et al. (2019), Fig. 1b](https://amt.copernicus.org/articles/12/6865/2019/) | An unannotated photo crop containing 48 wells enters evaluation. The two highlighted example wells are outside the crop. | CC BY 4.0. The source figure, crop coordinates and image hashes are recorded. |

The droplet photos in [Polen et al. (2018), Fig. 2](https://amt.copernicus.org/articles/11/5315/2018/)
were also screened. They are excluded from this run because drawn lines and
arrows cross droplet neighborhoods. Paper photo crops are reported separately
from raw recordings because their resolution and framing differ.

Every CIF training frame supplies four positive and two explicit negative crops.
The sampled cell IDs vary across the sequence. Other real training images supply
four variants of each reviewed object. This bounds memory use while including
the whole training recording. A saved network is eligible only after every
training frame has actually contributed to an update.

The smaller scoring model uses 48 uniformly spaced CIF training frames, and full
detection evaluation uses 32 uniformly spaced CIF evaluation frames. Both lists
include their endpoints and are fixed before results are calculated. All other
training and evaluation images participate, for 55 scoring-model training images
and 39 evaluated images. Reserved CIF frames outside that evaluation sample are
not claimed as tested. Reports keep recording-level results separate because
nearby frames share the same droplets.

## Labels and training transformations

- A frozen droplet remains a positive cell. Labels identify liquid-bearing or
  frozen sample locations, not whether they froze during the recording.
- An incomplete saved selection supplies positive examples only. Unmarked wells
  remain unknown. Real training negatives are explicitly reviewed empty holes,
  holder features or background locations.
- Supplied freezing-event coordinates need review: an omitted event is not proof
  that a droplet is absent. The first CIF recording has two such visible droplets.
- Training uses cropped cell neighborhoods with bounded shifts and scale changes,
  flips, rotations, brightness/contrast/gamma changes, color variation, grayscale
  conversion and modest blur. Transformations retain the marked cell and its
  label. Evaluation images are not augmented.
- Training scenes use one measurement radius for the cell interior rather than
  the enclosing holder. For evaluation, each marked example retains its own
  radius, and proposed circles use the median example radius. Reference matching
  uses each labeled cell's actual radius. This corrects the older benchmark's
  first-radius shortcut for PKU; those results are not directly interchangeable.
  This experiment does not establish arbitrary mixed-size detection.

## Training and comparison

The new network starts from the original ImageNet weights. Its final three
convolution blocks are updated; earlier blocks and the stored normalization
statistics stay fixed. The former model fitted on real-stage images does not
initialize the new training. Each training batch gives equal weight to real and
synthetic examples, with recording groups sampled evenly within each source.

Real scoring-model training uses the annotated centers and at most two nearby
proposals per labeled object. This includes reviewed negative locations even
when the proposal finder does not select them. Ambiguous overlaps are excluded;
unlabeled areas never become negative examples. Both networks use the same
training positions. Evaluation retains the ordinary proposal procedure.

Separate synthetic validation scenes choose the saved network. Another separate
synthetic set chooses selection cutoffs. Neither step uses the reserved real
evaluation images. This retains a limitation: the final cutoff is selected on
generated scenes, so its behavior on real images still needs measurement.

The cutoff objective is fixed before evaluation: maximize
`5 × correct / (5 × correct + 4 × missed + extra)`.
This is called the F2 score. A missed cell contributes four times the penalty of
an extra selection, reflecting the preference to find most cells and manually
remove a few mistakes. Report both cells found and extra selections; the score
alone can hide an unacceptable tradeoff.

The comparison includes the untouched network with direct example matching,
the untouched network with a synthetic-only scoring model, the untouched network
with a new real-plus-synthetic scoring model, and the updated network with a
matched real-plus-synthetic scoring model. A scoring model combines image
measurements into the decision to keep a proposed circle. All three fitted
scoring models use the same new cutoff objective; the direct-matching baseline
retains its previously recorded cutoff.

Only the two matched real-plus-synthetic versions isolate the effect of updating
the network. Comparing the two untouched-network scoring models isolates adding
real examples to their training. Comparisons with earlier reports must also
acknowledge the changed cutoff objective and evaluation subset.

One- and two-example results, candidate coverage, extra selections and runtime
are reported separately by setup. Partial annotations support recovery of known
cells and unmatched counts, but cannot establish precision. Repeated example
choices on one picture are not independent evaluation images.
