# Icescopy documentation

Icescopy turns images or videos of freezing experiments into reviewed freeze events and temperature-aligned count tables. Use this documentation to learn the workflow, find a control, understand the output, or contribute to the application.

This guide describes the **2.3.8 source, Windows app, and macOS app**. See [Installation and Setup](Installation-and-Setup.md) for the download that matches your computer. The [README](../README.md) provides a short introduction; this wiki supplies the detailed instructions.

## Start here

| Your goal | Start with |
| --- | --- |
| Install the desktop app | [Installation and Setup](Installation-and-Setup.md) |
| Complete your first analysis | [Quick Start](Quick-Start.md) |
| Find a button, panel, or keyboard shortcut | [Interface and Shortcuts](Interface-and-Shortcuts.md) |
| Understand frames, cells, events, and result dependencies | [Concepts and Data Flow](Concepts-and-Data-Flow.md) |
| Fix a problem | [Troubleshooting](Troubleshooting.md) |
| Work on the code | [Developer Guide](Developer-Guide.md) |

## Analyze an experiment

Follow this order for a new analysis. Each guide explains its controls and checks.

1. [Load and review frames](Loading-and-Reviewing-Frames.md). Check the image order or video clips before annotating.
2. [Prepare the image](Image-Editing.md), then [draw and edit cells](Annotation-Workflow.md). A cell is the circular area measured for one droplet or well.
3. [Assign samples and enter metadata](Sample-Metadata.md). A sample groups related cells; metadata describes that sample.
4. [Set analysis intervals and find freeze events](Analysis-and-Results.md). Review the detections, tune the settings, rerun, and then make manual corrections.
5. [Import temperature records](Temperature-Import.md). Check time matching, sample groups, and any blank correction or repeated cycles.
6. [Save the session and export results](Sessions-Export-and-Preferences.md). Use the [Output Reference](Output-Reference.md) to interpret the tables.

Keep the original images or videos: a saved session refers to those files rather than containing them. Use **Save Session As...** and a new export folder when comparing alternative analyses.

## Reference and explanation

- [Interface and Shortcuts](Interface-and-Shortcuts.md): menus, panels, timeline controls, and keyboard behavior.
- [Sample Metadata](Sample-Metadata.md): sample identity, built-in fields, custom fields, and shared values.
- [Output Reference](Output-Reference.md): CSV columns, units, missing values, and count interpretation.
- [Concepts and Data Flow](Concepts-and-Data-Flow.md): what each stage produces and what to repeat after an edit.
- [Sessions, Export, and Preferences](Sessions-Export-and-Preferences.md): saved state, external files, recovery, and application settings.

## Develop and maintain Icescopy

| Topic | Guide |
| --- | --- |
| Set up a checkout, run checks, and prepare a change | [Developer Guide](Developer-Guide.md) |
| Understand modules and how data moves through the application | [Architecture Overview](Architecture-Overview.md) |
| Change cell data, editing, or drawing behavior | [Cell System](Cell-System.md) |
| Locate Python modules, classes, and functions | [API Reference](API-Reference.md) |
| Update, validate, and publish these pages | [Documentation Guide](Documentation-Guide.md) |

The API reference describes internal Python code. It is not a promise that every class or method is a stable extension interface.

## Help and historical notes

Report reproducible problems through [GitHub Issues](https://github.com/bochens/Icescopy/issues). Include the application version, operating system, steps, and relevant error text. [Report a problem](Troubleshooting.md#report-a-problem) explains what to include without sharing private experiment files.

The dated [Windows save-recovery notes](Windows-Save-Recovery.md) and [Windows Preferences investigation](Windows-Preferences-Investigation.md) preserve evidence behind earlier fixes. They are historical maintenance records, not installation instructions or a list of current defects.
