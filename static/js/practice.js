(function () {
  const svg = document.querySelector("svg.world-map");
  const optionsEl = document.getElementById("options");
  const feedback = document.getElementById("feedback");
  const nextBtn = document.getElementById("next-btn");
  const counter = document.getElementById("counter");
  let asked = 0;
  let correct = 0;

  function renderScore() {
    counter.textContent = "Soru " + asked + " · Doğru " + correct;
  }

  async function load() {
    feedback.textContent = "";
    feedback.className = "feedback";
    nextBtn.hidden = true;
    const { payload } = await api.get("/api/practice/question/");
    asked += 1;
    renderScore();
    worldMap.highlight(svg, payload.iso2);
    optionsEl.replaceChildren(
      ...payload.options.map((name) => {
        const btn = document.createElement("button");
        btn.type = "button";
        btn.className = "option";
        btn.textContent = name;
        btn.addEventListener("click", () => answer(name));
        return btn;
      })
    );
  }

  async function answer(value) {
    optionsEl.querySelectorAll("button").forEach((b) => (b.disabled = true));
    const result = await api.post("/api/practice/answer/", { value });
    if (result.correct) correct += 1;
    renderScore();
    optionsEl.querySelectorAll("button").forEach((b) => {
      if (b.textContent === result.answer) b.classList.add("right");
      else if (b.textContent === value) b.classList.add("wrong");
    });
    feedback.textContent = result.correct ? "Doğru!" : "Yanlış — doğru cevap: " + result.answer;
    feedback.className = "feedback " + (result.correct ? "ok" : "bad");
    nextBtn.hidden = false;
  }

  nextBtn.addEventListener("click", load);
  load();
})();
