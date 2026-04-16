/* =============================================================================
   results.js  –  Results dashboard rendering and PDF download
   ============================================================================= */

// ── Main entry point ──────────────────────────────────────────────────────────

function renderResults(result) {
  renderTierBanner(result.tier);
  renderGauge(result.combined.combined_score);
  renderScoreCards(result.combined);
  renderDimensionBars(
    'gov-bars',
    result.governance.dimension_scores,
    result.governance.dimension_labels
  );

  if (result.profiling) {
    const profSection = document.getElementById('prof-section');
    profSection.classList.remove('hidden');
    const profDimLabels = {
      completeness: 'Completeness',
      uniqueness:   'Uniqueness',
      validity:     'Validity',
      consistency:  'Consistency',
      timeliness:   'Timeliness',
    };
    const profScores = {};
    Object.entries(result.profiling.dimensions).forEach(([k, v]) => {
      profScores[k] = v.score;
    });
    renderDimensionBars('prof-bars', profScores, profDimLabels);
    renderColumnTable(result.profiling.column_stats || []);
  }

  renderRecommendations(result.recommendations || []);

  // Wire up buttons
  document.getElementById('btn-pdf').addEventListener('click', () => downloadPDF(result));
  document.getElementById('btn-restart').addEventListener('click', () => window.location.reload());
}

// ── Tier banner ───────────────────────────────────────────────────────────────

function renderTierBanner(tier) {
  const icons  = { gold: '★', silver: '◆', bronze: '●' };
  const banner = document.getElementById('tier-banner');
  const tKey   = tier.tier || 'bronze';
  const colour = tier.colour || '#A0522D';

  banner.style.background = hexToRgba(colour, 0.1);
  banner.style.border      = `1.5px solid ${hexToRgba(colour, 0.3)}`;

  document.getElementById('tier-icon').textContent          = icons[tKey] || '●';
  document.getElementById('tier-icon').style.color          = colour;
  document.getElementById('tier-label').textContent         = `${tier.label || 'Bronze'} Tier`;
  document.getElementById('tier-label').style.color         = colour;
  document.getElementById('tier-desc').textContent          = tier.description || '';

  // Next tier nudge
  if (tier.next_tier && tier.points_to_next > 0) {
    const nudge = document.createElement('div');
    nudge.style.cssText = 'margin-top:8px;font-size:12px;opacity:.75;';
    nudge.textContent   = `${tier.points_to_next} points to ${tier.next_tier} tier`;
    document.getElementById('tier-desc').after(nudge);
  }
}

// ── Circular gauge ────────────────────────────────────────────────────────────

function renderGauge(score) {
  const pct    = Math.min(Math.max(score, 0), 100);
  const colour = scoreColour(pct);
  const deg    = Math.round(pct / 100 * 360);

  const gauge = document.getElementById('score-gauge');
  gauge.style.background =
    `conic-gradient(${colour} 0deg ${deg}deg, #E5E7EB ${deg}deg 360deg)`;

  document.getElementById('gauge-score').textContent = Math.round(pct);
  document.getElementById('gauge-score').style.color = colour;
}

// ── Score cards ───────────────────────────────────────────────────────────────

function renderScoreCards(combined) {
  const cards = document.getElementById('score-cards');
  cards.innerHTML = '';

  const govPct  = combined.governance_weight !== undefined
    ? combined.weights_used.governance * 100
    : 60;
  const profPct = combined.weights_used
    ? combined.weights_used.profiling * 100
    : 40;

  const cardDefs = [
    {
      label: 'Governance Score',
      value: combined.governance_score,
      sub:   `${govPct.toFixed(0)}% weighting · ${combined.governance_contribution?.toFixed(1)} pts contributed`,
    },
  ];
  if (combined.profiling_score !== null && combined.profiling_score !== undefined) {
    cardDefs.push({
      label: 'Profiling Score',
      value: combined.profiling_score,
      sub:   `${profPct.toFixed(0)}% weighting · ${combined.profiling_contribution?.toFixed(1)} pts contributed`,
    });
  }

  cardDefs.forEach(def => {
    const col = scoreColour(def.value);
    const el  = document.createElement('div');
    el.className = 'score-card';
    el.innerHTML = `
      <div class="score-card-label">${def.label}</div>
      <div class="score-card-value" style="color:${col}">${def.value?.toFixed(1)}</div>
      <div class="score-card-sub">${def.sub}</div>
    `;
    cards.appendChild(el);
  });
}

// ── Dimension bar charts ──────────────────────────────────────────────────────

function renderDimensionBars(containerId, scores, labels) {
  const container = document.getElementById(containerId);
  if (!container) return;
  container.innerHTML = '';

  Object.entries(scores).forEach(([key, score]) => {
    const label = labels[key] || key;
    const col   = scoreColour(score);
    const cls   = score >= 80 ? 'bar-green' : score >= 60 ? 'bar-amber' : 'bar-red';

    const row = document.createElement('div');
    row.className = 'dim-bar-row';
    row.innerHTML = `
      <div class="dim-bar-name">${label}</div>
      <div class="dim-bar-track">
        <div class="dim-bar-fill ${cls}" style="width:${score}%"></div>
      </div>
      <div class="dim-bar-val" style="color:${col}">${Math.round(score)}</div>
    `;
    container.appendChild(row);
  });
}

// ── Column statistics table ───────────────────────────────────────────────────

function renderColumnTable(columnStats) {
  const section = document.getElementById('col-stats-section');
  const table   = document.getElementById('col-stats-table');
  if (!columnStats.length) { section.classList.add('hidden'); return; }

  const showValidity = columnStats.some(c => c.validity_pct !== null);

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
        const vpct = c.validity_pct !== null && c.validity_pct !== undefined
          ? `<td style="color:${scoreColour(c.validity_pct)}">${c.validity_pct}%</td>`
          : showValidity ? '<td>—</td>' : '';
        return `
          <tr>
            <td><strong>${c.column}</strong></td>
            <td style="color:${scoreColour(c.completeness)}">${c.completeness}%</td>
            <td>${c.uniqueness}%</td>
            <td>${c.standard_name ? `<span class="tag tag-blue">${c.standard_name}</span>` : '—'}</td>
            ${vpct}
            <td style="color:var(--muted);font-size:11px">${(c.sample || []).join(', ')}</td>
          </tr>
        `;
      }).join('')}
    </tbody>
  `;
}

// ── Recommendations ───────────────────────────────────────────────────────────

function renderRecommendations(recs) {
  const list = document.getElementById('rec-list');
  const section = document.getElementById('recs-section');

  if (!recs.length) {
    section.classList.add('hidden');
    return;
  }

  list.innerHTML = recs.map((rec, i) => {
    const priClass = rec.priority === 'high' ? 'priority-high' : 'priority-medium';
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
  }).join('');
}

// ── PDF download ──────────────────────────────────────────────────────────────

async function downloadPDF(result) {
  const btn = document.getElementById('btn-pdf');
  btn.disabled = true;
  btn.textContent = '⏳ Generating PDF…';

  try {
    const res = await fetch('/api/report', {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify(result),
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({ error: 'Unknown error' }));
      throw new Error(err.error || 'PDF generation failed');
    }

    const blob = await res.blob();
    const url  = URL.createObjectURL(blob);
    const a    = document.createElement('a');
    const name = (result.table_name || 'report').replace(/\s+/g, '_');
    a.href     = url;
    a.download = `DQ_Assessment_${name}.pdf`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  } catch (e) {
    alert('PDF download failed: ' + e.message);
  } finally {
    btn.disabled    = false;
    btn.textContent = '⬇ Download PDF Report';
  }
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function scoreColour(score) {
  if (score >= 80) return '#16A34A';   // green
  if (score >= 60) return '#D97706';   // amber
  return '#DC2626';                    // red
}

function hexToRgba(hex, alpha) {
  const r = parseInt(hex.slice(1, 3), 16);
  const g = parseInt(hex.slice(3, 5), 16);
  const b = parseInt(hex.slice(5, 7), 16);
  return `rgba(${r},${g},${b},${alpha})`;
}
