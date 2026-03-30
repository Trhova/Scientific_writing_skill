# Document Ingestion

Use this reference when the source material is in external document formats.

## Supported inputs

- PDF
- DOCX
- PPTX
- XLSX
- CSV
- TXT
- Markdown

## Preferred workflow

1. Resolve the paper or document record first when the input is supposed to be a scientific paper. Use `scripts/paper_access.py`.
2. Convert documents into clean Markdown or structured text.
3. Preserve page, slide, or sheet provenance where practical.
4. Record any extraction failures or ambiguities instead of silently dropping content.

## Converter behavior

The bundled `scripts/convert_documents.py` script:

- reads plain text formats directly
- extracts OOXML content from DOCX, PPTX, and XLSX without heavy dependencies
- tries `pdftotext`, then `mutool`, then `pymupdf`, then `pypdf`, then `pdfplumber` for PDFs if available
- can expose OCR as an explicit fallback, but OCR is off by default
- writes Markdown or text output plus a manifest of warnings and failures

## Graceful failure rules

- If embedded images, equations, comments, or tracked changes cannot be extracted reliably, say so.
- If a PDF is image-only and OCR is unavailable, report that text extraction is incomplete.
- If a PDF fails ordinary extraction and OCR is disabled, report that OCR would be needed rather than pretending full text was read.
- If spreadsheet formulas cannot be reconstructed, extract visible cell values and note the limitation.

## Downstream use

After conversion:

- extract identifiers with `scripts/extract_metadata.py`
- if the source is meant to function as a paper, keep the paper access state from `scripts/paper_access.py`
- build evidence maps from the cleaned text
- cite converted documents as working evidence, not as final bibliographic records, unless formal metadata is later confirmed
