/* =============================================================================
   wizard.js  –  Step navigation, questionnaire, CSV upload
   ============================================================================= */

const state = {
  tableName:        '',
  dataUseType:      'analytical',   // selected on step 1
  questions:        [],
  dimensionLabels:  {},
  standards:        {},
  currentDimension: 0,
  answers:          {},
  csvContent:       null,
  columnStandards:  {},
  columnFlags:      {},
  assessResult:     null,
};

const ORDERED_DIMS = [
  'governance_ownership',
  'quality_management',
  'lineage_documentation',
  'security_access',
  'training_compliance',
];

document.addEventListener('DOMContentLoaded', async () => {
  await Promise.all([loadQuestions(), loadStandards()]);
  initStep1();
  initUpload();
});

async function loadQuestions() {
  try {
    const res  = await fetch('/api/questions');
    const data = await res.json();
    state.questions       = data.questions || [];
    state.dimensionLabels = data.dimension_labels || {};
  } catch (e) { console.error('Failed to load questions', e); }
}

async function loadStandards() {
  try {
    const res = await fetch('/api/standards');
    state.standards = await res.json();
  } catch (e) { console.error('Failed to load standards', e); }
}

// ── Step navigation ───────────────────────────────────────────────────────────

function showStep(stepId) {
  document.querySelectorAll('.step').forEach(s => s.classList.remove('active'));
  document.getElementById(stepId).classList.add('active');
  updateStepIndicator(stepId);
  window.scrollTo({ top: 0, behavior: 'smooth' });
}

function updateStepIndicator(stepId) {
  const map = { 'step-setup': 1, 'step-questionnaire': 2, 'step-upload': 3, 'step-results': 4 };
  const current = map[stepId] || 1;
  for (let i = 1; i <= 4; i++) {
    const dot  = document.getElementById(`dot-${i}`);
    const line = document.getElementById(`line-${i}`);
    dot.classList.remove('active', 'done');
    if (i < current)        dot.classList.add('done');
    else if (i === current) dot.classList.add('active');
    if (line) { line.classList.remove('done'); if (i < current) line.classList.add('done'); }
  }
}

// ── STEP 1 ────────────────────────────────────────────────────────────────────

function initStep1() {
  const input = document.getElementById('table-name-input');
  const btn   = document.getElementById('btn-begin');

  // Data use type selector
  document.querySelectorAll('.type-card').forEach(card => {
    card.addEventListener('click', () => {
      document.querySelectorAll('.type-card').forEach(c => c.classList.remove('selected'));
      card.classList.add('selected');
      state.dataUseType = card.dataset.type;
    });
  });

  btn.addEventListener('click', () => {
    const name = input.value.trim();
    if (!name) { input.focus(); input.style.borderColor = 'var(--red)'; return; }
    input.style.borderColor = '';
    state.tableName = name;
    state.currentDimension = 0;
    renderQuestionnaire();
    showStep('step-questionnaire');
  });

  input.addEventListener('keydown', e => { if (e.key === 'Enter') btn.click(); });
  input.addEventListener('input',   () => { input.style.borderColor = ''; });
}

// ── STEP 2: Questionnaire ─────────────────────────────────────────────────────

function renderQuestionnaire() {
  const dimId    = ORDERED_DIMS[state.currentDimension];
  const dimLabel = state.dimensionLabels[dimId] || dimId;
  const dimQs    = state.questions.filter(q => q.dimension === dimId);

  document.getElementById('dim-badge').textContent = `Dimension ${state.currentDimension + 1} of 5`;
  document.getElementById('dim-title').textContent = dimLabel;

  const container = document.getElementById('questions-container');
  container.innerHTML = '';

  dimQs.forEach(q => {
    const globalIndex = state.questions.findIndex(x => x.id === q.id) + 1;
    const selectedVal = state.answers[q.id];
    const block = document.createElement('div');
    block.className = 'question-block';
    block.innerHTML = `
      <div class="q-number">Q${globalIndex}</div>
      <div class="ref">${q.reference || ''}</div>
      <div class="q-text">${q.text}</div>
      <div class="radio-cards" id="cards-${q.id}">
        ${q.options.map(opt => `
          <div class="radio-card ${selectedVal == opt.value ? 'selected' : ''}"
               data-qid="${q.id}" data-val="${opt.value}">
            <div class="mat-val">${opt.value}</div>
            <div class="mat-label">${opt.label}</div>
          </div>`).join('')}
      </div>`;
    container.appendChild(block);
  });

  container.querySelectorAll('.radio-card').forEach(card => {
    card.addEventListener('click', () => {
      const qid = card.dataset.qid;
      state.answers[qid] = parseInt(card.dataset.val, 10);
      document.querySelectorAll(`[data-qid="${qid}"]`).forEach(c => c.classList.remove('selected'));
      card.classList.add('selected');
      updateProgress();
    });
  });

  const isLast = state.currentDimension === ORDERED_DIMS.length - 1;

  const btnPrev = document.getElementById('btn-prev');
  const newPrev = btnPrev.cloneNode(true);
  btnPrev.parentNode.replaceChild(newPrev, btnPrev);
  newPrev.style.display = state.currentDimension === 0 ? 'none' : '';
  newPrev.addEventListener('click', () => {
    if (state.currentDimension > 0) { state.currentDimension--; renderQuestionnaire(); }
  });

  const btnNext = document.getElementById('btn-next');
  const newNext = btnNext.cloneNode(true);
  btnNext.parentNode.replaceChild(newNext, btnNext);
  newNext.textContent = isLast ? 'Continue to Data Profiling →' : 'Next →';
  newNext.addEventListener('click', () => {
    if (isLast) showStep('step-upload');
    else { state.currentDimension++; renderQuestionnaire(); }
  });

  const btnSkip = document.getElementById('btn-skip-profiling');
  const newSkip = btnSkip.cloneNode(true);
  btnSkip.parentNode.replaceChild(newSkip, btnSkip);
  newSkip.addEventListener('click', () => runAssessment());

  updateProgress();
}

function updateProgress() {
  const answered = Object.keys(state.answers).length;
  const total    = state.questions.length || 20;
  const pct      = Math.round(answered / total * 100);
  document.getElementById('progress-fill').style.width  = pct + '%';
  document.getElementById('progress-label').textContent = `${answered} of ${total} answered`;
}

// ── STEP 3: Upload ────────────────────────────────────────────────────────────

function initUpload() {
  const zone      = document.getElementById('upload-zone');
  const fileInput = document.getElementById('file-input');
  const btnBack   = document.getElementById('btn-back-to-q');

  btnBack.addEventListener('click', () => {
    state.currentDimension = ORDERED_DIMS.length - 1;
    renderQuestionnaire();
    showStep('step-questionnaire');
  });

  zone.addEventListener('click', () => fileInput.click());
  zone.addEventListener('dragover',  e => { e.preventDefault(); zone.classList.add('dragover'); });
  zone.addEventListener('dragleave', () => zone.classList.remove('dragover'));
  zone.addEventListener('drop', e => {
    e.preventDefault(); zone.classList.remove('dragover');
    if (e.dataTransfer.files[0]) handleFile(e.dataTransfer.files[0]);
  });
  fileInput.addEventListener('change', () => { if (fileInput.files[0]) handleFile(fileInput.files[0]); });
  document.getElementById('btn-run').addEventListener('click', () => runAssessment());
}

async function handleFile(file) {
  if (!file.name.toLowerCase().endsWith('.csv')) { alert('Please upload a .csv file.'); return; }

  showSpinner(true);
  const csvText = await readFileAsText(file);
  const formData = new FormData();
  formData.append('file', file);

  try {
    const res  = await fetch('/api/upload', { method: 'POST', body: formData });
    const text = await res.text();
    let data;
    try { data = JSON.parse(text); } catch (_) {
      showSpinner(false);
      alert('Server error (status ' + res.status + '). Check Render logs.');
      return;
    }
    showSpinner(false);
    if (data.error) { alert('Upload error: ' + data.error); return; }

    state.csvContent  = csvText;
    state.columnFlags = {};

    const successEl = document.getElementById('upload-success');
    successEl.textContent = `✓ ${file.name} uploaded — ${data.row_count.toLocaleString()} rows · ${data.col_count} columns`;
    successEl.style.display = 'block';

    renderPreview(data);
    renderColumnMapping(data.columns, data.col_hints || {});
    document.getElementById('preview-section').classList.remove('hidden');
    document.getElementById('btn-run').disabled = false;
  } catch (e) {
    showSpinner(false);
    alert('Upload failed: ' + e.message);
  }
}

function readFileAsText(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload  = e => resolve(e.target.result);
    reader.onerror = reject;
    reader.readAsText(file);
  });
}

function renderPreview(data) {
  document.getElementById('preview-meta').textContent =
    `${data.row_count.toLocaleString()} rows · ${data.col_count} columns`;
  const cols = data.columns;
  const rows = data.preview || [];
  document.getElementById('preview-table').innerHTML = `
    <thead><tr>${cols.map(c => `<th>${c}</th>`).join('')}</tr></thead>
    <tbody>${rows.map(row =>
      `<tr>${cols.map(c => `<td>${row[c] ?? ''}</td>`).join('')}</tr>`
    ).join('')}</tbody>`;
}

function renderColumnMapping(columns, colHints) {
  const grid = document.getElementById('mapping-grid');
  grid.innerHTML = '';

  const optionGroups = Object.entries(state.standards).map(([cat, stds]) =>
    `<optgroup label="${cat}">${stds.map(s =>
      `<option value="${s.id}" title="${s.description}">${s.name}</option>`
    ).join('')}</optgroup>`
  ).join('');

  columns.forEach(col => {
    const hint        = colHints[col] || 'text';
    const autoSuggest = hint === 'date' ? 'date_iso' : '';
    const saved       = state.columnFlags[col] || { mandatory: false, unique: false };

    const row = document.createElement('div');
    row.className = 'mapping-row';
    row.innerHTML = `
      <div>
        <div class="col-name">${col}</div>
        <div class="col-hint">${hint}</div>
      </div>
      <select>
        <option value="">No standard / Skip</option>
        ${optionGroups}
      </select>
      <div class="col-flags">
        <label class="flag-label">
          <input type="checkbox" class="flag-mandatory" ${saved.mandatory ? 'checked' : ''}> Mandatory
        </label>
        <label class="flag-label">
          <input type="checkbox" class="flag-unique" ${saved.unique ? 'checked' : ''}> Unique
        </label>
      </div>`;
    grid.appendChild(row);

    const sel = row.querySelector('select');
    if (autoSuggest && sel.querySelector(`option[value="${autoSuggest}"]`)) {
      sel.value = autoSuggest;
      state.columnStandards[col] = autoSuggest;
    }
    sel.addEventListener('change', e => {
      if (e.target.value) state.columnStandards[col] = e.target.value;
      else delete state.columnStandards[col];
    });

    state.columnFlags[col] = { mandatory: saved.mandatory, unique: saved.unique };
    row.querySelector('.flag-mandatory').addEventListener('change', e => {
      state.columnFlags[col].mandatory = e.target.checked;
    });
    row.querySelector('.flag-unique').addEventListener('change', e => {
      state.columnFlags[col].unique = e.target.checked;
    });
  });
}

// ── Assessment ────────────────────────────────────────────────────────────────

async function runAssessment() {
  showSpinner(true);
  try {
    const payload = {
      table_name:         state.tableName,
      data_use_type:      state.dataUseType,
      governance_answers: state.answers,
      csv_content:        state.csvContent,
      column_standards:   state.columnStandards,
      column_flags:       state.columnFlags,
    };

    const res  = await fetch('/api/assess', {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify(payload),
    });

    const text = await res.text();
    let data;
    try { data = JSON.parse(text); } catch (_) {
      showSpinner(false);
      alert('Server error (status ' + res.status + '). The assessment could not complete.');
      return;
    }

    showSpinner(false);
    if (data.error) { alert('Assessment error: ' + data.error); return; }

    state.assessResult = data;
    showStep('step-results');
    if (typeof renderResults === 'function') renderResults(data);
  } catch (e) {
    showSpinner(false);
    alert('Assessment failed: ' + e.message);
  }
}

function showSpinner(visible) {
  document.getElementById('spinner').classList.toggle('active', visible);
}
