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

  cancelBtn.addEventListener("click", async () => {
    cancelBtn.disabled = true;
    try {
      await api.post("/api/rooms/" + id + "/cancel/");
    } catch (e) { /* already started or cancelled: the poll redirects */ }
    stop();
    if (!leaving) location.href = "/lobby/";
  });
})();
