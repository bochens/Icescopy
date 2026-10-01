# Small water-droplet experiment

## Current work: a small detector users can train

The user chose a lightweight trainable program and stopped further neural
model work. Use a random forest, a collection of small decision trees, to
classify image regions directly from local intensity, contrast, edge and texture
features. Detection must not depend on a preliminary circle finder finding
every droplet. Convert matching image regions into ordinary circular cells.

Training input is one or more saved `.icescopy` sessions and their linked media.
The user explicitly requires no separately labeled negatives: every desired
droplet must be marked in each chosen training frame; other circles/background
are negative examples. Boundary bands and padding remain ignored. Do not use
our separately reviewed empty/invalid annotations to train this benchmark;
they are evaluation evidence only. Keep augmentation labels aligned.

The trainer saves numeric tree data in an `.icescopy-model.json` file. Icescopy
loads the file and detects cells on its current image/video frame. Keep this
experimental, support cancellation and one-step undo, protect existing cells,
and preserve original sessions/images. Report missed/offset droplets, reviewed
empty selections, other extras, training time, model size and inference time.

The custom model's six-pass empty-well penalty continuation has finished. Its
validation loss improved, but the reserved PCR region still has all eight
reviewed empty wells selected. Do not treat that run as a solved detector or
integrate it into the app. FamNet work remains stopped.

## Custom model continuation

Current direction: focus on the custom joint model. The unchanged FamNet
comparison is complete and its files are preserved. The user stopped the
proposed FamNet fine-tuning before any training or optimizer update began.
Do not start that experiment.

The current custom model has a specific failure: on the PCR fitting region,
filled and empty wells have almost the same strongest confidence response. The
old validation tile bank also covered only two of eight reviewed empty wells.
The next bounded continuation keeps the model and inference unchanged. It
penalizes the strongest false response in each reviewed empty region, keeps
invalid center points separate, and requires every positive and reviewed empty
center to appear in both fitting and validation caches. The two negative
categories share the existing total weight, so adding easy background pixels
cannot dilute a false well response.

Continue from the preserved spatial fit-v2 weights for six passes of 60 updates.
Keep the same positive, offset and radius losses, learning rates and batch
normalization. Select against the initial checkpoint using the fully covered
validation set. Preserve the old model if no trained checkpoint improves that
score. Use fresh output/cache folders; retain all original annotations and
earlier results. Compare detections with the existing cutoff before any separate
synthetic calibration. Reserved regions have already been inspected and are
diagnostics, not a fresh blinded test.

## Previous experiments

The first joint model reduced some extra selections on PKU but performed worse
on PCR: only 25 of 158 remaining droplets were accurately centered in the first
two-example trial, with 61 additional selections. Do not adopt that model.

Two experiments were run separately:

- Test the authors' pretrained FamNet without further training or image-specific
  adaptation. Report its estimated count separately from individual detections.
- Restart the custom joint model from the preserved synthetic-only encoder.
  Split each original photo into separate fitting, validation and test regions
  before creating rotated, flipped, uniformly scaled or lighting-adjusted tiles.
  No reserved test pixels or droplets enter training or model selection.

The private spatial manifest retains 210 fitting, 99 validation and 106 test
droplets. Six circles crossing region boundaries are excluded. These are unseen
regions of previously inspected photos, not independently collected recordings.
All active source images, synthetic images and split annotations are together
under `training-data/water-droplets`; original images and sessions are unchanged.

The fixed custom run uses 12 passes of 60 updates, otherwise the joint recipe
below. Known droplet interiors allow only one center. Full reviewed empty
regions receive an additional direct false-selection penalty in the same loss.
Unknown real pixels remain ignored. The saved model minimizes validation loss
averaged equally over real and synthetic domains, then equally over their
scenes. All fitting positives must receive updates before selection is allowed.
Separate synthetic calibration determines the confidence cutoff. Test results
are reported after the model and cutoff are fixed; they do not select another run.

The sections below retain the history and limitations of previous experiments.

The user's follow-up asks for more crop and rotation variation. A new preserved
run uses 240 distinct tiles per real fitting region, arbitrary rotation angles,
uniform scale factors from 0.75 to 1.25, and crop positions across the tile core.
The sampler visits unused variants before repeating them after label coverage.
Its fixed budget is 20 passes of 60 updates. It uses the same synthetic-only
parent and separated source regions; no additional original images are needed.

An audit of the training preview found unmarked droplets created by mirror
padding beyond the source region. Those pixels were excluded from the loss,
but their surrounding features could still influence predictions. The new run
uses constant padding for training and inference, with no copied objects. The
old checkpoint and its previews are retained. Test regions have now been viewed;
later comparisons remain reserved-region diagnostics, not a fresh blinded test.

This replaces the earlier full-recording real-image training plan. The user has
supplied five labeled sessions and authorized training after the save-prompt fix
was committed. That fix is recorded in commit `1b08821`; no app rebuild is part
of this experiment.

## Scope and starting model

- Detect water droplets, including water inside PCR wells, under different lighting.
- Start from the saved synthetic-posttrained network, not the original ImageNet
  network. Preserve the synthetic checkpoint unchanged and save any later model
  under a new name. The private labeling manifest records its exact hash.
- Continue using one or two marked examples and one current image or video frame.
  Exclude existing cells. Keep freezing detection and app integration separate.

## User labels

The private `training-data/water-droplets` folder contains one
unmarked early image for each of five setups: CSU cold stage, CSU IS PCR wells,
PKU, TAMU and CIF. The PCR image was supplied specifically to include filled
and empty wells. Previous data and labeling folders are preserved.

The user saved an `.icescopy` session beside each image. The 421 circles describe
droplets or water inside wells, not just bright
reflections or deliberately reduced brightness-measurement areas. After positive
labels were finished, 137 clearly empty wells or background locations were
reviewed as negative examples. Unmarked or ambiguous locations do not
automatically become negatives. Each user radius is preserved. Source images
and sessions are copied without alteration into the private run directory.

## Fixed training run

- Update the final three neural blocks from the unchanged synthetic-trained
  parent. Freeze the earlier blocks and stored normalization statistics.
- Use four passes of 40 updates, 32 positive/positive/negative crop triplets per
  update, AdamW learning rate 0.00005, margin 0.2 and parent-preservation weight
  0.1. Each batch is half real and half synthetic, with equal instrument weights.
- Make eight variants of each reviewed real object: 4,464 real crops. Use only
  uniform scaling, rotation, flips and bounded crop shifts for geometry; vary
  brightness, contrast, gamma, color and blur without changing the label. Keep
  the complete central droplet inside its crop.
- Every manually marked positive must contribute to a weight update before a
  checkpoint is eligible. Reuse only verified frozen-layer synthetic features;
  recompute teacher embeddings from the synthetic-trained parent network.
- Separate synthetic validation chooses among trained checkpoints; report its
  initial parent loss too. Separate synthetic calibration chooses the selection
  cutoff using F2, which penalizes a missed cell four times as much as an extra
  selection. No real diagnostic result selects weights or cutoffs.
- Fit matched scoring models for the parent and updated networks. Fix three
  single-example and two two-example trials per real image before scoring.

One image per setup is a small starting experiment. Many droplets in one picture
share lighting and background; they do not prove robustness across new recordings.
All five real photos enter training. Report recovery of marked targets, selections
at known negative locations and other unclassified additions as training
diagnostics. Report synthetic test results separately. PKU enters training, so
its older evaluation results cannot serve as independent validation of this new
model. Future real evaluation needs separately labeled recordings; keep their
images and all derived variants out of fitting and cutoff selection.

## First completed run

The fixed four-pass run completed in 229 seconds. Pass three had the lowest
synthetic validation loss, 0.016775 versus 0.020262 for the parent. Every one of
the 421 manual positives contributed to an update. Eleven convolution weight
arrays changed; the earlier layers and stored normalization statistics stayed
unchanged. The original checkpoint, source images and saved sessions were
verified unchanged.

With the same scoring-model fitting procedure for both networks, recovery of
marked targets with two supplied examples increased from 97.2% to 98.8%.
Extra selections remained substantial. The table shows the range across the
two fixed example pairs for each training photo; supplied examples are excluded
from the target counts.

| Setup | Marked targets found | Extra selections |
| --- | --- | --- |
| CSU cold stage | 48 / 48 | 1 |
| CSU IS PCR wells | 158 / 158 | 49–64 |
| PKU | 82–86 / 88 | 16–50 |
| TAMU | 14 / 14 | 0 |
| CIF | 102 / 103 | 5–6 |

None of the explicitly labeled negative locations was selected in these
two-example trials. That does **not** establish correct detection elsewhere:
visual inspection found many extra circles between PCR wells and PKU holes,
beside droplets, or on a bright background feature. Most are poorly centered
selections, even when the marked targets are also found. Incomplete labels do
not support an overall precision estimate, and these training photos do not
measure performance on unseen recordings.

Full current-frame calls on the PKU photo took 8.96 seconds for the parent and
9.16 seconds for the updated model, including preprocessing and selection but
excluding model/file loading. Both calls reproduced the cached comparison
selections. The optional structured synthetic comparison was stopped because
small radius differences caused many extra feature computations; its partial
files are retained and no aggregate result is reported.

A separate full PCR-frame call took 11.18 seconds and reproduced the reported
selections. Repeating it added no cells. A brightness-changed frame preserved
all existing IDs and positions without duplicating them, while adding one new
selection. File input and decoded RGB/BGR frame arrays produced identical
preprocessed pixels for all five source images. This checks the experimental
current-frame API, not an integration into the app's video workflow.

The next experiment should label the misleading patches near droplets as
explicit negatives and improve recognition of the droplet center. Simply
rejecting every closely spaced circle could remove distinct nearby droplets.
Keep the current model experimental; it is not ready for app integration.

## Prepared center-negative extension (not run)

The user identified another misplaced PKU circle that the broad recovery count
had accepted. Its center was 0.92 reference radii from the manual center. The
second run therefore retains broad recovery for comparison and adds a separate
placement measure: a centered detection must be within 0.35 of the marked
circle's radius. Report both models under the same two measures, with median
and 90th-percentile center errors. Preview colors must distinguish misplaced
matches from centered detections.

The new private manifest preserves every original positive and negative. It
adds 669 invalid detection centers: 248 actual failed selections from the first
run, checked visually, and one deliberately displaced example for each of the
421 user circles. These labels mean the proposed center is wrong; they do not
mean that water is absent from the surrounding crop. Every rounded crop center
is at least 0.55 reference radii from every marked positive. Ambiguous distant
unmarked objects are excluded.

The approved second run starts from the first manual-trained checkpoint and
keeps the same four passes, update count, learning rate and synthetic replay.
It reuses the original 4,464 manual crops and adds four variants per new center,
for 22,152 total manual and synthetic crops. New center-negative crops have no
translation, center jitter or radius jitter; rotation, flips, uniform scaling
and lighting variation keep the invalid location at the center. Sampling splits
manual negatives equally between old examples and new invalid centers, while
cycling new centers through actual updates. Teacher embeddings are regenerated
from the preserved first-run model.

Compare the complete previous detector, including its frozen scorer and cutoff,
with the updated detector using the same fixed example selections. Also fit a
new scorer over the unchanged first-run network to distinguish scorer changes
from neural-weight changes. Keep the earlier synthetic F2 calibration rule;
centering is an additional reported measure, not a retrospective cutoff change.
Use only the five manual photos and the reserved synthetic validation/calibration
sets for this bounded run. Leave the optional structured stress test out.

Before this prepared run was launched, the user requested both changes together:
jointly learn circle location and rejection, using the original positives and
new negative examples in the same training. That supersedes the scorer-only
second run above. Its data preparation and tested code are preserved, but no
weights were trained with it. The next model must generate/refine centers with
shared image features rather than depend on the old hand-built circle proposals.
Keep example guidance, current-frame inputs, geometry-preserving augmentation,
explicit-label boundaries and existing-cell protection. Agree on a bounded
joint-training recipe before launching it.

## Joint detector: current experiment

The user has now authorized one detector that learns where to place circles
and when to reject them, with positives and negatives in the same training run.
The prepared scorer-only extension above remains unrun.

The active images and labels are together under the ignored
`training-data/water-droplets` folder. The five instrument folders retain their
original images and saved sessions; `synthetic-v1` holds the 40 synthetic images;
`annotations/real-reviewed-v2.json` contains the reviewed real labels.
`ACTIVE-DATASET.json` identifies the current manifests and hashes. Earlier
copies remain in their original output folders. Training uses the combined
dataset paths; model outputs and derived caches remain in a fresh output folder.

The design combines two established ideas: exemplar matching, as described in
[Learning To Count Everything](https://arxiv.org/abs/2104.08391), and direct
center, offset and size prediction from
[Objects as Points](https://arxiv.org/abs/1904.07850). This is a small adaptation
using our preserved MobileNet features, not either paper's published detector
or a claim to reproduce its benchmark results.

- Initialize image features from the first manual-trained checkpoint. Earlier
  feature blocks and stored normalization statistics stay frozen. Train the last
  three feature blocks and a new small decoder together.
- Compare shared image features with features of one or two marked examples.
  Predict a center score, fine position correction and radius at each location.
  There is no hand-built circle proposal stage or separately fitted classifier.
- Scale the image uniformly using example size. Preserve aspect ratio. Use
  transformed tiles, rotations, flips and lighting changes with labels transformed
  by the same geometry. The current frame is the only image input.
- Combine center confidence, position and radius losses in each update. Weight
  false center predictions explicitly. Synthetic images have complete background
  labels; real images have known positives, reviewed empty/background regions
  and the new invalid-center points. Other real locations remain unknown.
- Begin with four passes of 60 updates, four tiles per update, half real and half
  synthetic. Use separate learning rates for the pretrained features (0.00005)
  and new decoder (0.0002). Record actual positive and invalid-center coverage.
- Use separate synthetic validation for checkpoint selection and separate
  synthetic calibration for a cutoff based on centered F1, which balances missed
  and extra selections. Do not select the cutoff from the five real photos.
- Compare against the actual first detector, retaining its saved classifier and
  cutoff. Report raw recovered, accurately centered, missed and extra counts,
  normalized position errors, CPU runtime and repeated-frame duplicate checks.

The five real photos are training diagnostics. Their augmented versions are not
independent test images. A stricter placement measure is essential: a recovered
circle within one reference radius can still be visibly misplaced. The new
preview only uses green for centers within 0.35 reference radii.
