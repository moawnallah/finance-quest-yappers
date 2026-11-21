"""Convert the three downloaded files into series.csv rows. Run once by hand; no calls at runtime.

    python series/import_demo_series.py <raw_dir> series/series.csv

<raw_dir> holds (downloaded 2026-11-21, not committed):
    gus/cpi.csv     GUS "Miesięczne wskaźniki cen ... od 1982 roku", CSV (cp1250), from
                    https://stat.gov.pl/obszary-tematyczne/ceny-handel/wskazniki-cen/wskazniki-cen-towarow-i-uslug-konsumpcyjnych-pot-inflacja-/miesieczne-wskazniki-cen-towarow-i-uslug-konsumpcyjnych-od-1982-roku
    nbp/rates.xml   https://static.nbp.pl/dane/stopy/stopy_procentowe_archiwum.xml
    oecd/share.csv  https://sdmx.oecd.org/public/rest/data/OECD.SDD.STES,DSD_STES@DF_FINMARK,/POL.M.SHARE.IX.....?startPeriod=2005-01&dimensionAtObservation=AllDimensions
                    (header Accept: application/vnd.sdmx.data+csv)
Note: this rewrites the whole table; add other series to the script before running it again.
"""
import sys, csv, datetime as dt, xml.etree.ElementTree as ET
d, out = sys.argv[1], sys.argv[2]

rows = []
# GUS: same month previous year = 100 -> % y/y (minus 100), 2019-01..2025-12
for line in open(f"{d}/gus/cpi.csv", encoding="cp1250").read().splitlines()[1:]:
    f = line.split(";")
    if len(f) > 5 and f[1] == "Polska" and f[2] == "Analogiczny miesiąc poprzedniego roku = 100" and f[5]:
        y, m = int(f[3]), int(f[4])
        if 2019 <= y <= 2025:
            rows.append(("gus_cpi_pl_m", dt.date(y, m, 1), round(float(f[5].replace(",", ".")) - 100, 1), "GUS", "reuse with source (stat.gov.pl/copyright)"))
# NBP: reference rate in force on the last day of each month, 2019-01..2025-12
root = ET.parse(f"{d}/nbp/rates.xml").getroot()
changes = sorted((dt.date.fromisoformat(p.get("obowiazuje_od")), float(q.get("oprocentowanie").replace(",", ".")))
                 for p in root.iter("pozycje") for q in p.iter("pozycja") if q.get("id") == "ref")
for y in range(2019, 2026):
    for m in range(1, 13):
        end = (dt.date(y + (m == 12), m % 12 + 1, 1) - dt.timedelta(days=1))
        rate = [r for day, r in changes if day <= end][-1]
        rows.append(("nbp_ref_rate_m", dt.date(y, m, 1), rate, "NBP", "Source: NBP, www.nbp.pl"))
# OECD: share price index Poland, 2015 = 100, 2005-01..2025-12
for r in csv.DictReader(open(f"{d}/oecd/share.csv", encoding="utf-8", newline="")):
    y, m = map(int, r["TIME_PERIOD"].split("-"))
    if r["REF_AREA"] == "POL" and r["MEASURE"] == "SHARE" and r["UNIT_MEASURE"] == "IX" and r["FREQ"] == "M" and 2005 <= y <= 2025:
        rows.append(("oecd_share_prices_pl_m", dt.date(y, m, 1), round(float(r["OBS_VALUE"]), 4), "OECD", "CC BY 4.0"))
rows.sort(key=lambda r: (r[0], r[1]))
with open(out, "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f, lineterminator="\n"); w.writerow(["series_id", "date", "value", "source", "licence"])
    for r in rows: w.writerow([r[0], r[1].isoformat(), r[2], r[3], r[4]])
from collections import Counter; print(Counter(r[0] for r in rows))
