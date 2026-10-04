# MLE air-concentration demonstration

`m1-mle-air-concentration.png` is a direct Qt capture of Icescopy 2.6.0's INP toolkit client, after a fresh calculation through the external INP-toolkit 0.4.2 executable. The figure contains only the application window, with its native controls and actual calculated curves.

The input is Carson's untreated M1 base-rerun recording, opened from `test_261002.icescopy` in `(M1) 08.12.25 base rerun`. The saved group contains five air-sample dilutions: 1, 13, 169, 2197, and 28561. Each has 32 wells of 50 µL. Sample_5 is explicitly marked as the water blank.

The air normalization uses the session's metadata: 17,829.1 L sampled air, 10 mL suspension, and a filter fraction of 1. The saved water blank inherited the last sample's dilution value, 28561. The capture script sets that marked blank to dilution 1 in memory, as required for undiluted water by the toolkit. Original counts, the source session, and normal application preferences remain unchanged; the script verifies the source session's hash afterward.

Calculation uses MLE, water-blank correction, the saved full-range choices, and the 0 to −35 °C starting grid in 0.5 °C steps. The uncertainty setting is z = 1.96, giving nominal approximate 95% bounds at each temperature. The combined result has 43 finite grid points from −7.5 to −28.5 °C, in `INP_per_L_air`. Black is the combined curve; colors are the separately calculated individual dilutions. The native uncertainty shading and logarithmic concentration axis are retained.

The original experiment data are external inputs to the capture script. To reproduce with Icescopy's Python environment, run from the repository root:

```sh
python resources/readme/2026-10-04-inp/capture.py \
  --session /path/to/test_261002.icescopy \
  --toolkit /path/to/inptk \
  --destination /path/to/new-figure-folder
```

The linked recording images must be available. Preferences are isolated in a temporary directory. The script refuses to overwrite an existing figure. The window is resized and its controls pane widened for readability; interface elements and result curves are captured directly without additional artwork.
