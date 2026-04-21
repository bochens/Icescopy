from __future__ import annotations

import re
import shutil
import subprocess
from dataclasses import dataclass
from datetime import date
from pathlib import Path


REPO_DIR = Path(__file__).resolve().parents[1]
MANUAL_DIR = REPO_DIR / "manual"
OUTPUT_PDF_DIR = REPO_DIR / "output" / "pdf"
OUTPUT_LATEX_DIR = REPO_DIR / "output" / "latex"
BUILD_DIR = OUTPUT_LATEX_DIR / "build"
GENERATED_DIR = OUTPUT_LATEX_DIR / "generated"
TEMPLATE_PATH = REPO_DIR / "documentation" / "latex" / "icescopy-manual-template.tex"
ICON_PATH = REPO_DIR / "resources" / "app_icons" / "IcescopyApp.png"
GENERATED_ICON_NAME = "IcescopyApp.png"

README_PATH = MANUAL_DIR / "README.md"
CHAPTER_PATHS = sorted(MANUAL_DIR.glob("[0-9][0-9]-*.md"))

TEX_SPECIALS = {
    "\\": r"\textbackslash{}",
    "&": r"\&",
    "%": r"\%",
    "$": r"\$",
    "#": r"\#",
    "_": r"\_",
    "{": r"\{",
    "}": r"\}",
    "~": r"\textasciitilde{}",
    "^": r"\textasciicircum{}",
}


@dataclass
class ManualSection:
    title: str
    path: Path
    content: str


def read_section(path: Path) -> ManualSection:
    content = path.read_text(encoding="utf-8")
    first_heading = next(
        (line[2:].strip() for line in content.splitlines() if line.startswith("# ")),
        path.stem,
    )
    return ManualSection(title=first_heading, path=path, content=content)


def remove_first_h1(content: str) -> str:
    lines = content.splitlines()
    for index, line in enumerate(lines):
        if line.startswith("# "):
            return "\n".join(lines[:index] + lines[index + 1 :]).lstrip("\n")
    return content


def strip_links(text: str) -> str:
    return re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", text)


def escape_latex(text: str) -> str:
    return "".join(TEX_SPECIALS.get(ch, ch) for ch in text)


def format_inline(text: str) -> str:
    text = strip_links(text)
    parts = re.split(r"(`[^`]+`)", text)
    rendered: list[str] = []
    for part in parts:
        if part.startswith("`") and part.endswith("`") and len(part) >= 2:
            rendered.append(r"\texttt{" + escape_latex(part[1:-1]) + "}")
        else:
            rendered.append(escape_latex(part))
    return "".join(rendered)


def slugify_pdf_name(path: Path) -> str:
    words = re.split(r"[-_]+", path.stem)
    suffix = "-".join(word.capitalize() for word in words)
    return f"Icescopy-Manual-{suffix}.pdf"


def is_label_line(text: str) -> bool:
    return bool(re.fullmatch(r"[A-Z][A-Za-z0-9 /-]{1,40}:", text))


def build_list(lines: list[str], ordered: bool) -> str:
    env = "enumerate" if ordered else "itemize"
    items = [r"\begin{" + env + r"}[leftmargin=*,itemsep=0.35em,topsep=0.4em]"]
    pattern = r"^\d+\.\s+" if ordered else r"^-\s+"
    for line in lines:
        item_text = re.sub(pattern, "", line.strip())
        items.append(r"\item " + format_inline(item_text))
    items.append(r"\end{" + env + "}")
    return "\n".join(items)


def build_code_block(lines: list[str]) -> str:
    code = "\n".join(lines).rstrip("\n")
    return "\n".join(
        [
            r"\begin{manualcode}",
            code,
            r"\end{manualcode}",
        ]
    )


def build_paragraph(lines: list[str]) -> str:
    text = " ".join(line.strip() for line in lines if line.strip())
    if is_label_line(text):
        return r"\manuallead{" + format_inline(text[:-1]) + "}"
    return format_inline(text) + "\n"


def markdown_to_latex(content: str, top_heading_command: str) -> str:
    lines = content.splitlines()
    blocks: list[str] = []
    index = 0

    while index < len(lines):
        stripped = lines[index].strip()
        if not stripped:
            index += 1
            continue

        if stripped.startswith("```"):
            index += 1
            code_lines: list[str] = []
            while index < len(lines) and not lines[index].strip().startswith("```"):
                code_lines.append(lines[index].rstrip("\n"))
                index += 1
            blocks.append(build_code_block(code_lines))
            index += 1
            continue

        if stripped.startswith("# "):
            blocks.append(
                "\\" + top_heading_command + "{" + format_inline(stripped[2:].strip()) + "}"
            )
            index += 1
            continue

        if stripped.startswith("## "):
            blocks.append(r"\section{" + format_inline(stripped[3:].strip()) + "}")
            index += 1
            continue

        if stripped.startswith("### "):
            blocks.append(r"\subsection{" + format_inline(stripped[4:].strip()) + "}")
            index += 1
            continue

        if re.match(r"^-\s+", stripped):
            list_lines: list[str] = []
            while index < len(lines) and re.match(r"^-\s+", lines[index].strip()):
                list_lines.append(lines[index].strip())
                index += 1
            blocks.append(build_list(list_lines, ordered=False))
            continue

        if re.match(r"^\d+\.\s+", stripped):
            list_lines = []
            while index < len(lines) and re.match(r"^\d+\.\s+", lines[index].strip()):
                list_lines.append(lines[index].strip())
                index += 1
            blocks.append(build_list(list_lines, ordered=True))
            continue

        paragraph_lines = [lines[index].strip()]
        index += 1
        while index < len(lines):
            next_stripped = lines[index].strip()
            if not next_stripped:
                break
            if (
                next_stripped.startswith("#")
                or next_stripped.startswith("```")
                or re.match(r"^-\s+", next_stripped)
                or re.match(r"^\d+\.\s+", next_stripped)
            ):
                break
            paragraph_lines.append(lines[index].strip())
            index += 1
        blocks.append(build_paragraph(paragraph_lines))

    return "\n\n".join(blocks).strip() + "\n"


def build_document_tex(
    *,
    title: str,
    subtitle: str,
    include_toc: bool,
    intro_content: str,
    body_content: str,
) -> str:
    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    replacements = {
        "@@MANUAL_TITLE@@": format_inline(title),
        "@@MANUAL_SUBTITLE@@": format_inline(subtitle),
        "@@MANUAL_DATE@@": escape_latex(date.today().isoformat()),
        "@@MANUAL_ICON_PATH@@": escape_latex(GENERATED_ICON_NAME),
        "@@MANUAL_INCLUDE_TOC@@": r"\tableofcontents" if include_toc else "",
        "@@MANUAL_FRONTMATTER@@": intro_content.strip(),
        "@@MANUAL_BODY@@": body_content.strip(),
    }
    for placeholder, value in replacements.items():
        template = template.replace(placeholder, value)
    return template


def run_tectonic(tex_path: Path, output_pdf_path: Path) -> None:
    BUILD_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_PDF_DIR.mkdir(parents=True, exist_ok=True)

    if shutil.which("tectonic") is None:
        raise RuntimeError("tectonic is not installed")

    for _ in range(2):
        subprocess.run(
            [
                "tectonic",
                "--keep-logs",
                "--keep-intermediates",
                "--outdir",
                str(BUILD_DIR),
                str(tex_path),
            ],
            cwd=REPO_DIR,
            check=True,
        )

    built_pdf = BUILD_DIR / (tex_path.stem + ".pdf")
    if not built_pdf.exists():
        raise RuntimeError(f"expected PDF was not produced: {built_pdf}")
    shutil.copy2(built_pdf, output_pdf_path)


def build_combined_manual(sections: list[ManualSection]) -> None:
    intro = read_section(README_PATH)
    intro_body = markdown_to_latex(remove_first_h1(intro.content), top_heading_command="chapter*")
    body = "\n\n".join(markdown_to_latex(section.content, "chapter") for section in sections)

    tex = build_document_tex(
        title="Icescopy Manual",
        subtitle="User guide for image-based freezing analysis",
        include_toc=True,
        intro_content=intro_body,
        body_content=body,
    )
    tex_path = GENERATED_DIR / "Icescopy-Manual.tex"
    tex_path.write_text(tex, encoding="utf-8")
    run_tectonic(tex_path, OUTPUT_PDF_DIR / "Icescopy-Manual.pdf")


def build_chapter_manuals(sections: list[ManualSection]) -> None:
    for section in sections:
        body = markdown_to_latex(section.content, "chapter")
        tex = build_document_tex(
            title=section.title,
            subtitle="Icescopy manual chapter",
            include_toc=False,
            intro_content="",
            body_content=body,
        )
        tex_path = GENERATED_DIR / f"{section.path.stem}.tex"
        tex_path.write_text(tex, encoding="utf-8")
        run_tectonic(tex_path, OUTPUT_PDF_DIR / slugify_pdf_name(section.path))


def main() -> None:
    OUTPUT_PDF_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_LATEX_DIR.mkdir(parents=True, exist_ok=True)
    GENERATED_DIR.mkdir(parents=True, exist_ok=True)
    BUILD_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ICON_PATH, GENERATED_DIR / GENERATED_ICON_NAME)

    sections = [read_section(path) for path in CHAPTER_PATHS]
    build_combined_manual(sections)
    build_chapter_manuals(sections)


if __name__ == "__main__":
    main()
