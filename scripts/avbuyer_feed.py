#!/usr/bin/env python3
"""
FLYINGGROUP Aircraft Comparison Tool: daily AvBuyer market feed.

Reads the public AvBuyer private-jet overview pages (robots.txt: crawl-delay 1 s; we wait 1.5 s),
keeps for-sale listings of the types in the tool, adds the registration from each listing's
detail page (fetched once per listing and cached), and writes market_data.js next to the tool.

  python3 avbuyer_feed.py --out "<Toolkit folder>/market_data.js" [--max-seconds 160]

Safe by design: the output is only replaced when the crawl reached the last overview page and
found at least 80% of the previous listing count. Each run can stop early (time budget); the
registration cache is kept, so the next run continues where this one stopped.
Exit code 0 = feed written, 2 = feed written but registrations still pending, 1 = failed (old feed kept).
"""
import urllib.request, urllib.error, re, html, json, time, os, sys, argparse, datetime, collections, gzip

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0 Safari/537.36"
BASE = "https://www.avbuyer.com"
LIST = BASE + "/aircraft/private-jets"
DELAY = 1.5
HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, "reg_cache.json")
HIST = os.path.join(HERE, "history")

# AvBuyer model title -> tool type. Only exact models or the same aircraft under another name.
TYPE_MAP = {
 "Bombardier Challenger 300": "Challenger 300", "Bombardier Challenger 350": "Challenger 350",
 "Bombardier Challenger 3500": "Challenger 3500", "Bombardier Challenger 604": "Challenger 604",
 "Bombardier Challenger 605": "Challenger 605", "Canadair CL-605": "Challenger 605",
 "Bombardier Challenger 650": "Challenger 650",
 "Bombardier Global 5000": "Global 5000", "Bombardier Global 6000": "Global 6000",
 "Bombardier Global 6500": "Global 6500", "Bombardier Global 7500": "Global 7500",
 "Bombardier Global Express XRS": "Global XRS",
 "Bombardier Learjet 40": "Learjet 40", "Bombardier Learjet 45": "Learjet 45",
 "Bombardier Learjet 45XR": "LearJet 45XR", "Bombardier Learjet 60": "LearJet 60",
 "Bombardier Learjet 70": "Learjet 70", "Bombardier Learjet 75": "Learjet 75",
 "Cessna Citation CJ1": "Citation CJ1", "Cessna Citation CJ1+": "Citation CJ1+",
 "Cessna Citation CJ2": "Citation CJ2", "Cessna Citation CJ2+": "Citation CJ2+",
 "Cessna Citation CJ3": "Citation CJ3", "Cessna Citation CJ3+": "Citation CJ3+",
 "Cessna Citation CJ4": "Citation CJ4", "Cessna Citation CJ4 Gen 2": "Citation CJ4 Gen2",
 "Cessna Citation CJ4 Gen2": "Citation CJ4 Gen2",
 "Cessna Citation Latitude": "Citation Latitude  680A", "Cessna Citation Longitude": "Citation Longitude",
 "Cessna Citation M2": "Citation M2", "Cessna Citation M2 Gen2": "Citation M2 Gen2", "Cessna Citation M2 GEN2": "Citation M2 Gen2",
 "Cessna Citation Mustang": "Citation Mustang", "Cessna Citation Sovereign": "Citation Sovereign",
 "Cessna Citation Sovereign+": "Citation Sovereign+", "Cessna Citation VII": "Citation VII",
 "Cessna Citation X": "Citation X", "Cessna Citation XLS": "Citation XLS", "Cessna Citation XLS+": "Citation XLS+",
 "Cessna Citation XLS Gen2": "Citation XLS Gen2", "Cessna Citation XLS Gen 2": "Citation XLS Gen2",
 "Cirrus Vision SF50": "VisionJet SF50", "Cirrus SF50 Vision G2+ Elite": "VisionJet SF50", "Cirrus SF50 Vision Jet": "VisionJet SF50",
 "Dassault Falcon 100": "Falcon 100", "Dassault Falcon 50": "Falcon 50",
 "Dassault Falcon 2000EX": "Falcon 2000EX", "Dassault Falcon 2000EX EASy": "Falcon 2000EX EASy",
 "Dassault Falcon 2000LXS": "Falcon 2000LXS", "Dassault Falcon 2000S": "Falcon 2000S",
 "Dassault Falcon 6X": "Falcon 6X", "Dassault Falcon 7X": "Falcon 7X", "Dassault Falcon 8X": "Falcon 8X",
 "Dassault Falcon 900B": "Falcon 900B", "Dassault Falcon 900C": "Falcon 900C", "Dassault Falcon 900DX": "Falcon 900DX",
 "Dassault Falcon 900EX": "Falcon 900EX", "Dassault Falcon 900EX EASy": "Falcon 900EX EASy", "Dassault Falcon 900LX": "Falcon 900LX",
 "Embraer Legacy 450": "Legacy 450", "Embraer Legacy 500": "Legacy 500",
 "Embraer Phenom 100": "Phenom 100", "Embraer Phenom 100E": "Phenom 100E", "Embraer Phenom 100EV": "Phenom 100EV",
 "Embraer Phenom 100EX": "Phenom 100EX", "Embraer Phenom 300": "Phenom 300", "Embraer Phenom 300E": "Phenom 300E",
 "Embraer Praetor 500": "Praetor 500", "Embraer Praetor 600": "Praetor 600",
 "Gulfstream G150": "Gulfstream G150", "Gulfstream G200": "Gulfstream G200", "Gulfstream G280": "Gulfstream G280",
 "Gulfstream G400": "Gulfstream G400", "Gulfstream G450": "Gulfstream G450",
 "Gulfstream G500 (GVII)": "Gulfstream G500", "Gulfstream G550": "Gulfstream G550", "Gulfstream G600": "Gulfstream G600",
 "Gulfstream G650": "Gulfstream G650", "Gulfstream G650ER": "Gulfstream G650ER", "Gulfstream G700": "Gulfstream G700",
 "Hawker 400XP": "400XP", "Hawker 400XPR": "400XPR", "Hawker 800XP": "800XP", "Hawker 850XP": "850XP", "Hawker 900XP": "900XP",
 "Honda HondaJet": "HondaJet", "Honda HondaJet Elite": "HondaJet Elite",
 "Pilatus PC-24": "Pilatus PC24",
}
# EASA member states (EU 27 + Iceland, Liechtenstein, Norway, Switzerland): nationality prefixes
EASA_PREFIX = ["OE","OO","LZ","9A","5B","OK","OY","ES","OH","F","D","SX","HA","EI","EJ","I","YL","LY","LX","9H",
               "PH","SP","SN","CS","YR","OM","S5","EC","EM","SE","TF","LN","HB"]
GONE = re.compile(r"now sold|off market", re.I)

def latest_history():
    """Newest daily snapshot in history/ (plain .json or gzipped .json.gz), or None."""
    if not os.path.isdir(HIST): return None
    hs = sorted(f for f in os.listdir(HIST) if f.endswith(".json") or f.endswith(".json.gz"))
    if not hs: return None
    p = os.path.join(HIST, hs[-1])
    with (gzip.open(p, "rt", encoding="utf-8") if p.endswith(".gz") else open(p, encoding="utf-8")) as f:
        return json.load(f)

def get(url, tries=3):
    for a in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "en"})
            with urllib.request.urlopen(req, timeout=40) as r:
                return r.read().decode("utf-8", "ignore")
        except urllib.error.HTTPError as e:
            if e.code == 404: return None
            time.sleep(5 * (a + 1))
        except Exception:
            time.sleep(5 * (a + 1))
    raise RuntimeError("fetch failed: " + url)

def texts(fragment):
    t = html.unescape(re.sub(r"<[^>]+>", "|", fragment))
    t = re.sub(r"\s+", " ", t)
    return [x.strip() for x in t.split("|") if x.strip()]

def parse_cards(page):
    rows = []
    for c in re.split(r'<div id="item_card_', page)[1:]:
        lid = c.split('"')[0]
        if "wanted-item" in c[:200]: continue
        href = re.search(r'href="(/aircraft/private-jets/[^"]+/' + re.escape(lid) + r')"', c)
        title = re.search(r'<h2 class="item-title"><a[^>]*>(.*?)</a>', c, re.S)
        price = re.search(r'<div class="price">(.*?)</div>', c, re.S)
        if not (href and title): continue
        t = texts(re.sub(r"<picture>.*?</picture>", "", c.split('class="share-')[0], flags=re.S))
        def after(lbl):
            for x in t:
                if x.startswith(lbl + " "): return x[len(lbl) + 1:].strip()
            return ""
        loc = next((x for x in t if x.endswith("For Sale by")), "")
        seller = t[t.index(loc) + 1] if loc and loc in t and t.index(loc) + 1 < len(t) else ""
        rows.append({
            "id": lid, "title": html.unescape(title.group(1)).strip(),
            "price_raw": html.unescape(re.sub(r"<[^>]+>", " ", price.group(1))).strip() if price else "",
            "yom": after("Year"), "serial": after("S/N"), "ttaf": after("Total Time"),
            "location": loc[:-len("For Sale by")].strip(" ,") if loc else "", "seller": seller,
            "listed_update": after("Updated"), "url": BASE + href.group(1),
        })
    return rows

def price_fields(p):
    p = re.sub(r"\s+", " ", p or "").strip()
    m = re.search(r"Price:\s*([A-Z]{3})\s*[^\d]*([\d,]+)", p)
    if m:
        out = {"price": f"{m.group(1)} {m.group(2)}", "currency": m.group(1), "amount": int(m.group(2).replace(",", ""))}
        if re.search(r"reduced", p, re.I): out["status"] = "Price reduced"
        return out
    if re.search(r"deal pending", p, re.I): return {"price": "Deal pending", "status": "Deal pending"}
    if re.search(r"make offer", p, re.I): return {"price": "Make offer"}
    if re.search(r"call|email|request", p, re.I): return {"price": "Upon request"}
    return {"price": p or "Upon request"}

def reg_type(reg):
    if not reg or reg == "-": return "—"
    r = reg.upper()
    if re.match(r"^N-?\d", r): return "N-reg"
    pre = r.split("-")[0]
    if pre in EASA_PREFIX: return "EASA"
    return pre if "-" in r else "—"

def detail_reg(url):
    s = get(url)
    if s is None: return "-"
    t = texts(re.sub(r"<script.*?</script>|<style.*?</style>", "", s, flags=re.S))
    for i, x in enumerate(t):
        if x == "Reg" and i + 1 < len(t) and i >= 2 and t[i - 2] == "S/N":
            return t[i + 1]
    return "-"

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--max-seconds", type=float, default=160)
    ap.add_argument("--regs-only", action="store_true", help="only fetch pending registrations for the last feed")
    ap.add_argument("--gzip-history", action="store_true", help="store the daily snapshot as history/YYYY-MM-DD.json.gz (used in the GitHub repository)")
    a = ap.parse_args()
    t0 = time.time()
    if a.regs_only:
        cache = json.load(open(CACHE)) if os.path.exists(CACHE) else {}
        todo = [r for r in (latest_history() or {"listings": []})["listings"] if r["id"] not in cache]
        for r in todo:
            if time.time() - t0 > a.max_seconds: break
            try: cache[r["id"]] = detail_reg(r["url"])
            except Exception: pass
            time.sleep(DELAY)
        json.dump(cache, open(CACHE + ".tmp", "w")); os.replace(CACHE + ".tmp", CACHE)
        left = sum(1 for r in todo if r["id"] not in cache)
        print(f"regs-only: fetched={len(todo)-left} pending={left}"); sys.exit(2 if left else 0)
    # 1. overview pages
    cards, p, total = [], 1, None
    while True:
        s = get(LIST + ("" if p == 1 else f"/page-{p}"))
        if s is None: break
        got = parse_cards(s)
        m = re.search(r"Showing \d+ - (\d+) of (\d+)", s)
        if m: total = int(m.group(2))
        cards += got
        if not m or int(m.group(1)) >= int(m.group(2)): break
        p += 1; time.sleep(DELAY)
    complete = total is not None
    seen_ids = set(); listings = []; unmapped = collections.Counter()
    for c in cards:
        if c["id"] in seen_ids: continue
        seen_ids.add(c["id"])
        if GONE.search(c["price_raw"]): continue
        typ = TYPE_MAP.get(c["title"])
        if not typ: unmapped[c["title"]] += 1; continue
        row = {"type": typ, "model": c["title"], "yom": c["yom"] or "—", "ttaf": c["ttaf"] or "—",
               "location": c["location"] or "—", "seller": c["seller"] or "—", "serial": c["serial"] or "—",
               "url": c["url"], "source": "AvBuyer", "id": c["id"], "listed_update": c["listed_update"]}
        row.update(price_fields(c["price_raw"]))
        listings.append(row)
    # 2. registrations (cached per listing id)
    cache = json.load(open(CACHE)) if os.path.exists(CACHE) else {}
    pending = [r for r in listings if r["id"] not in cache]
    for r in pending:
        if time.time() - t0 > a.max_seconds: break
        try: cache[r["id"]] = detail_reg(r["url"])
        except Exception: pass
        time.sleep(DELAY)
    json.dump(cache, open(CACHE + ".tmp", "w")); os.replace(CACHE + ".tmp", CACHE)
    left = 0
    for r in listings:
        reg = cache.get(r["id"])
        if reg is None: left += 1
        r["reg"] = reg.upper() if reg and reg != "-" else "—"
        r["reg_type"] = reg_type(reg) if reg else "—"
    # 3. sanity check against the previous feed, then write atomically
    # previous count from the local history (the OneDrive copy may be a cloud-only placeholder)
    prev = 0
    try: prev = (latest_history() or {}).get("count", 0)
    except Exception: prev = 0
    if not complete or (prev and len(listings) < 0.8 * prev):
        print(f"FAILED: complete={complete} listings={len(listings)} previous={prev}; old feed kept"); sys.exit(1)
    now = datetime.datetime.now(datetime.timezone.utc)
    feed = {"updated": now.strftime("%Y-%m-%dT%H:%M:%SZ"), "source": "AvBuyer (avbuyer.com)",
            "count": len(listings), "jets_on_site": total, "registrations_pending": left,
            "unmapped_models": dict(sorted(unmapped.items())), "listings": listings}
    js = ("// Generated by avbuyer_feed.py. Do not edit; it is overwritten daily.\n"
          "window.FG_MARKET_FEED = " + json.dumps(feed, ensure_ascii=False, separators=(",", ":")) + ";\n")
    tmp = a.out + ".tmp"
    open(tmp, "w", encoding="utf-8").write(js); os.replace(tmp, a.out)
    os.makedirs(HIST, exist_ok=True)
    day = now.strftime("%Y-%m-%d")
    if a.gzip_history:
        with gzip.open(os.path.join(HIST, day + ".json.gz"), "wt", encoding="utf-8") as f: json.dump(feed, f, ensure_ascii=False)
    else:
        json.dump(feed, open(os.path.join(HIST, day + ".json"), "w"), ensure_ascii=False)
    print(f"OK listings={len(listings)} jets_on_site={total} unmapped={sum(unmapped.values())} "
          f"reg_pending={left} seconds={time.time()-t0:.0f}")
    sys.exit(2 if left else 0)

if __name__ == "__main__":
    main()
