# PinPoint-GEOGUESSER

Geography game - code can be customized for any geography.

**Play it:** https://jtrouern.github.io/PinPoint-GEOGUESSER/

## Developer notes

Pinpoint is a GeoSense-style geography game: a blank map, a place name, and ten seconds to click where it is. Closer and faster guesses score more, up to 1,000 points per place.

The game is split into a generic **engine** and any number of **map packs**. The engine knows nothing about the US, Australia or India. Each pack is a small JSON file that names some outlines and some places, and a build script bundles everything into one self-contained HTML file you can upload anywhere.

## Folder layout

```
pinpoint/
  docs/index.html        the built game (GitHub Pages serves this folder)
  engine/template.html   the game engine (HTML, CSS, JavaScript)
  packs/*.json           one map pack per file; the file-name prefix sets menu order
  geo/*.json             outline files (TopoJSON or GeoJSON) that packs refer to by name
  tools/build.py         bundles engine + packs + outlines into dist/pinpoint.html
  tools/make_pack.py     turns any GeoJSON of regions into a new pack
  tools/prep_us_counties.py   worked example of cleaning names before packing
  tools/packjson.py      shared helper for writing readable pack files
```

You need Python 3 to run the tools. Nothing else is required, except `pip install geonamescache` if you want `make_pack.py` to add cities automatically.

## Everyday workflow

1. Edit a pack in `packs/`, or add a new one.
2. Run `python3 tools/build.py --out docs/index.html`.
3. Open `docs/index.html` in a browser to test.
4. Commit and push. GitHub Pages republishes the game within a minute or two, and the Ghost embed picks it up automatically.

Without `--out`, `build.py` writes to `dist/pinpoint.html`, which Git ignores; use that for test builds.

To build a game with only some maps, which also makes the file smaller:

```
python3 tools/build.py --packs queensland,australia --out dist/aussie.html
```

`build.py` checks every pack before building and stops with a plain-English list of problems (a missing outline file, a pool name typo, a coordinate out of range).

## Adding a new geography

### The quick way: `make_pack.py`

Any set of regions works if you can get it as GeoJSON: Indian states, US counties, Irish counties, Canadian provinces, national parks, watersheds, ecoregions.

1. **Get outlines.** Good free sources:
   - Natural Earth admin-1 (states and provinces for every country): naturalearthdata.com
   - geoBoundaries (admin levels 1–3 for most countries): geoboundaries.org
   - US Census cartographic boundary files (counties, tracts, districts)

   If the file is a shapefile, KML or anything else, open mapshaper.org, drop it in, optionally click Simplify, then Export as GeoJSON.

2. **Find the name field.**

   ```
   python3 tools/make_pack.py my_regions.geojson --list-props
   ```

3. **Make the pack.** This is the exact command used for the India map:

   ```
   python3 tools/make_pack.py india_states.geojson --id india --title India \
     --name-prop name --word state --cities 100 --order 80 \
     --words "Delhi=union territory" --words "Ladakh=union territory" \
     --credit "Natural Earth (public domain)"
   ```

   It writes `geo/india.geo.json` (simplified outlines) and `packs/80-india.json` (a starter pack with a regions pool, a cities pool, a mix, a map frame and a scoring scale sized to the region).

4. **Review, then build.** Open the pack file and read through it. Automatic city lists come from GeoNames and need a human pass: the India list had a few odd entries and a misfiled city, and was missing several state capitals, all fixed by hand. Then run `build.py`.

Useful options: `--where STATE=CT` keeps only matching features, `--rename "Old=New"` tidies names, `--simplify 0.03` shrinks a big file, `--regions-per-game 4` changes the mix.

### When names need real cleanup

If names need more than a rename list (US counties need "County", "Parish" or "Borough" and a state abbreviation), fix them once in a small script and store the result as extra properties in the outline file. `tools/prep_us_counties.py` is a complete example. The pack then points at those properties with `nameProp` and `wordProp`.

### One outline file, many maps

A pack can filter regions, so one file can feed several maps. **New England Counties** uses the same outlines as **US Counties** with:

```json
"where": {"prop": "state", "in": ["CT", "RI", "MA", "VT", "NH", "ME"]}
```

A Connecticut-only map would be the same with `"in": ["CT"]`, a tighter `frame`, and a smaller `scale`.

## The pack format

```json
{
  "id": "india",
  "title": "India",
  "sub": "28 states, 8 union territories and 109 cities",
  "scale": 700,
  "credits": ["Natural Earth (public domain)", "GeoNames (CC BY 4.0)"],
  "view": {"frame": [[67.3, 5.9], [98.2, 36.4]]},
  "layers": [
    {"geo": "world", "object": "countries", "style": "context"},
    {"geo": "india", "style": "land"}
  ],
  "pools": {
    "regions": {"word": "state", "regions": {"geo": "india", "nameProp": "name",
                "words": {"Delhi": "union territory"}}},
    "cities":  {"word": "city", "items": [["Mumbai, Maharashtra", 19.073, 72.883]]}
  },
  "mix": {"regions": 6, "cities": 4}
}
```

| Field | Meaning |
|---|---|
| `id` | Short unique name. Also keys the player's saved best score. |
| `title`, `sub` | Button heading and one-line description on the start screen. |
| `scale` | Miles at which a guess scores zero. Smaller is stricter. Roughly a third of the map's width is a good start. |
| `credits` | Data sources. All packs' credits are collected on the start screen. Keep any that a license requires. |
| `rounds`, `seconds`, `revealMs` | Optional per-pack overrides of the defaults (10 places, 10 seconds, 2.6 seconds to show the answer). |
| `words` | Optional prompt wording for kinds, e.g. `{"park": "national park"}`. |
| `_notes` | Free text for developers. Ignored by the game and stripped from the build. |

**`view`**, how the map is framed:

- `frame`: `[[westLon, southLat], [eastLon, northLat]]`. The map zooms to this box.
- `projection`: `conicConformal` (the default with a frame; good for most countries and states), `albersUsa` (US with Alaska and Hawaii inset), `naturalEarth1` (whole world), `mercator`, `equirectangular`, or `conicEqualArea`.
- `rotate`, `parallels`: optional fine-tuning; worked out from the frame if omitted.
- With no frame and no world projection, the map fits the first `land` layer.

**`layers`**, drawn bottom to top:

- `geo`: an outline file in `geo/`, by name without extension.
- `object`: for TopoJSON files with several layers (e.g. `countries`, `states`). Omit for GeoJSON.
- `style`: `land` (filled shapes), `context` (faded land for surrounding areas), or `borders` (shared internal borders only; TopoJSON files only).
- `width`: line thickness. `focus`: list of names drawn at full strength while the rest fade, as Queensland does.
- If `layers` is omitted, the engine draws the world faintly plus each regions pool.

**`pools`**, the places a game draws from. Each pool has a `word` used in the prompt ("Where is this *state*?") and either `items` or `regions`.

- `items`: a list of places. Either `["Label", lat, lon]` for a point, or `{"n": "Name", "k": "kind", "p": [[lat, lon], ...], "r": miles}`:
  - one point in `p` for a spot; several for a line such as a river, reef or range;
  - `r` above 0 makes any click within that many miles count as on target;
  - `k` overrides the pool's word for that place ("Where is this *desert*?").
- `regions`: polygons from an outline file. A click inside counts as on target; otherwise distance is to the nearest edge. Settings: `geo`, `object`, `nameProp` (which property is the name), `wordProp` (a property holding a per-region word), `words` (per-name overrides), `exclude` (names to leave out), and `where` (`{"prop": ..., "in": [...]}` or `{"prop": ..., "startsWith": ...}`).

**`mix`**: how many places to draw from each pool per game. If the counts fall short of `rounds`, the rest are drawn at random from all pools.

**Scoring**: points = 1000 × accuracy² × speed, where accuracy = 1 − distance ÷ scale, and speed runs from 1.0 for an instant click down to 0.5 at the last second.

## Engine settings

At the top of the engine script in `engine/template.html`:

- `DEFAULTS`: rounds per game, seconds per place, reveal time, default scale.
- `WORDS`: default prompt wording for kinds.
- Colors and fonts: the CSS variables at the top of `<style>` (light theme first, then dark).

Rebuild after changing the engine.

## Included maps

| Menu | Pack file | Notes |
|---|---|---|
| United States | `10-us.json` | 200 cities |
| Europe | `20-europe.json` | 250 cities |
| World | `30-world.json` | Capitals and megacities |
| Advanced | `40-advanced.json` | 500 lesser-known cities |
| Australia | `50-australia.json` | States, cities, towns, 74 landscape features |
| Queensland | `60-queensland.json` | Cities, towns, 39 features |
| Mexico | `70-mexico.json` | 32 states, 109 cities |
| India | `80-india.json` | 36 states and UTs, 109 cities |
| US Counties | `90-us-counties.json` | All 3,142 counties and equivalents |
| New England Counties | `95-new-england-counties.json` | 67 counties, filtered from the same file |

The full build is about 2.1 MB, mostly the world and US-county outlines. A build without the county maps is about 1.1 MB.

India's boundaries follow Natural Earth's de facto lines, which differ from the Government of India's official map in Jammu & Kashmir and Ladakh. If you publish the India map to an audience in India, consider substituting official outlines.

## Hosting

- **GitHub Pages:** in the repository's Settings → Pages, choose "Deploy from a branch", branch `main`, folder `/docs`. The game then lives at `https://<your-username>.github.io/<repo-name>/`.
- **Ghost:** embed that address in a page with an HTML card:

  ```html
  <iframe src="https://jtrouern.github.io/PinPoint-GEOGUESSER/"
          style="width:100%; height:80vh; min-height:560px; border:0; display:block;"
          title="Pinpoint geography game" loading="lazy"></iframe>
  ```

- **Best scores** live in each visitor's own browser (`localStorage`, keys `pinpoint-best-<pack id>`). There's no shared leaderboard.
- **Internet access:** the game loads D3 and topojson-client from public CDNs and fonts from Google Fonts. For fully offline use, download those and point the `<script src>` tags at local copies.

## License

**MIT License:** the engine, the build tools, and the hand-compiled place lists (Australian and Queensland towns and features, extra Mexican towns, Indian capitals added by hand) are released under the [MIT License](LICENSE). Anyone may use, copy, modify and redistribute them, including commercially, as long as the copyright and license notice stay with the code.

**Third-party material keeps its own terms:**

| Material | License | What you must do |
|---|---|---|
| City lists from GeoNames | CC BY 4.0 | Keep the GeoNames credit (packs carry it in `credits`) |
| Natural Earth outlines | Public domain | Nothing; credit appreciated |
| US Census outlines | Public domain | Nothing; credit appreciated |
| `world-atlas` / `us-atlas` packaging | ISC | Keep the credit |
| D3, topojson-client (loaded from CDN) | ISC | Nothing extra; not bundled |

When you add a pack from another source, check its license and put the required credit in the pack's `credits` field. geoBoundaries data is mostly CC BY 4.0 or open; check each country's entry.
