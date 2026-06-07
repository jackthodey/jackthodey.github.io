(function () {
  "use strict";

  const state = {
    quiz: null,
    player: null,
  };

  const els = {
    tabBtns: document.querySelectorAll(".tab-btn"),
    tabPlay: document.getElementById("tab-play"),
    tabLeaderboard: document.getElementById("tab-leaderboard"),

    screenName: document.getElementById("screen-name"),
    screenQuiz: document.getElementById("screen-quiz"),
    screenResults: document.getElementById("screen-results"),

    quizTitle: document.getElementById("quiz-title"),
    quizTitle2: document.getElementById("quiz-title-2"),
    playerButtons: document.getElementById("player-buttons"),
    nameError: document.getElementById("name-error"),

    currentPlayer: document.getElementById("current-player"),
    quizForm: document.getElementById("quiz-form"),
    submitBtn: document.getElementById("submit-quiz"),
    quizError: document.getElementById("quiz-error"),

    yourScore: document.getElementById("your-score"),
    answerBreakdown: document.getElementById("answer-breakdown"),
    weeklyStatus: document.getElementById("weekly-status"),
    weeklyTable: document.querySelector("#weekly-table tbody"),
    familyScore: document.getElementById("family-score"),
    familyBreakdown: document.getElementById("family-breakdown"),
    playAgain: document.getElementById("play-again"),

    leaderboardTable: document.querySelector("#leaderboard-table tbody"),
    leaderboardEmpty: document.getElementById("leaderboard-empty"),
  };

  function showScreen(id) {
    [els.screenName, els.screenQuiz, els.screenResults].forEach((s) => s.classList.remove("active"));
    document.getElementById(id).classList.add("active");
  }

  function switchTab(name) {
    els.tabBtns.forEach((b) => b.classList.toggle("active", b.dataset.tab === name));
    els.tabPlay.classList.toggle("active", name === "play");
    els.tabLeaderboard.classList.toggle("active", name === "leaderboard");
    if (name === "leaderboard") loadLeaderboard();
  }

  els.tabBtns.forEach((btn) => btn.addEventListener("click", () => switchTab(btn.dataset.tab)));

  // ---------------------------------------------------------------- loading
  async function loadQuiz() {
    try {
      const res = await fetch("/api/quiz/current");
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        els.quizTitle.textContent = err.error || "No quiz available yet. Check back soon!";
        return;
      }
      state.quiz = await res.json();
      els.quizTitle.textContent = state.quiz.title;
      els.quizTitle2.textContent = state.quiz.title;
      renderPlayerButtons();
    } catch (e) {
      els.quizTitle.textContent = "Couldn't load this week's quiz.";
    }
  }

  function renderPlayerButtons() {
    els.playerButtons.innerHTML = "";
    state.quiz.players.forEach((name) => {
      const btn = document.createElement("button");
      btn.className = "player-btn";
      btn.textContent = name;
      btn.addEventListener("click", () => selectPlayer(name));
      els.playerButtons.appendChild(btn);
    });
  }

  function selectPlayer(name) {
    state.player = name;
    els.nameError.textContent = "";
    els.currentPlayer.textContent = name;
    renderQuizForm();
    showScreen("screen-quiz");
  }

  // ------------------------------------------------------------- quiz form
  function renderQuizForm() {
    els.quizForm.innerHTML = "";
    state.quiz.questions.forEach((q, idx) => {
      const card = document.createElement("div");
      card.className = "question-card";

      const text = document.createElement("div");
      text.className = "q-text";
      text.textContent = `${idx + 1}. ${q.text}`;
      card.appendChild(text);

      if (q.type === "text") {
        const input = document.createElement("input");
        input.type = "text";
        input.className = "text-answer";
        input.name = `q-${q.id}`;
        input.dataset.qid = q.id;
        input.placeholder = "Type your answer";
        card.appendChild(input);
      } else {
        (q.options || []).forEach((opt) => {
          const label = document.createElement("label");
          label.className = "option-row";

          const input = document.createElement("input");
          input.type = "radio";
          input.name = `q-${q.id}`;
          input.value = opt;
          input.dataset.qid = q.id;
          input.addEventListener("change", () => {
            card.querySelectorAll(".option-row").forEach((r) => r.classList.remove("selected"));
            label.classList.add("selected");
          });

          label.appendChild(input);
          label.appendChild(document.createTextNode(opt));
          card.appendChild(label);
        });
      }

      els.quizForm.appendChild(card);
    });
  }

  function collectAnswers() {
    const answers = {};
    state.quiz.questions.forEach((q) => {
      const field = els.quizForm.querySelector(`[name="q-${q.id}"]${q.type === "text" ? "" : ":checked"}`);
      answers[q.id] = field ? field.value.trim() : "";
    });
    return answers;
  }

  els.submitBtn.addEventListener("click", async () => {
    els.quizError.textContent = "";
    const answers = collectAnswers();
    const unanswered = state.quiz.questions.filter((q) => !answers[q.id]);
    if (unanswered.length) {
      els.quizError.textContent = `Please answer all questions (${unanswered.length} left).`;
      return;
    }

    els.submitBtn.disabled = true;
    els.submitBtn.textContent = "Grading…";
    try {
      const res = await fetch("/api/submit", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: state.player, quiz_id: state.quiz.id, answers }),
      });
      const data = await res.json();
      if (!res.ok) {
        els.quizError.textContent = data.error || "Something went wrong submitting your answers.";
        return;
      }
      renderYourResult(data);
      await renderWeeklyResults(state.quiz.id);
      showScreen("screen-results");
    } catch (e) {
      els.quizError.textContent = "Couldn't reach the server. Try again.";
    } finally {
      els.submitBtn.disabled = false;
      els.submitBtn.textContent = "Submit Answers";
    }
  });

  // ---------------------------------------------------------------- results
  function renderYourResult(data) {
    els.yourScore.textContent = `${data.name} scored ${data.score} / ${data.total}`;
    els.answerBreakdown.innerHTML = "";
    data.breakdown.forEach((b, idx) => {
      const li = document.createElement("li");
      li.className = b.correct ? "correct" : "incorrect";
      const meta = b.correct
        ? `Your answer: ${b.your_answer || "(blank)"}`
        : `Your answer: ${b.your_answer || "(blank)"} — correct answer: ${b.correct_answer}`;
      li.innerHTML = `${idx + 1}. ${b.text}<span class="meta">${meta}</span>`;
      els.answerBreakdown.appendChild(li);
    });
  }

  async function renderWeeklyResults(quizId) {
    try {
      const res = await fetch(`/api/results/${encodeURIComponent(quizId)}`);
      if (!res.ok) return;
      const data = await res.json();

      els.weeklyTable.innerHTML = "";
      data.weekly.forEach((row) => {
        const tr = document.createElement("tr");
        tr.innerHTML = `<td>${row.name}</td><td>${row.score} / ${row.total}</td>`;
        els.weeklyTable.appendChild(tr);
      });

      els.weeklyStatus.textContent = `${data.submitted_count} of ${data.player_count} family members have played this week.`;

      if (data.family) {
        els.familyScore.textContent = `Family combined score: ${data.family.score} / ${data.family.total}`;
        els.familyBreakdown.innerHTML = "";
        data.family.breakdown.forEach((b, idx) => {
          const li = document.createElement("li");
          li.className = b.correct ? "correct" : "incorrect";
          const who = b.solved_by.length ? `Solved by: ${b.solved_by.join(", ")}` : "Nobody got this one yet";
          li.innerHTML = `${idx + 1}. ${b.text}<span class="meta">${who} — correct answer: ${b.correct_answer}</span>`;
          els.familyBreakdown.appendChild(li);
        });
        if (data.submitted_count < data.player_count) {
          els.familyScore.textContent += " (so far — more family members still to play)";
        }
      } else {
        els.familyScore.textContent = "Waiting for family members to play…";
        els.familyBreakdown.innerHTML = "";
      }
    } catch (e) {
      els.weeklyStatus.textContent = "Couldn't load this week's results.";
    }
  }

  els.playAgain.addEventListener("click", () => {
    state.player = null;
    els.nameError.textContent = "";
    showScreen("screen-name");
  });

  // ------------------------------------------------------------ leaderboard
  async function loadLeaderboard() {
    try {
      const res = await fetch("/api/leaderboard");
      const data = await res.json();
      els.leaderboardTable.innerHTML = "";
      if (!data.leaderboard.length) {
        els.leaderboardEmpty.textContent = "No quizzes played yet — be the first!";
        return;
      }
      els.leaderboardEmpty.textContent = "";
      data.leaderboard.forEach((row) => {
        const tr = document.createElement("tr");
        tr.innerHTML = `<td>${row.name}</td><td>${row.quizzes_played}</td><td>${row.total_score} / ${row.total_possible}</td><td>${row.average_pct}%</td>`;
        els.leaderboardTable.appendChild(tr);
      });
    } catch (e) {
      els.leaderboardEmpty.textContent = "Couldn't load the leaderboard.";
    }
  }

  loadQuiz();
  showScreen("screen-name");
})();
