#!/usr/bin/env python3
"""Render a Markdown manuscript to PDF with deterministic local asset handling."""

from __future__ import annotations

import argparse
import hashlib
import html
import re
import sys
from pathlib import Path
from typing import Iterable

import fitz
import markdown
from bs4 import BeautifulSoup, NavigableString, Tag
from pypdf import PdfReader, PdfWriter
from weasyprint import CSS, HTML


IMAGE_PATTERN = re.compile(
    r"!\[(?P<alt>[^\]]*)\]\((?P<src>[^)\s]+)(?:\s+\"(?P<title>[^\"]+)\")?\)"
    r"(?P<attrs>\{[^}]*\})?"
)
WIDTH_PATTERN = re.compile(r"width\s*=\s*([0-9.]+%?)")
HEIGHT_PATTERN = re.compile(r"height\s*=\s*([0-9.]+%?)")
FIGURE_CAPTION_RE = re.compile(r"^Figure\s+\d+[A-Za-z]?\.", re.IGNORECASE)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Render a Markdown manuscript to PDF using the scientific-writing-workbench pipeline."
    )
    parser.add_argument("input", help="Input Markdown file")
    parser.add_argument(
        "-o",
        "--output",
        help="Output PDF path (defaults to input stem with .pdf)",
    )
    parser.add_argument(
        "--title",
        help="Explicit PDF metadata title (defaults to first H1 or input stem)",
    )
    return parser.parse_args()


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


def parse_image_attrs(raw_attrs: str | None) -> dict[str, str]:
    attrs: dict[str, str] = {}
    if not raw_attrs:
        return attrs
    width_match = WIDTH_PATTERN.search(raw_attrs)
    height_match = HEIGHT_PATTERN.search(raw_attrs)
    if width_match:
        attrs["width"] = width_match.group(1)
    if height_match:
        attrs["height"] = height_match.group(1)
    return attrs


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


def convert_pdf_figure_to_svg(asset_path: Path, cache_dir: Path) -> Path:
    digest = file_digest(asset_path)
    svg_path = cache_dir / f"{asset_path.stem}-{digest}.svg"
    if svg_path.exists():
        return svg_path

    with fitz.open(asset_path) as document:
        if document.page_count == 0:
            raise ValueError(f"PDF figure has no pages: {asset_path}")
        svg_text = document[0].get_svg_image(text_as_path=False)
    svg_path.write_text(svg_text, encoding="utf-8")
    return svg_path


def normalize_asset(asset_path: Path, cache_dir: Path) -> Path:
    if asset_path.suffix.lower() == ".pdf":
        return convert_pdf_figure_to_svg(asset_path, cache_dir)
    return asset_path


def image_replacer(match: re.Match[str], base_dir: Path, cache_dir: Path) -> str:
    alt_text = match.group("alt") or ""
    src = match.group("src")
    title = match.group("title")
    attrs = parse_image_attrs(match.group("attrs"))

    source_path = (base_dir / src).resolve()
    chosen_asset = normalize_asset(preferred_asset(source_path), cache_dir)

    attr_chunks = [f'src="{html.escape(chosen_asset.as_uri(), quote=True)}"']
    attr_chunks.append(f'alt="{html.escape(alt_text, quote=True)}"')
    if title:
        attr_chunks.append(f'title="{html.escape(title, quote=True)}"')
    if "width" in attrs:
        attr_chunks.append(f'style="width: {html.escape(attrs["width"], quote=True)};"')
    if "height" in attrs:
        style_index = next((i for i, value in enumerate(attr_chunks) if value.startswith("style=")), None)
        height_rule = f"height: {html.escape(attrs['height'], quote=True)};"
        if style_index is None:
            attr_chunks.append(f'style="{height_rule}"')
        else:
            current = attr_chunks[style_index][7:-1]
            attr_chunks[style_index] = f'style="{current} {height_rule}"'
    return f"<img {' '.join(attr_chunks)} />"


def preprocess_markdown(markdown_text: str, base_dir: Path, cache_dir: Path) -> str:
    return IMAGE_PATTERN.sub(lambda match: image_replacer(match, base_dir, cache_dir), markdown_text)


def markdown_to_html(markdown_text: str) -> str:
    return markdown.markdown(
        markdown_text,
        extensions=[
            "extra",
            "tables",
            "attr_list",
            "sane_lists",
            "md_in_html",
        ],
        output_format="html5",
    )


def is_caption_paragraph(tag: Tag) -> bool:
    if tag.name != "p":
        return False
    strong = tag.find("strong", recursive=False)
    if strong is None:
        return False
    text = strong.get_text(" ", strip=True)
    return bool(FIGURE_CAPTION_RE.match(text))


def wrap_figures(soup: BeautifulSoup) -> None:
    for paragraph in list(soup.find_all("p")):
        if paragraph.find("img", recursive=False) is None:
            continue
        next_node = paragraph.find_next_sibling()
        figure = soup.new_tag("figure")
        paragraph.wrap(figure)
        image = paragraph.find("img", recursive=False)
        if image is None:
            continue
        paragraph.replace_with(image.extract())
        if isinstance(next_node, Tag) and is_caption_paragraph(next_node):
            figcaption = soup.new_tag("figcaption")
            for child in list(next_node.contents):
                figcaption.append(child.extract())
            figure.append(figcaption)
            next_node.decompose()


def mark_references_section(soup: BeautifulSoup) -> None:
    for heading in soup.find_all(re.compile("^h[1-6]$")):
        if heading.get_text(" ", strip=True).lower() == "references":
            sibling = heading.find_next_sibling()
            while sibling is not None and sibling.name not in {"h1", "h2", "h3", "h4", "h5", "h6"}:
                if isinstance(sibling, Tag):
                    existing = sibling.get("class", [])
                    if "references" not in existing:
                        sibling["class"] = existing + ["references"]
                sibling = sibling.find_next_sibling()
            break


def resolve_title(soup: BeautifulSoup, input_path: Path, explicit_title: str | None) -> str:
    if explicit_title:
        return explicit_title
    first_h1 = soup.find("h1")
    if first_h1 is not None:
        return first_h1.get_text(" ", strip=True)
    return input_path.stem.replace("_", " ")


def build_html_document(body_html: str, css_path: Path, title: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{html.escape(title)}</title>
  <link rel="stylesheet" href="{css_path.resolve().as_uri()}" />
</head>
<body>
{body_html}
</body>
</html>
"""


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
    base_dir = input_path.parent.resolve()
    cache_dir = build_cache_dir(output_pdf)
    css_path = Path(__file__).resolve().parents[1] / "assets" / "pdf_style.css"

    markdown_text = input_path.read_text(encoding="utf-8")
    preprocessed = preprocess_markdown(markdown_text, base_dir, cache_dir)
    body_html = markdown_to_html(preprocessed)

    soup = BeautifulSoup(body_html, "html.parser")
    wrap_figures(soup)
    mark_references_section(soup)
    title = resolve_title(soup, input_path, explicit_title)

    html_text = build_html_document(str(soup), css_path, title)
    tmp_pdf = output_pdf.with_suffix(".tmp.pdf")
    HTML(string=html_text, base_url=base_dir.as_uri()).write_pdf(
        str(tmp_pdf),
        stylesheets=[CSS(filename=str(css_path))],
        full_fonts=True,
        hinting=True,
        optimize_images=False,
    )
    normalize_pdf_metadata(tmp_pdf, output_pdf, title)
    tmp_pdf.unlink(missing_ok=True)


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
