#!/usr/bin/env python3
"""Render a Markdown manuscript to PDF with the skill's official Pandoc pipeline."""

from __future__ import annotations

import argparse
import hashlib
import re
import shutil
import subprocess
import sys
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
    return SUP_PATTERN.sub(lambda match: f"^{match.group(1).strip()}^", markdown_text)


def image_replacer(
    match: re.Match[str],
    *,
    input_dir: Path,
    scratch_dir: Path,
    cache_dir: Path,
) -> str:
    alt_text = match.group("alt") or ""
    src = match.group("src")
    title = match.group("title")
    width, height = parse_image_attrs(match.group("attrs"))

    chosen = normalize_asset(preferred_asset((input_dir / src).resolve()), cache_dir)
    rel_path = Path(shutil.os.path.relpath(chosen, scratch_dir))

    image_md = f"![{alt_text}](<{rel_path.as_posix()}>)"
    attr_parts: list[str] = []
    if width:
        attr_parts.append(f"width={width}")
    if height:
        attr_parts.append(f"height={height}")
    if attr_parts:
        image_md += "{" + " ".join(attr_parts) + "}"
    if title:
        image_md += f' <!-- title: {title} -->'
    return image_md


def preprocess_markdown(markdown_text: str, *, input_dir: Path, scratch_dir: Path, cache_dir: Path) -> str:
    text = rewrite_superscripts(markdown_text)
    return IMAGE_PATTERN.sub(
        lambda match: image_replacer(match, input_dir=input_dir, scratch_dir=scratch_dir, cache_dir=cache_dir),
        text,
    )


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
        "--from=markdown+raw_html+superscript",
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
