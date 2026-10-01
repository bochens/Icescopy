# Workflow figures with the Icescopy 2.5.0 toolbar

These PNGs are direct Qt widget captures of the current application. They omit the desktop, operating-system title bar, sharing indicator, and pointer. No interface elements or detections are composited onto them. Earlier figures remain in their original folders.

- `grid-annotation.png`: Colorado State University Ice Spectrometer PCR plates, with placed cells and a pinned grid preview.
- `sample-assignment.png`: the same setup, with 192 cells assigned to six sample groups. Metadata is illustrative.
- `droplet-selection.png`: Texas A&M University's droplet stage, with two selected examples and fourteen cells added by the bundled model. Normal red cell outlines and blue selection outlines are retained.
- `linked-frame-review.png`: Peking University's cold stage, with neighboring frames and the selected droplet's measured brightness. The app's freeze finder uses a ten-frame convolution half-window, a five-frame peak-width minimum, and brightening detection; the detected freeze event and current frame are both 149.

The capture script reads the original plate session's geometry without loading its large result tables. It measures the PKU droplet directly from its image sequence. Original sessions and images are not modified, and temporary preferences and frame-name links are removed when the script finishes. The plate session's checksum is verified afterward.

Run with the app's Python environment on macOS:

```sh
python resources/readme/2026-10-01-workflow/capture.py \
  --plate-session /path/to/plate.icescopy \
  --pku-frames /path/to/pku-frames \
  --destination /path/to/new-figure-folder
```

The destination must not already contain these figures. The plate session must still refer to accessible source images. No source recording names or local dataset paths are included in the public figures or this script.
