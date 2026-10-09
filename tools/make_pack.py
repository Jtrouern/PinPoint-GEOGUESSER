#!/usr/bin/env python3
"""Turn any GeoJSON of regions into a ready-to-play Pinpoint map pack.

Example (Indian states):

    python3 tools/make_pack.py india_states.geojson --id india \\
        --title "India" --sub "States, union territories and cities" \\
        --name-prop name --word state --cities 100 --order 80

This writes two files:
    geo/india.geo.json   the outlines, simplified and trimmed to one name field
    packs/80-india.json  a starter pack: regions pool, optional cities pool,
                         a mix, a map frame and a scoring scale

Then run `python3 tools/build.py`. Open the pack file afterwards to adjust
wording, the mix, or the scale; it is plain JSON.

Options worth knowing:
    --name-prop    which property holds each region's name (try --list-props)
    --where        keep only features whose property matches: STATE=CT
    --simplify     tolerance in degrees (default 0.01, about 1 km). Raise it
                   to shrink the file; 0 keeps every vertex.
    --cities N     add N cities from GeoNames inside the regions, labelled
                   "City, Region". Needs: pip install geonamescache
    --words        per-region prompt word overrides: "Delhi=union territory"

Input must be GeoJSON with Polygon/MultiPolygon features in longitude/latitude
(EPSG:4326). For shapefiles or other formats, convert first at
https://mapshaper.org (import, then Export > GeoJSON).
Standard library only, except --cities.
"""
import argparse, json, math, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from packjson import dump_pack  # noqa: E402


# ---------- geometry helpers ----------
def dp(pts, tol):
    """Douglas-Peucker line simplification."""
    if tol <= 0 or len(pts) < 5:
        return pts
    keep = [False] * len(pts)
    keep[0] = keep[-1] = True
    stack = [(0, len(pts) - 1)]
    while stack:
        a, b = stack.pop()
        ax, ay = pts[a]
        bx, by = pts[b]
        dx, dy = bx - ax, by - ay
        L = dx * dx + dy * dy
        best, idx = 0, None
        for i in range(a + 1, b):
            px, py = pts[i]
            if L == 0:
                d = (px - ax) ** 2 + (py - ay) ** 2
            else:
                t = max(0, min(1, ((px - ax) * dx + (py - ay) * dy) / L))
                d = (px - ax - t * dx) ** 2 + (py - ay - t * dy) ** 2
            if d > best:
                best, idx = d, i
        if idx is not None and best > tol * tol:
            keep[idx] = True
            stack += [(a, idx), (idx, b)]
    return [p for p, k in zip(pts, keep) if k]


def polys(geom):
    if geom["type"] == "Polygon":
        return [geom["coordinates"]]
    if geom["type"] == "MultiPolygon":
        return geom["coordinates"]
    return []


def simplify_geom(geom, tol, prec):
    out = []
    for poly in polys(geom):
        rings = []
        for ring in poly:
            r = [[round(x, prec), round(y, prec)] for x, y in dp(ring, tol)]
            r = [p for i, p in enumerate(r) if i == 0 or p != r[i - 1]]
            if len(r) >= 4:
                rings.append(r)
        if rings:
            out.append(rings)
    if not out:
        return None
    return {"type": "Polygon", "coordinates": out[0]} if len(out) == 1 else {"type": "MultiPolygon", "coordinates": out}


def in_ring(x, y, ring):
    inside = False
    j = len(ring) - 1
    for i in range(len(ring)):
        xi, yi = ring[i]
        xj, yj = ring[j]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi) + xi:
            inside = not inside
        j = i
    return inside


def contains(geom, x, y):
    for poly in polys(geom):
        if in_ring(x, y, poly[0]) and not any(in_ring(x, y, h) for h in poly[1:]):
            return True
    return False


def bbox(features):
    xs, ys = [], []
    for f in features:
        for poly in polys(f["geometry"]):
            for x, y in poly[0]:
                xs.append(x)
                ys.append(y)
    return min(xs), min(ys), max(xs), max(ys)


def miles(a, b):
    R = 3958.8
    p1, p2 = math.radians(a[0]), math.radians(b[0])
    h = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(b[1] - a[1]) / 2) ** 2
    return 2 * R * math.asin(math.sqrt(h))


# ---------- main ----------
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("geojson")
    ap.add_argument("--list-props", action="store_true", help="print the first feature's properties and stop")
    ap.add_argument("--id", help="short id, letters/numbers/dashes (e.g. india)")
    ap.add_argument("--title")
    ap.add_argument("--sub", default="")
    ap.add_argument("--name-prop", default="name")
    ap.add_argument("--word", default="region", help='prompt word: "Where is this <word>?"')
    ap.add_argument("--words", action="append", default=[], help='override per region: "Name=word"')
    ap.add_argument("--rename", action="append", default=[], help='rename a region: "Old=New"')
    ap.add_argument("--where", action="append", default=[], help='keep features with PROP=VALUE (repeatable)')
    ap.add_argument("--simplify", type=float, default=0.01)
    ap.add_argument("--precision", type=int, default=3, help="decimal places kept (3 = ~100 m)")
    ap.add_argument("--cities", type=int, default=0)
    ap.add_argument("--min-pop", type=int, default=15000)
    ap.add_argument("--city-gap", type=float, default=0, help="min miles between cities (default: auto)")
    ap.add_argument("--regions-per-game", type=int, default=None)
    ap.add_argument("--order", type=int, default=90, help="start-screen position; becomes the file-name prefix")
    ap.add_argument("--credit", action="append", default=[], help="credit line for the outline source")
    a = ap.parse_args()

    with open(a.geojson, encoding="utf-8") as f:
        src = json.load(f)
    feats = src["features"] if src.get("type") == "FeatureCollection" else [src]
    if a.list_props:
        print(json.dumps(feats[0].get("properties"), indent=2, ensure_ascii=False))
        return
    if not (a.id and a.title):
        ap.error("--id and --title are required")

    for cond in a.where:
        k, v = cond.split("=", 1)
        feats = [f for f in feats if str((f.get("properties") or {}).get(k)) == v]
    rename = dict(r.split("=", 1) for r in a.rename)
    out, skipped = [], []
    for f in feats:
        name = (f.get("properties") or {}).get(a.name_prop)
        if name in (None, ""):
            skipped.append("(no name)")
            continue
        g = simplify_geom(f["geometry"], a.simplify, a.precision) if f.get("geometry") else None
        if not g:
            skipped.append(str(name))
            continue
        out.append({"type": "Feature", "properties": {"name": rename.get(name, name)}, "geometry": g})
    if not out:
        sys.exit(f"No usable features. Is '{a.name_prop}' the right --name-prop? Try --list-props.")
    names = [f["properties"]["name"] for f in out]
    dupes = sorted({n for n in names if names.count(n) > 1})

    os.makedirs(os.path.join(ROOT, "geo"), exist_ok=True)
    geo_file = os.path.join(ROOT, "geo", f"{a.id}.geo.json")
    with open(geo_file, "w", encoding="utf-8") as f:
        json.dump({"type": "FeatureCollection", "features": out}, f, separators=(",", ":"), ensure_ascii=False)

    w, s, e, n = bbox(out)
    padx, pady = (e - w) * 0.03, (n - s) * 0.03
    frame = [[round(w - padx, 2), round(s - pady, 2)], [round(e + padx, 2), round(n + pady, 2)]]
    diag = miles((s, w), (n, e))
    scale = int(max(50, round(diag * 0.35, -1)))

    pools = {"regions": {"word": a.word, "regions": {"geo": a.id, "nameProp": "name"}}}
    if a.words:
        pools["regions"]["regions"]["words"] = dict(x.split("=", 1) for x in a.words)
    credits = a.credit or ["see pack file"]
    if a.cities:
        try:
            import geonamescache
        except ImportError:
            sys.exit("--cities needs: pip install geonamescache")
        gap = a.city_gap or max(5, diag / 60)
        gc = geonamescache.GeonamesCache(min_city_population=a.min_pop)
        cand = [c for c in gc.get_cities().values() if w <= c["longitude"] <= e and s <= c["latitude"] <= n]
        cand.sort(key=lambda c: -c["population"])
        items, placed = [], []
        for c in cand:
            p = (c["latitude"], c["longitude"])
            if any(miles(p, q) < gap for q in placed):
                continue
            region = next((f["properties"]["name"] for f in out if contains(f["geometry"], p[1], p[0])), None)
            if not region:
                continue
            placed.append(p)
            items.append([f"{c['name']}, {region}", round(p[0], 3), round(p[1], 3)])
            if len(items) >= a.cities:
                break
        pools["cities"] = {"word": "city", "items": items}
        credits.append('<a href="https://www.geonames.org">GeoNames</a> (CC BY 4.0)')
    rpg = a.regions_per_game if a.regions_per_game is not None else (6 if a.cities else 10)
    mix = {"regions": rpg}
    if a.cities:
        mix["cities"] = max(0, 10 - rpg)

    pack = {
        "_notes": "Generated by tools/make_pack.py. Edit freely; see README for every field.",
        "id": a.id, "title": a.title, "sub": a.sub or f"{len(out)} {a.word}s", "scale": scale,
        "credits": credits,
        "view": {"frame": frame},
        "layers": [
            {"geo": "world", "object": "countries", "style": "context"},
            {"geo": a.id, "style": "land"},
        ],
        "pools": pools, "mix": mix,
    }
    os.makedirs(os.path.join(ROOT, "packs"), exist_ok=True)
    pack_file = os.path.join(ROOT, "packs", f"{a.order:02d}-{a.id}.json")
    dump_pack(pack, pack_file)

    kb = os.path.getsize(geo_file) / 1024
    print(f"Wrote {geo_file} ({len(out)} regions, {kb:,.0f} KB)")
    print(f"Wrote {pack_file} (scale {scale} mi" + (f", {len(pools['cities']['items'])} cities" if a.cities else "") + ")")
    if skipped:
        print(f"Skipped {len(skipped)} feature(s) without a name or usable polygon: {', '.join(skipped[:8])}")
    if dupes:
        print(f"Warning: duplicate names (players can't tell these apart): {', '.join(dupes[:10])}")
    if kb > 1500:
        print("Tip: that outline file is large; try --simplify 0.03 or simplify at mapshaper.org.")
    print("Next: python3 tools/build.py")


if __name__ == "__main__":
    main()
