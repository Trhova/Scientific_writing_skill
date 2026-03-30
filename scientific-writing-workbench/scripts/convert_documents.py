#!/usr/bin/env python3
"""Convert common document formats into plain text or Markdown."""

from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Convert PDFs and office files into text or Markdown.")
    parser.add_argument("inputs", nargs="+", help="Input files to convert.")
    parser.add_argument("--output-dir", help="Directory for converted outputs.")
    parser.add_argument("--manifest", action="store_true", help="Emit a JSON conversion manifest to stderr.")
    return parser.parse_args()


def write_output(source: Path, content: str, output_dir: Path | None) -> None:
    if output_dir is None:
        print(f"# Source: {source}")
        print()
        print(content.rstrip())
        print()
        return
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{source.name}.md"
    output_path.write_text(content, encoding="utf-8")


def read_text_file(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="utf-8", errors="replace")


def convert_csv(path: Path) -> str:
    rows = []
    with open(path, newline="", encoding="utf-8") as handle:
        reader = csv.reader(handle)
        for row in reader:
            rows.append("| " + " | ".join(cell.strip() for cell in row) + " |")
    if not rows:
        return ""
    if len(rows) == 1:
        return rows[0]
    separator = "|" + "|".join([" --- " for _ in rows[0].split("|")[1:-1]]) + "|"
    return "\n".join([rows[0], separator, *rows[1:]])


def text_from_xml(xml_bytes: bytes) -> list[str]:
    root = ET.fromstring(xml_bytes)
    texts = []
    for element in root.iter():
        if element.text and element.text.strip():
            texts.append(element.text.strip())
    return texts


def convert_docx(path: Path) -> str:
    paragraphs = []
    with zipfile.ZipFile(path) as archive:
        xml_bytes = archive.read("word/document.xml")
        root = ET.fromstring(xml_bytes)
        namespace = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
        for paragraph in root.findall(".//w:p", namespace):
            parts = [node.text.strip() for node in paragraph.findall(".//w:t", namespace) if node.text and node.text.strip()]
            if parts:
                paragraphs.append("".join(parts))
    return "\n\n".join(paragraphs)


def convert_pptx(path: Path) -> str:
    slides = []
    with zipfile.ZipFile(path) as archive:
        slide_names = sorted(
            name for name in archive.namelist() if name.startswith("ppt/slides/slide") and name.endswith(".xml")
        )
        for index, slide_name in enumerate(slide_names, start=1):
            texts = text_from_xml(archive.read(slide_name))
            slides.append(f"## Slide {index}\n\n" + "\n".join(texts))
    return "\n\n".join(slides)


def convert_xlsx(path: Path) -> str:
    sections = []
    with zipfile.ZipFile(path) as archive:
        shared_strings = []
        if "xl/sharedStrings.xml" in archive.namelist():
            shared_root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
            shared_strings = text_from_xml(ET.tostring(shared_root, encoding="utf-8"))

        workbook = ET.fromstring(archive.read("xl/workbook.xml"))
        ns = {"x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main", "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships"}
        sheet_names = [sheet.attrib.get("name", f"Sheet{idx}") for idx, sheet in enumerate(workbook.findall(".//x:sheet", ns), start=1)]

        sheet_files = sorted(
            name for name in archive.namelist() if name.startswith("xl/worksheets/sheet") and name.endswith(".xml")
        )
        for index, sheet_file in enumerate(sheet_files):
            root = ET.fromstring(archive.read(sheet_file))
            rows = []
            for row in root.findall(".//x:row", ns):
                cells = []
                for cell in row.findall("x:c", ns):
                    value = cell.findtext("x:v", default="", namespaces=ns)
                    if cell.attrib.get("t") == "s" and value.isdigit():
                        numeric_index = int(value)
                        value = shared_strings[numeric_index] if numeric_index < len(shared_strings) else value
                    cells.append(value)
                if any(cell.strip() for cell in cells):
                    rows.append("| " + " | ".join(cells) + " |")
            title = sheet_names[index] if index < len(sheet_names) else f"Sheet{index + 1}"
            if rows:
                separator = "|" + "|".join([" --- " for _ in rows[0].split("|")[1:-1]]) + "|"
                sections.append(f"## {title}\n\n" + "\n".join([rows[0], separator, *rows[1:]]))
    return "\n\n".join(sections)


def convert_pdf(path: Path) -> tuple[str, list[str]]:
    warnings = []
    try:
        result = subprocess.run(
            ["pdftotext", "-layout", str(path), "-"],
            capture_output=True,
            text=True,
            check=True,
        )
        text = result.stdout.strip()
        if text:
            return text, warnings
    except (FileNotFoundError, subprocess.CalledProcessError):
        warnings.append("pdftotext unavailable or failed")

    for module_name in ("pypdf", "PyPDF2"):
        try:
            module = __import__(module_name)
            reader = module.PdfReader(str(path))
            pages = []
            for page_number, page in enumerate(reader.pages, start=1):
                extracted = page.extract_text() or ""
                pages.append(f"## Page {page_number}\n\n{extracted.strip()}")
            text = "\n\n".join(pages).strip()
            if text:
                warnings.append(f"used {module_name} fallback")
                return text, warnings
        except Exception:
            continue

    warnings.append("no PDF text extractor succeeded; scanned or image-only content may need OCR")
    return "", warnings


def convert_file(path: Path) -> tuple[str, list[str]]:
    suffix = path.suffix.lower()
    if suffix in {".txt", ".md"}:
        return read_text_file(path), []
    if suffix == ".csv":
        return convert_csv(path), []
    if suffix == ".docx":
        return convert_docx(path), []
    if suffix == ".pptx":
        return convert_pptx(path), []
    if suffix == ".xlsx":
        return convert_xlsx(path), ["formula logic is not reconstructed; visible cell values only"]
    if suffix == ".pdf":
        return convert_pdf(path)
    return "", [f"unsupported file type: {suffix or '<no suffix>'}"]


def main() -> int:
    args = parse_args()
    output_dir = Path(args.output_dir) if args.output_dir else None
    manifest = []
    failures = 0

    for raw_input in args.inputs:
        path = Path(raw_input)
        if not path.exists():
            print(f"warning: {path} does not exist", file=sys.stderr)
            manifest.append({"source": str(path), "status": "missing", "warnings": ["file does not exist"]})
            failures += 1
            continue

        try:
            content, warnings = convert_file(path)
        except (OSError, zipfile.BadZipFile, ET.ParseError) as exc:
            warnings = [str(exc)]
            content = ""

        status = "ok" if content else "warning"
        if not content:
            failures += 1
        else:
            write_output(path, content, output_dir)

        manifest.append({"source": str(path), "status": status, "warnings": warnings})

    if args.manifest:
        print(json.dumps(manifest, indent=2, ensure_ascii=True), file=sys.stderr)

    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
