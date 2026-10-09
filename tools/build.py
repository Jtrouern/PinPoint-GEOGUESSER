#!/usr/bin/env python3
"""Assemble Pinpoint into one self-contained HTML file.

    python3 tools/build.py                      # every pack -> dist/pinpoint.html
    python3 tools/build.py --packs us,india     # only these packs, in this order
    python3 tools/build.py --out dist/india.html --packs india

Packs come from packs/*.json, sorted by file name (so "10-us.json" comes
before "20-europe.json"). Each pack names the outline files it needs by
key; build.py loads geo/<key>.topo.json or geo/<key>.geo.json and inlines
only the ones used, so a smaller selection gives a smaller file.
Standard library only.
"""
import argparse, glob, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from packjson import load_pack  # noqa: E402


def geo_path(key):
    for ext in (".topo.json", ".geo.json", ".json"):
        p = os.path.join(ROOT, "geo", key + ext)
        if os.path.exists(p):
            return p
    return None


def geo_keys(pack):
    keys = {l["geo"] for l in pack.get("layers", [])}
    for pool in pack.get("pools", {}).values():
        if "regions" in pool:
            keys.add(pool["regions"]["geo"])
    if not pack.get("layers"):
        keys.add("world")  # default layers use the world outline as context
    return keys


def check(pack, geo, problems):
    pid = pack.get("id", "?")
    for k in ("id", "title", "pools"):
        if k not in pack:
            problems.append(f"{pid}: missing required field '{k}'")
    for name, pool in pack.get("pools", {}).items():
        if "regions" not in pool and "items" not in pool:
            problems.append(f"{pid}: pool '{name}' needs either 'items' or 'regions'")
        for i, it in enumerate(pool.get("items", [])):
            if isinstance(it, list):
                ok = len(it) == 3 and isinstance(it[0], str) and -90 <= it[1] <= 90 and -180 <= it[2] <= 180
            else:
                ok = "n" in it and "p" in it and all(-90 <= a <= 90 and -180 <= b <= 180 for a, b in it["p"])
            if not ok:
                problems.append(f"{pid}: pool '{name}' item {i + 1} looks wrong: {json.dumps(it, ensure_ascii=False)[:80]}")
        if "regions" in pool:
            r = pool["regions"]
            g = geo.get(r["geo"])
            if g and g.get("type") == "Topology" and r.get("object") and r["object"] not in g["objects"]:
                problems.append(f"{pid}: geo '{r['geo']}' has no object '{r['object']}' (has {list(g['objects'])})")
    for name in pack.get("mix", {}):
        if name not in pack.get("pools", {}):
            problems.append(f"{pid}: mix names pool '{name}', which does not exist")
    for l in pack.get("layers", []):
        g = geo.get(l["geo"])
        if g and g.get("type") == "Topology" and l.get("object") and l["object"] not in g["objects"]:
            problems.append(f"{pid}: layer geo '{l['geo']}' has no object '{l['object']}'")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--packs", help="comma-separated pack ids to include, in order (default: all)")
    ap.add_argument("--out", default=os.path.join(ROOT, "dist", "pinpoint.html"))
    a = ap.parse_args()

    packs = [load_pack(p) for p in sorted(glob.glob(os.path.join(ROOT, "packs", "*.json")))]
    if a.packs:
        want = [s.strip() for s in a.packs.split(",")]
        byid = {p["id"]: p for p in packs}
        missing = [w for w in want if w not in byid]
        if missing:
            sys.exit(f"Unknown pack id(s): {', '.join(missing)}. Available: {', '.join(byid)}")
        packs = [byid[w] for w in want]
    if not packs:
        sys.exit("No packs found in packs/")

    geo, problems = {}, []
    for key in sorted(set().union(*(geo_keys(p) for p in packs))):
        p = geo_path(key)
        if not p:
            problems.append(f"geo '{key}' not found in geo/ (looked for {key}.topo.json / {key}.geo.json)")
            continue
        with open(p, encoding="utf-8") as f:
            geo[key] = json.load(f)
    for p in packs:
        check(p, geo, problems)
    if problems:
        print("Problems found:\n  " + "\n  ".join(problems))
        sys.exit(1)

    with open(os.path.join(ROOT, "engine", "template.html"), encoding="utf-8") as f:
        html = f.read()
    for p in packs:
        p.pop("_notes", None)
    html = html.replace("/*GEO*/{}", json.dumps(geo, separators=(",", ":"), ensure_ascii=False), 1)
    html = html.replace("/*PACKS*/[]", json.dumps(packs, separators=(",", ":"), ensure_ascii=False), 1)
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as f:
        f.write(html)
    kb = os.path.getsize(a.out) / 1024
    print(f"Built {a.out}: {len(packs)} map(s) [{', '.join(p['id'] for p in packs)}], {kb:,.0f} KB")


if __name__ == "__main__":
    main()
