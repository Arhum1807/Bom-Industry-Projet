
# BOM Analyser & CAD Drawing Generator

A comprehensive engineering tool that provides two core features for engineering drawings and CAD diagrams (Isgec Heavy Engineering / Adani port project format):

1. **Feature 1: 📊 Material Requirements Report & Grouping Analysis**
   - Automatically extracts the Bill of Materials (BoM), Title Block metadata, Hardware, Dispatch Units, and Reference Drawings.
   - Smart material grouping by Purchase Item Code (`PURCHASE_ITEM_CODE`) with intelligent dimension combining (e.g. `150x200x12THK` + `69x200x12THK` → `219x200x12THK`).
   - Generates a full 5-page PDF **Material Requirements Report** and an Excel spreadsheet (`.xlsx`).

2. **Feature 2: 📐 CAD Drawing BOM Generator (Generate BOM on CAD Sheet)**
   - When only CAD diagrams are given without a BOM table (or when updating drawings), this feature analyzes the CAD diagram and generates both the **GENERATED BILL OF MATERIALS ** table and the **SUMMARY** table directly onto the CAD sheet on the side (above the title block and beside drawings).
   - Produces a production-grade stamped CAD Drawing PDF (`[Drawing_ID]_WITH_BOM.pdf`) ready for manufacturing and fabrication.
   - Provides an interactive visual inspection viewer with zoom controls directly in the browser.

---

## Web Application (Recommended)

1. Run the web server:
```bash
cd bom_tool
python app.py
```
2. Open in your browser: **[http://localhost:5050](http://localhost:5050)**
3. Use the top feature switcher to select:
   - **Feature 1**: 📊 Material Report (PDF & Excel)
   - **Feature 2**: 📐 CAD Drawing BOM (On-Sheet Table Stamping & Preview)
4. Drag and drop any engineering drawing PDF or image (JPG, PNG, TIFF, BMP, WEBP), or click **"📂 Browse Drawing File"**.
5. Switch effortlessly between the **Interactive CAD Sheet View** (with the stamped BOM on the side) and the **Full Material Requirements Breakdown**.
6. Download outputs:
   - `⬇ Download CAD Drawing with Generated BOM (PDF)`
   - `📄 Full Text Report (PDF)`
   - `📊 Download Excel Report (.xlsx)`

---

## CLI Usage

### Single drawing (generates both Report & CAD Drawing with BOM)
```bash
python bom_cli.py path/to/drawing.pdf
```
Outputs:
- `path/to/drawing_REPORT.pdf` (Feature 1: 5-page Material Requirements Report)
- `path/to/drawing_WITH_BOM.pdf` (Feature 2: CAD drawing with BOM and SUMMARY tables stamped on the side)
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