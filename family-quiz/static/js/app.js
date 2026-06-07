(function () {
  "use strict";

  const state = {
    questionCount: 25,
    players: [],
    player: null,
    weekId: null,
    marks: [], // array of true/false/null, one per question
  };

  const els = {
    tabBtns: document.querySelectorAll(".tab-btn"),
    tabPlay: document.getElementById("tab-play"),
    tabLeaderboard: document.getElementById("tab-leaderboard"),

    screenSetup: document.getElementById("screen-setup"),
    screenMark: document.getElementById("screen-mark"),
    screenResults: document.getElementById("screen-results"),

    weekInput: document.getElementById("week-input"),
    playerButtons: document.getElementById("player-buttons"),
    setupError: document.getElementById("setup-error"),

    currentPlayer: document.getElementById("current-player"),
    currentWeek: document.getElementById("current-week"),
    markGrid: document.getElementById("mark-grid"),
    submitMarks: document.getElementById("submit-marks"),
    backToSetup: document.getElementById("back-to-setup"),
    markError: document.getElementById("mark-error"),

    yourScore: document.getElementById("your-score"),
    weeklyStatus: document.getElementById("weekly-status"),
    weeklyTable: document.querySelector("#weekly-table tbody"),
    familyScore: document.getElementById("family-score"),
    familyDetail: document.getElementById("family-detail"),
    playAgain: document.getElementById("play-again"),

    leaderboardTable: document.querySelector("#leaderboard-table tbody"),
    leaderboardEmpty: document.getElementById("leaderboard-empty"),
  };

  function showScreen(id) {
    [els.screenSetup, els.screenMark, els.screenResults].forEach((s) => s.classList.remove("active"));
    document.getElementById(id).classList.add("active");
  }

  function switchTab(name) {
    els.tabBtns.forEach((b) => b.classList.toggle("active", b.dataset.tab === name));
    els.tabPlay.classList.toggle("active", name === "play");
    els.tabLeaderboard.classList.toggle("active", name === "leaderboard");
    if (name === "leaderboard") loadLeaderboard();
  }

  els.tabBtns.forEach((btn) => btn.addEventListener("click", () => switchTab(btn.dataset.tab)));

  function mostRecentSaturday() {
    const d = new Date();
    const day = d.getDay(); // 0 = Sunday ... 6 = Saturday
    const diff = (day + 1) % 7; // days since last Saturday
    d.setDate(d.getDate() - diff);
    return d.toISOString().slice(0, 10);
  }

  // ---------------------------------------------------------------- setup
  async function loadConfig() {
    try {
      const res = await fetch("/api/config");
      const data = await res.json();
      state.questionCount = data.question_count;
      state.players = data.players;
      renderPlayerButtons();
    } catch (e) {
      els.setupError.textContent = "Couldn't load the quiz settings.";
    }
  }

  function renderPlayerButtons() {
    els.playerButtons.innerHTML = "";
    state.players.forEach((name) => {
      const btn = document.createElement("button");
      btn.className = "player-btn";
      btn.textContent = name;
      btn.addEventListener("click", () => selectPlayer(name));
      els.playerButtons.appendChild(btn);
    });
  }

  function selectPlayer(name) {
    const week = els.weekInput.value;
    if (!week) {
      els.setupError.textContent = "Please choose the week-ending date first.";
      return;
    }
    state.player = name;
    state.weekId = week;
    state.marks = new Array(state.questionCount).fill(null);
    els.setupError.textContent = "";
    els.currentPlayer.textContent = name;
    els.currentWeek.textContent = week;
    renderMarkGrid();
    showScreen("screen-mark");
  }

  els.weekInput.value = mostRecentSaturday();

  // ------------------------------------------------------------- mark grid
  function renderMarkGrid() {
    els.markGrid.innerHTML = "";
    for (let i = 0; i < state.questionCount; i++) {
      const row = document.createElement("div");
      row.className = "mark-row";

      const label = document.createElement("span");
      label.className = "mark-label";
      label.textContent = `Q${i + 1}`;
      row.appendChild(label);

      const right = document.createElement("button");
      right.className = "mark-btn mark-right";
      right.textContent = "Right";
      right.addEventListener("click", () => setMark(i, true, row));

      const wrong = document.createElement("button");
      wrong.className = "mark-btn mark-wrong";
      wrong.textContent = "Wrong";
      wrong.addEventListener("click", () => setMark(i, false, row));

      row.appendChild(right);
      row.appendChild(wrong);
      els.markGrid.appendChild(row);
    }
  }

  function setMark(index, value, row) {
    state.marks[index] = value;
    row.querySelector(".mark-right").classList.toggle("selected", value === true);
    row.querySelector(".mark-wrong").classList.toggle("selected", value === false);
  }

  els.backToSetup.addEventListener("click", () => {
    state.player = null;
    showScreen("screen-setup");
  });

  els.submitMarks.addEventListener("click", async () => {
    els.markError.textContent = "";
    const unmarked = state.marks.filter((m) => m === null).length;
    if (unmarked) {
      els.markError.textContent = `Please mark every question (${unmarked} left).`;
      return;
    }

    els.submitMarks.disabled = true;
    els.submitMarks.textContent = "Saving…";
    try {
      const res = await fetch("/api/submit", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: state.player, week_id: state.weekId, results: state.marks }),
      });
      const data = await res.json();
      if (!res.ok) {
        els.markError.textContent = data.error || "Something went wrong saving your results.";
        return;
      }
      renderYourResult(data);
      await renderWeeklyResults(state.weekId);
      showScreen("screen-results");
    } catch (e) {
      els.markError.textContent = "Couldn't reach the server. Try again.";
    } finally {
      els.submitMarks.disabled = false;
      els.submitMarks.textContent = "Submit Results";
    }
  });

  // ---------------------------------------------------------------- results
  function renderYourResult(data) {
    els.yourScore.textContent = `${data.name} scored ${data.score} / ${data.total}`;
  }

  async function renderWeeklyResults(weekId) {
    try {
      const res = await fetch(`/api/results/${encodeURIComponent(weekId)}`);
      if (!res.ok) return;
      const data = await res.json();

      els.weeklyTable.innerHTML = "";
      data.weekly.forEach((row) => {
        const tr = document.createElement("tr");
        tr.innerHTML = `<td>${row.name}</td><td>${row.score} / ${row.total}</td>`;
        els.weeklyTable.appendChild(tr);
      });

      els.weeklyStatus.textContent = `${data.submitted_count} of ${data.player_count} family members have entered results for this week.`;

      if (data.family) {
        els.familyScore.textContent = `Family combined score: ${data.family.score} / ${data.family.total}`;
        const solvedCount = data.family.breakdown.filter((b) => b.correct).length;
        els.familyDetail.textContent = `As a team you'd have nailed ${solvedCount} of ${data.family.total} questions between you.`;
        if (data.submitted_count < data.player_count) {
          els.familyScore.textContent += " (so far — more family members still to enter results)";
        }
      } else {
        els.familyScore.textContent = "Waiting for family members to enter their results…";
        els.familyDetail.textContent = "";
      }
    } catch (e) {
      els.weeklyStatus.textContent = "Couldn't load this week's results.";
    }
  }

  els.playAgain.addEventListener("click", () => {
    state.player = null;
    showScreen("screen-setup");
  });

  // ------------------------------------------------------------ leaderboard
  async function loadLeaderboard() {
    try {
      const res = await fetch("/api/leaderboard");
      const data = await res.json();
      els.leaderboardTable.innerHTML = "";
      if (!data.leaderboard.length) {
        els.leaderboardEmpty.textContent = "No results entered yet — be the first!";
        return;
      }
      els.leaderboardEmpty.textContent = "";
      data.leaderboard.forEach((row) => {
        const tr = document.createElement("tr");
        tr.innerHTML = `<td>${row.name}</td><td>${row.weeks_played}</td><td>${row.total_score} / ${row.total_possible}</td><td>${row.average_pct}%</td>`;
        els.leaderboardTable.appendChild(tr);
      });
    } catch (e) {
      els.leaderboardEmpty.textContent = "Couldn't load the leaderboard.";
    }
  }

  loadConfig();
  showScreen("screen-setup");
})();
