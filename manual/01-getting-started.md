# Get Started

Use this page to load images, create a session, and understand the main workspace.

## Before You Start

Have these ready:
- an ordered image sequence
- a writable location for the `.icescopy` session file
- optional external temperature data files if you plan to import them later

## Core Workflow

Use this order for a standard run:

1. Create a new session.
2. Add images or add an image folder.
3. Sort the image list if needed.
4. Annotate cells.
5. Assign samples if your experiment uses sample groups.
6. Run analysis.
7. Review the `Grayscale Plot` dock and the `Results Tables` dock.
8. Import external temperature data if needed.
9. Save the session.
10. Export result tables.

## Start A New Session

1. Open `File -> New Session`.
2. Add images with `File -> Add Images...` or `File -> Add Folder...`.
3. Check the image order in the `Images` dock.
4. Save the session with `File -> Save Session` or `File -> Save Session As...`.

Result:
- the session is ready for annotation
- the image list and frame slider are populated

Practical rule:
- save once near the start so later relink operations can write back into the same session file automatically

## Open An Existing Session

1. Open `File -> Open Session...`.
2. Select the `.icescopy` file.
3. Review the restored image list, cells, samples, and results tables.

If the session opens but images are missing:
1. Open `File -> Relink Images Folder...`.
2. Select the folder that contains the session images.

Result:
- the saved working state is restored

What is restored:
- image paths and image order
- cells and keyframe geometry
- sample catalog entries
- image-edit state
- existing results tables

## Main Workspace

The exact dock arrangement can change, but these panels are the main working areas:
- `Images`
- `Tool Options`
- `Sample Catalog`
- `Cells`
- `Grayscale Plot`
- `Results Tables`
- `Console`
- frame slider and image viewer

## Use The Viewer And Timeline

The viewer supports:
- one-image view
- two-image view
- three-image view

When two or three images are shown, you can switch between:
- left-right layout
- top-down layout

The timeline is used for:
- frame navigation
- keyframes
- flags
- changing the visible timeline resolution

Use the smaller timeline-resolution slider when the image sequence is long and you need finer control over the main frame slider.

Working pattern:
1. Use the large frame slider to scrub through the sequence.
2. Use the small resolution slider to zoom the visible timeline range when precise frame access is difficult.
3. Use the diamond button to mark keyframes when cell geometry changes across the run.
4. Use the flag button to mark frames that need review.

Important:
- keyframes and flags are frame markers only
- keyframes affect interpolated cell geometry
- flags are review markers and are exported through `flag_state` in the grayscale results

## Read The Images Dock

The `Images` dock is also a frame marker view.

Marker meanings:
- `K`: keyframe
- `F`: flagged frame

Use the `Images` dock to:
- confirm image order
- jump to a specific frame
- review where keyframes and flags are already set

## Main Menus

Use `File` for session and export actions:
- new session
- open session
- save session
- save session as
- add images
- add folder
- relink images folder
- output results

Use `Analysis` for processing:
- run analysis
- import temperature data
- CSU and TAMU importers live under this submenu

Use `Window` to show, hide, and reset docks.

## Sort Images

Use `File -> Sort Images` if the loaded order is wrong.

Common sort methods include:
- natural filename
- filename ascending
- filename descending
- created time
- modified time
- EXIF time

If a sort method is not valid for the current session, the app rejects it instead of partially applying it.

Use sorting carefully:
- sorting changes frame order
- changed frame order invalidates existing analysis results
- if you sort after annotation or analysis, review the sequence again before continuing

## Keyboard Shortcuts

Common shortcuts:
- `A`: Cursor
- `S`: Add Cell
- `G`: Grid Tool
- `E`: Edit Cell
- `D`: Delete Cells
- `Z`: Pan and Zoom
- `Space`: temporary pan while working in another tool
- `Enter`: apply the focused action, such as `Set` for freeze frame or `Apply` for crop
- `Cmd+S` or `Ctrl+S`: save session

## Next Step

After loading images, continue with [Annotate cells](</Users/C832577250/Project/Icescopy/manual/02-cell-annotation-tools.md>).
