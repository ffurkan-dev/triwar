#!/usr/bin/env python3
"""Build static/maps/world.svg and game/fixtures/countries.json from Natural Earth.

Source: Natural Earth Admin 0 Countries 1:110m (public domain).
Usage: python scripts/build_world_svg.py [path/to/ne_110m_admin_0_countries.geojson]
Without an argument the GeoJSON is downloaded to a temporary file (not kept in the repo).
Standard library only.
"""
import json
import math
import sys
import tempfile
import urllib.request
from pathlib import Path

URL = "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/ne_110m_admin_0_countries.geojson"
ROOT = Path(__file__).resolve().parent.parent
SVG_OUT = ROOT / "static" / "maps" / "world.svg"
FIXTURE_OUT = ROOT / "game" / "fixtures" / "countries.json"

MAP_WIDTH = 1000
# Countries whose projected area (px^2 in a 1000px-wide map) is below this start inactive.
MIN_ACTIVE_AREA = 25.0
EXCLUDED_ISO2 = {"AQ"}  # Antarctica is left off the map entirely.
# Disputed or dependent territories stay on the map but are never asked in the prototype.
NEVER_ACTIVE = {"EH", "XK", "PS", "FK", "NC", "PR", "TF", "GL"}

# Natural Earth uses non-ISO codes for a few entries.
ISO2_FIXES = {"CN-TW": "TW"}

# Fixes for Natural Earth's Turkish names (reviewed once by hand).
NAME_TR_OVERRIDES = {
    "XK": "Kosova",
    "TW": "Tayvan",
    "CN": "Çin",
    "ZA": "Güney Afrika",
    "CY": "Kıbrıs",
    "CZ": "Çekya",
    "CD": "Kongo Demokratik Cumhuriyeti",
    "CG": "Kongo Cumhuriyeti",
    "MK": "Kuzey Makedonya",
    "SZ": "Esvatini",
    "TL": "Doğu Timor",
    "GW": "Gine-Bissau",
    "CI": "Fildişi Sahili",
    "US": "Amerika Birleşik Devletleri",
    "GB": "Birleşik Krallık",
    "KR": "Güney Kore",
    "KP": "Kuzey Kore",
}


def project(lon, lat):
    """Natural Earth projection (Šavrič et al.). Returns (x, y) with y pointing up."""
    lam, phi = math.radians(lon), math.radians(lat)
    p2, p4 = phi * phi, phi**4
    x = lam * (0.8707 - 0.131979 * p2 + p4 * (-0.013791 + p4 * (0.003971 * p2 - 0.001529 * p4)))
    y = phi * (1.007226 + p2 * (0.015085 + p4 * (-0.044475 + 0.028874 * p2 - 0.005916 * p4)))
    return x, y


def polygons(geometry):
    if geometry["type"] == "Polygon":
        return [geometry["coordinates"]]
    return geometry["coordinates"]


def iso2_of(props):
    code = props["ISO_A2"]
    if code == "-99":  # France, Norway, Kosovo...: fall back to the "eh" field
        code = props["ISO_A2_EH"]
    code = ISO2_FIXES.get(code, code)
    return None if code == "-99" else code


def load_geojson(arg):
    if arg:
        return json.loads(Path(arg).read_text(encoding="utf-8"))
    with tempfile.TemporaryDirectory() as tmp:
        target = Path(tmp) / "countries.geojson"
        print(f"Downloading {URL}")
        urllib.request.urlretrieve(URL, target)
        return json.loads(target.read_text(encoding="utf-8"))


def ring_area(points):
    return abs(sum(x1 * y2 - x2 * y1 for (x1, y1), (x2, y2) in zip(points, points[1:] + points[:1]))) / 2


def main():
    data = load_geojson(sys.argv[1] if len(sys.argv) > 1 else None)
    features = [f for f in data["features"] if iso2_of(f["properties"]) not in EXCLUDED_ISO2]

    # Projection bounds decide the scale/offset so the map fits the viewBox.
    all_pts = [
        project(lon, lat)
        for f in features
        for poly in polygons(f["geometry"])
        for ring in poly
        for lon, lat in ring
    ]
    min_x, max_x = min(p[0] for p in all_pts), max(p[0] for p in all_pts)
    min_y, max_y = min(p[1] for p in all_pts), max(p[1] for p in all_pts)
    scale = MAP_WIDTH / (max_x - min_x)
    height = round((max_y - min_y) * scale)

    def to_svg(lon, lat):
        x, y = project(lon, lat)
        return round((x - min_x) * scale, 1), round((max_y - y) * scale, 1)

    paths, fixture, seen = [], [], set()
    for f in sorted(features, key=lambda f: f["properties"]["NAME"]):
        props = f["properties"]
        iso2 = iso2_of(props)
        parts, area = [], 0.0
        for poly in polygons(f["geometry"]):
            for i, ring in enumerate(poly):
                pts = [to_svg(lon, lat) for lon, lat in ring]
                pts = [p for j, p in enumerate(pts) if j == 0 or p != pts[j - 1]]
                if len(pts) < 3:
                    continue
                if i == 0:
                    area += ring_area(pts)
                parts.append("M" + "L".join(f"{x:g},{y:g}" for x, y in pts) + "Z")
        if not parts:
            continue
        d = "".join(parts)
        if iso2 is None:
            paths.append(f'<path class="land" d="{d}"/>')  # no code: drawn grey, never asked
            continue
        if iso2 in seen:
            raise SystemExit(f"duplicate ISO2 {iso2}")
        seen.add(iso2)
        paths.append(f'<path id="{iso2}" class="country" d="{d}"/>')
        fixture.append(
            {
                "model": "game.country",
                "pk": iso2,
                "fields": {
                    "name_tr": NAME_TR_OVERRIDES.get(iso2, props["NAME_TR"]),
                    "name_en": props["NAME_EN"],
                    "continent": props["CONTINENT"],
                    "is_active": iso2 not in NEVER_ACTIVE and area >= MIN_ACTIVE_AREA and props["CONTINENT"] != "Seven seas (open ocean)",
                },
            }
        )

    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" class="world-map" viewBox="0 0 {MAP_WIDTH} {height}" '
        f'role="img" aria-label="Dünya haritası">\n<rect class="ocean" width="{MAP_WIDTH}" height="{height}"/>\n'
        + "\n".join(paths)
        + "\n</svg>\n"
    )
    SVG_OUT.write_text(svg, encoding="utf-8")
    fixture.sort(key=lambda o: o["fields"]["name_en"])
    FIXTURE_OUT.write_text(json.dumps(fixture, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    active = sum(o["fields"]["is_active"] for o in fixture)
    print(f"{SVG_OUT.relative_to(ROOT)}: {len(paths)} shapes, {SVG_OUT.stat().st_size // 1024} KB, {MAP_WIDTH}x{height}")
    print(f"{FIXTURE_OUT.relative_to(ROOT)}: {len(fixture)} countries, {active} active")


if __name__ == "__main__":
    main()
