# Data sources and attribution

One row per source used in a task (docs/task_engines.md, "Data series and licences").
Fill it in when a real series goes into `series/data/`.

| Source | URL | Licence | Retrieved | Changes made | Series ids |
|---|---|---|---|---|---|
| Synthetic (own) | - | own work | - | generated from parameters in `series/catalog.yaml` | synth_company_d1, synth_pl10y_d3 |
| GUS, Miesięczne wskaźniki cen towarów i usług konsumpcyjnych od 1982 roku | https://stat.gov.pl/obszary-tematyczne/ceny-handel/wskazniki-cen/wskazniki-cen-towarow-i-uslug-konsumpcyjnych-pot-inflacja-/miesieczne-wskazniki-cen-towarow-i-uslug-konsumpcyjnych-od-1982-roku | stat.gov.pl/copyright: reuse with the source given (checked 2026-11-21) | 2026-11-21 | table "Analogiczny miesiąc poprzedniego roku = 100" minus 100 = % y/y; final values; 2019-01 to 2025-12 | gus_cpi_pl_m |
| NBP, stopy procentowe NBP (archive XML) | https://static.nbp.pl/dane/stopy/stopy_procentowe_archiwum.xml | NBP website terms: "Source: NBP, www.nbp.pl" (checked 2026-11-21) | 2026-11-21 | reference rate in force on the last day of each month, from the effective dates; 2019-01 to 2025-12 | nbp_ref_rate_m |
| OECD, Financial market (DSD_STES@DF_FINMARK), share prices Poland, index 2015 = 100 | https://data-explorer.oecd.org/ (SDMX API, POL.M.SHARE.IX) | CC BY 4.0, OECD default (checked 2026-11-21) | 2026-11-21 | none (monthly average price index, no dividends); 2005-01 to 2025-12 | oecd_share_prices_pl_m |
