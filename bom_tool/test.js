
let currentJobId = null;
let pollTimer = null;

// ── Upload Handlers ──────────────────────────────────────────────────────────

const dropZone   = document.getElementById('drop-zone');
const fileInput  = document.getElementById('file-input');
const browseBtn  = document.getElementById('browse-btn');

// Trigger file picker on click
dropZone.addEventListener('click', (e) => {
  fileInput.click();
});

browseBtn.addEventListener('click', (e) => {
  e.stopPropagation(); // Avoid double click inside dropZone
  fileInput.click();
});

// File selection handler
function handleFileSelect(e) {
  const files = (e.target && e.target.files) || fileInput.files;
  if (files && files.length > 0) {
    const file = files[0];
    fileInput.value = ''; // Reset so same file can be re-selected if needed
    uploadFile(file);
  }
}

fileInput.addEventListener('change', handleFileSelect);
fileInput.addEventListener('input', handleFileSelect);

// Drag & drop handlers
['dragenter', 'dragover'].forEach(name => {
  dropZone.addEventListener(name, (e) => {
    e.preventDefault();
    e.stopPropagation();
    dropZone.classList.add('drag-over');
  });
});

['dragleave', 'drop'].forEach(name => {
  dropZone.addEventListener(name, (e) => {
    e.preventDefault();
    e.stopPropagation();
    dropZone.classList.remove('drag-over');
  });
});

dropZone.addEventListener('drop', (e) => {
  e.preventDefault();
  e.stopPropagation();
  dropZone.classList.remove('drag-over');
  const dt = e.dataTransfer;
  if (dt && dt.files && dt.files.length > 0) {
    uploadFile(dt.files[0]);
  }
});

function formatBytes(bytes) {
  if (bytes === 0) return '0 Bytes';
  const k = 1024;
  const sizes = ['Bytes', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
}

function uploadFile(file) {
  if (!file) return;
  show('progress');
  const sizeText = file.size ? ' (' + formatBytes(file.size) + ')' : '';
  setProgress('Uploading drawing…', file.name + sizeText, 15);

  const fd = new FormData();
  fd.append('file', file);

  fetch('/upload', { method: 'POST', body: fd })
    .then(r => {
      if (!r.ok) {
        return r.json().then(data => { throw new Error(data.error || ('HTTP ' + r.status)); });
      }
      return r.json();
    })
    .then(data => {
      if (data.error) { showError(data.error); return; }
      currentJobId = data.job_id;
      pollStatus();
    })
    .catch(e => showError('Upload error: ' + e.message));
}

function pollStatus() {
  if (!currentJobId) return;
  fetch('/status/' + currentJobId)
    .then(r => {
      if (!r.ok) throw new Error('Status request failed');
      return r.json();
    })
    .then(data => {
      if (data.status === 'queued') {
        setProgress('Queued for processing…', 'Preparing extraction pipeline', 25);
        pollTimer = setTimeout(pollStatus, 700);
      } else if (data.status === 'extracting') {
        setProgress('Extracting drawing data…', 'Reading BoM table, title block & hardware specifications', 55);
        pollTimer = setTimeout(pollStatus, 700);
      } else if (data.status === 'generating') {
        setProgress('Generating PDF report…', 'Compiling material groups and engineering summary', 85);
        pollTimer = setTimeout(pollStatus, 600);
      } else if (data.status === 'done') {
        setProgress('Done!', 'Loading report results…', 100);
        setTimeout(() => renderResults(data.result), 350);
      } else if (data.status === 'error') {
        showError(data.error || 'Unknown error occurred during processing.');
      } else {
        pollTimer = setTimeout(pollStatus, 700);
      }
    })
    .catch(err => {
      console.warn('Poll error:', err);
      pollTimer = setTimeout(pollStatus, 1500);
    });
}

// ── UI state ─────────────────────────────────────────────────────────────────

function show(section) {
  document.getElementById('upload-section').style.display   = section === 'upload'   ? '' : 'none';
  document.getElementById('progress-section').style.display = section === 'progress' ? '' : 'none';
  document.getElementById('error-section').style.display    = section === 'error'    ? '' : 'none';
  document.getElementById('results-section').style.display  = section === 'results'  ? '' : 'none';
}

function setProgress(title, sub, pct) {
  document.getElementById('progress-title').textContent = title;
  document.getElementById('progress-sub').textContent   = sub;
  document.getElementById('progress-bar').style.width   = pct + '%';
}

function showError(msg) {
  show('error');
  document.getElementById('error-msg').textContent = msg;
}

function reset() {
  if (pollTimer) clearTimeout(pollTimer);
  currentJobId = null;
  fileInput.value = '';
  show('upload');
}

function downloadReport() {
  if (currentJobId) window.location = '/download/' + currentJobId;
}

// ── Render results ────────────────────────────────────────────────────────────

function esc(s) {
  if (s === null || s === undefined || s === '') return '–';
  return String(s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

function renderResults(r) {
  if (!r) { showError('No data extracted from drawing.'); return; }

  show('results');

  const tb = r.title_block || {};

  // Title
  const docId = tb.document_id || 'Engineering Drawing';
  document.getElementById('results-title').textContent = docId;

  // Stats
  const s = r.stats || {};
  document.getElementById('st-bom').textContent  = s.bom_count !== undefined ? s.bom_count : '–';
  document.getElementById('st-grp').textContent  = s.grouped_count !== undefined ? s.grouped_count : '–';
  document.getElementById('st-hw').textContent   = s.hardware_count !== undefined ? s.hardware_count : '–';
  document.getElementById('st-du').textContent   = s.du_count !== undefined ? s.du_count : '–';
  document.getElementById('st-refs').textContent = s.refs_count !== undefined ? s.refs_count : '–';
  document.getElementById('st-wt').textContent   = s.total_weight ? s.total_weight : '–';

  document.getElementById('grp-count').textContent = s.grouped_count || 0;
  document.getElementById('hw-count').textContent  = s.hardware_count || 0;
  document.getElementById('bom-count').textContent = s.bom_count || 0;
  document.getElementById('du-count').textContent  = s.du_count || 0;
  document.getElementById('ref-count').textContent = s.refs_count || 0;

  // Part 1: Info grid
  const infoItems = [
    ['Document ID',   tb.document_id,    true],
    ['Project ID',    tb.project_id,     true],
    ['Element ID',    tb.element_id,     true],
    ['Title',         [tb.title_line1, tb.title_line2].filter(Boolean).join(' — '), false],
    ['Revision',      tb.revision,       false],
    ['Date',          tb.date,           false],
    ['Scale',         tb.scale,          false],
    ['Sheet Size',    tb.sheet_size,     false],
    ['Year',          tb.year,           false],
    ['Total Weight',  tb.total_weight_kg ? tb.total_weight_kg + ' kg' : '', false],
    ['Drawn By',      tb.drawn_by,       false],
    ['Checked By',    tb.checked_by,     false],
    ['Approved By',   tb.approved_by,    false],
    ['Client',        tb.client,         false],
    ['Consultant',    tb.consultant,     false],
    ['Service',       tb.service,        false],
  ].filter(([,v]) => v);

  const ig = document.getElementById('info-grid');
  ig.innerHTML = infoItems.map(([label, val, mono]) =>
    `<div class="info-item">
      <div class="info-label">${esc(label)}</div>
      <div class="info-value ${mono ? 'mono' : ''}">${esc(val)}</div>
    </div>`
  ).join('');

  // Revision history
  if (tb.revision_history && tb.revision_history.length) {
    document.getElementById('rev-history-wrap').style.display = '';
    document.getElementById('rev-tbody').innerHTML = tb.revision_history.map(rv =>
      `<tr>
        <td>${esc(rv.rev)}</td>
        <td>${esc(rv.date)}</td>
        <td>${esc(rv.revised_by)}</td>
        <td>${esc(rv.approved_by)}</td>
        <td>${esc(rv.description)}</td>
      </tr>`
    ).join('');
  } else {
    document.getElementById('rev-history-wrap').style.display = 'none';
  }

  // Part 2: Grouped materials
  const gb = document.getElementById('grp-tbody');
  const grouped = r.grouped_materials || [];
  gb.innerHTML = grouped.map((g, i) => {
    const isCombined = g.parts_combined > 1;
    const combinedTag = isCombined
      ? `<span class="combined-badge">✦ ${g.parts_combined} parts combined</span>` : '';

    let breakdownHtml = '';
    if (isCombined && g.source_item_nos && g.source_item_nos.length) {
      const rows = g.source_item_nos.map((no, idx) => {
        const sz = (g.source_sizes && g.source_sizes[idx]) || '';
        return `<div class="breakdown-row">
          <span class="breakdown-no">Part #${esc(no)}</span>
          <span class="dim-original">${esc(sz)}</span>
        </div>`;
      }).join('');

      breakdownHtml = `
        <br>
        <button type="button" class="breakdown-btn" onclick="toggleBreakdown(this)">▶ Show combination detail</button>
        <div class="breakdown-panel">
          ${rows}
          <div style="margin-top:.5rem;font-size:.72rem;color:var(--accent);font-weight:600">→ Combined: ${esc(g.combined_size)}</div>
        </div>`;
    }

    const wtStr = (g.total_weight_kg !== null && g.total_weight_kg !== undefined && !isNaN(g.total_weight_kg))
      ? Number(g.total_weight_kg).toFixed(3)
      : '–';

    return `<tr>
      <td>${i + 1}</td>
      <td style="font-weight:600;color:#fff">${esc(g.description)}${combinedTag}${breakdownHtml}</td>
      <td class="mono-td">${esc(g.specification)}</td>
      <td><span class="dim-combined">${esc(g.combined_size)}</span></td>
      <td><span class="qty-badge">${g.total_quantity || 1}</span></td>
      <td>${wtStr}</td>
      <td class="mono-td">${esc(g.purchase_item_code)}</td>
      <td style="text-align:center;color:${isCombined ? 'var(--accent2)' : 'var(--muted)'};font-weight:${isCombined ? '700' : '400'}">${g.parts_combined || 1}</td>
    </tr>`;
  }).join('');

  // Part 3: Hardware
  const hb = document.getElementById('hw-tbody');
  const hardware = r.hardware_items || [];
  if (hardware.length) {
    document.getElementById('hw-card').style.display = '';
    hb.innerHTML = hardware.map(h => {
      const uwt = (h.unit_weight_kg !== null && h.unit_weight_kg !== undefined && !isNaN(h.unit_weight_kg))
        ? Number(h.unit_weight_kg).toFixed(3) : '–';
      const twt = (h.total_weight_kg !== null && h.total_weight_kg !== undefined && !isNaN(h.total_weight_kg))
        ? Number(h.total_weight_kg).toFixed(3) : '–';

      return `<tr>
        <td><span class="hw-mark">${esc(h.bolt_mark || '–')}</span></td>
        <td>${esc(h.description)}</td>
        <td class="mono-td">${esc(h.purchase_item_code)}</td>
        <td><span class="qty-badge">${h.quantity}</span></td>
        <td>${uwt}</td>
        <td>${twt}</td>
      </tr>`;
    }).join('');
  } else {
    document.getElementById('hw-card').style.display = 'none';
  }

  // Part 4: Raw BoM
  const bb = document.getElementById('bom-tbody');
  const bomItems = r.bom_items || [];
  if (bomItems.length) {
    document.getElementById('bom-card').style.display = '';
    bb.innerHTML = bomItems.map(b => {
      const wt = (b.part_weight_kg !== null && b.part_weight_kg !== undefined && !isNaN(b.part_weight_kg))
        ? Number(b.part_weight_kg).toFixed(3) : '–';

      return `<tr>
        <td class="mono-td">Part #${esc(b.item_no)}</td>
        <td>${esc(b.description)}</td>
        <td class="mono-td">${esc(b.specification)}</td>
        <td>${esc(b.size)}</td>
        <td><span class="qty-badge">${b.quantity}</span></td>
        <td>${wt}</td>
        <td class="mono-td">${esc(b.purchase_item_code)}</td>
      </tr>`;
    }).join('');
  } else {
    document.getElementById('bom-card').style.display = 'none';
  }

  // Part 5: Dispatch Units
  const db = document.getElementById('du-tbody');
  const dispatchUnits = r.dispatch_units || [];
  if (dispatchUnits.length) {
    document.getElementById('du-card').style.display = '';
    db.innerHTML = dispatchUnits.map(d => {
      const wt = (d.du_weight_kg !== null && d.du_weight_kg !== undefined && !isNaN(d.du_weight_kg))
        ? Number(d.du_weight_kg).toFixed(2) : '–';

      return `<tr>
        <td><span class="du-mark">${esc(d.du_no)}</span></td>
        <td style="font-weight:600;color:#fff">${esc(d.description)}</td>
        <td class="mono-td">${esc(d.du_type)}</td>
        <td>${wt}</td>
        <td><span class="qty-badge">${esc(d.uom)}</span></td>
        <td class="mono-td">${esc(d.purchase_item_code)}</td>
      </tr>`;
    }).join('');
  } else {
    document.getElementById('du-card').style.display = 'none';
  }

  // Part 6: References
  const rb = document.getElementById('ref-tbody');
  const refs = r.reference_drawings || [];
  if (refs.length) {
    document.getElementById('ref-card').style.display = '';
    rb.innerHTML = refs.map(rd =>
      `<tr>
        <td class="mono-td">${esc(rd.document_id)}</td>
        <td>${esc(rd.description)}</td>
      </tr>`
    ).join('');
  } else {
    document.getElementById('ref-card').style.display = 'none';
  }
}

function toggleBreakdown(btn) {
  const panel = btn.nextElementSibling;
  const open  = panel.style.display === 'block';
  panel.style.display = open ? 'none' : 'block';
  btn.textContent     = (open ? '▶' : '▼') + ' ' + (open ? 'Show' : 'Hide') + ' combination detail';
}
