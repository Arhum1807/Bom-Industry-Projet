"""
bom_extractor.py
Core extraction logic for engineering drawing PDFs (Isgec/Adani format).

The PDF text extraction gives each BoM field on its own line in the order:
  item_no
  description
  specification
  size
  quantity
  part_weight_kg
  purchase_item_code

Hardware rows appear as:
  0  PURCHASE_CODE  DESCRIPTION  B  F1  QTY  WT  EA
(sometimes split across lines)

Dispatch Unit rows follow the pattern:
  DU_NO  DESCRIPTION  TYPE  REMARK  QTY  WT  UOM  PICODE
"""

import re
import pymupdf as fitz
from dataclasses import dataclass, field
from typing import Optional, List


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class TitleBlock:
    document_id: str = ""
    title_line1: str = ""
    title_line2: str = ""
    project_id: str = ""
    element_id: str = ""
    total_weight_kg: str = ""
    year: str = ""
    sheet_size: str = ""
    scale: str = ""
    drawn_by: str = ""
    checked_by: str = ""
    approved_by: str = ""
    date: str = ""
    client: str = ""
    consultant: str = ""
    service: str = "MECHANICAL"
    revision: str = ""
    revision_history: List[dict] = field(default_factory=list)


@dataclass
class BomItem:
    item_no: str = ""
    description: str = ""
    specification: str = ""
    size: str = ""
    remark: str = ""
    part_weight_kg: float = 0.0
    quantity: int = 0
    purchase_item_code: str = ""
    dim1: Optional[float] = None
    dim2: Optional[float] = None
    thickness: Optional[float] = None
    length: Optional[float] = None


@dataclass
class HardwareItem:
    purchase_item_code: str = ""
    description: str = ""
    bolt_mark: str = ""
    quantity: int = 0
    unit_weight_kg: float = 0.0
    uom: str = "EA"


@dataclass
class DispatchUnit:
    du_no: str = ""
    description: str = ""
    du_type: str = ""
    du_weight_kg: float = 0.0
    uom: str = "KG"
    purchase_item_code: str = ""


@dataclass
class ReferenceDrawing:
    document_id: str = ""
    description: str = ""


@dataclass
class DrawingData:
    title_block: TitleBlock = field(default_factory=TitleBlock)
    bom_items: List[BomItem] = field(default_factory=list)
    hardware_items: List[HardwareItem] = field(default_factory=list)
    dispatch_units: List[DispatchUnit] = field(default_factory=list)
    reference_drawings: List[ReferenceDrawing] = field(default_factory=list)
    raw_text: str = ""


# ---------------------------------------------------------------------------
# Utility regexes
# ---------------------------------------------------------------------------
RE_DOC_ID    = re.compile(r'^ES\d{5}-[\dA-Z]+-[A-Z]+-\d+$')
RE_PROJ_ID   = re.compile(r'ES-\d{5}')
RE_ELEM_ID   = re.compile(r'\d{2}-\d{2}-\d{2}-\d{2}-\d{2}')
RE_PLATE_DIM = re.compile(r'([\d.]+)\s*[xX]\s*([\d.]+)\s*[xX]\s*([\d.]+)\s*THK', re.IGNORECASE)
RE_LEN_DIM   = re.compile(r'([\d.]+)\s*LG\.?', re.IGNORECASE)
RE_PICODE    = re.compile(r'^[A-Z]{2,4}\d{8,}[A-Z0-9]*$')
RE_SPEC      = re.compile(r'^IS:\d+', re.IGNORECASE)
RE_SIZE_PLATE= re.compile(r'^\d[\d.\s]*[xX][\d.\s]*[xX][\d.\s]*THK', re.IGNORECASE)
RE_SIZE_LEN  = re.compile(r'^\d[\d.]*\s*LG\.?', re.IGNORECASE)
RE_FLOAT     = re.compile(r'^[\d.]+$')
RE_INT       = re.compile(r'^\d+$')
RE_ITEM_NO   = re.compile(r'^\d{1,3}[A-Z]?$')

STRUCT_KEYWORDS = {
    'UB', 'ISMC', 'ISMB', 'ISA', 'PLATE', 'PIPE',
    'RHS', 'SHS', 'FLAT', 'ROUND', 'CHANNEL', 'ANGLE',
    'L ', 'SECTION',
}

def _is_description(line: str) -> bool:
    """Check if a line looks like a structural material description."""
    line = line.strip().upper()
    if any(line.startswith(kw) for kw in STRUCT_KEYWORDS):
        return True
    if line.startswith('L ') and re.match(r'^L \d+', line):
        return True
    return False


def _clean(s): return ' '.join(s.split())
def _f(s):
    try: return float(str(s).strip())
    except: return 0.0
def _i(s):
    try: return int(str(s).strip())
    except: return 0


def _parse_plate_dims(size_str):
    m = RE_PLATE_DIM.search(size_str)
    if m:
        return float(m.group(1)), float(m.group(2)), float(m.group(3))
    return None, None, None


def _parse_len(size_str):
    m = RE_LEN_DIM.search(size_str)
    return float(m.group(1)) if m else None


# ---------------------------------------------------------------------------
# Title block
# ---------------------------------------------------------------------------

def _find_title_block(text: str, lines: list) -> TitleBlock:
    tb = TitleBlock()

    # Document ID
    doc_ids = [l.strip() for l in lines if RE_DOC_ID.match(l.strip())]
    if doc_ids:
        tb.document_id = doc_ids[0]

    # Project ID
    pids = RE_PROJ_ID.findall(text)
    if pids:
        tb.project_id = pids[0]

    # Element ID
    eids = RE_ELEM_ID.findall(text)
    if eids:
        tb.element_id = eids[0]

    # Scale
    m = re.search(r'\b(1:\d+)\b', text)
    if m:
        tb.scale = m.group(1)

    # Year
    m = re.search(r'\b(202\d)\b', text)
    if m:
        tb.year = m.group(1)

    # Total weight: look for "IT.WT" followed by a number on next line
    for i, line in enumerate(lines):
        if line.strip() in ('IT.WT', 'TOTAL WEIGHT IN kg.'):
            # Look for number within 3 lines
            for j in range(i+1, min(i+4, len(lines))):
                if RE_FLOAT.match(lines[j].strip()):
                    tb.total_weight_kg = lines[j].strip()
                    break

    # Sheet size
    m = re.search(r'\b(A0|A1|A2|A3|A4)\b', text)
    if m:
        tb.sheet_size = m.group(1)

    # Service title: look for "MECH." line (the main service description)
    for i, line in enumerate(lines):
        stripped = line.strip()
        if 'MECH.' in stripped and 'SYSTEM' in stripped.upper() and len(stripped) > 20:
            tb.title_line1 = stripped
            # Next non-empty line with sufficient length is subtitle
            for j in range(i+1, min(i+5, len(lines))):
                nxt = lines[j].strip()
                if nxt and len(nxt) > 8 and 'MECH' not in nxt.upper():
                    tb.title_line2 = nxt
                    break
            break

    # Client
    for line in lines:
        if 'PORT COMPANY' in line or 'DHAMRA PORT' in line:
            tb.client = line.strip()
            break

    # Consultant
    for line in lines:
        if 'ADANI INFRA' in line:
            tb.consultant = line.strip()
            break

    # People codes + date
    # They appear in cluster: DRAWN_BY, CHECKED_BY, APPROVED_BY, DATE
    # followed or preceded by "MECHANICAL"
    person_re = re.compile(r'^([A-Z]{2,4})$')
    date_re   = re.compile(r'^\d{1,2}[-./]\d{1,2}[-./]\d{2,4}$')
    SKIP = {'YES','NO','EPC','MECH','HDG','KG','EA','UB','IS','GR',
            'THE','FOR','CAD','OK','MHS','FAB','GA','IM','OK','NOS',
            'ALL','HOT','DIP','LTD','PVT','INC','AGO'}

    for i, line in enumerate(lines):
        if line.strip() == 'MECHANICAL':
            # Gather person codes and dates nearby
            nearby = lines[max(0,i-6):i+6]
            persons = [l.strip() for l in nearby if person_re.match(l.strip()) and l.strip() not in SKIP]
            dates   = [l.strip() for l in nearby if date_re.match(l.strip())]
            if len(persons) >= 3 and not tb.drawn_by:
                tb.drawn_by    = persons[0]
                tb.checked_by  = persons[1]
                tb.approved_by = persons[2]
            if dates and not tb.date:
                tb.date = dates[-1]
            break

    # Revision history
    # Pattern in lines: '-- 01' ... 'DRAWING REVISED AS PER MARKED' ... date ... persons
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        # Look for pattern: "--" or "-" followed by revision number on same or next line
        m = re.match(r'^(?:--|-)?\s*(\d{1,2})$', line)
        if m:
            rev_num = m.group(1)
            # Look ahead for date, persons, description
            segment = ' '.join(l.strip() for l in lines[i:min(i+10, len(lines))])
            date_m = re.search(r'(\d{1,2}[-./]\d{1,2}[-./]\d{2,4})', segment)
            desc_m = re.search(r'(DRAWING REVISED[\w\s.]+)', segment, re.IGNORECASE)
            persons_in_seg = [l.strip() for l in lines[i:min(i+10, len(lines))]
                              if person_re.match(l.strip()) and l.strip() not in SKIP]
            if date_m and desc_m and persons_in_seg:
                tb.revision_history.append({
                    'rev': rev_num,
                    'date': date_m.group(1),
                    'revd_by': persons_in_seg[0] if len(persons_in_seg) > 0 else '',
                    'appd_by': persons_in_seg[1] if len(persons_in_seg) > 1 else '',
                    'description': _clean(desc_m.group(1)),
                })
        i += 1

    # Revision: the current revision number appears just before document ID
    if doc_ids:
        doc_idx = next((i for i, l in enumerate(lines) if l.strip() == tb.document_id), -1)
        if doc_idx >= 2:
            # Check line before document_id for revision number
            for j in range(doc_idx-1, max(0, doc_idx-4), -1):
                cand = lines[j].strip()
                if RE_INT.match(cand) and int(cand) <= 20:
                    tb.revision = cand
                    break

    return tb


# ---------------------------------------------------------------------------
# BoM extraction (7 lines per row)
# ---------------------------------------------------------------------------

def _parse_bom_section(lines: list) -> List[BomItem]:
    """
    The BoM rows in the PDF are each split across exactly 7 lines:
      [0] item_no    (e.g. '1', '4A', etc.)
      [1] description (e.g. 'UB 356x171x51', 'PLATE', 'ISMC 250')
      [2] specification (e.g. 'IS:2062')
      [3] size        (e.g. '2993 LG.', '300 x 380 x 16THK')
      [4] quantity    (e.g. '4')
      [5] part_weight (e.g. '57.27')
      [6] purchase_code (e.g. 'IPPR01001600000')

    Before the BoM block there is a DU (dispatch unit) block.
    We detect BoM rows by looking for the pattern:
      item_no (INT or INT+LETTER) -> description keyword -> IS:xxxx -> size -> int -> float -> PICODE
    """
    items = []

    n = len(lines)
    i = 0
    while i < n - 6:
        # Check for 7-line BoM row pattern
        l0 = lines[i].strip()
        l1 = lines[i+1].strip() if i+1 < n else ''
        l2 = lines[i+2].strip() if i+2 < n else ''
        l3 = lines[i+3].strip() if i+3 < n else ''
        l4 = lines[i+4].strip() if i+4 < n else ''
        l5 = lines[i+5].strip() if i+5 < n else ''
        l6 = lines[i+6].strip() if i+6 < n else ''

        if (RE_ITEM_NO.match(l0)
                and _is_description(l1)
                and RE_SPEC.match(l2)
                and (RE_SIZE_PLATE.match(l3) or RE_SIZE_LEN.match(l3) or RE_FLOAT.match(l3))
                and RE_INT.match(l4)
                and RE_FLOAT.match(l5)
                and RE_PICODE.match(l6)):

            item = BomItem(
                item_no=l0,
                description=_clean(l1),
                specification=_clean(l2),
                size=_clean(l3),
                quantity=_i(l4),
                part_weight_kg=_f(l5),
                purchase_item_code=l6,
            )
            d1, d2, thk = _parse_plate_dims(item.size)
            if d1 is not None:
                item.dim1, item.dim2, item.thickness = d1, d2, thk
            else:
                item.length = _parse_len(item.size)

            items.append(item)
            i += 7
            continue

        i += 1

    def _natural_sort_key(it):
        m = re.match(r'^(\d+)(.*)', it.item_no)
        if m:
            return (int(m.group(1)), m.group(2))
        return (99999, it.item_no)

    items.sort(key=_natural_sort_key)
    return items


# ---------------------------------------------------------------------------
# Hardware extraction
# ---------------------------------------------------------------------------

def _parse_hardware_section(text: str) -> List[HardwareItem]:
    """
    Hardware rows in raw text (space-delimited within one line):
      0  FWASHA16H00000G  HSS Plain Washer M16,IS:6649,HDG  B  F1  16  0.329  EA
    """
    items = []
    hw_re = re.compile(
        r'^0\s+([A-Z0-9]{10,})\s+(.+?)\s+B\s+(F\d+)\s+(\d+)\s+([\d.]+)\s+(EA)',
        re.IGNORECASE | re.MULTILINE
    )
    for m in hw_re.finditer(text):
        items.append(HardwareItem(
            purchase_item_code=m.group(1),
            description=_clean(m.group(2)),
            bolt_mark=m.group(3).upper(),
            quantity=_i(m.group(4)),
            unit_weight_kg=_f(m.group(5)),
            uom='EA',
        ))
    return items


# ---------------------------------------------------------------------------
# Dispatch unit extraction
# ---------------------------------------------------------------------------

def _parse_dispatch_units(lines: list) -> List[DispatchUnit]:
    """
    DU rows appear as 8 consecutive lines:
      [0] DU_NO (alphanumeric, e.g. 'BCU4CFR1')
      [1] DESCRIPTION
      [2] TYPE ('F','B','A')
      [3] REMARK ('-' or text)
      [4] QTY
      [5] WEIGHT
      [6] UOM ('KG', 'EA')
      [7] PURCHASE_CODE
    """
    units = []
    DU_NO_RE    = re.compile(r'^[A-Z][A-Z0-9]{3,}$')
    TYPE_RE     = re.compile(r'^(F|B|A)$', re.IGNORECASE)
    REMARK_RE   = re.compile(r'^(-|[\w.]+)$')
    UOM_RE      = re.compile(r'^(KG|EA)$', re.IGNORECASE)
    PICODE8_RE  = re.compile(r'^\w{7,}$')

    n = len(lines)
    i = 0
    while i < n - 7:
        l0 = lines[i].strip()
        l1 = lines[i+1].strip() if i+1 < n else ''
        l2 = lines[i+2].strip() if i+2 < n else ''
        l3 = lines[i+3].strip() if i+3 < n else ''
        l4 = lines[i+4].strip() if i+4 < n else ''
        l5 = lines[i+5].strip() if i+5 < n else ''
        l6 = lines[i+6].strip() if i+6 < n else ''
        l7 = lines[i+7].strip() if i+7 < n else ''

        if (DU_NO_RE.match(l0)
                and l1 and not RE_SPEC.match(l1)
                and TYPE_RE.match(l2)
                and REMARK_RE.match(l3)
                and RE_INT.match(l4)
                and RE_FLOAT.match(l5)
                and UOM_RE.match(l6)
                and PICODE8_RE.match(l7)
                # Not a BoM item (BoM starts with INT item_no)
                and not RE_ITEM_NO.match(l0)):

            units.append(DispatchUnit(
                du_no=l0,
                description=_clean(l1),
                du_type=l2.upper(),
                du_weight_kg=_f(l5),
                uom=l6.upper(),
                purchase_item_code=l7,
            ))
            i += 8
            continue
        i += 1

    return units


# ---------------------------------------------------------------------------
# Reference drawings extraction
# ---------------------------------------------------------------------------

def _parse_reference_drawings(lines: list, own_id: str) -> List[ReferenceDrawing]:
    refs = []
    n = len(lines)
    i = 0
    while i < n:
        line = lines[i].strip()
        if RE_DOC_ID.match(line) and line != own_id:
            desc = ""
            if i + 1 < n:
                nxt = lines[i+1].strip()
                if nxt and not RE_DOC_ID.match(nxt) and len(nxt) > 5:
                    desc = nxt
                    i += 1
            refs.append(ReferenceDrawing(document_id=line, description=desc))
        i += 1

    seen = set()
    unique = []
    for r in refs:
        if r.document_id not in seen:
            seen.add(r.document_id)
            unique.append(r)
    return unique


# ---------------------------------------------------------------------------
# Main API
# ---------------------------------------------------------------------------

def extract_drawing_data(pdf_path: str) -> DrawingData:
    doc = fitz.open(pdf_path)
    full_text = ""
    all_lines = []
    for page in doc:
        page_text = page.get_text()
        full_text += page_text + "\n"
        all_lines.extend(page_text.splitlines())
    doc.close()

    data = DrawingData(raw_text=full_text)
    data.title_block        = _find_title_block(full_text, all_lines)
    data.bom_items          = _parse_bom_section(all_lines)
    data.hardware_items     = _parse_hardware_section(full_text)
    data.dispatch_units     = _parse_dispatch_units(all_lines)
    data.reference_drawings = _parse_reference_drawings(
        all_lines, data.title_block.document_id)
    return data