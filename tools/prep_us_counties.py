#!/usr/bin/env python3
"""One-off prep for the US counties pack (kept as a worked example).

Input:  counties-10m.json from the us-atlas npm package
        (https://github.com/topojson/us-atlas, Census Bureau data, ISC)
Output: geo/us-counties.topo.json, the same TopoJSON with two added
        properties per county:
          label  "Hartford County, CT", "Orleans Parish, LA", "Juneau, AK"
          word   county / parish / borough or census area / independent city
        The pack reads these with nameProp "label" and wordProp "word".

Shows the general trick: when names need tidying beyond a rename list,
do it once in a small script and store the result in the outline file,
so the game engine stays generic.

    python3 tools/prep_us_counties.py path/to/counties-10m.json
"""
import json, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ST = {"01": "AL", "02": "AK", "04": "AZ", "05": "AR", "06": "CA", "08": "CO", "09": "CT", "10": "DE", "11": "DC",
      "12": "FL", "13": "GA", "15": "HI", "16": "ID", "17": "IL", "18": "IN", "19": "IA", "20": "KS", "21": "KY",
      "22": "LA", "23": "ME", "24": "MD", "25": "MA", "26": "MI", "27": "MN", "28": "MS", "29": "MO", "30": "MT",
      "31": "NE", "32": "NV", "33": "NH", "34": "NJ", "35": "NM", "36": "NY", "37": "NC", "38": "ND", "39": "OH",
      "40": "OK", "41": "OR", "42": "PA", "44": "RI", "45": "SC", "46": "SD", "47": "TN", "48": "TX", "49": "UT",
      "50": "VT", "51": "VA", "53": "WA", "54": "WV", "55": "WI", "56": "WY", "72": "PR"}

topo = json.load(open(sys.argv[1], encoding="utf-8"))
kept = []
for g in topo["objects"]["counties"]["geometries"]:
    fips = str(g.get("id", "")).zfill(5)
    st = ST.get(fips[:2])
    if not st or st == "PR":
        continue
    name = g["properties"]["name"]
    code = int(fips[2:])
    if st == "LA":
        label, word = f"{name} Parish", "parish"
    elif st == "AK":
        label, word = name, "borough or census area"
    elif code >= 500 and st in ("VA", "MD", "MO", "NV"):  # independent cities
        label, word = f"{name} (city)", "independent city"
    elif st == "DC":
        label, word = "Washington, D.C.", "district"
    else:
        label, word = f"{name} County", "county"
    g["properties"].update(label=f"{label}, {st}" if st != "DC" else label, word=word, state=st)
    kept.append(g)
topo["objects"]["counties"]["geometries"] = kept
out = os.path.join(ROOT, "geo", "us-counties.topo.json")
json.dump(topo, open(out, "w", encoding="utf-8"), separators=(",", ":"))
print(f"Wrote {out}: {len(kept)} counties, {os.path.getsize(out) / 1024:,.0f} KB")
