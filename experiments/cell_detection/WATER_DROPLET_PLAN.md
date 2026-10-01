# Small water-droplet experiment

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
