"""
app.py - Flask web application for BOM Analyser
"""

import os
import json
import uuid
import threading
from pathlib import Path
from flask import Flask, render_template, request, jsonify, send_file, abort

# Tool modules
import sys
sys.path.insert(0, str(Path(__file__).parent))

from image_extractor import extract_any
from material_grouper import group_bom_items, get_section_summary
from report_generator import generate_report

app = Flask(__name__)
app.config['TEMPLATES_AUTO_RELOAD'] = True

UPLOAD_DIR = Path(__file__).parent / 'uploads'
REPORT_DIR = Path(__file__).parent / 'uploads' / 'reports'
UPLOAD_DIR.mkdir(exist_ok=True)
REPORT_DIR.mkdir(exist_ok=True)

ALLOWED_EXTS = {'.pdf', '.jpg', '.jpeg', '.png', '.tiff', '.tif', '.bmp', '.webp'}

# In-memory job store: job_id -> { status, result, error, report_path }
JOBS = {}
JOBS_LOCK = threading.Lock()


def _serialise_data(data, grouped, sec_summary):
    """Convert DrawingData + grouped + section_summary to JSON-serialisable dict."""
    tb = data.title_block
    return {
        'title_block': {
            'document_id'    : tb.document_id,
            'title_line1'    : tb.title_line1,
            'title_line2'    : tb.title_line2,
            'project_id'     : tb.project_id,
            'element_id'     : tb.element_id,
            'revision'       : tb.revision,
            'date'           : tb.date,
            'scale'          : tb.scale,
            'sheet_size'     : tb.sheet_size,
            'year'           : tb.year,
            'total_weight_kg': tb.total_weight_kg,
            'drawn_by'       : tb.drawn_by,
            'checked_by'     : tb.checked_by,
            'approved_by'    : tb.approved_by,
            'client'         : tb.client,
            'consultant'     : tb.consultant,
            'service'        : tb.service,
            'revision_history': tb.revision_history,
        },
        'section_summary': {
            'items': [
                {
                    'sr_no': item.sr_no,
                    'section': item.section,
                    'total_weight_kg': item.total_weight_kg
                }
                for item in sec_summary.items
            ],
            'grand_total_kg': sec_summary.grand_total_kg
        },
        'bom_items': [
            {
                'item_no'           : b.item_no,
                'description'       : b.description,
                'specification'     : b.specification,
                'size'              : b.size,
                'quantity'          : b.quantity,
                'part_weight_kg'    : b.part_weight_kg,
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
                'source_sizes'      : [s.size for s in g.source_items],
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
                'total_weight_kg'   : round(h.unit_weight_kg * h.quantity, 3),
                'uom'               : h.uom,
            }
            for h in data.hardware_items
        ],
        'dispatch_units': [
            {
                'du_no'             : d.du_no,
                'description'       : d.description,
                'du_type'           : d.du_type,
                'du_weight_kg'      : d.du_weight_kg,
                'uom'               : d.uom,
                'purchase_item_code': d.purchase_item_code,
            }
            for d in data.dispatch_units
        ],
        'reference_drawings': [
            {'document_id': r.document_id, 'description': r.description}
            for r in data.reference_drawings
        ],
        'stats': {
            'bom_count'     : len(data.bom_items),
            'grouped_count' : len(grouped),
            'section_count' : len(sec_summary.items),
            'hardware_count': len(data.hardware_items),
            'du_count'      : len(data.dispatch_units),
            'refs_count'    : len(data.reference_drawings),
            'total_weight'  : sec_summary.grand_total_kg if sec_summary.grand_total_kg else tb.total_weight_kg,
        }
    }


def _process_job(job_id: str, file_path: str):
    """Background thread: extract data + generate report."""
    try:
        with JOBS_LOCK:
            JOBS[job_id]['status'] = 'extracting'

        data        = extract_any(file_path)
        sec_summary = get_section_summary(data.bom_items)
        grouped     = group_bom_items(data.bom_items)

        with JOBS_LOCK:
            JOBS[job_id]['status'] = 'generating'

        report_name = f"{job_id}_REPORT.pdf"
        report_path = str(REPORT_DIR / report_name)
        generate_report(data, report_path)

        excel_name = f"{job_id}_GROUPED.xlsx"
        excel_path = str(REPORT_DIR / excel_name)
        from report_generator import generate_grouped_excel, generate_annotated_pdf
        generate_grouped_excel(grouped, sec_summary, excel_path)

        annotated_name = f"{job_id}_ANNOTATED.pdf"
        annotated_path = str(REPORT_DIR / annotated_name)
        generate_annotated_pdf(file_path, grouped, sec_summary, annotated_path)

        result = _serialise_data(data, grouped, sec_summary)

        with JOBS_LOCK:
            JOBS[job_id].update({
                'status'     : 'done',
                'result'     : result,
                'report_path': report_path,
                'report_name': report_name,
                'excel_path' : excel_path,
                'excel_name' : excel_name,
                'annotated_path': annotated_path,
                'annotated_name': annotated_name,
            })
    except Exception as e:
        import traceback
        with JOBS_LOCK:
            JOBS[job_id].update({
                'status': 'error',
                'error' : str(e),
                'trace' : traceback.format_exc(),
            })


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/upload', methods=['POST'])
def upload():
    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400

    f = request.files['file']
    if not f.filename:
        return jsonify({'error': 'Empty filename'}), 400

    ext = Path(f.filename).suffix.lower()
    if ext not in ALLOWED_EXTS:
        return jsonify({'error': f'Unsupported file type: {ext}. Allowed: {", ".join(sorted(ALLOWED_EXTS))}'}), 400

    job_id   = str(uuid.uuid4())
    save_path = str(UPLOAD_DIR / f"{job_id}{ext}")
    f.save(save_path)

    with JOBS_LOCK:
        JOBS[job_id] = {
            'status'     : 'queued',
            'filename'   : f.filename,
            'result'     : None,
            'report_path': None,
            'excel_path' : None,
            'error'      : None,
        }

    # Process in background thread
    t = threading.Thread(target=_process_job, args=(job_id, save_path), daemon=True)
    t.start()

    return jsonify({'job_id': job_id})


@app.route('/status/<job_id>')
def status(job_id):
    with JOBS_LOCK:
        job = JOBS.get(job_id)
    if not job:
        return jsonify({'error': 'Job not found'}), 404
    return jsonify({
        'status'  : job['status'],
        'filename': job.get('filename', ''),
        'result'  : job.get('result'),
        'error'   : job.get('error'),
    })


@app.route('/download/<job_id>')
def download(job_id):
    with JOBS_LOCK:
        job = JOBS.get(job_id)
    if not job or job['status'] != 'done':
        abort(404)
    # Prefer drawing with SUMMARY table stamped in-place
    annotated_path = job.get('annotated_path')
    if annotated_path and os.path.exists(annotated_path):
        filename = Path(job['filename']).stem + '_WITH_SUMMARY.pdf'
        return send_file(annotated_path, as_attachment=True, download_name=filename)
    report_path = job['report_path']
    filename = Path(job['filename']).stem + '_REPORT.pdf'
    return send_file(report_path, as_attachment=True, download_name=filename)


@app.route('/download_excel/<job_id>')
def download_excel(job_id):
    with JOBS_LOCK:
        job = JOBS.get(job_id)
    if not job or job['status'] != 'done':
        abort(404)
    excel_path = job.get('excel_path')
    if not excel_path or not os.path.exists(excel_path):
        abort(404)
    filename = Path(job['filename']).stem + '_GROUPED_MATERIALS.xlsx'
    return send_file(excel_path, as_attachment=True, download_name=filename)


@app.route('/download_annotated/<job_id>')
def download_annotated(job_id):
    with JOBS_LOCK:
        job = JOBS.get(job_id)
    if not job or job['status'] != 'done':
        abort(404)
    annotated_path = job.get('annotated_path')
    if not annotated_path or not os.path.exists(annotated_path):
        abort(404)
    filename = Path(job['filename']).stem + '_WITH_SUMMARY.pdf'
    return send_file(annotated_path, as_attachment=True, download_name=filename)


@app.route('/download_report/<job_id>')
def download_report_pdf(job_id):
    with JOBS_LOCK:
        job = JOBS.get(job_id)
    if not job or job['status'] != 'done':
        abort(404)
    report_path = job['report_path']
    filename = Path(job['filename']).stem + '_REPORT.pdf'
    return send_file(report_path, as_attachment=True, download_name=filename)


if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=5050)