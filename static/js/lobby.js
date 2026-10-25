(function () {
  const list = document.getElementById("room-list");
  const empty = document.getElementById("room-empty");
  const loading = document.getElementById("room-loading");
  const msg = document.getElementById("lobby-msg");
  const form = document.getElementById("create-form");

  function showMessage(text) {
    msg.textContent = text;
    msg.hidden = !text;
  }

  function badge(cls, text) {
    const span = document.createElement("span");
    span.className = "badge " + cls;
    span.textContent = text;
    return span;
  }

  function renderRoom(room) {
    const card = document.createElement("div");
    card.className = "room-card";

    const info = document.createElement("div");
    const name = document.createElement("strong");
    name.textContent = room.host_username;
    const st = room.host_stats;
    const stats = document.createElement("small");
    stats.className = "stats";
    stats.textContent = " " + st.wins + " G · " + st.losses + " M · " + st.draws + " B";
    stats.setAttribute("aria-label", st.wins + " galibiyet, " + st.losses + " mağlubiyet, " + st.draws + " beraberlik");
    name.append(stats);
    const badges = document.createElement("div");
    badges.className = "room-badges";
    badges.append(
      badge("badge-primary", room.challenge_label),
      badge(room.time_limit === 20 ? "badge-accent" : "badge-cyan", room.time_limit + " sn")
    );
    info.append(name, badges);

    const btn = document.createElement("button");
    btn.className = "btn";
    btn.type = "button";
    btn.textContent = "Katıl";
    btn.addEventListener("click", () => join(room.id, btn));

    card.append(info, btn);
    return card;
  }

  let lastSignature = null;

  async function refresh() {
    try {
      const data = await api.get("/api/rooms/");
      // Re-render only on change so buttons are not replaced under the cursor.
      const signature = data.rooms.map((r) => r.id).join();
      if (signature !== lastSignature) {
        lastSignature = signature;
        list.replaceChildren(...data.rooms.map(renderRoom));
      }
      loading.hidden = true;
      empty.hidden = data.rooms.length > 0;
      showMessage("");
    } catch (e) {
      if (e.status === 401) location.href = "/login/";
      else {
        loading.hidden = true;
        showMessage("Odalar yüklenemedi, yeniden deneniyor…");
      }
    }
  }

  async function join(id, btn) {
    btn.disabled = true;
    showMessage("");
    try {
      const data = await api.post("/api/rooms/" + id + "/join/");
      location.href = data.url;
    } catch (e) {
      showMessage(e.message);
      btn.disabled = false;
      refresh();
    }
  }

  if (form) {
    form.addEventListener("submit", async (ev) => {
      ev.preventDefault();
      showMessage("");
      const fd = new FormData(form);
      try {
        const data = await api.post("/api/rooms/", {
          challenge_type: fd.get("challenge_type"),
          time_limit: Number(fd.get("time_limit")),
        });
        location.href = data.url;
      } catch (e) {
        showMessage(e.message);
      }
    });
  }

  api.poll(refresh, 3000);
})();
