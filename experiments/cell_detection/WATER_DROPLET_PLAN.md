# Small water-droplet experiment

This replaces the earlier full-recording real-image training plan. Training
remains paused while the user labels the images.

## Scope and starting model

- Detect water droplets, including water inside PCR wells, under different lighting.
- Start from the saved synthetic-posttrained network, not the original ImageNet
  network. Preserve the synthetic checkpoint unchanged and save any later model
  under a new name. The private labeling manifest records its exact hash.
- Continue using one or two marked examples and one current image or video frame.
  Exclude existing cells. Keep freezing detection and app integration separate.

## User labels

The private `output/water-droplet-labeling-20260930-v2` folder contains one
unmarked early image for each of five setups: CSU cold stage, CSU IS PCR wells,
PKU, TAMU and CIF. The PCR image was supplied specifically to include filled
and empty wells. Previous data and labeling folders are preserved.

The user will mark the water-bearing area and save `labels.icescopy` beside each
image. These circles describe droplets or water inside wells, not just bright
reflections or deliberately reduced brightness-measurement areas. After positive
labels are finished, review clearly empty wells as negative examples. Unmarked
or ambiguous locations do not automatically become negatives.

## Next steps after labeling

1. Check session coordinates against the unchanged source image and confirm which
   labels are complete. Store a new annotation manifest; preserve all old labels.
2. Adapt the experimental trainer to initialize from the synthetic checkpoint.
   The existing `hybrid_neural_train.py` still starts from ImageNet and does not
   implement this revised plan. Do not run it as though it does.
3. Use modest crop, flip, color and brightness variants derived only from training
   images. Choose separate evaluation recordings and keep all related variants
   on their original side of the split.
4. Compare the unchanged synthetic model with the updated model on the same
   evaluation images and example choices before making accuracy claims.

One image per setup is a small starting experiment. Many droplets in one picture
share lighting and background; they do not prove robustness across new recordings.
PKU is now intended for training, so its older evaluation results cannot serve
as independent validation of this new model.
