#!/usr/bin/env python3
"""Render a Markdown manuscript to PDF with the skill's official Pandoc pipeline."""

from __future__ import annotations

import argparse
import html
import hashlib
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import cairosvg
from pypdf import PdfReader, PdfWriter


IMAGE_PATTERN = re.compile(
    r"!\[(?P<alt>[^\]]*)\]\((?P<src>[^)\s]+)(?:\s+\"(?P<title>[^\"]+)\")?\)"
    r"(?P<attrs>\{[^}]*\})?"
)
SUP_PATTERN = re.compile(r"<sup>(.*?)</sup>", re.DOTALL)
WIDTH_PATTERN = re.compile(r"width\s*=\s*([0-9.]+%?)")
HEIGHT_PATTERN = re.compile(r"height\s*=\s*([0-9.]+%?)")
HEADING_PATTERN = re.compile(r"^\s{0,3}#{1,6}\s+")
RAW_PAGEBREAK_PATTERN = re.compile(r"^\s*\\newpage\s*$")
FIGURE_TITLE_PATTERN = re.compile(r"^\s*\*\*Figure\s+[A-Za-z]?\d+[A-Za-z]?.*", re.IGNORECASE)
STRUCTURAL_BREAK_PATTERN = re.compile(r"^\s{0,3}(#{1,6}\s+|!\[|```|:::|\|)")
CAPTION_CONTINUATION_PATTERN = re.compile(r"^\s*(\*\*)?\([A-Za-z0-9]+\)(\*\*)?\s*")


@dataclass
class FigureBlock:
    image_markdown: str
    image_path: Path
    width_hint: str | None
    height_hint: str | None
    caption_lines: list[str]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Render a Markdown manuscript to PDF using Pandoc + Tectonic."
    )
    parser.add_argument("input", help="Input Markdown file")
    parser.add_argument(
        "-o",
        "--output",
        help="Output PDF path (defaults to input stem with .pdf)",
    )
    parser.add_argument(
        "--title",
        help="Explicit title metadata. Defaults to the input stem.",
    )
    return parser.parse_args()


def env_bin_dir() -> Path:
    return Path(sys.executable).resolve().parent


def find_executable(name: str) -> str:
    candidate = env_bin_dir() / name
    if candidate.exists():
        return str(candidate)
    resolved = shutil.which(name)
    if resolved:
        return resolved
    raise FileNotFoundError(f"Required executable not found: {name}")


def build_cache_dir(output_pdf: Path) -> Path:
    cache_dir = output_pdf.parent / ".render_pdf_cache" / output_pdf.stem
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir


def file_digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()[:16]


def parse_image_attrs(raw_attrs: str | None) -> tuple[str | None, str | None]:
    if not raw_attrs:
        return None, None
    width_match = WIDTH_PATTERN.search(raw_attrs)
    height_match = HEIGHT_PATTERN.search(raw_attrs)
    width = width_match.group(1) if width_match else None
    height = height_match.group(1) if height_match else None
    return width, height


def preferred_asset(source: Path) -> Path:
    candidates: list[Path] = []
    for suffix in (".pdf", ".svg"):
        sibling = source.with_suffix(suffix)
        if sibling.exists() and sibling != source:
            candidates.append(sibling)
    if source.exists():
        candidates.append(source)
    for candidate in candidates:
        if candidate.exists():
            return candidate
    raise FileNotFoundError(f"Missing figure asset: {source}")


def svg_to_pdf(asset_path: Path, cache_dir: Path) -> Path:
    digest = file_digest(asset_path)
    pdf_path = cache_dir / f"{asset_path.stem}-{digest}.pdf"
    if pdf_path.exists():
        return pdf_path
    cairosvg.svg2pdf(url=str(asset_path), write_to=str(pdf_path))
    return pdf_path


def normalize_asset(asset_path: Path, cache_dir: Path) -> Path:
    if asset_path.suffix.lower() == ".svg":
        return svg_to_pdf(asset_path, cache_dir)
    return asset_path


def rewrite_superscripts(markdown_text: str) -> str:
    rewritten = SUP_PATTERN.sub(lambda match: f"^{match.group(1).strip()}^", markdown_text)
    return re.sub(r"(?<=\S)\s+\^([^^]+)\^", r"^\1^", rewritten)


def resolve_image_markdown(
    image_markdown: str,
    *,
    input_dir: Path,
    cache_dir: Path,
) -> tuple[str, Path, str | None, str | None]:
    match = IMAGE_PATTERN.fullmatch(image_markdown.strip())
    if match is None:
        raise ValueError(f"Unsupported image syntax: {image_markdown}")

    alt_text = match.group("alt") or ""
    src = match.group("src")
    title = match.group("title")
    width, height = parse_image_attrs(match.group("attrs"))

    chosen = normalize_asset(preferred_asset((input_dir / src).resolve()), cache_dir)
    rel_path = Path(shutil.os.path.relpath(chosen, input_dir))

    normalized = f"![{alt_text}](<{rel_path.as_posix()}>)"
    attr_parts: list[str] = []
    if width:
        attr_parts.append(f"width={width}")
    if height:
        attr_parts.append(f"height={height}")
    if attr_parts:
        normalized += "{" + " ".join(attr_parts) + "}"
    if title:
        normalized += f' <!-- title: {title} -->'
    return normalized, rel_path, width, height


def is_caption_start(line: str) -> bool:
    return bool(FIGURE_TITLE_PATTERN.match(line))


def is_structural_break(line: str) -> bool:
    return bool(STRUCTURAL_BREAK_PATTERN.match(line))


def find_figure_block(lines: list[str], start: int) -> tuple[FigureBlock, int] | None:
    image_line = lines[start].strip()
    if IMAGE_PATTERN.fullmatch(image_line) is None:
        return None
    if start + 1 >= len(lines):
        return None

    caption_start = start + 1
    while caption_start < len(lines) and lines[caption_start].strip() == "":
        caption_start += 1
    if caption_start >= len(lines) or not is_caption_start(lines[caption_start]):
        return None

    caption_lines: list[str] = []
    index = caption_start
    pending_blank = False
    while index < len(lines):
        stripped = lines[index].strip()
        if stripped == "":
            pending_blank = True
            index += 1
            continue
        if index > caption_start and is_structural_break(lines[index]):
            break
        if pending_blank and caption_lines and not CAPTION_CONTINUATION_PATTERN.match(stripped):
            break
        if pending_blank and caption_lines:
            caption_lines.append("")
        caption_lines.append(lines[index].rstrip())
        pending_blank = False
        index += 1

    return FigureBlock(
        image_markdown=image_line,
        image_path=Path(),
        width_hint=None,
        height_hint=None,
        caption_lines=caption_lines,
    ), index


def latex_escape(text: str) -> str:
    replacements = {
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
    return "".join(replacements.get(char, char) for char in text)


def markdown_inline_to_latex(text: str) -> str:
    text = html.unescape(text.strip())
    placeholders: list[str] = []

    def stash(rendered: str) -> str:
        placeholders.append(rendered)
        return f"@@PLACEHOLDER{len(placeholders) - 1}@@"

    patterns = [
        (r"`([^`]+)`", lambda match: r"\texttt{" + latex_escape(match.group(1)) + "}"),
        (r"\*\*([^*]+)\*\*", lambda match: r"\textbf{" + markdown_inline_to_latex(match.group(1)) + "}"),
        (r"(?<!\*)\*([^*]+)\*(?!\*)", lambda match: r"\emph{" + markdown_inline_to_latex(match.group(1)) + "}"),
        (r"\^([^^]+)\^", lambda match: r"\textsuperscript{" + latex_escape(match.group(1)) + "}"),
    ]

    transformed = re.sub(
        r"\\([\\`*_{}\[\]()#+\-.!^<>])",
        lambda match: stash(latex_escape(match.group(1))),
        text,
    )
    for pattern, renderer in patterns:
        transformed = re.sub(pattern, lambda match: stash(renderer(match)), transformed)

    transformed = latex_escape(transformed)
    for index, rendered in enumerate(placeholders):
        transformed = transformed.replace(latex_escape(f"@@PLACEHOLDER{index}@@"), rendered)
    return transformed


def caption_lines_to_latex(lines: list[str]) -> str:
    chunks: list[str] = []
    paragraph: list[str] = []
    for line in lines:
        if line.strip() == "":
            if paragraph:
                chunks.append(" ".join(part.strip() for part in paragraph if part.strip()))
                paragraph = []
            continue
        paragraph.append(line.strip())
    if paragraph:
        chunks.append(" ".join(part.strip() for part in paragraph if part.strip()))

    latex_paragraphs = []
    for chunk in chunks:
        converted = markdown_inline_to_latex(chunk)
        latex_paragraphs.append(converted)
    return "\n\n".join(latex_paragraphs)


def split_caption_latex(caption_latex: str) -> tuple[str, str]:
    paragraphs = [part.strip() for part in caption_latex.split("\n\n") if part.strip()]
    if not paragraphs:
        return "", ""
    lead = paragraphs[0]
    rest = "\n\n".join(paragraphs[1:]) if len(paragraphs) > 1 else ""
    return lead, rest


def width_hint_to_fraction(width_hint: str | None, fallback: float) -> float:
    if width_hint is None:
        return fallback
    if width_hint.endswith("%"):
        try:
            fraction = float(width_hint[:-1]) / 100.0
            return min(max(fraction, 0.45), 1.0)
        except ValueError:
            return fallback
    return fallback


def build_figure_block_latex(block: FigureBlock) -> str:
    caption_text = " ".join(line.strip() for line in block.caption_lines if line.strip())
    caption_length = len(caption_text)
    caption_paragraphs = sum(1 for line in block.caption_lines if line.strip() == "") + 1
    dedicated_page = caption_length > 360 or caption_paragraphs > 1

    image_width = width_hint_to_fraction(block.width_hint, 1.0)
    if dedicated_page:
        image_width = min(image_width, 1.0)
        image_height = "0.88\\textheight"
        command = "thesisfigurepage"
    else:
        image_width = min(image_width, 1.0)
        image_height = "0.84\\textheight"
        command = "thesisfigureblock"

    caption_latex = caption_lines_to_latex(block.caption_lines)
    lead_latex, rest_latex = split_caption_latex(caption_latex)
    return (
        "\n```{=latex}\n"
        f"\\{command}{{{image_width:.2f}\\linewidth}}{{{image_height}}}{{{latex_escape(block.image_path.as_posix())}}}{{%\n"
        f"{lead_latex}\n"
        "}{%\n"
        f"{rest_latex}\n"
        "}\n"
        "```\n"
    )


def preprocess_markdown(markdown_text: str, *, input_dir: Path, scratch_dir: Path, cache_dir: Path) -> str:
    text = rewrite_superscripts(markdown_text)
    lines = text.splitlines()
    output: list[str] = []
    index = 0

    while index < len(lines):
        line = lines[index]
        if RAW_PAGEBREAK_PATTERN.match(line):
            output.extend(["", r"\newpage", ""])
            index += 1
            continue

        figure_match = find_figure_block(lines, index)
        if figure_match is not None:
            block, next_index = figure_match
            normalized_image, image_path, width_hint, height_hint = resolve_image_markdown(
                block.image_markdown,
                input_dir=input_dir,
                cache_dir=cache_dir,
            )
            block.image_markdown = normalized_image
            block.image_path = image_path
            block.width_hint = width_hint
            block.height_hint = height_hint
            output.append(build_figure_block_latex(block))
            output.append("")
            index = next_index
            continue

        if IMAGE_PATTERN.fullmatch(line.strip()) is not None:
            normalized_image, _, _, _ = resolve_image_markdown(
                line.strip(),
                input_dir=input_dir,
                cache_dir=cache_dir,
            )
            output.append(normalized_image)
            index += 1
            continue

        output.append(line)
        index += 1

    return "\n".join(output) + "\n"


def normalize_pdf_metadata(source_pdf: Path, output_pdf: Path, title: str) -> None:
    reader = PdfReader(str(source_pdf))
    writer = PdfWriter()
    for page in reader.pages:
        writer.add_page(page)
    writer.add_metadata(
        {
            "/Title": title,
            "/Producer": "scientific-writing-workbench render_pdf.py",
            "/Creator": "scientific-writing-workbench render_pdf.py",
        }
    )
    with output_pdf.open("wb") as handle:
        writer.write(handle)


def render_pdf(input_path: Path, output_pdf: Path, explicit_title: str | None) -> None:
    pandoc_bin = find_executable("pandoc")
    tectonic_bin = find_executable("tectonic")
    input_dir = input_path.parent.resolve()
    output_pdf = output_pdf.resolve()
    cache_dir = build_cache_dir(output_pdf)
    scratch_dir = cache_dir / "work"
    scratch_dir.mkdir(parents=True, exist_ok=True)

    header_path = Path(__file__).resolve().parents[1] / "assets" / "pandoc_header.tex"

    preprocessed = preprocess_markdown(
        input_path.read_text(encoding="utf-8"),
        input_dir=input_dir,
        scratch_dir=scratch_dir,
        cache_dir=cache_dir,
    )
    temp_md = scratch_dir / f"{input_path.stem}.md"
    temp_pdf = scratch_dir / f"{input_path.stem}.pdf"
    temp_md.write_text(preprocessed, encoding="utf-8")

    metadata_title = explicit_title or input_path.stem.replace("_", " ")
    command = [
        pandoc_bin,
        str(temp_md),
        "--standalone",
        "--from=markdown+raw_tex+raw_html+superscript",
        "--output",
        str(temp_pdf),
        "--pdf-engine",
        tectonic_bin,
        "--include-in-header",
        str(header_path),
        "--resource-path",
        f"{scratch_dir}:{input_dir}",
        "-V",
        "papersize:letter",
        "-V",
        "colorlinks=true",
        "-V",
        "linkcolor=blue",
        "-V",
        "urlcolor=blue",
    ]
    subprocess.run(command, cwd=str(input_dir), check=True)
    normalize_pdf_metadata(temp_pdf, output_pdf, metadata_title)


def main() -> int:
    args = parse_args()
    input_path = Path(args.input).resolve()
    if not input_path.exists():
        raise SystemExit(f"Input file not found: {input_path}")
    output_pdf = Path(args.output).resolve() if args.output else input_path.with_suffix(".pdf")
    output_pdf.parent.mkdir(parents=True, exist_ok=True)

    render_pdf(input_path, output_pdf, args.title)
    print(output_pdf)
    return 0


if __name__ == "__main__":
    sys.exit(main())
