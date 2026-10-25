(function () {
  const SMALL = 14; // bbox side (SVG units) under which a country gets a pulse ring
  const NS = "http://www.w3.org/2000/svg";

  function clear(svg) {
    svg.querySelectorAll(".country.target").forEach((el) => el.classList.remove("target"));
    svg.querySelectorAll(".pulse-ring").forEach((el) => el.remove());
  }

  // Paints the country with the given ISO2 code; tiny countries also get a ring around them.
  function highlight(svg, iso2) {
    clear(svg);
    const path = svg.getElementById ? svg.getElementById(iso2) : svg.querySelector("#" + iso2);
    if (!path) return false;
    path.classList.add("target");
    path.parentNode.appendChild(path); // draw on top of its neighbours
    const box = path.getBBox();
    if (Math.max(box.width, box.height) < SMALL) {
      const ring = document.createElementNS(NS, "circle");
      ring.setAttribute("class", "pulse-ring");
      ring.setAttribute("cx", box.x + box.width / 2);
      ring.setAttribute("cy", box.y + box.height / 2);
      ring.setAttribute("r", 12);
      svg.appendChild(ring);
    }
    return true;
  }

  window.worldMap = { highlight, clear };
})();
