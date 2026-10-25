(function () {
  const csrf = document.querySelector('meta[name="csrf-token"]').content;

  async function request(method, url, body) {
    const opts = { method, headers: { Accept: "application/json" }, credentials: "same-origin" };
    if (method !== "GET") {
      opts.headers["X-CSRFToken"] = csrf;
      opts.headers["Content-Type"] = "application/json";
      opts.body = JSON.stringify(body || {});
    }
    const resp = await fetch(url, opts);
    let data = {};
    try { data = await resp.json(); } catch (e) { /* non-JSON error page */ }
    if (!resp.ok) {
      const err = new Error(data.error || "Bir hata oluştu.");
      err.status = resp.status;
      throw err;
    }
    return data;
  }

  // Runs `tick` every `ms` while the tab is visible; fires immediately on show.
  function poll(tick, ms) {
    let timer = null;
    function start() {
      if (timer) return;
      tick();
      timer = setInterval(tick, ms);
    }
    function stop() {
      clearInterval(timer);
      timer = null;
    }
    document.addEventListener("visibilitychange", () => (document.hidden ? stop() : start()));
    if (!document.hidden) start();
    return stop;
  }

  window.api = {
    get: (url) => request("GET", url),
    post: (url, body) => request("POST", url, body),
    poll,
  };
})();
