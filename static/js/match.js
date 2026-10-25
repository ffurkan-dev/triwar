(function () {
  const root = document.getElementById("match");
  const id = root.dataset.id;
  const svg = document.querySelector("svg.world-map");
  const el = (name) => document.getElementById(name);
  const optionsEl = el("options");
  const overlay = el("overlay");
  const statusLine = el("status-line");
  const CIRC = 2 * Math.PI * 28;

  let state = null;
  let offset = 0; // server clock minus client clock, in ms
  let builtIndex = -1;
  let answering = false;

  el("timer-bar").style.strokeDasharray = CIRC;

  function serverNow() {
    return Date.now() + offset;
  }

  function buildOptions(round) {
    builtIndex = round.index;
    optionsEl.replaceChildren(
      ...round.payload.options.map((name) => {
        const btn = document.createElement("button");
        btn.type = "button";
        btn.className = "option";
        btn.textContent = name;
        btn.addEventListener("click", () => submit(name));
        return btn;
      })
    );
  }

  async function submit(value) {
    if (answering || !state || state.round.my_answer) return;
    answering = true;
    state.round.my_answer = value; // lock immediately; the next poll confirms
    paint();
    try {
      await api.post("/api/matches/" + id + "/answer/", { round_index: state.round.index, value });
    } catch (e) {
      statusLine.textContent = e.message;
    }
    answering = false;
    poll();
  }

  function paintOptions(round, reveal) {
    const buttons = optionsEl.querySelectorAll("button");
    buttons.forEach((b) => {
      const name = b.textContent;
      b.disabled = round.phase !== "question" || !!round.my_answer;
      b.classList.toggle("selected", round.my_answer === name && !reveal);
      b.classList.toggle("right", !!reveal && name === reveal.answer);
      b.classList.toggle("wrong", !!reveal && name !== reveal.answer && round.my_answer === name);
    });
  }

  function paintTimer(round) {
    const text = el("timer-text");
    const bar = el("timer-bar");
    if (round.phase !== "question") {
      bar.style.strokeDashoffset = round.phase === "countdown" ? 0 : CIRC;
      text.textContent = "";
      bar.classList.remove("urgent");
      return;
    }
    const remaining = Math.max(0, Date.parse(round.deadline) - serverNow());
    const total = state.time_limit * 1000;
    bar.style.strokeDashoffset = CIRC * (1 - remaining / total);
    bar.classList.toggle("urgent", remaining <= 5000);
    text.textContent = Math.ceil(remaining / 1000);
  }

  function paint() {
    if (!state || !state.round) return;
    const { round, reveal, players } = state;

    el("me-name").textContent = players.me.username;
    el("opp-name").textContent = players.opponent.username;
    el("me-score").textContent = players.me.score;
    el("opp-score").textContent = players.opponent.score;
    el("round-label").textContent = "Tur " + (round.index + 1) + " / " + round.total;

    if (round.phase === "countdown") {
      worldMap.clear(svg);
      const left = Math.max(1, Math.ceil((Date.parse(round.started_at) - serverNow()) / 1000));
      overlay.textContent = left;
      overlay.hidden = false;
      optionsEl.replaceChildren();
      builtIndex = -1;
      statusLine.textContent = "Hazır ol!";
      el("opp-status").textContent = "";
    } else {
      overlay.hidden = true;
      if (builtIndex !== round.index) {
        buildOptions(round);
        worldMap.highlight(svg, round.payload.iso2);
        statusLine.textContent = "";
      }
      paintOptions(round, reveal);
      if (round.phase === "question") {
        el("opp-status").textContent = round.opponent_answered ? "Rakip cevapladı" : "";
        if (round.my_answer && !statusLine.textContent) statusLine.textContent = "Cevabın alındı, rakip bekleniyor…";
      } else if (reveal) {
        el("opp-status").textContent = "";
        const mine = reveal.answers.me;
        statusLine.className = "feedback " + (mine && mine.correct ? "ok" : "bad");
        const opp = reveal.answers.opponent;
        statusLine.textContent =
          (mine ? (mine.correct ? "Doğru! " : "Yanlış. ") : "Cevap vermedin. ") +
          "Doğru cevap: " + reveal.answer + ". " +
          players.opponent.username + ": " + (opp ? opp.value : "cevap vermedi") + ".";
      }
    }
    if (round.phase !== "reveal") statusLine.className = "feedback";
    paintTimer(round);
  }

  async function poll() {
    try {
      const sentAt = Date.now();
      const data = await api.get("/api/matches/" + id + "/state/");
      offset = Date.parse(data.server_now) - (sentAt + Date.now()) / 2;
      if (data.status === "finished") {
        location.href = data.result_url;
        return;
      }
      if (data.status !== "active") {
        location.href = "/lobby/";
        return;
      }
      if (!answering) state = data;
      paint();
    } catch (e) {
      if (e.status === 401) location.href = "/login/";
    }
  }

  api.poll(poll, 1000);
  setInterval(() => state && paint(), 200); // smooth countdown between polls
})();
