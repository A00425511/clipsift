#!/usr/bin/env python3
"""Build species_list.json from seed_species.csv using WoRMS and GBIF (stdlib only).

Rerunnable. Network failures never stop the run: unresolved names stay in the
list with null IDs. Local names from the seed are always kept.
"""
import csv, json, sys, time, datetime, hashlib
import urllib.request, urllib.parse, urllib.error
from pathlib import Path

HERE = Path(__file__).resolve().parent
SEED = HERE / "seed_species.csv"
UA = "clipsift-species-builder/0.1 (prototype; polite, one request at a time)"
WORMS = "https://www.marinespecies.org/rest"
GBIF = "https://api.gbif.org/v1"
SLEEP = 0.7
TIMEOUT = 20
RETRIES = 2
TODAY = datetime.date.today()


def get_json(url):
    """Return (parsed json or None, error string or None). Never raises."""
    err = None
    for attempt in range(RETRIES + 1):
        time.sleep(SLEEP)
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
                body = resp.read()
                if resp.status == 204 or not body:
                    return None, None
                return json.loads(body.decode("utf-8")), None
        except urllib.error.HTTPError as e:
            if e.code in (204, 404):
                return None, None
            err = f"HTTP {e.code}"
        except Exception as e:  # network down, timeout, bad json
            err = type(e).__name__
        time.sleep(2 * (attempt + 1))
    return None, err


def uniq(items, exclude=()):
    seen = {x.lower() for x in exclude}
    out = []
    for x in items:
        x = (x or "").strip()
        if x and x.lower() not in seen:
            seen.add(x.lower())
            out.append(x)
    return out


def resolve_worms(name):
    q = urllib.parse.quote(name)
    recs, err = get_json(f"{WORMS}/AphiaRecordsByName/{q}?like=false&marine_only=false")
    if err:
        return None, [], [], err
    if not recs:
        return None, [], [], "no WoRMS match"
    rec = next((r for r in recs if r.get("status") == "accepted"), recs[0])
    aid = rec.get("AphiaID")
    note = None
    if rec.get("status") != "accepted" and rec.get("valid_AphiaID"):
        aid = rec["valid_AphiaID"]
        note = f"WoRMS: {name} is unaccepted, used valid name {rec.get('valid_name')}"
    vern, _ = get_json(f"{WORMS}/AphiaVernacularsByAphiaID/{aid}")
    names = [v.get("vernacular") for v in (vern or []) if (v.get("language_code") == "eng" or v.get("language") == "English")]
    syn, _ = get_json(f"{WORMS}/AphiaSynonymsByAphiaID/{aid}")
    aliases = [s.get("scientificname") for s in (syn or [])]
    if note:
        aliases.append(rec.get("scientificname"))
    return aid, names, aliases, note


def resolve_gbif(name):
    q = urllib.parse.urlencode({"name": name})
    d, err = get_json(f"{GBIF}/species/match?{q}")
    if err:
        return None, err
    if not d or d.get("matchType") in (None, "NONE") or "usageKey" not in d:
        return None, "no GBIF match"
    return d["usageKey"], None


def main():
    seed = list(csv.DictReader(open(SEED, newline="", encoding="utf-8")))
    date = TODAY.isoformat()
    out, unresolved, notes = [], [], []
    for i, row in enumerate(seed, 1):
        name = row["scientific_name"].strip()
        print(f"[{i}/{len(seed)}] {name}", flush=True)
        aid, w_names, w_alias, w_note = resolve_worms(name)
        gkey, g_err = resolve_gbif(name)
        local = [x for x in row.get("local_names", "").split(";")]
        common = uniq([row["common_name"]] + local + w_names)
        aliases = uniq(w_alias, exclude=[name])
        id_notes = row.get("id_notes", "").strip()
        sources = [{"name": "Seed list: " + row["source_note"].strip(), "retrieved": date}]
        if aid is not None:
            sources.append({"name": "WoRMS", "retrieved": date})
        if gkey is not None:
            sources.append({"name": "GBIF species match", "retrieved": date})
        if aid is None or gkey is None:
            unresolved.append({"scientific_name": name,
                               "worms": None if aid is not None else w_note,
                               "gbif": None if gkey is not None else g_err})
        if aid is None and not (w_note or "").startswith("no WoRMS"):
            notes.append(f"{name}: WoRMS lookup failed ({w_note})")
        out.append({
            "aphia_id": aid, "gbif_key": gkey, "scientific_name": name,
            "common_names": common, "aliases": aliases, "group": row["group"], "rank": row.get("rank") or "species",
            "flags": {"at_risk": row["at_risk"] == "1", "invasive": row["invasive"] == "1",
                      "range_expander": row["range_expander"] == "1"},
            "ns_status_tier": "unknown",
            "id_notes": " ".join(x for x in [id_notes, ("Status: " + row["status_note"]) if row.get("status_note") else ""] if x),
            "sources": sources,
        })
    text = json.dumps(out, indent=2, ensure_ascii=False) + "\n"
    (HERE / "species_list.json").write_text(text, encoding="utf-8")
    versioned = f"species_list_v{TODAY:%Y.%m.%d}.json"
    (HERE / versioned).write_text(text, encoding="utf-8")
    manifest = {
        "retrieved": date, "versioned_file": versioned,
        "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "seed_file": SEED.name, "total": len(out),
        "worms_resolved": sum(1 for s in out if s["aphia_id"] is not None),
        "gbif_resolved": sum(1 for s in out if s["gbif_key"] is not None),
        "fully_resolved": len(out) - len(unresolved),
        "unresolved": unresolved, "notes": notes,
    }
    (HERE / "species_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"Done. {manifest['fully_resolved']}/{len(out)} fully resolved; "
          f"WoRMS {manifest['worms_resolved']}, GBIF {manifest['gbif_resolved']}; "
          f"{len(unresolved)} with a missing ID.")


if __name__ == "__main__":
    sys.exit(main())
