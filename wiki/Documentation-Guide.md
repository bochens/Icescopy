# Documentation Guide

Use this page when changing Icescopy's documentation. The versioned `wiki/` directory in the application repository is the source of truth. GitHub's **Wiki** tab is a separate Git repository; a change merged into the application repository does not automatically update that tab.

## Structure and audience

The documentation follows the practical distinction between tutorials, task guides, reference, and explanation described by [Diátaxis](https://diataxis.fr/start-here/). It is a documentation framework, not a formal certification standard.

| Reader need | Where it belongs | What to include |
| --- | --- | --- |
| Learn a first successful workflow | Quick Start | Prerequisites, ordered actions, expected results, links for later detail |
| Complete a particular task | User workflow guides | Starting state, exact controls, steps, outcome checks, relevant recovery |
| Look up a fact | Interface, Output, API reference | Names, units, formats, accepted values, behavior, limitations |
| Understand why parts relate | Concepts, Architecture, Cell System | Data flow, responsibilities, dependencies, and design constraints |
| Make a code change | Developer Guide | Setup, source map, focused validation, packaging and contribution expectations |

Keep the README a short entry point and feature tour. Put detailed controls, format requirements, and long procedures here. Do not make users read API internals to perform a normal task.

## Write a task guide

Use [Google's procedure-writing guidance](https://developers.google.com/style/procedures) for clear actions and context:

1. State the task and prerequisites before the steps.
2. Name the actual menu or panel before the action, such as **Analysis → Run Analysis**.
3. Use numbered steps for a sequence and a table for parallel choices.
4. Describe the expected visible result at meaningful checkpoints.
5. Explain what to do if that result does not appear.
6. Link to detailed reference or background instead of repeating it at length.

Define specialized terms on first use. Distinguish an editable field from a calculated result, a frame index from time, and a displayed preview from an applied change. State units and zero-based indexing explicitly where they matter.

Do not invent defaults or recommend scientific thresholds without evidence. A useful parameter guide explains the direction of an adjustment and how to check its effect; it does not promise one value works for all experiments.

## Verify facts against the code

For a user-facing change, inspect the action wiring, the called implementation, and relevant tests. Check labels in the UI when feasible. A tooltip can be incomplete or stale, so verify behavior rather than copying it uncritically.

For a format or calculation, inspect the parser/writer and the function producing values. Clearly distinguish input validation, implemented arithmetic, and scientific interpretation. Use generic synthetic examples; never copy private experiment paths, sample identities, or raw records into public docs.

For a source/API change, keep the module index and generated source references current. Avoid hand-maintained line numbers without a check. API inventories describe what exists; they do not make internal methods stable public contracts.

## Links, names, and screenshots

- Use one descriptive level-one heading per page, followed by logically nested headings.
- Use filenames such as `Temperature-Import.md`. Keep established page names and anchors where possible so existing links continue to work.
- In the application repository, use ordinary relative links: `[Temperature Import](Temperature-Import.md)` and source links such as `[frame source](../src/icescopy_frame_source.py)`.
- Link to the platform's actual released installer. Do not assume every release contains binaries for every platform.
- Keep screenshots under `resources/readme/` or another reviewed repository asset directory. Add new filenames when replacing an example so older assets remain available.
- Capture the app window only. Use readable labels, useful zoom, the correct selected controls, and visible task-relevant panels. Exclude pointer overlays and unrelated desktop content.
- Keep screenshots consistent with the described step. Do not alter an image to depict a state the application did not produce.

`_Sidebar.md` and `_Footer.md` supply navigation in GitHub's Wiki tab; [GitHub documents these filenames](https://docs.github.com/en/communities/documenting-your-project-with-wikis/creating-a-footer-or-sidebar-for-your-wiki). The Home page also exposes the guide structure for readers browsing the repository directly.

## Validate an update

From the repository root, with the development environment active:

```bash
python tools/update_api_reference.py --check
python tools/wiki_docs.py check
git diff --check
```

API descriptions and the selected methods live in `tools/api_reference.json`. After a source change, update that catalog as needed and run `python tools/update_api_reference.py` to refresh the API pages. The updater reads Python syntax without importing the application. It refuses missing modules/classes/selected methods rather than inventing descriptions. Review the generated diff, then run the read-only checks above.

The link checker covers local files, Markdown heading anchors, and source-line bounds in the wiki and README. It skips fenced code examples and external URLs. It does not verify the meaning of a claim, test a download, or replace a rendered-page review. Its Markdown handling is intentionally limited to the ordinary inline links and headings used by this documentation; extend it before introducing unsupported link syntax.

Also review:

1. The path through Home → Quick Start → the next detailed guide.
2. A user task from prerequisites through a saved/exported result.
3. Source-derived parameter values and output definitions.
4. Tables, code fences, diagrams, and image sizes in rendered Markdown.
5. External release/download links changed by this update.
6. The diff for private information and unrelated application changes.

Run application tests when behavior or examples depend on changed application code. A prose-only update does not require repeating the entire GUI test suite; link checks alone do not establish factual accuracy either.

## Publish to the GitHub Wiki

GitHub maintains the wiki in `https://github.com/bochens/Icescopy.wiki.git`. See [GitHub's editing instructions](https://docs.github.com/en/communities/documenting-your-project-with-wikis/adding-or-editing-wiki-pages).

1. Review and commit the documentation in the application repository. Publish that commit so source and screenshot links can resolve.
2. Run the documentation checks.
3. Stage a converted copy in a **new directory**. Supply the full published application commit as `--source-ref`:

   ```bash
   python tools/wiki_docs.py stage --destination /path/to/new-wiki-stage --source-ref <full-40-character-commit>
   ```

4. Clone or update the separate wiki repository. Review any remote changes before applying the staged files.
5. Copy the staged Markdown files into that checkout. Inspect its diff, including `_Sidebar.md` and `_Footer.md`. Preserve existing page URLs and review any proposed removal separately.
6. Commit and push the wiki update.
7. Open Home, a workflow page, an API source link, and a screenshot in the published wiki. Verify navigation and rendering.

The staging command converts intra-wiki `.md` links to wiki page routes, repository links to GitHub file URLs, and image links to raw asset URLs. Source and image links are pinned to the supplied commit so a later code change does not silently invalidate a line reference or screenshot.

The command does not publish, modify the source pages, overwrite an existing staging directory, or delete older wiki pages. It requires a locally available commit containing the current wiki pages and linked files, and refuses differences from that commit. It does not contact GitHub to verify publication; confirm the commit is pushed before publishing the wiki.

## Keep historical records distinct

Preserve dated investigation notes when they explain a fix or limitation. Mark their scope and point readers to current instructions. Avoid placing old test-build status alongside installation steps as if it described the current release.

Related: [Developer Guide](Developer-Guide.md) | [Architecture Overview](Architecture-Overview.md) | [API Reference](API-Reference.md)
