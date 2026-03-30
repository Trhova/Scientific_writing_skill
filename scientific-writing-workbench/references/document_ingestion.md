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

1. Convert documents into clean Markdown or structured text.
2. Preserve page, slide, or sheet provenance where practical.
3. Record any extraction failures or ambiguities instead of silently dropping content.

## Converter behavior

The bundled `scripts/convert_documents.py` script:

- reads plain text formats directly
- extracts OOXML content from DOCX, PPTX, and XLSX without heavy dependencies
- tries `pdftotext`, then `pypdf`, then `PyPDF2` for PDFs if available
- writes Markdown or text output plus a manifest of warnings and failures

## Graceful failure rules

- If embedded images, equations, comments, or tracked changes cannot be extracted reliably, say so.
- If a PDF is image-only and OCR is unavailable, report that text extraction is incomplete.
- If spreadsheet formulas cannot be reconstructed, extract visible cell values and note the limitation.

## Downstream use

After conversion:

- extract identifiers with `scripts/extract_metadata.py`
- build evidence maps from the cleaned text
- cite converted documents as working evidence, not as final bibliographic records, unless formal metadata is later confirmed
