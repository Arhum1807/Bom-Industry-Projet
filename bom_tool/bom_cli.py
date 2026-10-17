#!/usr/bin/env python3
"""
bom_cli.py - Engineering Drawing PDF Material Requirements Report Generator

Usage:
  python bom_cli.py <drawing.pdf>
  python bom_cli.py <drawing.pdf> --output <report.pdf>
  python bom_cli.py <drawing.pdf> --debug
  python bom_cli.py --batch <directory/> [--output-dir <reports/>]
  python bom_cli.py --help
"""

import sys
import os
import argparse
import json
from pathlib import Path

TOOL_DIR = Path(__file__).parent
sys.path.insert(0, str(TOOL_DIR))

from bom_extractor import extract_drawing_data
from material_grouper import group_bom_items, get_section_summary
from report_generator import generate_report, generate_annotated_pdf, generate_cad_drawing_with_bom


# ── Banner ──────────────────────────────────────────────────────────────────

def print_header():
    print()
    print("=" * 65)
    print("  BOM ANALYSER  –  Engineering Drawing Material Report Tool")
    print("  Isgec Heavy Engineering Ltd. | Adani Port Projects")
    print("=" * 65)
    print()


# ── Console summary ─────────────────────────────────────────────────────────

def print_summary(data, grouped):
    tb = data.title_block
    print(f"  Document ID   : {tb.document_id}")
    print(f"  Title         : {tb.title_line1}")
    if tb.title_line2:
        print(f"                  {tb.title_line2}")
    print(f"  Project ID    : {tb.project_id}")
    print(f"  Element ID    : {tb.element_id}")
    print(f"  Revision      : {tb.revision}  |  Date: {tb.date}")
    print(f"  Scale         : {tb.scale}  |  Weight: {tb.total_weight_kg} kg")
    print(f"  Drawn By      : {tb.drawn_by}  |  Checked: {tb.checked_by}  |  Approved: {tb.approved_by}")
    print()
    print(f"  BoM items          : {len(data.bom_items)}")
    print(f"  Grouped materials  : {len(grouped)}")
    print(f"  Hardware items     : {len(data.hardware_items)}")
    print(f"  Reference drawings : {len(data.reference_drawings)}")
    print()


def print_grouped_summary(grouped):
    if not grouped:
        return
    print("  GROUPED MATERIALS:")
    print("  " + "-" * 60)
    for i, g in enumerate(grouped, 1):
        combined_note = f"  [COMBINED: {len(g.source_items)} parts]" if len(g.source_items) > 1 else ""
        print(f"  {i:2d}. {g.description:<20} {g.specification:<12} "
              f"{g.combined_size:<28} x{g.total_quantity:<4} "
              f"{g.total_weight_kg:>9.2f} kg{combined_note}")
    print()


def print_hardware_summary(items):
    if not items:
        return
    print("  HARDWARE REQUIREMENTS:")
    print("  " + "-" * 60)
    for hw in items:
        print(f"  [{hw.bolt_mark}] {hw.description:<47} x{hw.quantity:<5} {hw.uom}")
    print()


# ── JSON debug export ────────────────────────────────────────────────────────

def export_json(data, grouped, output_path):
    out = {
        'title_block': {
            'document_id'   : data.title_block.document_id,
            'title'         : f"{data.title_block.title_line1} {data.title_block.title_line2}".strip(),
            'project_id'    : data.title_block.project_id,
            'element_id'    : data.title_block.element_id,
            'revision'      : data.title_block.revision,
            'date'          : data.title_block.date,
            'scale'         : data.title_block.scale,
            'total_weight_kg': data.title_block.total_weight_kg,
            'drawn_by'      : data.title_block.drawn_by,
            'checked_by'    : data.title_block.checked_by,
            'approved_by'   : data.title_block.approved_by,
            'client'        : data.title_block.client,
            'consultant'    : data.title_block.consultant,
        },
        'bom_items': [
            {
                'item_no': b.item_no, 'description': b.description,
                'specification': b.specification, 'size': b.size,
                'quantity': b.quantity, 'part_weight_kg': b.part_weight_kg,
                'purchase_item_code': b.purchase_item_code,
            }
            for b in data.bom_items
        ],
        'grouped_materials': [
            {
                'purchase_item_code': g.purchase_item_code,
                'description'       : g.description,
                'specification'     : g.specification,
                'combined_size'     : g.combined_size,
                'total_quantity'    : g.total_quantity,
                'total_weight_kg'   : round(g.total_weight_kg, 3),
                'parts_combined'    : len(g.source_items),
                'source_item_nos'   : [s.item_no for s in g.source_items],
            }
            for g in grouped
        ],
        'hardware_items': [
            {
                'purchase_item_code': h.purchase_item_code,
                'description'       : h.description,
                'bolt_mark'         : h.bolt_mark,
                'quantity'          : h.quantity,
                'unit_weight_kg'    : h.unit_weight_kg,
            }
            for h in data.hardware_items
        ],
        'reference_drawings': [
            {'document_id': r.document_id, 'description': r.description}
            for r in data.reference_drawings
        ],
    }
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
    print(f"  JSON debug export: {output_path}")


# ── Core processing ──────────────────────────────────────────────────────────

def process_single(pdf_path, output_pdf=None, debug=False, output_dir=None):
    pdf_path = str(pdf_path)
    print(f"  Processing: {os.path.basename(pdf_path)}")
    print("  Extracting drawing data...", end='', flush=True)

    data = extract_drawing_data(pdf_path)
    print(" done.")

    grouped = group_bom_items(data.bom_items)

    print_summary(data, grouped)
    print_grouped_summary(grouped)
    print_hardware_summary(data.hardware_items)

    base = Path(pdf_path).stem
    out_dir = Path(output_dir) if output_dir else Path(pdf_path).parent
    out_dir.mkdir(parents=True, exist_ok=True)

    if not output_pdf:
        output_pdf = str(out_dir / f"{base}_REPORT.pdf")

    print("  Generating PDF report...", end='', flush=True)
    generate_report(data, output_pdf)
    print(" done.")
    print(f"\n  Report saved to: {output_pdf}")

    sec_summary = get_section_summary(data.bom_items)
    cad_bom_pdf = str(out_dir / f"{base}_WITH_BOM.pdf")
    print("  Generating drawing with BOM & SUMMARY tables (Feature 2)...", end='', flush=True)
    generate_cad_drawing_with_bom(pdf_path, data.bom_items, sec_summary, cad_bom_pdf)
    print(" done.")
    print(f"  Drawing with Generated BOM saved to: {cad_bom_pdf}")

    annotated_pdf = str(out_dir / f"{base}_ANNOTATED.pdf")
    generate_annotated_pdf(pdf_path, grouped, sec_summary, annotated_pdf, bom_items=data.bom_items)

    if debug:
        json_path = str(out_dir / f"{base}_debug.json")
        export_json(data, grouped, json_path)

    return output_pdf


def process_batch(input_dir, output_dir=None, debug=False):
    input_dir = Path(input_dir)
    # Skip any previously-generated REPORT pdfs
    pdfs = sorted(
        p for p in input_dir.glob("*.pdf")
        if '_REPORT' not in p.stem
    )

    if not pdfs:
        print(f"  No (non-report) PDF files found in: {input_dir}")
        return

    print(f"  Found {len(pdfs)} PDF file(s) to process.\n")

    success = 0
    failures = []
    for pdf in pdfs:
        print("  " + "-" * 60)
        try:
            process_single(str(pdf), output_dir=output_dir, debug=debug)
            success += 1
        except Exception as e:
            failures.append((str(pdf), str(e)))
            import traceback
            print(f"\n  FAILED: {pdf.name} -> {e}")
            traceback.print_exc()
            print()

    print("\n  " + "=" * 60)
    print(f"  Batch complete: {success}/{len(pdfs)} succeeded.")
    if failures:
        print("  Failed files:")
        for f, e in failures:
            print(f"    - {Path(f).name}: {e}")


# ── CLI entry point ──────────────────────────────────────────────────────────

def main():
    print_header()

    parser = argparse.ArgumentParser(
        prog='bom_cli',
        description='Engineering Drawing PDF – Material Requirements Report Generator',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python bom_cli.py drawing.pdf
  python bom_cli.py drawing.pdf -o custom_report.pdf
  python bom_cli.py drawing.pdf --debug
  python bom_cli.py --batch ./drawings/ --output-dir ./reports/
        """
    )
    parser.add_argument('pdf',          nargs='?', help='Input engineering drawing PDF')
    parser.add_argument('--output','-o',           help='Output PDF report path')
    parser.add_argument('--debug',  '-d', action='store_true',
                        help='Also export extracted data as JSON for debugging')
    parser.add_argument('--batch', '-b', metavar='DIR',
                        help='Process all PDFs in a directory (skips *_REPORT.pdf files)')
    parser.add_argument('--output-dir',  metavar='DIR',
                        help='Output directory for generated reports')

    args = parser.parse_args()

    if args.batch:
        process_batch(args.batch, output_dir=args.output_dir, debug=args.debug)
    elif args.pdf:
        if not os.path.isfile(args.pdf):
            print(f"  ERROR: File not found: {args.pdf}")
            sys.exit(1)
        process_single(args.pdf, output_pdf=args.output, debug=args.debug,
                       output_dir=args.output_dir)
    else:
        parser.print_help()


if __name__ == '__main__':
    main()