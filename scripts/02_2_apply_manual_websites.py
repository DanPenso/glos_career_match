"""Apply manually curated employer websites from the user paste."""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from glos_recommender.labels import public_employer_website  # noqa: E402

SEED = ROOT / "data" / "seed" / "companies_seed.csv"
MASTER = ROOT / "app" / "app_data" / "companies_master.csv"

# company_id -> raw note from user (domain or "No active…")
RAW: dict[str, str] = {
    "GLC033": "primadental.com (Trades as Prima Dental Group)",
    "GLC034": "abec.co.uk",
    "GLC035": "aceo.co.uk",
    "GLC036": "allstonespeedyskips.co.uk",
    "GLC037": "anderburyhotels.co.uk",
    "GLC038": "quartzelec.com (Acquired by Quartzelec)",
    "GLC039": "270climbing.com (Operates 270 Climbing Park)",
    "GLC040": "auremcare.com",
    "GLC041": "auremcare.com",
    "GLC042": "bamfordcollection.com",
    "GLC043": "barnwood.co.uk",
    "GLC044": "barworks.co.uk",
    "GLC045": "bence.co.uk (Part of George Bence Group)",
    "GLC046": "benefacttrust.co.uk",
    "GLC047": "berkhampsteadschool.co.uk",
    "GLC048": "No active public website (Private investment/holding company)",
    "GLC049": "summitmedicalgroup.com (Summit Medical Group)",
    "GLC050": "No active public website",
    "GLC051": "brewhouseandkitchen.com",
    "GLC052": "brsk.co.uk",
    "GLC053": "calcot.co (Calcot & Spa)",
    "GLC054": "camargue.uk",
    "GLC055": "capfun.co.uk",
    "GLC056": "castellum.co.uk",
    "GLC057": "No active public website",
    "GLC058": "cbh.org.uk",
    "GLC059": "sandfordparkslido.org.uk",
    "GLC060": "campden.school",
    "GLC061": "cleeveschool.net",
    "GLC062": "commercial.co.uk",
    "GLC063": "coriniumeducationtrust.net",
    "GLC064": "cotswoldlakestrust.org",
    "GLC065": "crippsandco.com (Cripps & Co)",
    "GLC066": "No active public website",
    "GLC067": "dairypartners.co.uk",
    "GLC068": "No active public website",
    "GLC069": "No active public website",
    "GLC070": "earnzplc.com",
    "GLC071": "ecclesiastical.com",
    "GLC072": "ecotricity.co.uk",
    "GLC073": "elmbridgepumps.com",
    "GLC074": "ecovision.co.uk (Previously Ecovision Group)",
    "GLC075": "No active public website",
    "GLC076": "No active public website",
    "GLC077": "deanforestrailway.co.uk",
    "GLC078": "fowa.org.uk",
    "GLC079": "bence.co.uk",
    "GLC080": "gloucester.anglican.org",
    "GLC081": "everymantheatre.org.uk",
    "GLC082": "gloucestershirewildlifetrust.co.uk",
    "GLC083": "hercules-construction.co.uk",
    "GLC084": "hollingsworth-vose.com",
    "GLC085": "howardtenens.com",
    "GLC086": "huntingtonhouse.co.uk",
    "GLC087": "No active public website",
    "GLC088": "innovarenewables.com",
    "GLC089": "innovarenewables.com",
    "GLC090": "insuco.com",
    "GLC091": "jammaccaregroup.co.uk",
    "GLC092": "jgtravelgroup.com (JG Travel Group)",
    "GLC093": "jgtravelgroup.com (JG Travel Group)",
    "GLC094": "jspsafety.com",
    "GLC095": "kubus.com",
    "GLC096": "lastmile-uk.com",
    "GLC097": "No active public website",
    "GLC098": "No active public website",
    "GLC099": "meningitisnow.org",
    "GLC100": "markeygroup.co.uk",
    "GLC101": "etheridgeconstruction.co.uk",
    "GLC102": "nationalstar.org",
    "GLC104": "sheppardhouse.co.uk (Sheppard House)",
    "GLC105": "nov.com (National Oilwell Varco)",
    "GLC106": "oneillandbrennan.com",
    "GLC107": "No active public website",
    "GLC108": "onechurch.uk",
    "GLC109": "thepandmgroup.co.uk",
    "GLC110": "No active public website (Holding company)",
    "GLC111": "No active public website (Holding company)",
    "GLC112": "patesgs.org",
    "GLC113": "pennantplc.com",
    "GLC114": "No active public website (Holding company)",
    "GLC115": "pipehawk.com",
    "GLC116": "No active public website (Holding company)",
    "GLC117": "pooky.com",
    "GLC118": "primadental.com (Prima Dental Group)",
    "GLC119": "procook.co.uk",
    "GLC120": "No active public website",
    "GLC121": "renishaw.com",
    "GLC122": "reputation.com",
    "GLC123": "ridgewaybeg.co.uk",
    "GLC124": "No active public website (Holding company)",
    "GLC125": "rmt.org",
    "GLC126": "sailpoint.com",
}

# User list stopped before GLC127–129; leave those unchanged unless known empty.


def to_https(raw: str) -> str | None:
    text = str(raw or "").strip()
    if not text:
        return None
    if text.lower().startswith("no active"):
        return None
    # Take first token before space / parenthesis
    token = re.split(r"[\s(]", text, maxsplit=1)[0].strip().rstrip(".,;")
    if not token or "." not in token:
        return None
    if token.startswith("http://") or token.startswith("https://"):
        url = token
    else:
        url = "https://www." + token.lstrip("www.")
    # Special: some domains already include www preference — keep simple https://www.
    # For reputation.com corporate site, https://www.reputation.com is fine
    cleaned = public_employer_website(url)
    return cleaned or None


def apply_to(path: Path) -> dict[str, int]:
    df = pd.read_csv(path, dtype=str).fillna("")
    set_url = 0
    cleared = 0
    missing_ids = []
    for cid, raw in RAW.items():
        hit = df["company_id"].astype(str) == cid
        if not hit.any():
            missing_ids.append(cid)
            continue
        url = to_https(raw)
        if url:
            df.loc[hit, "website"] = url
            set_url += int(hit.sum())
        else:
            # Explicitly no public site — keep blank (not CH)
            df.loc[hit, "website"] = ""
            cleared += int(hit.sum())
    df.to_csv(path, index=False)
    return {"set_url": set_url, "cleared": cleared, "missing_ids": missing_ids}


def main() -> None:
    # Sanity: every RAW maps or clears
    bad = []
    for cid, raw in RAW.items():
        if raw.lower().startswith("no active"):
            continue
        if not to_https(raw):
            bad.append((cid, raw))
    if bad:
        raise SystemExit(f"Could not parse URLs: {bad}")

    s = apply_to(SEED)
    m = apply_to(MASTER)
    print("seed:", {k: v for k, v in s.items() if k != "missing_ids"}, "missing", s["missing_ids"])
    print("master:", {k: v for k, v in m.items() if k != "missing_ids"}, "missing", m["missing_ids"])

    seed = pd.read_csv(SEED, dtype=str).fillna("")
    with_site = seed["website"].map(lambda u: bool(public_employer_website(u))).sum()
    without = len(seed) - with_site
    print(f"seed now: {with_site} with public website, {without} without")

    # Spot-check a few
    for cid in ("GLC033", "GLC103", "GLC048", "GLC121", "GLC059"):
        row = seed.loc[seed["company_id"] == cid, ["name", "website"]]
        print(row.to_string(index=False))


if __name__ == "__main__":
    main()
