#!/usr/bin/env python3
"""Build step for the SEC Risk-Factor Diff tool.

Fetches the two most recent 10-K filings for a curated set of companies from
SEC EDGAR, extracts the 'Item 1A. Risk Factors' section from each, and bundles
the plain text into a single static index.html. The year-over-year diff runs
client-side in the browser.

EDGAR requires a descriptive User-Agent with a contact email (set below). That
contact is sent only to SEC at build time; it is NOT written into index.html.
Re-run to refresh: `python3 build.py`.
"""
import hashlib
import json
import os
import re
import sys
import time
import urllib.request

CACHE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".cache")

# EDGAR fair-access requires a descriptive User-Agent with a contact email.
# Set your own before running:  export SEC_CONTACT="Your Name your-email@example.com"
# It is sent only to SEC at fetch time and is never written into index.html.
UA = os.environ.get("SEC_CONTACT") or "example-research contact@example.com"

# ticker -> (CIK, display name, sector)
COMPANIES = [
    ("AAPL", 320193, "Apple", "Technology"),
    ("NVDA", 1045810, "NVIDIA", "Semiconductors"),
    ("GOOGL", 1652044, "Alphabet", "Communication Services"),
    ("AMZN", 1018724, "Amazon", "Consumer / Cloud"),
    ("TSLA", 1318605, "Tesla", "Automotive"),
    ("KO", 21344, "Coca-Cola", "Consumer Staples"),
    ("WMT", 104169, "Walmart", "Retail"),
    ("XOM", 34088, "ExxonMobil", "Energy"),
    ("DIS", 1744489, "Walt Disney", "Media"),
    ("JNJ", 200406, "Johnson & Johnson", "Healthcare"),
]


def get(url, tries=4, cache=True):
    cp = os.path.join(CACHE, hashlib.sha256(url.encode()).hexdigest()[:20])
    if cache and os.path.exists(cp) and os.path.getsize(cp) > 100:
        with open(cp, "rb") as fh:
            return fh.read()
    last = None
    for _ in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=45) as r:
                data = r.read()
            if cache:
                os.makedirs(CACHE, exist_ok=True)
                with open(cp, "wb") as fh:
                    fh.write(data)
            return data
        except Exception as e:
            last = e
            time.sleep(1.0)
    raise last


def to_text(html):
    t = re.sub(r"(?is)<(script|style).*?</\1>", " ", html)
    t = re.sub(r"(?s)<[^>]+>", " ", t)
    for a, b in [("&#160;", " "), ("&nbsp;", " "), ("&amp;", "&"), ("&#8217;", "'"),
                 ("&#8220;", '"'), ("&#8221;", '"'), ("&#39;", "'"), ("&rsquo;", "'"),
                 ("&ldquo;", '"'), ("&rdquo;", '"'), ("&#147;", '"'), ("&#148;", '"'),
                 ("&#146;", "'"), ("&#151;", "-"), ("&#8212;", "-")]:
        t = t.replace(a, b)
    t = re.sub(r"\s+", " ", t).strip()
    t = re.sub(r"Table of Contents", " ", t, flags=re.I)  # navigation boilerplate
    return re.sub(r"\s+", " ", t).strip()


def _anchor(txt):
    ends = (list(re.finditer(r"item\s*1b\.?\s*unresolved\s*staff\s*comments", txt, re.I))
            or list(re.finditer(r"item\s*1b[\.\s]", txt, re.I))
            or list(re.finditer(r"item\s*2\.?\s*propert", txt, re.I)))
    if not ends:
        return ""
    end = ends[-1].start()
    starts = [m.end() for m in re.finditer(r"item\s*1a\.?\s*risk\s*factors", txt[:end], re.I)]
    return txt[starts[-1]:end].strip() if starts else ""


def _longest(txt):
    starts = [m.end() for m in re.finditer(r"item\s*1a\.?\s*risk\s*factors", txt, re.I)]
    best = ""
    for s in starts:
        rest = txt[s:]
        m = (re.search(r"item\s*1b\.?\s*unresolved", rest, re.I) or re.search(r"item\s*1b[\.\s]", rest, re.I)
             or re.search(r"item\s*2\.?\s*propert", rest, re.I))
        cand = rest[:m.start()] if m else ""
        if len(cand) > len(best):
            best = cand
    return best.strip()


def extract_rf(txt):
    s = _anchor(txt)
    return s if len(s.split()) >= 1500 else _longest(txt)


def latest_10ks(cik, k=2):
    sub = json.loads(get("https://data.sec.gov/submissions/CIK%010d.json" % cik))
    f = sub["filings"]["recent"]
    out = []
    for i in range(len(f["form"])):
        if f["form"][i] == "10-K":
            out.append((f["filingDate"][i], f["accessionNumber"][i].replace("-", ""), f["primaryDocument"][i]))
        if len(out) >= k:
            break
    return sub["name"], out


def main():
    companies = []
    for tk, cik, name, sector in COMPANIES:
        try:
            _, filings = latest_10ks(cik, 2)
            years = []
            for date, accn, doc in filings:
                url = "https://www.sec.gov/Archives/edgar/data/%d/%s/%s" % (cik, accn, doc)
                text = extract_rf(to_text(get(url).decode("utf-8", "replace")))
                w = len(text.split())
                if w < 1500:
                    sys.stderr.write("  %s %s: weak extract (%d words), skipping year\n" % (tk, date[:4], w))
                    continue
                years.append({"year": date[:4], "date": date, "words": w, "text": text})
                time.sleep(0.3)
            if len(years) >= 2:
                companies.append({"ticker": tk, "name": name, "sector": sector, "years": years})
                sys.stderr.write("%-6s %s  %s\n" % (tk, name, " ".join("%s:%dw" % (y["year"], y["words"]) for y in years)))
            else:
                sys.stderr.write("%-6s SKIP (need 2 clean years)\n" % tk)
        except Exception as e:
            sys.stderr.write("%-6s ERROR %s\n" % (tk, e))
        time.sleep(0.3)

    bundle = {"built": time.strftime("%Y-%m-%d"), "companies": companies}
    payload = json.dumps(bundle, separators=(",", ":"), ensure_ascii=False)
    with open("index.template.html", encoding="utf-8") as f:
        template = f.read()
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(template.replace("/*__DATA__*/", payload))
    sys.stderr.write("wrote index.html (%d KB) — %d companies\n" % (len(payload) // 1024, len(companies)))


if __name__ == "__main__":
    main()
