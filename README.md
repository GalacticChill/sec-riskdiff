# SEC Risk-Factor Diff

A static, keyless tool that shows **year-over-year changes to the "Item 1A. Risk
Factors" section** of a company's 10-K — the sentences added and removed, plus the
*emerging language* (new or intensified terms) that signals what a company is newly
worried about.

Live: https://galacticchill.github.io/sec-riskdiff/

## How it works
- `build.py` fetches each company's two most recent 10-Ks from **SEC EDGAR**, extracts
  the Item 1A section (anchored on the "Item 1B. Unresolved Staff Comments" boundary),
  and bundles the plain text into `index.html`.
- The browser computes a sentence-level **LCS diff** between the two years and surfaces
  emerging unigrams/bigrams — all client-side, no key, no network calls.

## Refreshing the data
EDGAR requires a descriptive User-Agent with a contact email. Set your own, then build:

```bash
export SEC_CONTACT="Your Name your-email@example.com"
python3 build.py
```

Educational tool — not investment advice. Filing text © the respective registrants / SEC EDGAR (public).
