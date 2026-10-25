(function () {
  const root = document.getElementById("room");
  const id = root.dataset.id;
  const cancelBtn = document.getElementById("cancel-btn");
  let leaving = false;

  const stop = api.poll(async () => {
    try {
      const data = await api.get("/api/rooms/" + id + "/");
      if (data.status === "active") {
        leaving = true;
        location.href = data.match_url;
      } else if (data.status !== "waiting") {
        leaving = true;
        location.href = "/lobby/";
      }
    } catch (e) { /* retry on next tick */ }
  }, 2000);

  // Closing the tab cancels the room; the 10-minute staleness rule is the fallback.
  window.addEventListener("pagehide", () => {
    if (leaving) return;
    const data = new FormData();
    data.append("csrfmiddlewaretoken", document.querySelector('meta[name="csrf-token"]').content);
    navigator.sendBeacon("/api/rooms/" + id + "/cancel/", data);
  });

  cancelBtn.addEventListener("click", async () => {
    cancelBtn.disabled = true;
    leaving = true;
    try {
      await api.post("/api/rooms/" + id + "/cancel/");
    } catch (e) { /* already started or cancelled: the poll redirects */ }
    stop();
    location.href = "/lobby/";
  });
})();
