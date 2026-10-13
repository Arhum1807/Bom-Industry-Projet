
# BOM Analyser – Engineering Drawing Material Report Generator

A complete web application and CLI tool that reads engineering drawing PDFs and images/scans (Isgec Heavy Engineering / Adani port project format), extracts the Bill of Materials (BoM), groups identical parts by part number, combines their dimensions intelligently, and generates a formatted PDF report.

---

## Web Application (Recommended)

1. Run the web server:
```bash
cd bom_tool
python app.py
```
2. Open in your browser: **[http://localhost:5050](http://localhost:5050)**
3. Drag and drop any engineering drawing PDF or image (JPG, PNG, TIFF, BMP, WEBP), or click **"📂 Browse Files"**.
4. The tool extracts, organizes, and displays all 6 parts of the engineering drawing:
   - **Part 1: 📄 Drawing Information** — Project metadata, Title block, and Revision history.
   - **Part 2: 🔩 Grouped Material Requirements** — Groups identical parts by part code and sums dimensions (e.g. 150x200x12THK + 69x200x12THK → 219x200x12THK) with an interactive detail panel.
   - **Part 3: 🔧 Hardware & Fastener Requirements** — Bolts, nuts, and washers with marks, quantities, and weights.
   - **Part 4: 📋 Raw Bill of Materials (BoM)** — The original drawing BoM in sequential numerical order.
   - **Part 5: 📦 Dispatch Units (Shipping Packages)** — Fabrication shipping unit breakdown (DU No., Description, Type, Weight, UOM, Code).
   - **Part 6: 🔗 Reference Drawings** — Document IDs and descriptions for cross-referenced drawings.
5. Download the complete generated **PDF Report** via the **"⬇ Download PDF Report"** button.

---

## Features

- **Automatic BoM extraction** from engineering drawing PDFs and images
- **Smart material grouping** by part number (`PURCHASE_ITEM_CODE`):
  - Plates with the same width and thickness have their lengths summed
    *(e.g. 150x200x12THK + 69x200x12THK → 219x200x12THK)*
  - Structural sections (UB, ISMC, ISA, etc.) have their lengths totalled
- **Hardware/fastener extraction** (bolts, nuts, washers)
- **Drawing title block extraction** (document ID, revision, drawn/checked/approved by, client, etc.)
- **Dispatch Unit extraction** (DU packages, weights, UOM)
- **Reference drawing list** extraction
- **Built-in PyMuPDF OCR** with bundled tessdata for image/scan processing
- **Batch processing CLI** – process an entire folder of PDFs at once
- **JSON debug export** for traceability

---

## CLI Usage

### Single drawing
```bash
python bom_cli.py path/to/drawing.pdf
```
Output: `path/to/drawing_REPORT.pdf` (same directory as input)

### Custom output path
```bash
python bom_cli.py drawing.pdf --output reports/my_report.pdf
```

### With debug JSON export
```bash
python bom_cli.py drawing.pdf --debug
```
Generates both `drawing_REPORT.pdf` and `drawing_debug.json`.

### Batch processing
```bash
python bom_cli.py --batch ./drawings/ --output-dir ./reports/
```

---

## Core Modules

| File | Description |
|------|-------------|
| [app.py](file:///c:/Users/Arhum/Downloads/project/bom_tool/app.py) | Flask web app server & API endpoints |
| [templates/index.html](file:///c:/Users/Arhum/Downloads/project/bom_tool/templates/index.html) | Interactive web UI with drag & drop upload |
| [image_extractor.py](file:///c:/Users/Arhum/Downloads/project/bom_tool/image_extractor.py) | Image conversion and PyMuPDF OCR processing |
| [bom_extractor.py](file:///c:/Users/Arhum/Downloads/project/bom_tool/bom_extractor.py) | PDF text extraction and BoM parsing |
| [material_grouper.py](file:///c:/Users/Arhum/Downloads/project/bom_tool/material_grouper.py) | Part grouping and dimension-combining logic |
| [report_generator.py](file:///c:/Users/Arhum/Downloads/project/bom_tool/report_generator.py) | ReportLab PDF report generation |
| [bom_cli.py](file:///c:/Users/Arhum/Downloads/project/bom_tool/bom_cli.py) | Main CLI entry point |