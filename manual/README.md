# Icescopy Manual Source

This directory contains the preserved LaTeX source for the Icescopy user manual.

## Why this directory exists

The repository still had generated LaTeX sources under `output/latex/generated`, but the original template or source generator is no longer present in the repo.
That means the generated `.tex` files are currently the only editable LaTeX source of record.

This directory preserves that source in a stable location that is separate from generated build output.

## Contents

- `latex/Icescopy-Manual.tex`
  - the main manual document
- `latex/01-getting-started.tex`
- `latex/02-cell-annotation-tools.tex`
- `latex/03-image-edit.tex`
- `latex/04-analysis-and-results.tex`
- `latex/05-temperature-import.tex`
- `latex/06-sessions-export-preferences.tex`
- `latex/07-troubleshooting.tex`
- `latex/IcescopyApp.png`
  - icon asset used on the title pages

## Current source status

The files in `manual/latex/` were copied from:

- `output/latex/generated/`

They are not reconstructed from a higher-level source format.
If the manual is revised in LaTeX directly, this directory should be treated as the authoritative source.

## What is not included

This directory intentionally does not include:

- `output/latex/build/`
- generated PDFs
- `.aux`, `.log`, `.toc`, or other LaTeX build products

Only the files required to compile the manual are kept here.

## Compile entry point

The main entry point is:

- `manual/latex/Icescopy-Manual.tex`

The chapter files can also be compiled individually because each one is a complete LaTeX document.
