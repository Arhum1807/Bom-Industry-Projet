import pymupdf as fitz
from reportlab.platypus import Table, TableStyle
from reportlab.lib import colors
from reportlab.lib.units import mm
import tempfile
import os

def test():
    doc = fitz.open(r'c:\Users\Arhum\Downloads\project\ES00225-7544040101-FAB-0001.pdf')
    page = doc[0]
    W = page.rect.width
    H = page.rect.height
    
    data = [["Purchase Item Code", "Description", "Specification", "Combined Size", "Total Qty", "Total Weight (kg)", "Source Item Nos"]]
    # dummy rows
    for i in range(10):
        data.append([f"CODE{i}", "PLATE", "IS:2062", f"{i}0 x 100", str(i), f"{i}.5", "1, 2"])
        
    t = Table(data, colWidths=[(W-40*mm)/7]*7)
    t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#0D1B2A')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0,0), (-1,0), 8),
        ('BACKGROUND', (0,1), (-1,-1), colors.white),
        ('GRID', (0,0), (-1,-1), 0.5, colors.grey)
    ]))
    
    w, h = t.wrap(W - 40*mm, 10000)
    
    # create reportlab pdf with height h + 20*mm
    H_table = h + 20*mm
    with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp:
        tmp_name = tmp.name
    
    from reportlab.pdfgen import canvas
    c = canvas.Canvas(tmp_name, pagesize=(W, H_table))
    t.drawOn(c, 20*mm, 10*mm)
    c.save()
    
    # Create new document
    out_doc = fitz.open()
    new_page = out_doc.new_page(width=W, height=H + H_table)
    
    # Stamp original page at top
    new_page.show_pdf_page(fitz.Rect(0, 0, W, H), doc, 0)
    
    # Stamp table at bottom
    tbl_doc = fitz.open(tmp_name)
    new_page.show_pdf_page(fitz.Rect(0, H, W, H + H_table), tbl_doc, 0)
    
    out_doc.save(r'c:\Users\Arhum\Downloads\project\bom_tool\test_annotated_new.pdf')
    tbl_doc.close()
    os.unlink(tmp_name)

test()
