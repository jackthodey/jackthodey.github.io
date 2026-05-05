/* =============================================================================
   wizard.js  –  Step navigation, questionnaire rendering, CSV upload
   =============================================================================

   This file drives the 4-step wizard UI:
     Step 1 (step-setup)         – Enter dataset name
     Step 2 (step-questionnaire) – Answer governance questions one dimension at a time
     Step 3 (step-upload)        – Upload a CSV and map columns to data standards
     Step 4 (step-results)       – Show assessment results (rendered by results.js)

   All mutable wizard state is kept in the `state` object below so that any
   function can read or write it without needing to query the DOM.

   Architecture note: this file contains NO rendering of the results screen.
   That is handled entirely by results.js which exposes a single renderResults()
   function called at the end of runAssessment().
   ============================================================================= */

// ── Application state object ──────────────────────────────────────────────────
// Single source of truth for everything the wizard needs to track.
// All functions read from and write to this object rather than using local variables
// that would be lost across function calls.
const state = {
  tableName:        '',   // Dataset name entered by the user on step 1
  questions:        [],   // Full question list loaded from /api/questions (20 items)
  dimensionLabels:  {},   // Map of dimension_key → display label from /api/questions
  standards:        {},   // Grouped standards from /api/standards { Category: [{id, name,...}] }
  currentDimension: 0,    // 0-based index into ORDERED_DIMS — which dimension is shown in step 2
  answers:          {},   // User's questionnaire answers { q1: 3, q2: 1, ... }
  sessionId:        null, // UUID returned by /api/upload — sent back in /api/assess
  columnStandards:  {},   // Column-to-standard mapping the user builds on step 3 { col_name: std_id }
  assessResult:     null, // Full assessment result from /api/assess — used by results.js
};

// ── Dimension display order ────────────────────────────────────────────────────
// The questionnaire renders one dimension at a time.  This array defines the
// fixed display order (matching the order in questions.py DIMENSION_LABELS).
// It is used to drive the "Next →" navigation through the 5 dimensions.
const ORDERED_DIMS = [
  'governance_ownership',    // Dimension 1: Data ownership and governance policy (Q1–Q4)
  'quality_management',      // Dimension 2: DQ rules, monitoring, issue processes (Q5–Q8)
  'lineage_documentation',   // Dimension 3: Lineage, data dictionary, change management (Q9–Q12)
  'security_access',         // Dimension 4: Classification, RBAC, PII, audit logs (Q13–Q16)
  'training_compliance',     // Dimension 5: Training, controls, regulation, retention (Q17–Q20)
];


// =============================================================================
// Bootstrap — runs when the DOM is fully loaded
// =============================================================================

// DOMContentLoaded fires once all HTML elements are parsed and available.
// We use async so we can await the parallel API calls before initialising the UI.
document.addEventListener('DOMContentLoaded', async () => {
  // Load questions and standards simultaneously (Promise.all runs both fetches in parallel).
  // Neither function depends on the other, so parallel loading is faster than sequential.
  await Promise.all([loadQuestions(), loadStandards()]);

  // Initialise step 1 event listeners only after data is loaded.
  // (Step 2 is initialised lazily when the user clicks "Begin".)
  initStep1();

  // Initialise step 3 (upload) event listeners.
  // This can be done at startup because it doesn't depend on API data.
  initUpload();
});


// ── Data loaders ──────────────────────────────────────────────────────────────

async function loadQuestions() {
  // Fetch the questionnaire data from the Flask /api/questions endpoint.
  try {
    const res  = await fetch('/api/questions');  // GET request — returns JSON
    const data = await res.json();               // Parse the JSON response body

    // Store the questions list and dimension labels in the shared state object.
    // Fall back to empty defaults if the server returned unexpected data.
    state.questions       = data.questions       || [];
    state.dimensionLabels = data.dimension_labels || {};
  } catch (e) {
    // Network error or JSON parse failure — log to console but don't crash the app.
    // The questionnaire will be empty; the user will see blank questions.
    console.error('Failed to load questions', e);
  }
}

async function loadStandards() {
  // Fetch the available data standards from the Flask /api/standards endpoint.
  try {
    const res          = await fetch('/api/standards'); // GET request
    state.standards    = await res.json();              // Store grouped standards directly in state
  } catch (e) {
    console.error('Failed to load standards', e);
  }
}


// =============================================================================
// Step navigation
// =============================================================================

function showStep(stepId) {
  // Hide all steps by removing the "active" class from every element with class "step".
  // Only the element with class "active" is visible (controlled by CSS: .step { display:none })
  document.querySelectorAll('.step').forEach(s => s.classList.remove('active'));

  // Show the requested step by adding "active" to the specific step element.
  document.getElementById(stepId).classList.add('active');

  // Update the step indicator dots and connecting lines in the header progress bar.
  updateStepIndicator(stepId);

  // Scroll smoothly back to the top of the page so the user sees the new step from the top.
  window.scrollTo({ top: 0, behavior: 'smooth' });
}

function updateStepIndicator(stepId) {
  // Map step element IDs to 1-based step numbers for indicator logic.
  const map = { 'step-setup': 1, 'step-questionnaire': 2, 'step-upload': 3, 'step-results': 4 };

  // Determine which step number is currently active.
  const current = map[stepId] || 1;  // Default to 1 if stepId is not in the map

  // Update each dot (circle) and line (connector) in the progress indicator.
  for (let i = 1; i <= 4; i++) {
    const dot  = document.getElementById(`dot-${i}`);    // The circle element for step i
    const line = document.getElementById(`line-${i}`);   // The connector line after step i (may not exist for step 4)

    // Reset both classes on every iteration to avoid stale state.
    dot.classList.remove('active', 'done');

    if (i < current) {
      dot.classList.add('done');    // Steps before the current one are "done" (filled/ticked)
    } else if (i === current) {
      dot.classList.add('active');  // The current step is "active" (highlighted)
    }
    // Steps after current get neither class — they appear as unvisited (grey)

    if (line) {
      line.classList.remove('done');         // Reset the line's done state
      if (i < current) line.classList.add('done');  // Fill the line for completed step connectors
    }
  }
}


// =============================================================================
// STEP 1: Setup — dataset name entry
// =============================================================================

function initStep1() {
  const input = document.getElementById('table-name-input');  // The text field
  const btn   = document.getElementById('btn-begin');          // The "Begin Assessment" button

  // When the user clicks "Begin Assessment":
  btn.addEventListener('click', () => {
    const name = input.value.trim();  // Get the input value and strip leading/trailing whitespace

    if (!name) {
      // Name is empty — focus the field and highlight it red to signal required input.
      input.focus();
      input.style.borderColor = 'var(--red)';  // Uses the CSS custom property --red
      return;  // Stop here; don't advance to the questionnaire
    }

    input.style.borderColor = '';     // Reset border colour (remove the red error highlight)
    state.tableName = name;           // Save the dataset name to state
    state.currentDimension = 0;       // Reset to the first dimension in case user went back

    renderQuestionnaire();            // Build the questionnaire UI for dimension 0
    showStep('step-questionnaire');   // Navigate to step 2
  });

  // Allow pressing Enter in the text field to trigger the Begin button.
  input.addEventListener('keydown', e => { if (e.key === 'Enter') btn.click(); });

  // Clear the red border as soon as the user starts typing (removes the error state).
  input.addEventListener('input', () => { input.style.borderColor = ''; });
}


// =============================================================================
// STEP 2: Questionnaire rendering
// =============================================================================

function renderQuestionnaire() {
  // Determine which dimension to render based on the current index.
  const dimId    = ORDERED_DIMS[state.currentDimension];      // e.g. "governance_ownership"
  const dimLabel = state.dimensionLabels[dimId] || dimId;     // e.g. "Governance & Ownership"

  // Filter the full question list to only questions belonging to this dimension.
  const dimQs   = state.questions.filter(q => q.dimension === dimId);

  // The dimension number displayed to the user (1-based)
  const dimNum  = state.currentDimension + 1;

  // Update the dimension badge and title in the UI header area.
  document.getElementById('dim-badge').textContent  = `Dimension ${dimNum} of 5`;
  document.getElementById('dim-title').textContent  = dimLabel;

  // Clear the questions container so we can render fresh HTML for this dimension.
  const container = document.getElementById('questions-container');
  container.innerHTML = '';  // Empty the container (removes previous dimension's questions)

  // Render each question in this dimension as a "question block".
  dimQs.forEach((q, i) => {
    // Find the global question number (1–20) by looking up its index in the full question list.
    const globalIndex = state.questions.findIndex(x => x.id === q.id) + 1;  // +1 because findIndex is 0-based

    const block = document.createElement('div');  // Create a container div for this question
    block.className = 'question-block';

    // Look up any existing answer for this question (user may be returning to this dimension).
    const selectedVal = state.answers[q.id];

    // Build the question HTML using a template literal.
    // Each answer option becomes a "radio-card" div with data attributes.
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
          </div>
        `).join('')}
      </div>
    `;
    // selectedVal == opt.value uses loose equality so string "3" matches number 3.
    // data-qid stores the question ID for click handler use.
    // data-val stores the maturity value (1–4) for recording in state.

    container.appendChild(block);  // Add the question block to the DOM
  });

  // ── Attach click listeners to all radio cards ──────────────────────────────
  // We query AFTER appending all blocks so all cards are in the DOM.
  container.querySelectorAll('.radio-card').forEach(card => {
    card.addEventListener('click', () => {
      const qid = card.dataset.qid;          // The question ID (e.g. "q3")
      const val = parseInt(card.dataset.val, 10);  // The maturity value (1–4) as an integer

      state.answers[qid] = val;  // Record the user's answer in the state object

      // De-select all cards for this question, then select the clicked one.
      // querySelectorAll with attribute selector finds all cards with the same question ID.
      document.querySelectorAll(`[data-qid="${qid}"]`).forEach(c => c.classList.remove('selected'));
      card.classList.add('selected');  // Highlight the clicked card

      updateProgress();  // Update the progress bar to reflect the new answer count
    });
  });

  // ── Navigation buttons ─────────────────────────────────────────────────────
  const btnPrev = document.getElementById('btn-prev');          // "← Back" button
  const btnNext = document.getElementById('btn-next');          // "Next →" or "Continue to Data Profiling →"
  const btnSkip = document.getElementById('btn-skip-profiling'); // "Skip profiling" button

  // Hide "← Back" on the first dimension (there's nowhere to go back to).
  btnPrev.style.display = state.currentDimension === 0 ? 'none' : '';

  // Change the "Next" button label on the last dimension to signal the step change.
  const isLast = state.currentDimension === ORDERED_DIMS.length - 1;
  btnNext.textContent = isLast ? 'Continue to Data Profiling →' : 'Next →';

  // ── Clone-and-replace pattern to avoid stacking duplicate event listeners ──
  // Problem: every call to renderQuestionnaire() would ADD another event listener
  // to the same button element, so clicking "Next" on dimension 3 would fire
  // the listener that was attached on dimension 1, 2, AND 3.
  //
  // Solution: replace the button node with a fresh clone (no listeners) and attach
  // exactly one new listener.  cloneNode(true) copies the element and all its attributes
  // but NOT its event listeners.

  const newNext = btnNext.cloneNode(true);                  // Deep clone (keeps text content and classes)
  btnNext.parentNode.replaceChild(newNext, btnNext);        // Replace the old node in the DOM
  newNext.textContent = isLast ? 'Continue to Data Profiling →' : 'Next →';  // Re-set text on the clone
  newNext.addEventListener('click', () => {
    if (isLast) {
      showStep('step-upload');  // Last dimension → advance to the CSV upload step
    } else {
      state.currentDimension++;  // Advance to the next dimension index
      renderQuestionnaire();     // Re-render for the new dimension
    }
  });

  const newPrev = btnPrev.cloneNode(true);                  // Clone the back button
  btnPrev.parentNode.replaceChild(newPrev, btnPrev);
  newPrev.style.display = state.currentDimension === 0 ? 'none' : '';  // Re-apply visibility
  newPrev.addEventListener('click', () => {
    if (state.currentDimension > 0) {
      state.currentDimension--;  // Go back one dimension
      renderQuestionnaire();
    }
  });

  const newSkip = btnSkip.cloneNode(true);                  // Clone the skip button
  btnSkip.parentNode.replaceChild(newSkip, btnSkip);
  // Clicking "Skip profiling" runs the assessment immediately with sessionId=null
  // (governance-only mode — profiling_score will be null in the results)
  newSkip.addEventListener('click', () => runAssessment(null));

  updateProgress();  // Sync the progress bar with the current answer count
}

function updateProgress() {
  // Count how many questions have been answered so far (across all dimensions).
  const answered = Object.keys(state.answers).length;

  // Total questions: use the loaded count, or fall back to 20 if not yet loaded.
  const total    = state.questions.length || 20;

  // Calculate completion percentage (0–100, rounded to nearest integer).
  const pct      = Math.round(answered / total * 100);

  // Update the progress bar fill width (CSS width property as a percentage string).
  document.getElementById('progress-fill').style.width  = pct + '%';

  // Update the label showing answered/total count.
  document.getElementById('progress-label').textContent = `${answered} of ${total} answered`;
}


// =============================================================================
// STEP 3: CSV Upload
// =============================================================================

function initUpload() {
  // Cache references to the DOM elements we'll interact with.
  const zone      = document.getElementById('upload-zone');    // The drag-and-drop target area
  const fileInput = document.getElementById('file-input');     // The hidden <input type="file">
  const btnRun    = document.getElementById('btn-run');        // "Run Assessment" button
  const btnBack   = document.getElementById('btn-back-to-q'); // "← Back to Questions" button

  // Clicking "Back to Questions" returns to the last dimension of the questionnaire.
  btnBack.addEventListener('click', () => {
    state.currentDimension = ORDERED_DIMS.length - 1;  // Jump to the last dimension (dimension 5)
    renderQuestionnaire();                              // Re-render the questionnaire
    showStep('step-questionnaire');                     // Show the questionnaire step
  });

  // Clicking the upload zone triggers the hidden file input (opens file picker dialog).
  zone.addEventListener('click', () => fileInput.click());

  // Drag-and-drop: highlight the zone when the user drags a file over it.
  zone.addEventListener('dragover', e => {
    e.preventDefault();              // Prevent browser default (which would navigate to the file URL)
    zone.classList.add('dragover'); // Add class to apply the highlighted border (CSS .upload-zone.dragover)
  });

  // Remove the highlight when the user drags out of the zone without dropping.
  zone.addEventListener('dragleave', () => zone.classList.remove('dragover'));

  // Handle a drop event — extract the file and pass it to handleFile().
  zone.addEventListener('drop', e => {
    e.preventDefault();                  // Prevent browser default navigation
    zone.classList.remove('dragover');   // Remove the highlight immediately after drop
    const file = e.dataTransfer.files[0]; // Get the first file from the drop event
    if (file) handleFile(file);           // Process the file if one was dropped
  });

  // Handle a file selected via the file picker dialog.
  fileInput.addEventListener('change', () => {
    if (fileInput.files[0]) handleFile(fileInput.files[0]);  // Process the selected file
  });

  // The "Run Assessment" button sends the completed form data to /api/assess.
  // It uses state.sessionId which is set after a successful upload.
  btnRun.addEventListener('click', () => runAssessment(state.sessionId));
}

async function handleFile(file) {
  // Validate file extension before uploading.
  if (!file.name.toLowerCase().endsWith('.csv')) {
    alert('Please upload a .csv file.');
    return;  // Stop processing — only CSV files are accepted
  }

  // Build a multipart/form-data payload containing the file.
  // FormData automatically sets the correct Content-Type header.
  const formData = new FormData();
  formData.append('file', file);  // Field name "file" matches what Flask expects in request.files["file"]

  showSpinner(true);  // Show the loading spinner overlay during the upload

  try {
    // POST the file to the /api/upload endpoint.
    const res = await fetch('/api/upload', { method: 'POST', body: formData });

    // Guard: if the server crashes it may return HTML (error page) rather than JSON.
    // Read the response as text first, then try to parse it as JSON.
    const text = await res.text();  // Always read as text to avoid JSON parse errors crashing the app
    let data;
    try {
      data = JSON.parse(text);  // Attempt to parse as JSON
    } catch (_) {
      // Server returned non-JSON (e.g. a 500 HTML error page)
      showSpinner(false);
      alert('Server error (status ' + res.status + '). Check Render logs for details.');
      return;
    }

    showSpinner(false);  // Hide the spinner — response received

    // Check if the server returned an error in the JSON body.
    if (data.error) {
      alert('Upload error: ' + data.error + (data.detail ? '\n\n' + data.detail : ''));
      return;  // Show the error and stop
    }

    // Store the session ID returned by the server.
    // This UUID identifies the parsed DataFrame stored server-side and must be
    // echoed back in the /api/assess request.
    state.sessionId = data.session_id;

    // Show a success message with file name, row count, and column count.
    const successEl = document.getElementById('upload-success');
    successEl.textContent = `✓ ${file.name} uploaded — ${data.row_count.toLocaleString()} rows · ${data.col_count} columns`;
    successEl.style.display = 'block';  // Make the element visible (default is display:none)

    // Render the data preview table and the column mapping UI.
    renderPreview(data);
    renderColumnMapping(data.columns, data.col_hints || {});

    // Reveal the preview section (hidden by default until a file is uploaded).
    document.getElementById('preview-section').classList.remove('hidden');

    // Enable the "Run Assessment" button (disabled by default until a file is ready).
    document.getElementById('btn-run').disabled = false;

  } catch (e) {
    // Network-level error (e.g. server unreachable)
    showSpinner(false);
    alert('Upload failed: ' + e.message);
  }
}

function renderPreview(data) {
  // Update the "X rows · Y columns" metadata line above the preview table.
  document.getElementById('preview-meta').textContent =
    `${data.row_count.toLocaleString()} rows · ${data.col_count} columns`;

  const table = document.getElementById('preview-table');  // The <table> element to populate
  const cols  = data.columns;    // Array of column names from the server
  const rows  = data.preview || []; // Array of row objects (up to 5 rows)

  // Build the table HTML:
  //   <thead> with one <th> per column
  //   <tbody> with one <tr> per row, each cell showing the value or empty string for null
  table.innerHTML = `
    <thead><tr>${cols.map(c => `<th>${c}</th>`).join('')}</tr></thead>
    <tbody>
      ${rows.map(row =>
        `<tr>${cols.map(c => `<td>${row[c] ?? ''}</td>`).join('')}</tr>`
        // row[c] ?? '' uses nullish coalescing to show empty string for null/undefined values
      ).join('')}
    </tbody>
  `;
}

function renderColumnMapping(columns, colHints) {
  // Get the container grid where mapping rows will be inserted.
  const grid = document.getElementById('mapping-grid');
  grid.innerHTML = '';  // Clear any previous mapping rows (e.g. if user re-uploads a file)

  // Build the <optgroup>/<option> HTML for the standards dropdown.
  // state.standards is { Category: [{id, name, description},...] }
  const optionGroups = Object.entries(state.standards).map(([cat, stds]) =>
    // Each category becomes an <optgroup label="Category">
    `<optgroup label="${cat}">${stds.map(s =>
      // Each standard becomes an <option value="std_id" title="description">Standard Name</option>
      `<option value="${s.id}" title="${s.description}">${s.name}</option>`
    ).join('')}</optgroup>`
  ).join('');

  // Create one row per column in the uploaded CSV.
  columns.forEach(col => {
    const hint = colHints[col] || 'text';  // Type hint from the server ("numeric", "date", "text", "empty")

    const row = document.createElement('div');  // Create a grid row container
    row.className = 'mapping-row';

    // Auto-suggest a standard based on the column's type hint.
    // Currently only date columns get an auto-suggestion (ISO date standard).
    let autoSuggest = '';
    if (hint === 'date') autoSuggest = 'date_iso';  // Suggest ISO 8601 date format for date-like columns

    // Build the row HTML:
    //   Left cell: column name and type hint badge
    //   Right cell: standards dropdown
    // The select id is sanitised: spaces and non-alphanumeric chars → underscores.
    row.innerHTML = `
      <div>
        <div class="col-name">${col}</div>
        <div class="col-hint">${hint}</div>
      </div>
      <select id="map-${col.replace(/[^a-z0-9]/gi, '_')}">
        <option value="">No standard / Skip</option>
        ${optionGroups}
      </select>
    `;

    grid.appendChild(row);  // Add the row to the mapping grid

    // If there's an auto-suggestion, set the select element's value to it.
    if (autoSuggest) {
      const sel = row.querySelector('select');                          // The dropdown in this row
      const opt = sel.querySelector(`option[value="${autoSuggest}"]`); // Find the pre-suggested option
      if (opt) sel.value = autoSuggest;                                 // Set the dropdown value if the option exists
    }

    // Listen for changes to the dropdown.
    // When the user picks a standard, record it in state.columnStandards.
    // When they pick "No standard / Skip" (value=""), remove the mapping.
    row.querySelector('select').addEventListener('change', e => {
      if (e.target.value) {
        state.columnStandards[col] = e.target.value;  // Record the selected standard ID
      } else {
        delete state.columnStandards[col];  // Remove the mapping when "Skip" is selected
      }
    });

    // Pre-populate state for the auto-suggested standard
    // (so it's recorded even if the user doesn't interact with the dropdown)
    if (autoSuggest) state.columnStandards[col] = autoSuggest;
  });
}


// =============================================================================
// Assessment runner
// =============================================================================

async function runAssessment(sessionId) {
  // sessionId can be:
  //   - a UUID string from /api/upload (normal path — CSV was uploaded)
  //   - null (user clicked "Skip profiling" — governance-only mode)

  showSpinner(true);  // Show loading overlay while the server processes

  try {
    // Construct the payload to send to /api/assess.
    const payload = {
      table_name:         state.tableName,         // Dataset name from step 1
      governance_answers: state.answers,            // All answered questions { q1: 3, q2: 2, ... }
      session_id:         sessionId,               // UUID (or null for governance-only)
      column_standards:   state.columnStandards,   // Column→standard mapping from step 3
    };

    // POST the payload as JSON to the assessment API.
    const res  = await fetch('/api/assess', {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },  // Tell Flask the body is JSON
      body:    JSON.stringify(payload),                   // Serialise the payload to a JSON string
    });

    const data = await res.json();  // Parse the JSON response from Flask

    showSpinner(false);  // Hide the spinner

    if (data.error) {
      alert('Assessment error: ' + data.error);  // Show server-side error message
      return;
    }

    state.assessResult = data;         // Store the full result (useful for debugging or PDF re-send)
    showStep('step-results');          // Navigate to the results step

    // Call renderResults() from results.js to populate the results UI.
    // typeof check ensures we don't crash if results.js failed to load.
    if (typeof renderResults === 'function') renderResults(data);

  } catch (e) {
    // Network-level failure (e.g. server offline)
    showSpinner(false);
    alert('Assessment failed: ' + e.message);
  }
}


// =============================================================================
// Spinner (loading overlay)
// =============================================================================

function showSpinner(visible) {
  // Toggle the "active" class on the spinner overlay element.
  // CSS: #spinner { display:none } / #spinner.active { display:flex }
  // classList.toggle(className, force) adds the class if force=true, removes if false.
  document.getElementById('spinner').classList.toggle('active', visible);
}
