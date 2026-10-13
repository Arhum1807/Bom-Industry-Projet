"""
report_generator.py
Generates a beautifully formatted PDF report from DrawingData using ReportLab.
"""
import os
from datetime import datetime
from typing import Optional
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm, cm
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, KeepTogether, PageBreak
)
from reportlab.platypus.flowables import HRFlowable
from reportlab.lib.colors import HexColor, white, black

from bom_extractor import DrawingData, BomItem, HardwareItem
from material_grouper import group_bom_items, GroupedMaterial, get_section_summary, SectionSummary


# ---------------------------------------------------------------------------
# Colour palette
# ---------------------------------------------------------------------------
NAVY        = HexColor('#0D1B2A')
STEEL_BLUE  = HexColor('#1B4F72')
ACCENT_BLUE = HexColor('#2874A6')
LIGHT_BLUE  = HexColor('#D6EAF8')
MID_BLUE    = HexColor('#5DADE2')
DARK_GREY   = HexColor('#2C3E50')
MID_GREY    = HexColor('#7F8C8D')
LIGHT_GREY  = HexColor('#ECF0F1')
ORANGE      = HexColor('#E67E22')
GREEN       = HexColor('#1E8449')
WHITE       = white
BLACK       = black

PAGE_W, PAGE_H = A4


# ---------------------------------------------------------------------------
# Styles
# ---------------------------------------------------------------------------

def _make_styles():
    base = getSampleStyleSheet()

    styles = {
        'cover_title': ParagraphStyle('cover_title',
            parent=base['Title'],
            fontSize=28,
            textColor=WHITE,
            leading=34,
            alignment=TA_CENTER,
            fontName='Helvetica-Bold',
            spaceAfter=8,
        ),
        'cover_subtitle': ParagraphStyle('cover_subtitle',
            fontSize=14,
            textColor=HexColor('#BDC3C7'),
            leading=18,
            alignment=TA_CENTER,
            fontName='Helvetica',
        ),
        'cover_meta': ParagraphStyle('cover_meta',
            fontSize=11,
            textColor=HexColor('#AEB6BF'),
            leading=16,
            alignment=TA_CENTER,
            fontName='Helvetica',
        ),
        'section_heading': ParagraphStyle('section_heading',
            fontSize=15,
            textColor=WHITE,
            leading=20,
            fontName='Helvetica-Bold',
            spaceBefore=4,
            spaceAfter=2,
        ),
        'subsection': ParagraphStyle('subsection',
            fontSize=11,
            textColor=STEEL_BLUE,
            leading=15,
            fontName='Helvetica-Bold',
            spaceBefore=6,
            spaceAfter=3,
        ),
        'body': ParagraphStyle('body',
            fontSize=9,
            textColor=DARK_GREY,
            leading=13,
            fontName='Helvetica',
        ),
        'label': ParagraphStyle('label',
            fontSize=8,
            textColor=MID_GREY,
            leading=11,
            fontName='Helvetica',
        ),
        'value': ParagraphStyle('value',
            fontSize=9,
            textColor=DARK_GREY,
            leading=13,
            fontName='Helvetica-Bold',
        ),
        'table_header': ParagraphStyle('table_header',
            fontSize=8,
            textColor=WHITE,
            leading=11,
            fontName='Helvetica-Bold',
            alignment=TA_CENTER,
        ),
        'table_cell': ParagraphStyle('table_cell',
            fontSize=8,
            textColor=DARK_GREY,
            leading=11,
            fontName='Helvetica',
        ),
        'table_cell_bold': ParagraphStyle('table_cell_bold',
            fontSize=8,
            textColor=DARK_GREY,
            leading=11,
            fontName='Helvetica-Bold',
        ),
        'table_cell_center': ParagraphStyle('table_cell_center',
            fontSize=8,
            textColor=DARK_GREY,
            leading=11,
            fontName='Helvetica',
            alignment=TA_CENTER,
        ),
        'note': ParagraphStyle('note',
            fontSize=8,
            textColor=MID_GREY,
            leading=11,
            fontName='Helvetica-Oblique',
        ),
        'footer': ParagraphStyle('footer',
            fontSize=7,
            textColor=MID_GREY,
            leading=9,
            fontName='Helvetica',
            alignment=TA_CENTER,
        ),
    }
    return styles


# ---------------------------------------------------------------------------
# Header/Footer canvas
# ---------------------------------------------------------------------------

def _on_page(canvas, doc, data: DrawingData, styles):
    """Called for each page to draw fixed header and footer."""
    canvas.saveState()

    W, H = PAGE_W, PAGE_H
    margin = 15*mm

    # --- Header bar ---
    canvas.setFillColor(NAVY)
    canvas.rect(0, H - 18*mm, W, 18*mm, fill=1, stroke=0)

    canvas.setFont('Helvetica-Bold', 9)
    canvas.setFillColor(WHITE)
    canvas.drawString(margin, H - 11*mm, data.title_block.document_id or 'ENGINEERING DRAWING REPORT')

    canvas.setFont('Helvetica', 8)
    canvas.setFillColor(HexColor('#BDC3C7'))
    canvas.drawRightString(W - margin, H - 11*mm,
        f"Rev. {data.title_block.revision}  |  {data.title_block.date}")

    # Thin accent line under header
    canvas.setFillColor(ACCENT_BLUE)
    canvas.rect(0, H - 19*mm, W, 1*mm, fill=1, stroke=0)

    # --- Footer ---
    canvas.setFillColor(LIGHT_GREY)
    canvas.rect(0, 0, W, 10*mm, fill=1, stroke=0)

    canvas.setFont('Helvetica', 7)
    canvas.setFillColor(MID_GREY)
    canvas.drawString(margin, 3.5*mm,
        f"Generated: {datetime.now().strftime('%d %b %Y, %H:%M')}  |  "
        f"Isgec Heavy Engineering Ltd.")
    canvas.drawRightString(W - margin, 3.5*mm, f"Page {doc.page}")

    canvas.restoreState()


# ---------------------------------------------------------------------------
# Section builder helpers
# ---------------------------------------------------------------------------

def _section_header(title: str, styles) -> list:
    """Returns a colored section header block."""
    bg_table = Table(
        [[Paragraph(f"  {title}", styles['section_heading'])]],
        colWidths=[PAGE_W - 30*mm],
    )
    bg_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), STEEL_BLUE),
        ('LEFTPADDING', (0,0), (-1,-1), 6),
        ('RIGHTPADDING', (0,0), (-1,-1), 6),
        ('TOPPADDING', (0,0), (-1,-1), 5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5),
        ('ROWBACKGROUNDS', (0,0), (-1,-1), [STEEL_BLUE]),
    ]))
    return [Spacer(1, 4*mm), bg_table, Spacer(1, 3*mm)]


def _kv_table(pairs: list, styles, ncols: int = 2) -> Table:
    """Renders a 2-column key-value info table."""
    cell_w = (PAGE_W - 30*mm) / (ncols * 2)
    col_ws  = [cell_w * 0.85, cell_w * 1.15] * ncols

    rows = []
    row = []
    for i, (label, value) in enumerate(pairs):
        row.append(Paragraph(label, styles['label']))
        row.append(Paragraph(str(value) if value else '—', styles['value']))
        if len(row) == ncols * 2:
            rows.append(row)
            row = []
    if row:
        # Pad to full width
        while len(row) < ncols * 2:
            row.append('')
        rows.append(row)

    t = Table(rows, colWidths=col_ws, repeatRows=0)
    t.setStyle(TableStyle([
        ('FONTSIZE', (0,0), (-1,-1), 8),
        ('TOPPADDING', (0,0), (-1,-1), 3),
        ('BOTTOMPADDING', (0,0), (-1,-1), 3),
        ('LEFTPADDING', (0,0), (-1,-1), 4),
        ('RIGHTPADDING', (0,0), (-1,-1), 4),
        ('ROWBACKGROUNDS', (0,0), (-1,-1), [WHITE, LIGHT_GREY]),
        ('LINEBELOW', (0,0), (-1,-1), 0.3, HexColor('#D5D8DC')),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]))
    return t


def _build_bom_table(items: list, styles) -> Table:
    """Build the raw BoM table."""
    hdrs = ['#', 'Description', 'Specification', 'Size / Length', 'Qty', 'Wt/unit (kg)', 'Purchase Code']
    col_ws = [10*mm, 42*mm, 22*mm, 38*mm, 12*mm, 20*mm, 32*mm]

    header_row = [Paragraph(h, styles['table_header']) for h in hdrs]
    rows = [header_row]

    for i, item in enumerate(items):
        row = [
            Paragraph(item.item_no, styles['table_cell_center']),
            Paragraph(item.description, styles['table_cell_bold']),
            Paragraph(item.specification, styles['table_cell']),
            Paragraph(item.size, styles['table_cell']),
            Paragraph(str(item.quantity), styles['table_cell_center']),
            Paragraph(f"{item.part_weight_kg:.2f}", styles['table_cell_center']),
            Paragraph(item.purchase_item_code, styles['table_cell']),
        ]
        rows.append(row)

    t = Table(rows, colWidths=col_ws, repeatRows=1)
    t.setStyle(TableStyle([
        ('BACKGROUND',  (0,0), (-1,0),  STEEL_BLUE),
        ('TEXTCOLOR',   (0,0), (-1,0),  WHITE),
        ('FONTNAME',    (0,0), (-1,0),  'Helvetica-Bold'),
        ('FONTSIZE',    (0,0), (-1,0),  8),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [WHITE, LIGHT_GREY]),
        ('GRID',        (0,0), (-1,-1), 0.4, HexColor('#BDC3C7')),
        ('LINEBELOW',   (0,0), (-1,0),  1.5, ACCENT_BLUE),
        ('LEFTPADDING', (0,0), (-1,-1), 4),
        ('RIGHTPADDING',(0,0), (-1,-1), 4),
        ('TOPPADDING',  (0,0), (-1,-1), 3),
        ('BOTTOMPADDING',(0,0), (-1,-1), 3),
        ('VALIGN',      (0,0), (-1,-1), 'MIDDLE'),
    ]))
    return t


def _build_section_summary_table(summary: SectionSummary, styles) -> Table:
    """Build the Section Summary table matching drawing format."""
    hdrs = ['SR. NO.', 'SECTION', 'TOTAL (kg)']
    col_ws = [22*mm, 100*mm, 54*mm]

    header_row = [Paragraph(h, styles['table_header']) for h in hdrs]
    rows = [header_row]

    for item in summary.items:
        row = [
            Paragraph(str(item.sr_no), styles['table_cell_center']),
            Paragraph(item.section, styles['table_cell_bold']),
            Paragraph(f"{item.total_weight_kg:.2f}", styles['table_cell_center']),
        ]
        rows.append(row)

    # Grand Total row
    rows.append([
        Paragraph('', styles['table_cell']),
        Paragraph('Grand Total', styles['table_cell_bold']),
        Paragraph(f"{summary.grand_total_kg:.2f}", ParagraphStyle('gt_val', parent=styles['table_cell_bold'], alignment=TA_CENTER, textColor=STEEL_BLUE)),
    ])

    t = Table(rows, colWidths=col_ws, repeatRows=1)
    t.setStyle(TableStyle([
        ('BACKGROUND',   (0,0), (-1,0),  STEEL_BLUE),
        ('TEXTCOLOR',    (0,0), (-1,0),  WHITE),
        ('FONTNAME',     (0,0), (-1,0),  'Helvetica-Bold'),
        ('ROWBACKGROUNDS',(0,1),(-1,-2), [WHITE, LIGHT_GREY]),
        ('BACKGROUND',   (0,-1),(-1,-1), HexColor('#D6EAF8')),
        ('GRID',         (0,0), (-1,-1), 0.4, HexColor('#BDC3C7')),
        ('LINEABOVE',    (0,-1),(-1,-1), 1.5, STEEL_BLUE),
        ('LEFTPADDING',  (0,0), (-1,-1), 6),
        ('RIGHTPADDING', (0,0), (-1,-1), 6),
        ('TOPPADDING',   (0,0), (-1,-1), 4),
        ('BOTTOMPADDING',(0,0), (-1,-1), 4),
        ('VALIGN',       (0,0), (-1,-1), 'MIDDLE'),
    ]))
    return t


def _build_grouped_table(groups: list, styles) -> Table:
    """Build the combined/grouped materials table."""
    hdrs = ['#', 'Description', 'Specification', 'Combined Dimension', 'Total Qty', 'Total Wt (kg)', 'Purchase Code', 'Parts Combined']
    col_ws = [8*mm, 38*mm, 20*mm, 42*mm, 14*mm, 20*mm, 30*mm, 14*mm]

    header_row = [Paragraph(h, styles['table_header']) for h in hdrs]
    rows = [header_row]

    for i, g in enumerate(groups):
        n_parts = len(g.source_items)
        row = [
            Paragraph(str(i+1), styles['table_cell_center']),
            Paragraph(g.description, styles['table_cell_bold']),
            Paragraph(g.specification, styles['table_cell']),
            Paragraph(g.combined_size, styles['table_cell_bold']),
            Paragraph(str(g.total_quantity), styles['table_cell_center']),
            Paragraph(f"{g.total_weight_kg:.2f}", styles['table_cell_center']),
            Paragraph(g.purchase_item_code, styles['table_cell']),
            Paragraph(str(n_parts) if n_parts > 1 else '1', styles['table_cell_center']),
        ]
        rows.append(row)

    t = Table(rows, colWidths=col_ws, repeatRows=1)
    t.setStyle(TableStyle([
        ('BACKGROUND',   (0,0), (-1,0),  NAVY),
        ('TEXTCOLOR',    (0,0), (-1,0),  WHITE),
        ('FONTNAME',     (0,0), (-1,0),  'Helvetica-Bold'),
        ('FONTSIZE',     (0,0), (-1,0),  8),
        ('ROWBACKGROUNDS',(0,1),(-1,-1), [WHITE, LIGHT_BLUE]),
        ('GRID',         (0,0), (-1,-1), 0.4, HexColor('#AED6F1')),
        ('LINEBELOW',    (0,0), (-1,0),  1.5, MID_BLUE),
        ('LEFTPADDING',  (0,0), (-1,-1), 4),
        ('RIGHTPADDING', (0,0), (-1,-1), 4),
        ('TOPPADDING',   (0,0), (-1,-1), 3),
        ('BOTTOMPADDING',(0,0), (-1,-1), 3),
        ('VALIGN',       (0,0), (-1,-1), 'MIDDLE'),
    ]))

    for i, g in enumerate(groups):
        if len(g.source_items) > 1:
            t.setStyle(TableStyle([
                ('TEXTCOLOR', (3, i+1), (3, i+1), ACCENT_BLUE),
                ('FONTNAME',  (3, i+1), (3, i+1), 'Helvetica-Bold'),
                ('TEXTCOLOR', (7, i+1), (7, i+1), ORANGE),
                ('FONTNAME',  (7, i+1), (7, i+1), 'Helvetica-Bold'),
            ]))

    return t


def _build_hardware_table(items: list, styles) -> Table:
    hdrs = ['Purchase Code', 'Description', 'Mark', 'Quantity', 'Unit Wt (kg)', 'Total Wt (kg)', 'UOM']
    col_ws = [32*mm, 60*mm, 14*mm, 18*mm, 20*mm, 20*mm, 12*mm]

    header_row = [Paragraph(h, styles['table_header']) for h in hdrs]
    rows = [header_row]

    for i, hw in enumerate(items):
        total_wt = hw.unit_weight_kg * hw.quantity
        row = [
            Paragraph(hw.purchase_item_code, styles['table_cell']),
            Paragraph(hw.description, styles['table_cell']),
            Paragraph(hw.bolt_mark, styles['table_cell_bold']),
            Paragraph(str(hw.quantity), styles['table_cell_center']),
            Paragraph(f"{hw.unit_weight_kg:.3f}", styles['table_cell_center']),
            Paragraph(f"{total_wt:.2f}", styles['table_cell_center']),
            Paragraph(hw.uom, styles['table_cell_center']),
        ]
        rows.append(row)

    t = Table(rows, colWidths=col_ws, repeatRows=1)
    t.setStyle(TableStyle([
        ('BACKGROUND',   (0,0), (-1,0), GREEN),
        ('TEXTCOLOR',    (0,0), (-1,0), WHITE),
        ('FONTNAME',     (0,0), (-1,0), 'Helvetica-Bold'),
        ('ROWBACKGROUNDS',(0,1),(-1,-1),[WHITE, HexColor('#E9F7EF')]),
        ('GRID',         (0,0), (-1,-1), 0.4, HexColor('#A9DFBF')),
        ('LINEBELOW',    (0,0), (-1,0), 1.5, GREEN),
        ('LEFTPADDING',  (0,0), (-1,-1), 4),
        ('RIGHTPADDING', (0,0), (-1,-1), 4),
        ('TOPPADDING',   (0,0), (-1,-1), 3),
        ('BOTTOMPADDING',(0,0), (-1,-1), 3),
        ('VALIGN',       (0,0), (-1,-1), 'MIDDLE'),
    ]))
    return t


def _build_ref_table(refs, styles) -> Table:
    hdrs = ['Document ID', 'Description']
    col_ws = [55*mm, 121*mm]
    header_row = [Paragraph(h, styles['table_header']) for h in hdrs]
    rows = [header_row]
    for i, r in enumerate(refs):
        row = [
            Paragraph(r.document_id, styles['table_cell_bold']),
            Paragraph(r.description, styles['table_cell']),
        ]
        rows.append(row)
    t = Table(rows, colWidths=col_ws, repeatRows=1)
    t.setStyle(TableStyle([
        ('BACKGROUND',    (0,0),(-1,0),  DARK_GREY),
        ('TEXTCOLOR',     (0,0),(-1,0),  WHITE),
        ('ROWBACKGROUNDS',(0,1),(-1,-1), [WHITE, LIGHT_GREY]),
        ('GRID',          (0,0),(-1,-1), 0.4, HexColor('#BDC3C7')),
        ('LINEBELOW',     (0,0),(-1,0),  1.5, MID_BLUE),
        ('LEFTPADDING',   (0,0),(-1,-1), 4),
        ('RIGHTPADDING',  (0,0),(-1,-1), 4),
        ('TOPPADDING',    (0,0),(-1,-1), 3),
        ('BOTTOMPADDING', (0,0),(-1,-1), 3),
        ('VALIGN',        (0,0),(-1,-1), 'MIDDLE'),
    ]))
    return t


def _build_du_table(units, styles) -> Table:
    """Build the Dispatch Units (DU) table."""
    hdrs = ['DU No.', 'Description', 'Type', 'Weight (kg)', 'UOM', 'Purchase Code']
    col_ws = [28*mm, 60*mm, 14*mm, 24*mm, 15*mm, 35*mm]
    header_row = [Paragraph(h, styles['table_header']) for h in hdrs]
    rows = [header_row]
    for du in units:
        rows.append([
            Paragraph(du.du_no, styles['table_cell_center']),
            Paragraph(du.description, styles['table_cell']),
            Paragraph(du.du_type, styles['table_cell_center']),
            Paragraph(f"{du.du_weight_kg:.2f}", styles['table_cell_center']),
            Paragraph(du.uom, styles['table_cell_center']),
            Paragraph(du.purchase_item_code, styles['table_cell_center']),
        ])
    t = Table(rows, colWidths=col_ws, repeatRows=1)
    t.setStyle(TableStyle([
        ('BACKGROUND',    (0,0),(-1,0),  STEEL_BLUE),
        ('TEXTCOLOR',     (0,0),(-1,0),  WHITE),
        ('ROWBACKGROUNDS',(0,1),(-1,-1), [WHITE, LIGHT_GREY]),
        ('GRID',          (0,0),(-1,-1), 0.4, HexColor('#BDC3C7')),
        ('LINEBELOW',     (0,0),(-1,0),  1.5, ACCENT_BLUE),
        ('LEFTPADDING',   (0,0),(-1,-1), 4),
        ('RIGHTPADDING',  (0,0),(-1,-1), 4),
        ('TOPPADDING',    (0,0),(-1,-1), 3),
        ('BOTTOMPADDING', (0,0),(-1,-1), 3),
        ('VALIGN',        (0,0),(-1,-1), 'MIDDLE'),
    ]))
    return t


# ---------------------------------------------------------------------------
# Cover page
# ---------------------------------------------------------------------------

def _build_cover(data: DrawingData, styles) -> list:
    """Build a full-page cover panel using tables."""
    tb = data.title_block
    story = []

    cover_data = [
        [Paragraph("MATERIAL REQUIREMENTS REPORT", styles['cover_title'])],
        [Paragraph(tb.title_line1 or 'Engineering Drawing Analysis', styles['cover_subtitle'])],
        [Paragraph(tb.title_line2 or '', styles['cover_subtitle'])],
        [Spacer(1, 10*mm)],
        [Paragraph(f"Drawing No.: {tb.document_id}", styles['cover_meta'])],
        [Paragraph(f"Project ID: {tb.project_id}  |  Element ID: {tb.element_id}", styles['cover_meta'])],
        [Paragraph(f"Revision: {tb.revision}  |  Date: {tb.date}  |  Scale: {tb.scale}", styles['cover_meta'])],
        [Spacer(1, 8*mm)],
        [Paragraph(f"Client: {tb.client}", styles['cover_meta'])],
        [Paragraph(f"Consultant: {tb.consultant}", styles['cover_meta'])],
    ]

    t = Table(cover_data, colWidths=[PAGE_W - 30*mm])
    t.setStyle(TableStyle([
        ('BACKGROUND',    (0,0), (-1,-1), NAVY),
        ('LEFTPADDING',   (0,0), (-1,-1), 20),
        ('RIGHTPADDING',  (0,0), (-1,-1), 20),
        ('TOPPADDING',    (0,0), (-1,-1), 8),
        ('BOTTOMPADDING', (0,0), (-1,-1), 8),
        ('TOPPADDING',    (0,0), (0,0),   20),
    ]))

    story.append(Spacer(1, 25*mm))
    story.append(t)
    story.append(Spacer(1, 8*mm))

    story.append(Table([['']], colWidths=[PAGE_W - 30*mm],
                       style=TableStyle([('BACKGROUND',(0,0),(-1,-1), MID_BLUE),
                                         ('TOPPADDING',(0,0),(-1,-1), 1),
                                         ('BOTTOMPADDING',(0,0),(-1,-1), 1)])))
    story.append(Spacer(1, 8*mm))

    n_bom  = len(data.bom_items)
    n_hw   = len(data.hardware_items)
    n_grps = len(group_bom_items(data.bom_items))
    n_refs = len(data.reference_drawings)

    summary_data = [
        [
            _stat_box("BoM Items", str(n_bom), styles),
            _stat_box("Grouped Materials", str(n_grps), styles),
            _stat_box("Hardware Items", str(n_hw), styles),
            _stat_box("Ref. Drawings", str(n_refs), styles),
        ]
    ]
    st = Table(summary_data, colWidths=[(PAGE_W - 30*mm)/4]*4)
    st.setStyle(TableStyle([
        ('LEFTPADDING',   (0,0),(-1,-1), 3),
        ('RIGHTPADDING',  (0,0),(-1,-1), 3),
        ('TOPPADDING',    (0,0),(-1,-1), 3),
        ('BOTTOMPADDING', (0,0),(-1,-1), 3),
    ]))
    story.append(st)
    story.append(Spacer(1, 8*mm))

    story.append(Paragraph(
        f"Report generated on {datetime.now().strftime('%d %B %Y at %H:%M')}  |  "
        f"Total estimated weight: {tb.total_weight_kg} kg",
        styles['note']
    ))

    story.append(PageBreak())
    return story


def _stat_box(label: str, value: str, styles) -> Table:
    t = Table(
        [[Paragraph(value, ParagraphStyle('sv', fontSize=22, textColor=ACCENT_BLUE,
                                          fontName='Helvetica-Bold', alignment=TA_CENTER))],
         [Paragraph(label, ParagraphStyle('sl', fontSize=8, textColor=MID_GREY,
                                          fontName='Helvetica', alignment=TA_CENTER))]],
    )
    t.setStyle(TableStyle([
        ('BACKGROUND',    (0,0),(-1,-1), LIGHT_GREY),
        ('LEFTPADDING',   (0,0),(-1,-1), 8),
        ('RIGHTPADDING',  (0,0),(-1,-1), 8),
        ('TOPPADDING',    (0,0),(-1,-1), 8),
        ('BOTTOMPADDING', (0,0),(-1,-1), 4),
        ('BOTTOMPADDING', (0,1),(-1,1), 10),
        ('BOX', (0,0), (-1,-1), 1, HexColor('#D5D8DC')),
    ]))
    return t


# ---------------------------------------------------------------------------
# Main generator
# ---------------------------------------------------------------------------

def generate_report(data: DrawingData, output_path: str) -> str:
    """
    Generate the PDF report.
    Returns output_path on success.
    """
    styles = _make_styles()
    tb = data.title_block

    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        leftMargin=15*mm,
        rightMargin=15*mm,
        topMargin=22*mm,
        bottomMargin=14*mm,
        title=f"Material Requirements - {tb.document_id}",
        author="BOM Analyser Tool",
        subject="Engineering Drawing Material Report",
    )

    story = []

    # Cover page
    story += _build_cover(data, styles)

    # Section 1: Drawing Information
    story += _section_header("1. Drawing Information", styles)

    pairs = [
        ('Document ID',    tb.document_id),
        ('Project ID',     tb.project_id),
        ('Title',          f"{tb.title_line1}"),
        ('Element ID',     tb.element_id),
        ('Revision',       tb.revision),
        ('Date',           tb.date),
        ('Scale',          tb.scale),
        ('Sheet Size',     tb.sheet_size),
        ('Drawn By',       tb.drawn_by),
        ('Checked By',     tb.checked_by),
        ('Approved By',    tb.approved_by),
        ('Total Weight',   f"{tb.total_weight_kg} kg"),
        ('Client',         tb.client),
        ('Consultant',     tb.consultant),
        ('Service',        tb.service),
        ('Year',           tb.year),
    ]
    story.append(_kv_table(pairs, styles, ncols=2))
    story.append(Spacer(1, 5*mm))

    # Revision history
    if tb.revision_history:
        story.append(Paragraph("Revision History", styles['subsection']))
        rev_hdrs = ['Rev', 'Date', 'Revised By', 'Approved By', 'Description']
        rev_ws   = [12*mm, 25*mm, 22*mm, 22*mm, 95*mm]
        rev_rows = [[Paragraph(h, styles['table_header']) for h in rev_hdrs]]
        for r in tb.revision_history:
            rev_rows.append([
                Paragraph(r.get('rev',''), styles['table_cell_center']),
                Paragraph(r.get('date',''), styles['table_cell']),
                Paragraph(r.get('revd_by',''), styles['table_cell']),
                Paragraph(r.get('appd_by',''), styles['table_cell']),
                Paragraph(r.get('description',''), styles['table_cell']),
            ])
        rev_t = Table(rev_rows, colWidths=rev_ws, repeatRows=1)
        rev_t.setStyle(TableStyle([
            ('BACKGROUND',    (0,0),(-1,0),  DARK_GREY),
            ('TEXTCOLOR',     (0,0),(-1,0),  WHITE),
            ('ROWBACKGROUNDS',(0,1),(-1,-1), [WHITE, LIGHT_GREY]),
            ('GRID',          (0,0),(-1,-1), 0.4, HexColor('#BDC3C7')),
            ('LEFTPADDING',   (0,0),(-1,-1), 4),
            ('RIGHTPADDING',  (0,0),(-1,-1), 4),
            ('TOPPADDING',    (0,0),(-1,-1), 3),
            ('BOTTOMPADDING', (0,0),(-1,-1), 3),
            ('VALIGN',        (0,0),(-1,-1), 'MIDDLE'),
        ]))
        story.append(rev_t)
        story.append(Spacer(1, 5*mm))

    # Reference drawings
    if data.reference_drawings:
        story.append(Paragraph("Reference Drawings", styles['subsection']))
        story.append(_build_ref_table(data.reference_drawings, styles))
        story.append(Spacer(1, 5*mm))

    story.append(PageBreak())


    # Section 2: Material Requirements & Section Summary
    story += _section_header("2. Material Requirements & Section Summary", styles)

    # Drawing Section Summary
    sec_summary = get_section_summary(data.bom_items)
    if sec_summary.items:
        story.append(Paragraph("SUMMARY (Drawing Format)", styles['subsection']))
        story.append(Paragraph(
            "Section weight breakdown as formatted in drawing title blocks:",
            ParagraphStyle('info', fontSize=8, textColor=DARK_GREY, leading=12, fontName='Helvetica', spaceAfter=4)
        ))
        story.append(Spacer(1, 2*mm))
        story.append(_build_section_summary_table(sec_summary, styles))
        story.append(Spacer(1, 6*mm))

    grouped = group_bom_items(data.bom_items)
    if grouped:
        story.append(Paragraph("Grouped Material Requirements Breakdown", styles['subsection']))
        total_w = sum(g.total_weight_kg for g in grouped)
        story.append(Paragraph(
            f"Total of <b>{len(grouped)}</b> unique material types "
            f"(from {len(data.bom_items)} raw BoM entries). "
            f"Combined total weight: <b>{total_w:.2f} kg</b>. "
            "Items highlighted in <font color='#2874A6'><b>blue</b></font> had their "
            "dimensions combined from multiple parts with the same part number.",
            ParagraphStyle('info', fontSize=8, textColor=DARK_GREY,
                           leading=12, fontName='Helvetica', spaceAfter=4)
        ))
        story.append(Spacer(1, 2*mm))
        story.append(_build_grouped_table(grouped, styles))

        combined = [g for g in grouped if len(g.source_items) > 1]
        if combined:
            story.append(Spacer(1, 6*mm))
            story.append(Paragraph("Dimension Combination Details", styles['subsection']))
            story.append(Paragraph(
                "The following table shows how dimensions were combined for each grouped material:",
                ParagraphStyle('info', fontSize=8, textColor=MID_GREY, leading=12, fontName='Helvetica')
            ))
            story.append(Spacer(1, 2*mm))

            for g in combined:
                story.append(Spacer(1, 3*mm))
                hdr = Paragraph(
                    f"{g.description} — {g.purchase_item_code}",
                    styles['subsection']
                )
                story.append(hdr)

                detail_hdrs = ['Part No.', 'Original Size', 'Qty', 'Wt/pc (kg)', 'Contrib. Wt (kg)']
                detail_ws   = [20*mm, 60*mm, 15*mm, 25*mm, 25*mm]
                detail_rows = [[Paragraph(h, styles['table_header']) for h in detail_hdrs]]
                for src in g.source_items:
                    detail_rows.append([
                        Paragraph(src.item_no, styles['table_cell_center']),
                        Paragraph(src.size, styles['table_cell']),
                        Paragraph(str(src.quantity), styles['table_cell_center']),
                        Paragraph(f"{src.part_weight_kg:.3f}", styles['table_cell_center']),
                        Paragraph(f"{src.part_weight_kg * src.quantity:.2f}", styles['table_cell_center']),
                    ])
                detail_rows.append([
                    Paragraph('TOTAL', styles['table_cell_bold']),
                    Paragraph(f"→ Combined: {g.combined_size}", ParagraphStyle(
                        'comb', fontSize=8, textColor=ACCENT_BLUE, fontName='Helvetica-Bold')),
                    Paragraph(str(g.total_quantity), styles['table_cell_bold']),
                    Paragraph('', styles['table_cell']),
                    Paragraph(f"{g.total_weight_kg:.2f}", styles['table_cell_bold']),
                ])
                dt = Table(detail_rows, colWidths=detail_ws, repeatRows=1)
                dt.setStyle(TableStyle([
                    ('BACKGROUND',    (0,0),(-1,0),  ACCENT_BLUE),
                    ('TEXTCOLOR',     (0,0),(-1,0),  WHITE),
                    ('ROWBACKGROUNDS',(0,1),(-1,-2), [WHITE, LIGHT_BLUE]),
                    ('BACKGROUND',    (0,-1),(-1,-1), LIGHT_GREY),
                    ('FONTNAME',      (0,-1),(-1,-1), 'Helvetica-Bold'),
                    ('GRID',          (0,0),(-1,-1), 0.4, HexColor('#AED6F1')),
                    ('LINEABOVE',     (0,-1),(-1,-1), 1.5, ACCENT_BLUE),
                    ('LEFTPADDING',   (0,0),(-1,-1), 4),
                    ('RIGHTPADDING',  (0,0),(-1,-1), 4),
                    ('TOPPADDING',    (0,0),(-1,-1), 3),
                    ('BOTTOMPADDING', (0,0),(-1,-1), 3),
                    ('VALIGN',        (0,0),(-1,-1), 'MIDDLE'),
                ]))
                story.append(KeepTogether(dt))
    else:
        story.append(Paragraph("No BoM items found in this drawing.", styles['body']))

    story.append(PageBreak())

    # Section 3: Hardware / Fastener Requirements
    story += _section_header("3. Hardware & Fastener Requirements", styles)

    if data.hardware_items:
        total_hw = len(data.hardware_items)
        story.append(Paragraph(
            f"<b>{total_hw}</b> hardware item type(s) required. "
            "All hardware shall be Hot Dip Galvanized (HDG) unless otherwise specified.",
            ParagraphStyle('info', fontSize=8, textColor=DARK_GREY,
                           leading=12, fontName='Helvetica', spaceAfter=4)
        ))
        story.append(Spacer(1, 2*mm))
        story.append(_build_hardware_table(data.hardware_items, styles))
    else:
        story.append(Paragraph("No hardware items found in this drawing.", styles['body']))

    story.append(Spacer(1, 8*mm))

    # Section 4: Raw Bill of Materials
    story += _section_header("4. Raw Bill of Materials (BoM)", styles)

    if data.bom_items:
        story.append(Paragraph(
            f"<b>{len(data.bom_items)}</b> items from the original BoM table.",
            ParagraphStyle('info', fontSize=8, textColor=DARK_GREY,
                           leading=12, fontName='Helvetica', spaceAfter=4)
        ))
        story.append(Spacer(1, 2*mm))
        story.append(_build_bom_table(data.bom_items, styles))
    else:
        story.append(Paragraph("No BoM items found.", styles['body']))

    # Section 5: Dispatch Units
    if data.dispatch_units:
        story.append(Spacer(1, 6*mm))
        story += _section_header("5. Dispatch Units (Shipping Packages)", styles)
        story.append(Paragraph(
            f"<b>{len(data.dispatch_units)}</b> dispatch package(s) identified for fabrication delivery.",
            ParagraphStyle('info', fontSize=8, textColor=DARK_GREY,
                           leading=12, fontName='Helvetica', spaceAfter=4)
        ))
        story.append(Spacer(1, 2*mm))
        story.append(_build_du_table(data.dispatch_units, styles))

    def _page_cb(canvas, doc_obj):
        _on_page(canvas, doc_obj, data, styles)

    doc.build(story, onFirstPage=_page_cb, onLaterPages=_page_cb)
    return output_path


def generate_grouped_excel(grouped_materials, section_summary: Optional[SectionSummary], output_path: str):
    """
    Generate an Excel (.xlsx) file containing Section Summary and Grouped Material Requirements.
    """
    try:
        import openpyxl
        from openpyxl.styles import Font, Alignment, PatternFill
        from openpyxl.utils import get_column_letter

        wb = openpyxl.Workbook()

        header_font = Font(bold=True, color="FFFFFF")
        header_fill = PatternFill(start_color="0D1B2A", end_color="0D1B2A", fill_type="solid")
        header_align = Alignment(horizontal="center", vertical="center", wrap_text=True)
        data_align = Alignment(vertical="center", wrap_text=True)
        bold_font = Font(bold=True)

        # ---------------------------------------------------
        # Sheet 1: Section Summary (Drawing Format)
        # ---------------------------------------------------
        ws_sum = wb.active
        ws_sum.title = "SUMMARY"

        sum_headers = ["SR. NO.", "SECTION", "TOTAL WEIGHT (KG)"]
        for col_num, h in enumerate(sum_headers, 1):
            cell = ws_sum.cell(row=1, column=col_num)
            cell.value = h
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = header_align

        current_row = 2
        if section_summary and section_summary.items:
            for item in section_summary.items:
                ws_sum.cell(row=current_row, column=1, value=item.sr_no).alignment = Alignment(horizontal="center", vertical="center")
                ws_sum.cell(row=current_row, column=2, value=item.section).alignment = data_align
                ws_sum.cell(row=current_row, column=3, value=item.total_weight_kg).alignment = Alignment(horizontal="right", vertical="center")
                current_row += 1

            # Grand Total
            cell_gt_lbl = ws_sum.cell(row=current_row, column=2, value="Grand Total")
            cell_gt_lbl.font = bold_font
            cell_gt_val = ws_sum.cell(row=current_row, column=3, value=section_summary.grand_total_kg)
            cell_gt_val.font = bold_font
            cell_gt_val.alignment = Alignment(horizontal="right", vertical="center")

        ws_sum.column_dimensions['A'].width = 12
        ws_sum.column_dimensions['B'].width = 35
        ws_sum.column_dimensions['C'].width = 22

        # ---------------------------------------------------
        # Sheet 2: Grouped Materials
        # ---------------------------------------------------
        ws_grp = wb.create_sheet(title="Grouped Materials")

        headers = [
            "Purchase Item Code",
            "Description",
            "Specification",
            "Combined Size",
            "Total Qty",
            "Total Weight (kg)",
            "Parts Combined",
            "Source Item Nos"
        ]

        for col_num, header_text in enumerate(headers, 1):
            cell = ws_grp.cell(row=1, column=col_num)
            cell.value = header_text
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = header_align

        for row_num, gm in enumerate(grouped_materials, 2):
            source_item_nos = ", ".join(sorted(set(s.item_no for s in gm.source_items)))
            row_data = [
                gm.purchase_item_code,
                gm.description,
                gm.specification,
                gm.combined_size,
                gm.total_quantity,
                round(gm.total_weight_kg, 3) if gm.total_weight_kg else "",
                len(gm.source_items),
                source_item_nos
            ]

            for col_num, cell_value in enumerate(row_data, 1):
                cell = ws_grp.cell(row=row_num, column=col_num)
                cell.value = cell_value
                cell.alignment = data_align

        for col_num, col_cells in enumerate(ws_grp.columns, 1):
            max_length = 0
            column_letter = get_column_letter(col_num)
            for cell in col_cells:
                try:
                    if cell.value:
                        lines = str(cell.value).split('\n')
                        max_length = max(max_length, max(len(line) for line in lines))
                except:
                    pass
            adjusted_width = (max_length + 2)
            adjusted_width = min(adjusted_width, 50)
            adjusted_width = max(adjusted_width, 10)
            ws_grp.column_dimensions[column_letter].width = adjusted_width

        wb.save(output_path)
        return output_path
    except Exception as e:
        print(f"Error generating Excel report: {e}")
        return None


def generate_annotated_pdf(input_path: str, grouped_materials, section_summary: Optional[SectionSummary], output_path: str):
    """
    Overwrites the SUMMARY table directly on the input drawing PDF in-place.
    Detects the existing summary table on the drawing, whites out the old table/region,
    and draws the updated SUMMARY table matching the exact engineering drawing format:
    Centered 'SUMMARY' header, 'SR. NO.', 'SECTION', 'TOTAL' columns, individual section
    weights, and 'Grand Total'.
    Page dimensions and layout are preserved 100% exactly.
    """
    try:
        import os
        import pymupdf as fitz
        import shutil

        if not section_summary or not section_summary.items:
            shutil.copyfile(input_path, output_path)
            return output_path

        # If input is not a direct PDF (e.g. image format), convert to PDF
        ext = os.path.splitext(input_path)[1].lower()
        if ext in ['.jpg', '.jpeg', '.png', '.tiff', '.tif', '.bmp', '.webp']:
            img_doc = fitz.open(input_path)
            pdf_bytes = img_doc.convert_to_pdf()
            doc = fitz.open("pdf", pdf_bytes)
        else:
            doc = fitz.open(input_path)

        page = doc[0]
        W = page.rect.width
        H = page.rect.height

        scale_x = W / 792.0
        scale_y = H / 612.0

        # Try to locate summary position dynamically
        exact_rect = None
        # 1. Search for existing text "SUMMARY" in the bottom right quadrant
        for r in page.search_for("SUMMARY"):
            if r.x0 > W * 0.4 and r.y0 > H * 0.35:
                exact_rect = r
                break

        # 2. Search for existing table box or cloud from vector drawings
        if not exact_rect:
            for d in page.get_drawings():
                for item in d["items"]:
                    if item[0] == "re":
                        r = item[1]
                        if (470 * scale_x < r.x0 < 570 * scale_x and
                            390 * scale_y < r.y0 < 480 * scale_y and
                            50 * scale_x < r.width < 95 * scale_x and
                            35 * scale_y < r.height < 100 * scale_y):
                            exact_rect = r
                            break
                if exact_rect:
                    break

        if exact_rect:
            center_x = (exact_rect.x0 + exact_rect.x1) / 2.0
            table_top = exact_rect.y0
            if page.search_for("SUMMARY") and exact_rect in page.search_for("SUMMARY"):
                table_top = exact_rect.y1 + 2.0 * scale_y
        else:
            center_x = 556.90 * scale_x
            table_top = 448.83 * scale_y

        total_w = 72.04 * scale_x
        x0 = center_x - (total_w / 2.0)
        x1 = x0 + total_w

        col0_w = 19.57 * scale_x   # SR. NO.
        col1_w = 33.34 * scale_x   # SECTION
        col2_w = 19.13 * scale_x   # TOTAL

        items = section_summary.items
        n_items = len(items)
        row_h = 6.32 * scale_y

        # Rows: 1 header row + n item rows + 1 Grand Total row
        total_rows = n_items + 2
        table_bottom = table_top + total_rows * row_h

        # Whiteout area covering title and table with slight margin
        whiteout_rect = fitz.Rect(
            x0 - 1.5 * scale_x,
            table_top - 11.0 * scale_y,
            x1 + 1.5 * scale_x,
            table_bottom + 1.5 * scale_y
        )
        page.draw_rect(whiteout_rect, color=(1, 1, 1), fill=(1, 1, 1), overlay=True)

        # Draw outer rectangle box
        page.draw_rect(fitz.Rect(x0, table_top, x1, table_bottom),
                       color=(0, 0, 0), width=0.5, overlay=True)

        # "SUMMARY" Title centered above table box
        title_text = "SUMMARY"
        title_fs = 7.0 * min(scale_x, scale_y)
        title_w = fitz.get_text_length(title_text, fontname="hebo", fontsize=title_fs)
        page.insert_text(fitz.Point(x0 + (total_w - title_w) / 2.0, table_top - 2.0 * scale_y),
                         title_text, fontname="hebo", fontsize=title_fs, color=(0, 0, 0))

        # Horizontal gridlines
        for r in range(1, total_rows):
            y = table_top + r * row_h
            page.draw_line(fitz.Point(x0, y), fitz.Point(x1, y),
                           color=(0, 0, 0), width=0.5, overlay=True)

        # Vertical divider lines
        page.draw_line(fitz.Point(x0 + col0_w, table_top),
                       fitz.Point(x0 + col0_w, table_bottom),
                       color=(0, 0, 0), width=0.5, overlay=True)
        page.draw_line(fitz.Point(x0 + col0_w + col1_w, table_top),
                       fitz.Point(x0 + col0_w + col1_w, table_bottom),
                       color=(0, 0, 0), width=0.5, overlay=True)

        font_size_cell = 4.2 * min(scale_x, scale_y)
        baseline_offset = row_h * 0.72

        # Header row (row 0)
        h_base = table_top + baseline_offset
        h0 = "SR. NO."
        h0_w = fitz.get_text_length(h0, fontname="hebo", fontsize=font_size_cell)
        page.insert_text(fitz.Point(x0 + (col0_w - h0_w) / 2.0, h_base),
                         h0, fontname="hebo", fontsize=font_size_cell, color=(0, 0, 0))

        h1 = "SECTION"
        h1_w = fitz.get_text_length(h1, fontname="hebo", fontsize=font_size_cell)
        page.insert_text(fitz.Point(x0 + col0_w + (col1_w - h1_w) / 2.0, h_base),
                         h1, fontname="hebo", fontsize=font_size_cell, color=(0, 0, 0))

        h2 = "TOTAL"
        h2_w = fitz.get_text_length(h2, fontname="hebo", fontsize=font_size_cell)
        page.insert_text(fitz.Point(x0 + col0_w + col1_w + (col2_w - h2_w) / 2.0, h_base),
                         h2, fontname="hebo", fontsize=font_size_cell, color=(0, 0, 0))

        # Item rows
        for idx, item in enumerate(items):
            curr_top = table_top + (idx + 1) * row_h
            row_base = curr_top + baseline_offset

            # Col 0: Sr. No (centered)
            sr_str = str(idx + 1)
            sr_w = fitz.get_text_length(sr_str, fontname="helv", fontsize=font_size_cell)
            page.insert_text(fitz.Point(x0 + (col0_w - sr_w) / 2.0, row_base),
                             sr_str, fontname="helv", fontsize=font_size_cell, color=(0, 0, 0))

            # Col 1: Section name (left aligned with 1.5 pt padding)
            sec_str = item.section
            page.insert_text(fitz.Point(x0 + col0_w + 1.5 * scale_x, row_base),
                             sec_str, fontname="helv", fontsize=font_size_cell, color=(0, 0, 0))

            # Col 2: Total weight (right aligned with 1.5 pt padding)
            wt_str = f"{item.total_weight_kg:.2f}"
            wt_w = fitz.get_text_length(wt_str, fontname="helv", fontsize=font_size_cell)
            page.insert_text(fitz.Point(x1 - wt_w - 1.5 * scale_x, row_base),
                             wt_str, fontname="helv", fontsize=font_size_cell, color=(0, 0, 0))

        # Grand Total Row
        gt_top = table_top + (n_items + 1) * row_h
        gt_base = gt_top + baseline_offset

        gt_label = "Grand Total"
        gt_label_w = fitz.get_text_length(gt_label, fontname="helv", fontsize=font_size_cell)
        page.insert_text(fitz.Point(x0 + col0_w + (col1_w - gt_label_w) / 2.0, gt_base),
                         gt_label, fontname="helv", fontsize=font_size_cell, color=(0, 0, 0))

        gt_val = f"{section_summary.grand_total_kg:.2f}"
        gt_val_w = fitz.get_text_length(gt_val, fontname="hebo", fontsize=font_size_cell)
        page.insert_text(fitz.Point(x1 - gt_val_w - 1.5 * scale_x, gt_base),
                         gt_val, fontname="hebo", fontsize=font_size_cell, color=(0, 0, 0))

        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        doc.save(output_path)
        doc.close()
        return output_path

    except Exception as e:
        import traceback
        print(f"Error generating annotated PDF: {e}")
        traceback.print_exc()
        return None