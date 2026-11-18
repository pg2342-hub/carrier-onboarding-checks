#!/usr/bin/env python3
"""Run carrier onboarding checks on a batch of carrier packets.

  python3 run_checks.py                         # offline, from the captured snapshot
  python3 run_checks.py --source live           # query data.transportation.gov now
  python3 run_checks.py --naive                 # first-pass authority-age logic, for comparison

Writes reports/report_checks.md (one line per carrier plus the reasons), reports/run_log_checks.jsonl
(every check with the fields it read), and reports/tms_ready.json (the carriers a
person can approve for entry into the TMS).
"""
import argparse
import csv
import json
import os
import sys
from datetime import date, datetime

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from checks.fmcsa import LiveSource, SnapshotSource  # noqa: E402
from checks.rules import run_all  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--packets", default=os.path.join(HERE, "data", "packets.csv"))
    ap.add_argument("--rules", default=os.path.join(HERE, "rules", "m2_logistics.json"))
    ap.add_argument("--source", choices=["snapshot", "live"], default="snapshot")
    ap.add_argument("--snapshot", default=os.path.join(HERE, "data", "fmcsa_snapshot.json"))
    ap.add_argument("--today", help="YYYY-MM-DD (default: snapshot date, or today when live)")
    ap.add_argument("--naive", action="store_true", help="use first-pass authority-age logic")
    ap.add_argument("--out", default=os.path.join(HERE, "reports"))
    a = ap.parse_args()

    rules = json.load(open(a.rules))["rules"]
    src = LiveSource() if a.source == "live" else SnapshotSource(a.snapshot)
    if a.today:
        today = datetime.strptime(a.today, "%Y-%m-%d").date()
    elif a.source == "snapshot":
        today = datetime.strptime(src.captured_on, "%Y-%m-%d").date()
    else:
        today = date.today()

    packets = list(csv.DictReader(open(a.packets)))
    os.makedirs(a.out, exist_ok=True)
    tag = "naive" if a.naive else "checks"
    log = open(os.path.join(a.out, f"run_log_{tag}.jsonl"), "w")
    rows, ready, agree = [], [], 0
    for p in packets:
        decision, results, census, auth = run_all(p, src, rules, today, naive=a.naive)
        expected = p.get("expected", "")
        ok = (decision == expected) if expected else None
        agree += bool(ok)
        rows.append((p, decision, results, ok))
        for r in results:
            log.write(json.dumps({"case": p["case"], "dot": p["dot"], "check": r.check, "status": r.status,
                                  "detail": r.detail, "evidence": r.evidence, "source": src.name,
                                  "as_of": today.isoformat()}) + "\n")
        if decision == "READY FOR TMS ENTRY":
            ready.append({"usdot": p["dot"], "docket": auth.get("docket_number"),
                          "legal_name": census.get("legal_name"), "dba_name": census.get("dba_name"),
                          "phone": census.get("phone"), "email": census.get("email_address"),
                          "address": " ".join(filter(None, [census.get("phy_street"), census.get("phy_city"),
                                                            census.get("phy_state"), census.get("phy_zip")])),
                          "auto_liability_on_file": auth.get("bipd_file"),
                          "checked_on": today.isoformat(), "status": "pending approval"})
    log.close()
    if not a.naive:
        json.dump(ready, open(os.path.join(a.out, "tms_ready.json"), "w"), indent=2)

    lines = [f"# Carrier check report ({'naive authority logic' if a.naive else 'full checks'})", "",
             f"Source: {src.name}" + (f" (captured {src.captured_on})" if a.source == "snapshot" else "") +
             f" · as of {today} · rules: {os.path.basename(a.rules)}", "",
             "| Case | USDOT | Decision | Expected | Reasons |", "|---|---|---|---|---|"]
    for p, decision, results, ok in rows:
        reasons = "; ".join(f"{r.check}: {r.detail}" for r in results if r.status != "PASS") or "all checks clean"
        mark = "" if ok is None else (" ✓" if ok else " ✗")
        lines.append(f"| {p['case']} | {p['dot']} | {decision} | {p.get('expected', '')}{mark} | {reasons} |")
    n = len(rows)
    lines += ["", f"Matches the expected decision on {agree} of {n} cases.", ""]
    if a.naive:
        lines.append("Naive logic reads the most recent grant in the Motus AuthHist file, so carriers whose "
                     "authority was re-stamped during the 2026 MOTUS migration look new.")
    path = os.path.join(a.out, f"report_{tag}.md")
    open(path, "w").write("\n".join(lines) + "\n")
    print("\n".join(lines))
    return 0 if agree == n else 1


if __name__ == "__main__":
    sys.exit(main())
