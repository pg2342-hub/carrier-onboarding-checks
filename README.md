# Carrier onboarding checks on public FMCSA data

Demo page: https://pranavgudise.dev/carrier-onboarding-checks/

A small, runnable version of the checks in a pilot plan I wrote (a separate PDF, not in this repo). Before a carrier is keyed into a broker's TMS, it checks the carrier against FMCSA's public records and the broker's own rules, and sorts each one into **ready for TMS entry**, **exception queue** (a person looks first), or **do not set up**. Every check writes the fields it read to a log, so each decision can be traced.

The rule set is M2 Logistics' public carrier requirements (authority active at least six consecutive months, $1,000,000 auto liability, $100,000 cargo, certificate sent by the insurance agent). Safety-rating handling is a common broker rule, not on M2's page. Nothing here comes from M2's or Sola's systems.

## Run it

```
python3 run_checks.py                  # offline, from the snapshot captured 2026-11-18
python3 run_checks.py --naive          # same, with first-pass authority-age logic
python3 run_checks.py --source live    # query data.transportation.gov now (no key needed)
```

Python 3.9+ and the standard library only. Reports go to `reports/`.

## What is in it

| Path | What it is |
|---|---|
| `checks/fmcsa.py` | Reads FMCSA's open data (Company Census, Motus Carrier, Motus AuthHist, Motus RevokeSuspend, Out of Service Orders, and the legacy AuthHist archive), live or from the snapshot |
| `checks/rules.py` | Eight checks: identity, contact match, authority active, authority age, recent suspension notices, out-of-service orders, safety rating, insurance |
| `rules/m2_logistics.json` | The broker's rules, kept out of the code so a second broker is a new file |
| `data/fmcsa_snapshot.json` | Public FMCSA records for 8 real carriers, captured 2026-11-18 |
| `data/packets.csv` | 10 test packets: what a carrier submits (name, phone, email, certificate amounts) and the expected decision |
| `scripts/build_demo.py` | Rebuilds the demo page (`docs/index.html`) from the checks' own output |
| `reports/` | `report_checks.md`, `run_log_checks.jsonl` (every check and its evidence), `tms_ready.json` (carriers a person can approve for entry) |

The carriers and their FMCSA records are real public data as of 2026-11-18 (email addresses masked to their domain). The packet fields are constructed. Cases 4 and 5 are deliberately altered packets (a phone and email that do not match FMCSA; a short cargo amount on a certificate the carrier sent itself) and say nothing about those carriers. A decision here reflects only what FMCSA's files showed on that date against one broker's rules, not a judgment of any carrier.

## Results

| Logic | Matches the expected decision | Wrong calls |
|---|---|---|
| Full checks | 10 of 10 | none |
| Naive authority age | 7 of 10 | refuses two long-standing carriers as new (cases 1, 2, and 5) |

The 10 cases are built from 8 real carriers; cases 4 and 5 reuse the carriers from cases 3 and 2.

## The bug worth knowing about

FMCSA moved operating-authority data to its new registration system (MOTUS) in 2026, and the legacy files stopped updating on 2026-05-14. In the live Motus AuthHist file, thousands of long-standing authorities show an "Administrative status adjustment" to Inactive in June 2026 followed by a fresh grant, and some legacy authorities carry only a `GRANTED` row dated 2026-05-28 (the migration). Werner (USDOT 53467, authority granted 1992) shows Inactive on 2026-06-09 and Granted on 2026-06-16; Prosperity Trucking (USDOT 131895) has only the 2026-05-28 row.

A check that reads the latest grant date would call both carriers about five months old and refuse them under a six-month rule. `rules.py` treats those migration rows as noise, restarts the clock only on a real break (a revocation or suspension), and falls back to the legacy archive when the live file only has migration rows. When the legacy archive has the grant but no served date (Prosperity), the records cannot settle the grant date, so the carrier goes to a person instead of being refused or passed.

## Other choices

- **Cargo is checked on the certificate only.** FMCSA does not hold cargo filings for general freight, so the certificate (sent by the agent) is the only source.
- **Liability below the broker's rule but at the federal minimum goes to a person** when the certificate claims the higher limit, so the agent can confirm whether the extra coverage is real.
- **A contact mismatch never rejects.** It routes the carrier to a person who calls back on the number FMCSA has on file. Free-mail domains (gmail and similar) prove nothing, so for those only the phone counts.
- **A suspension notice in the last 12 months goes to a person** even if the authority is active again, because it usually means an insurance lapse.

## Limits

- Ten cases, written by hand. A real version would replay the broker's last few months of setups and compare against what staff decided.
- The rules about migration rows were found on a handful of carriers; a replay over a broker's full carrier list is the real test.
- It does not read the certificate itself, the W-9, or the broker's onboarding platform; in the pilot those come from the packet the bot collects.
- Live mode depends on the DOT data portal's daily refresh; a carrier's change today may not show until tomorrow.
