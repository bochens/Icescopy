# Tool And Action Transition State

This document is the interaction-state source of truth for Icescopy tool changes,
temporary pan, undo/redo, and preview/edit workflows.

The goal is simple:

- only committed changes belong to history
- only one unfinished placement/edit workflow may exist at a time
- temporary navigation should suspend an unfinished workflow, not destroy it
- switching to a different editing tool should cancel the unfinished workflow first

## State Types

There are three important state categories:

### 1. Committed session state

This is real app data and belongs to undo/redo:

- loaded images
- current frame
- circle selections
- keyframes / flagged frames
- grayscale / freeze results
- sort order

### 2. Stable tool state

This is the user-facing mode after transient work is finished:

- `cursor`
- `pan`
- `select`
- `grid`
- `edit-choose`
- `deselect`

These are allowed to survive ordinary UI actions.

### 3. Transient interaction state

This is unfinished work and must never be treated as committed history:

- floating single-add preview
- pinned single-add preview
- lifted single-edit preview
- floating grid preview
- pinned grid preview
- floating group-edit preview
- pinned group-edit preview
- remembered `previous_edit_mode` during temporary pan

Transient state must be either:

- applied
- canceled
- suspended and resumed later

## Core Rules

### Rule 1. Tool switches do not auto-commit

Switching tools must never silently turn one unfinished preview into a committed
 action, and it must never silently reinterpret one preview as another tool's
 preview.

Example:

- pinned single-circle preview -> `Grid`
- correct behavior: cancel the single preview, then enter empty grid mode
- incorrect behavior: reuse the single preview origin and suddenly create a grid

### Rule 2. Undo/redo only touches committed state

If the user is in the middle of add/edit/grid placement and presses undo or
redo:

- cancel the unfinished interaction first
- then undo/redo the last committed command

The preview itself is not a history item.

### Rule 3. Pan is a suspend/resume action

Pan is the only tool that may temporarily preserve an unfinished placement/edit
workflow.

That applies to:

- persistent pan-tool switch
- temporary `Space` pan

When pan ends, the prior unfinished workflow should resume exactly as it was:

- same tool/submode
- same float/pinned state
- same preview origin
- same group edit targets
- same inferred grid parameters

### Rule 4. Dialogs do not cancel work

Non-destructive dialogs should not destroy transient work:

- Settings / Preferences
- About
- Sort dialog
- ordinary menus

### Rule 5. Data-changing actions cancel transient work first

Actions that change the active image/session/history context must cancel
unfinished placement/edit state before they execute:

- undo / redo
- image navigation
- open session
- add images
- add folder
- remove images from session
- clear session
- resort current session

## Tool Transition Table

This table describes what should happen when the user explicitly switches tools.

| Trigger | If current state is unfinished | Behavior | Result |
| --- | --- | --- | --- |
| `Cursor` | any add/edit/grid preview | cancel transient preview/edit | enter `cursor`; keep ordinary scene selection if possible |
| `Pan` | any add/edit/grid preview | suspend, do not cancel | enter `pan`; resume exact prior state when pan ends |
| `Add Selection` | any add/edit/grid preview | cancel transient preview/edit | enter clean `select` mode with no preview until mouse enters current image |
| `Grid` | any add/edit/grid preview | cancel transient preview/edit | enter clean `grid` mode with no preview until mouse enters current image |
| `Edit` | add/grid preview | cancel unrelated preview first, then inspect current scene selection | no selection -> `edit-choose`; 1 selected -> single edit; multiple selected -> group edit |
| `Edit` | single/group edit already active | keep current edit workflow | remain in same edit submode |
| `Delete Selection` | any add/edit/grid preview | cancel transient preview/edit | enter `deselect` |

## Action Transition Table

This table covers important non-tool actions.

| Trigger | Behavior |
| --- | --- |
| `Space` temporary pan | suspend unfinished add/edit/grid state; restore it on key release |
| Undo / Redo | cancel unfinished add/edit/grid state first; then apply history command |
| Frame/image navigation | cancel unfinished add/edit/grid state first |
| Session load / image load / clear session | cancel unfinished add/edit/grid state first |
| Sort current session | cancel unfinished add/edit/grid state first |
| Settings / About / Sort dialog open | preserve current transient state |

## Preview Completion Rules

### Single add

- floating preview: mouse over current image
- single click: pin
- double click: pin + apply
- pinned preview: `Enter` applies
- pinned preview: `Float` returns to floating
- `Cancel`: return to `select`

After apply:

- remain in `select`
- clear the preview
- be ready to place another circle

### Single edit

- entering from one selected circle lifts that circle into preview mode
- floating preview: if supported, mouse repositions it
- single click: pin
- double click while floating: pin + apply
- pinned preview: `Enter` applies
- right click / `Esc`: cancel and return to `edit-choose`

After apply:

- return to `edit-choose`
- clear preview and edit markers

### Grid add

- floating preview: mouse over current image
- single click: pin
- double click while floating: pin + apply
- pinned preview: `Enter` applies
- pinned preview: `Float` returns to floating
- `Cancel`: stay in `grid` with no preview

After apply:

- remain in `grid`
- clear preview
- be ready to place another grid

### Group edit

- entering from multi-selection creates a group-edit preview
- single click: pin
- double click while floating: pin + apply
- pinned preview: `Enter` applies
- pinned preview: `Float` returns to floating
- right click / `Esc`: cancel and return to `edit-choose`

After apply:

- return to `edit-choose`
- clear group preview
- clear group edit markers

## Selection Rules

### Cursor

`Cursor` is the only real selection-management tool.

It is responsible for:

- click selection
- command/control-click add/remove selection
- rubber-band multi-selection

### Edit

`Edit` consumes the current selection; it should not create a separate,
competing selection system.

Behavior:

- no selected circles -> `edit-choose`
- one selected circle -> single edit
- multiple selected circles -> group edit

## Group Edit Identity Rule

Group edit must preserve circle identity by the original local reference frame
that existed when group edit started.

That means:

- `cell_id` stays attached to the same logical circle
- reshaping the grid must not flip numbering
- tilt/pitch changes must not reassign circles by a fresh geometric sort every time

## Recommended Suspension State

When pan suspends an unfinished workflow, the app should preserve:

- originating tool/submode
- preview float/pinned state
- preview origin
- preview offsets
- selected group ids
- stored group reference cells/order
- edit-target markers

When the user returns from pan, the app should restore that exact interaction.

## Known Current Mismatch

The current single-preview -> grid bug comes from breaking Rule 1.

Current problematic flow:

1. user pins a single-circle preview
2. user clicks `Grid`
3. app reuses the existing live preview origin
4. grid appears immediately from the old single preview

Desired behavior:

1. user pins a single-circle preview
2. user clicks `Grid`
3. app cancels the single-circle preview
4. app enters clean grid mode with no active preview until the mouse moves over the image

## Recommended Implementation Direction

The clean implementation is to treat every unfinished interaction as one of
three states:

- `none`
- `suspended`
- `active`

And every transition should explicitly answer:

1. cancel?
2. suspend?
3. resume?
4. apply?

That logic should live in one transition helper instead of being spread across
individual tool-button handlers.
