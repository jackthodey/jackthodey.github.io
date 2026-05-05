/* =============================================================================
   results.js  –  Results dashboard rendering and PDF download
   =============================================================================

   This file is responsible for ALL rendering on step 4 (the results screen).
   It is called by wizard.js via renderResults(data) once the /api/assess
   response is received.

   Sections rendered:
     1. Tier banner    – Gold / Silver / Bronze badge with tier description
     2. Circular gauge – conic-gradient dial showing the combined 0–100 score
     3. Score cards    – governance and profiling score breakdowns
     4. Dimension bars – horizontal bar charts for governance and profiling
     5. Column table   – per-column statistics from the CSV profiling
     6. Recommendations – ordered list of improvement action cards
     7. PDF download button handler

   Helper functions at the bottom (scoreColour, hexToRgba) are used by
   multiple render functions.
   ============================================================================= */


// =============================================================================
// Main entry point — called by wizard.js after /api/assess returns
// =============================================================================

function renderResults(result) {
  // result is the full JSON object returned by Flask /api/assess.
  // It contains: table_name, governance, profiling, combined, tier, recommendations.

  renderTierBanner(result.tier);            // Section 1: tier badge and description

  renderGauge(result.combined.combined_score);  // Section 2: circular score dial

  renderScoreCards(result.combined);        // Section 3: governance and profiling score cards

  // Section 4a: governance dimension bar chart
  // Pass the per-dimension scores and the human-readable labels from the API response.
  renderDimensionBars(
    'gov-bars',                              // ID of the container element for this chart
    result.governance.dimension_scores,      // { governance_ownership: 66.7, ... }
    result.governance.dimension_labels       // { governance_ownership: "Governance & Ownership", ... }
  );

  // Section 4b: profiling dimension bar chart (only if a CSV was uploaded)
  if (result.profiling) {
    const profSection = document.getElementById('prof-section');
    profSection.classList.remove('hidden');  // Reveal the profiling section (hidden by default)

    // Build a flat label map for the 5 profiling dimensions.
    const profDimLabels = {
      completeness: 'Completeness',
      uniqueness:   'Uniqueness',
      validity:     'Validity',
      consistency:  'Consistency',
      timeliness:   'Timeliness',
    };

    // Extract just the "score" field from each dimension's detail dict.
    // result.profiling.dimensions = { completeness: { score: 82.5, ... }, ... }
    const profScores = {};
    Object.entries(result.profiling.dimensions).forEach(([k, v]) => {
      profScores[k] = v.score;  // Flatten to { completeness: 82.5, ... }
    });

    renderDimensionBars('prof-bars', profScores, profDimLabels);  // Render the profiling bars

    // Section 5: column statistics table
    renderColumnTable(result.profiling.column_stats || []);  // Empty array fallback if no column_stats
  }

  // Section 6: improvement recommendations
  renderRecommendations(result.recommendations || []);  // Empty array if no recommendations

  // Section 7: wire up action buttons
  // PDF download button — sends result back to /api/report for server-side PDF generation.
  document.getElementById('btn-pdf').addEventListener('click', () => downloadPDF(result));

  // Restart button — full page reload resets the entire wizard to step 1.
  document.getElementById('btn-restart').addEventListener('click', () => window.location.reload());
}


// =============================================================================
// 1. Tier banner
// =============================================================================

function renderTierBanner(tier) {
  // Icon characters for each tier (displayed large in the banner)
  const icons  = { gold: '★', silver: '◆', bronze: '●' };

  const banner = document.getElementById('tier-banner');  // The banner container div
  const tKey   = tier.tier || 'bronze';    // Internal tier key e.g. "gold"
  const colour = tier.colour || '#A0522D'; // Hex colour string for the tier

  // Apply a faint tinted background and a lightly coloured border using the tier colour.
  // hexToRgba() converts the hex colour to rgba with a specified opacity.
  banner.style.background = hexToRgba(colour, 0.1);         // 10% opacity background tint
  banner.style.border      = `1.5px solid ${hexToRgba(colour, 0.3)}`; // 30% opacity border

  document.getElementById('tier-icon').textContent  = icons[tKey] || '●';  // Set icon character
  document.getElementById('tier-icon').style.color  = colour;               // Colour the icon

  document.getElementById('tier-label').textContent = `${tier.label || 'Bronze'} Tier`;  // e.g. "Gold Tier"
  document.getElementById('tier-label').style.color = colour;               // Colour the label

  document.getElementById('tier-desc').textContent  = tier.description || '';  // Narrative description

  // "X points to [next tier]" nudge message — shown if the user hasn't reached Gold.
  if (tier.next_tier && tier.points_to_next > 0) {
    const nudge = document.createElement('div');  // Create a new inline element
    nudge.style.cssText = 'margin-top:8px;font-size:12px;opacity:.75;';  // Compact inline style
    nudge.textContent   = `${tier.points_to_next} points to ${tier.next_tier} tier`;

    // Insert the nudge element AFTER the tier description element in the DOM.
    document.getElementById('tier-desc').after(nudge);
  }
}


// =============================================================================
// 2. Circular gauge (conic-gradient dial)
// =============================================================================

function renderGauge(score) {
  // Clamp score to 0–100 to prevent CSS issues from out-of-range values.
  const pct    = Math.min(Math.max(score, 0), 100);

  const colour = scoreColour(pct);  // Get the colour for this score (green/amber/red)

  // Convert the 0–100 percentage to a 0–360 degree arc for the conic-gradient.
  const deg    = Math.round(pct / 100 * 360);

  const gauge  = document.getElementById('score-gauge');  // The circular dial element

  // conic-gradient draws a pie chart from 0° to deg° in the score colour,
  // then fills the remainder (deg° to 360°) in a light grey.
  gauge.style.background =
    `conic-gradient(${colour} 0deg ${deg}deg, #E5E7EB ${deg}deg 360deg)`;

  // Update the numeric score label in the centre of the dial.
  document.getElementById('gauge-score').textContent = Math.round(pct);  // Integer score
  document.getElementById('gauge-score').style.color = colour;           // Match the arc colour
}


// =============================================================================
// 3. Score cards
// =============================================================================

function renderScoreCards(combined) {
  const cards = document.getElementById('score-cards');  // Container for score cards
  cards.innerHTML = '';  // Clear any previous cards

  // Extract the effective weights that were applied to the combined score.
  // Falls back to 60/40 if the weights_used field is missing.
  const govPct  = combined.governance_weight !== undefined
    ? combined.weights_used.governance * 100  // Convert fraction to percentage
    : 60;  // Default 60%
  const profPct = combined.weights_used
    ? combined.weights_used.profiling * 100   // Convert fraction to percentage
    : 40;  // Default 40%

  // Start with the governance card definition.
  const cardDefs = [
    {
      label: 'Governance Score',
      value: combined.governance_score,   // The 0–100 governance score
      // Sub-label shows the weight and actual contribution in points
      sub:   `${govPct.toFixed(0)}% weighting · ${combined.governance_contribution?.toFixed(1)} pts contributed`,
    },
  ];

  // Only add a profiling card if profiling data was included in the assessment.
  // null or undefined profiling_score means governance-only mode.
  if (combined.profiling_score !== null && combined.profiling_score !== undefined) {
    cardDefs.push({
      label: 'Profiling Score',
      value: combined.profiling_score,
      sub:   `${profPct.toFixed(0)}% weighting · ${combined.profiling_contribution?.toFixed(1)} pts contributed`,
    });
  }

  // Create one card element per definition.
  cardDefs.forEach(def => {
    const col = scoreColour(def.value);  // Colour the score value based on thresholds
    const el  = document.createElement('div');
    el.className = 'score-card';

    el.innerHTML = `
      <div class="score-card-label">${def.label}</div>
      <div class="score-card-value" style="color:${col}">${def.value?.toFixed(1)}</div>
      <div class="score-card-sub">${def.sub}</div>
    `;
    // def.value?.toFixed(1) uses optional chaining to safely call toFixed if value is defined.

    cards.appendChild(el);  // Add the card to the score cards container
  });
}


// =============================================================================
// 4. Dimension bar charts
// =============================================================================

function renderDimensionBars(containerId, scores, labels) {
  // containerId identifies which bar chart container to populate
  // (used for both governance bars "gov-bars" and profiling bars "prof-bars").

  const container = document.getElementById(containerId);
  if (!container) return;  // Guard: if the element doesn't exist, do nothing

  container.innerHTML = '';  // Clear existing bars before rendering

  // Create one bar row per dimension.
  Object.entries(scores).forEach(([key, score]) => {
    const label = labels[key] || key;  // Human-readable label; fall back to the key itself

    const col = scoreColour(score);  // Colour for the score number (green/amber/red)

    // CSS class for the bar fill colour:
    //   bar-green if score ≥ 80,  bar-amber if score ≥ 60,  bar-red if below 60
    const cls = score >= 80 ? 'bar-green' : score >= 60 ? 'bar-amber' : 'bar-red';

    const row = document.createElement('div');
    row.className = 'dim-bar-row';

    row.innerHTML = `
      <div class="dim-bar-name">${label}</div>
      <div class="dim-bar-track">
        <div class="dim-bar-fill ${cls}" style="width:${score}%"></div>
      </div>
      <div class="dim-bar-val" style="color:${col}">${Math.round(score)}</div>
    `;
    // dim-bar-fill width is set directly as a percentage — the CSS track provides the background.
    // Math.round(score) shows an integer score to avoid "82.50" style display.

    container.appendChild(row);
  });
}


// =============================================================================
// 5. Column statistics table
// =============================================================================

function renderColumnTable(columnStats) {
  const section = document.getElementById('col-stats-section');  // The whole column stats section
  const table   = document.getElementById('col-stats-table');    // The <table> element

  if (!columnStats.length) {
    section.classList.add('hidden');  // Hide the section entirely if there are no column stats
    return;
  }

  // Determine whether to show a "Valid %" column.
  // Only show it if at least one column has a validity percentage (i.e. was mapped to a standard).
  const showValidity = columnStats.some(c => c.validity_pct !== null);

  // Build the table HTML dynamically.
  table.innerHTML = `
    <thead>
      <tr>
        <th>Column</th>
        <th>Complete %</th>
        <th>Unique %</th>
        <th>Standard</th>
        ${showValidity ? '<th>Valid %</th>' : ''}
        <th>Sample</th>
      </tr>
    </thead>
    <tbody>
      ${columnStats.map(c => {
        // Build the validity percentage cell (or nothing if no validity for this column).
        const vpct = c.validity_pct !== null && c.validity_pct !== undefined
          ? `<td style="color:${scoreColour(c.validity_pct)}">${c.validity_pct}%</td>`  // Coloured percentage
          : showValidity ? '<td>—</td>' : '';  // Em dash placeholder if validity column is shown but no value

        return `
          <tr>
            <td><strong>${c.column}</strong></td>
            <td style="color:${scoreColour(c.completeness)}">${c.completeness}%</td>
            <td>${c.uniqueness}%</td>
            <td>${c.standard_name
              ? `<span class="tag tag-blue">${c.standard_name}</span>`  // Show standard as a styled tag
              : '—'}</td>
            ${vpct}
            <td style="color:var(--muted);font-size:11px">${(c.sample || []).join(', ')}</td>
          </tr>
        `;
        // c.sample is an array of up to 3 sample values — joined with ", " for display.
        // || [] prevents an error if sample is null/undefined.
      }).join('')}
    </tbody>
  `;
}


// =============================================================================
// 6. Recommendations
// =============================================================================

function renderRecommendations(recs) {
  const list    = document.getElementById('rec-list');       // The recommendation cards container
  const section = document.getElementById('recs-section');   // The whole recommendations section

  if (!recs.length) {
    section.classList.add('hidden');  // Hide the section if there are no recommendations
    return;
  }

  // Build an HTML card for each recommendation and join them into the container.
  list.innerHTML = recs.map((rec, i) => {
    // CSS class for the priority badge (red for high, amber for medium).
    const priClass = rec.priority === 'high' ? 'priority-high' : 'priority-medium';

    // Source label: distinguish governance from profiling recommendations.
    const source   = rec.source === 'profiling' ? '📊 Profiling' : '📋 Governance';

    return `
      <div class="rec-card">
        <div class="rec-header">
          <div class="rec-area">${i + 1}. ${rec.area}</div>
          <span class="priority-badge ${priClass}">${rec.priority}</span>
        </div>
        <div class="rec-score">${source} · Score: ${rec.score?.toFixed(0)}/100</div>
        <div class="rec-action mt-8">${rec.action}</div>
      </div>
    `;
    // i + 1 gives 1-based numbering for display.
    // rec.score?.toFixed(0) safely formats the score — returns undefined if score is null.
  }).join('');
}


// =============================================================================
// 7. PDF download
// =============================================================================

async function downloadPDF(result) {
  const btn = document.getElementById('btn-pdf');  // The download button element
  btn.disabled    = true;                          // Prevent double-clicks while generating
  btn.textContent = '⏳ Generating PDF…';         // Show loading state to the user

  try {
    // POST the full assessment result object back to /api/report.
    // The server generates the PDF from this data and streams it back.
    const res = await fetch('/api/report', {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify(result),  // Send the complete result JSON as the request body
    });

    if (!res.ok) {
      // Server returned a non-2xx status — extract the error message from JSON if possible.
      const err = await res.json().catch(() => ({ error: 'Unknown error' }));
      throw new Error(err.error || 'PDF generation failed');
    }

    // Convert the response body to a Blob (binary data in memory).
    const blob = await res.blob();

    // Create an object URL — a temporary browser-internal URL pointing to the Blob.
    const url  = URL.createObjectURL(blob);

    // Create a temporary <a> element to trigger the file download.
    const a    = document.createElement('a');

    // Sanitise the dataset name for the filename: replace runs of whitespace with underscores.
    const name = (result.table_name || 'report').replace(/\s+/g, '_');
    a.href     = url;
    a.download = `DQ_Assessment_${name}.pdf`;  // Set the suggested filename for the save dialog

    // The element must be in the DOM to trigger the click in all browsers.
    document.body.appendChild(a);
    a.click();               // Programmatically click the link to start the download
    document.body.removeChild(a);  // Remove the temporary element immediately after triggering

    // Revoke the object URL to free the in-memory Blob — otherwise it leaks until page unload.
    URL.revokeObjectURL(url);

  } catch (e) {
    alert('PDF download failed: ' + e.message);  // Show error to user
  } finally {
    // Reset the button state regardless of success or failure.
    // finally{} runs even if an exception was thrown.
    btn.disabled    = false;
    btn.textContent = '⬇ Download PDF Report';
  }
}


// =============================================================================
// Helper functions
// =============================================================================

function scoreColour(score) {
  // Return a CSS colour string based on score thresholds:
  //   ≥ 80 → green  (good / target met)
  //   ≥ 60 → amber  (acceptable but needs improvement)
  //   < 60 → red    (poor / action required)
  if (score >= 80) return '#16A34A';   // Tailwind green-600 equivalent
  if (score >= 60) return '#D97706';   // Tailwind amber-600 equivalent
  return '#DC2626';                    // Tailwind red-600 equivalent
}

function hexToRgba(hex, alpha) {
  // Convert a 6-digit hex colour string (e.g. "#C9A84C") to an rgba() CSS string.
  // Used to create semi-transparent versions of tier colours for the banner.
  //
  // hex.slice(1, 3) extracts characters 1–2 (the R component e.g. "C9")
  // parseInt(..., 16) converts the two-character hex string to a decimal integer (0–255)
  const r = parseInt(hex.slice(1, 3), 16);  // Red channel: hex chars 1–2
  const g = parseInt(hex.slice(3, 5), 16);  // Green channel: hex chars 3–4
  const b = parseInt(hex.slice(5, 7), 16);  // Blue channel: hex chars 5–6

  // Return the rgba() CSS function string with the specified alpha opacity (0.0–1.0)
  return `rgba(${r},${g},${b},${alpha})`;
}
