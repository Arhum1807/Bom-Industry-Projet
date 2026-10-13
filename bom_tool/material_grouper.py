import re
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Tuple
from bom_extractor import BomItem, RE_PLATE_DIM


@dataclass
class GroupedMaterial:
    purchase_item_code: str = ""
    description: str = ""
    specification: str = ""
    base_size: str = ""
    combined_size: str = ""
    total_quantity: int = 0
    total_weight_kg: float = 0.0
    source_items: List[BomItem] = field(default_factory=list)
    combined_dim1: Optional[float] = None
    dim2: Optional[float] = None
    thickness: Optional[float] = None
    total_length: Optional[float] = None
    unit_description: str = ""
    sub_groups: List['GroupedMaterial'] = field(default_factory=list)


@dataclass
class SectionSummaryItem:
    sr_no: int = 0
    section: str = ""
    total_weight_kg: float = 0.0


@dataclass
class SectionSummary:
    items: List[SectionSummaryItem] = field(default_factory=list)
    grand_total_kg: float = 0.0


def _is_plate(item: BomItem) -> bool:
    desc = item.description.upper()
    return ('PLATE' in desc or 'PLT' in desc) and (item.thickness is not None or RE_PLATE_DIM.search(item.size) is not None or 'THK' in item.size.upper())


def get_section_name(item: BomItem) -> str:
    """
    Returns section name as displayed in engineering drawing summary tables.
    e.g. 'UB 406x178x67' for sections, or 'PLT. 25 THK.' for plates.
    """
    desc = item.description.strip()
    u = desc.upper()
    if 'PLATE' in u or 'PLT' in u:
        thk = item.thickness
        if thk is None:
            m = RE_PLATE_DIM.search(item.size)
            if m:
                thk = float(m.group(3))
        if thk is not None:
            thk_str = f"{int(thk)}" if float(thk).is_integer() else f"{thk}"
            return f"PLT. {thk_str} THK."
        m = re.search(r'([\d.]+)\s*THK', item.size, re.IGNORECASE)
        if m:
            v = float(m.group(1))
            thk_str = f"{int(v)}" if v.is_integer() else f"{v}"
            return f"PLT. {thk_str} THK."
        return "PLT. THK."
    return desc


def get_section_summary(bom_items: List[BomItem]) -> SectionSummary:
    """
    Generate section summary table (SR. NO., SECTION, TOTAL WEIGHT) matching drawing format.
    """
    sections: Dict[str, float] = {}
    section_order: List[str] = []

    for item in bom_items:
        sec = get_section_name(item)
        if sec not in sections:
            sections[sec] = 0.0
            section_order.append(sec)
        sections[sec] += item.part_weight_kg

    items_list: List[SectionSummaryItem] = []
    grand_total = 0.0

    for idx, sec in enumerate(section_order, 1):
        wt = round(sections[sec], 2)
        grand_total += wt
        items_list.append(SectionSummaryItem(
            sr_no=idx,
            section=sec,
            total_weight_kg=wt
        ))

    return SectionSummary(
        items=items_list,
        grand_total_kg=round(grand_total, 2)
    )


def _plate_key(item: BomItem) -> Tuple:
    """Key for grouping plates: same dim2 and thickness."""
    return (round(item.dim2 or 0, 1), round(item.thickness or 0, 1))


def _combine_plate_items(items: List[BomItem], desc: str, spec: str, code: str) -> 'GroupedMaterial':
    """
    Combine plate items that share the same dim2 (width) and thickness.
    The first dimension (length) is summed (qty * dim1 for each part).
    """
    total_dim1   = sum((it.dim1 or 0) * it.quantity for it in items)
    total_weight = sum(it.part_weight_kg for it in items)
    total_qty    = sum(it.quantity for it in items)

    ref  = items[0]
    dim2 = ref.dim2 or 0
    thk  = ref.thickness or 0

    # Combined size: "sum_dim1 x dim2 x thkTHK"
    combined_size = f"{total_dim1:.0f} x {dim2:.0f} x {thk:.0f}THK"

    return GroupedMaterial(
        purchase_item_code=code,
        description=desc,
        specification=spec,
        base_size=f"{dim2:.0f}x{thk:.0f}THK",
        combined_size=combined_size,
        total_quantity=total_qty,
        total_weight_kg=total_weight,
        source_items=items,
        combined_dim1=total_dim1,
        dim2=dim2,
        thickness=thk,
    )


def _combine_section_items(items: List[BomItem], desc: str, spec: str, code: str) -> 'GroupedMaterial':
    """Sum total run length for sections."""
    total_length = sum((it.length or 0) * it.quantity for it in items)
    total_weight = sum(it.part_weight_kg for it in items)
    total_qty    = sum(it.quantity for it in items)
    combined_size = f"{total_length:.0f} LG. (combined)"

    return GroupedMaterial(
        purchase_item_code=code,
        description=desc,
        specification=spec,
        base_size=items[0].size if items else "",
        combined_size=combined_size,
        total_quantity=total_qty,
        total_weight_kg=total_weight,
        source_items=items,
        total_length=total_length,
        unit_description=desc,
    )


def _combine_generic(items: List[BomItem], desc: str, spec: str, code: str) -> 'GroupedMaterial':
    total_weight = sum(it.part_weight_kg for it in items)
    total_qty    = sum(it.quantity for it in items)
    sizes = list(dict.fromkeys(it.size for it in items))  # unique sizes in order
    combined_size = ' + '.join(sizes) if len(sizes) > 1 else sizes[0] if sizes else ''

    return GroupedMaterial(
        purchase_item_code=code,
        description=desc,
        specification=spec,
        base_size=items[0].size if items else '',
        combined_size=combined_size,
        total_quantity=total_qty,
        total_weight_kg=total_weight,
        source_items=items,
    )


def group_bom_items(bom_items: List[BomItem]) -> List['GroupedMaterial']:
    """
    Group items by purchase_item_code.
    For plates: sub-group further by (dim2, thickness) so only truly compatible
    plates are combined (same width and thickness -> can sum lengths).
    Returns a flat list of GroupedMaterial, one entry per sub-group.
    """
    # Group by purchase_item_code
    by_code: Dict[str, List[BomItem]] = {}
    for item in bom_items:
        code = item.purchase_item_code or f"UNKNOWN_{item.description}"
        if code not in by_code:
            by_code[code] = []
        by_code[code].append(item)

    result: List[GroupedMaterial] = []

    for code, items in by_code.items():
        if not items:
            continue

        ref = items[0]
        desc = ref.description
        spec = ref.specification

        if _is_plate(ref):
            # Sub-group by (dim2, thickness)
            sub: Dict[Tuple, List[BomItem]] = {}
            for it in items:
                key = _plate_key(it)
                if key not in sub:
                    sub[key] = []
                sub[key].append(it)

            for (d2, thk), group_items in sub.items():
                gm = _combine_plate_items(group_items, desc, spec, code)
                result.append(gm)

        elif ref.length is not None:
            result.append(_combine_section_items(items, desc, spec, code))
        else:
            result.append(_combine_generic(items, desc, spec, code))

    result.sort(key=lambda g: (g.description, g.purchase_item_code))
    return result


def format_material_summary(grouped: List[GroupedMaterial]) -> str:
    lines = []
    for g in grouped:
        note = f" [COMBINED: {len(g.source_items)} parts]" if len(g.source_items) > 1 else ""
        lines.append(
            f"[{g.purchase_item_code}] {g.description} {g.specification} "
            f"| {g.combined_size} | Qty: {g.total_quantity} "
            f"| Wt: {g.total_weight_kg:.2f} kg{note}"
        )
    return '\n'.join(lines)