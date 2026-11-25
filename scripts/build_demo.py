#!/usr/bin/env python3
"""Build docs/index.html, the demo page, from the checks' own output on the snapshot.

    python3 scripts/build_demo.py

Runs the full checks and the naive authority logic on data/packets.csv against
data/fmcsa_snapshot.json, then writes the page and runs scripts/demo_chrome.py on it.
"""
import csv
import html
import json
import os
import subprocess
import sys
from datetime import date, datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from checks.fmcsa import SnapshotSource  # noqa: E402
from checks.rules import run_all  # noqa: E402

REPO = "carrier-onboarding-checks"
SHORT = {"READY FOR TMS ENTRY": "Ready for TMS entry", "EXCEPTION QUEUE": "Exception queue",
         "DO NOT SET UP": "Do not set up"}
TIER = {"READY FOR TMS ENTRY": "ready", "EXCEPTION QUEUE": "queue", "DO NOT SET UP": "stop"}
CHECK_NAME = {"identity": "Identity", "contact": "Contact match", "authority_active": "Authority active",
              "authority_age": "Authority age", "notices": "Suspension notices", "out_of_service": "Out of service",
              "safety": "Safety rating", "insurance": "Insurance"}
NAMES = {"53467": "Werner Enterprises", "131895": "Prosperity Trucking", "100002": "Hribar Bros",
         "3436760": "West Twin Brothers", "4144337": "Amendment Hauling", "6951245": "Trash Panda Junk Removal",
         "1006607": "Timewise Trucking", "4499661": "Timagin Trucking"}

e = html.escape


def clean(s):
    return str(s).replace("—", ",").replace("–", "-")


def run(naive):
    rules = json.load(open(os.path.join(ROOT, "rules", "m2_logistics.json")))["rules"]
    src = SnapshotSource(os.path.join(ROOT, "data", "fmcsa_snapshot.json"))
    today = datetime.strptime(src.captured_on, "%Y-%m-%d").date()
    out = []
    for p in csv.DictReader(open(os.path.join(ROOT, "data", "packets.csv"))):
        decision, results, _, _ = run_all(p, src, rules, today, naive=naive)
        out.append((p, decision, results))
    return out, today, rules


def square(p, decision):
    """pass, fail, or crit. Critical = a carrier that should be stopped or reviewed is marked ready."""
    if decision == p["expected"]:
        return "pass"
    if decision == "READY FOR TMS ENTRY":
        return "crit"
    return "fail"


def verdict_row(label, sub, rows):
    kinds = [square(p, d) for p, d, _ in rows]
    passed, crit = kinds.count("pass"), kinds.count("crit")
    wrong = len(kinds) - passed
    cells = "".join(
        f'<a class="cell {k}" href="#case-{p["case"]}" data-case="{p["case"]}" '
        f'aria-label="{e(label)} case {p["case"]}: {"matches the expected call" if k == "pass" else "wrong call"}"></a>'
        for k, (p, _, _) in zip(kinds, rows))
    go = passed == len(kinds) and crit == 0
    note = "0 wrong calls" if not wrong else f"{wrong} wrong, {crit} critical"
    return (f'<div class="vrow"><div class="vwho"><b>{e(label)}</b><span>{e(sub)}</span></div>'
            f'<div class="strip s10" role="group" aria-label="{e(label)}: every case">{cells}</div>'
            f'<div class="vscore"><b>{passed}</b><span>of {len(kinds)} correct<br>{note}</span></div>'
            f'<span class="gate {"go" if go else "nogo"}">{"GO" if go else "NO-GO"}</span></div>'), passed


def reasons(results):
    bad = [r for r in results if r.status != "PASS"]
    if not bad:
        return "All eight checks clean"
    return "; ".join(f"{CHECK_NAME.get(r.check, r.check)}: {clean(r.detail)}" for r in bad)


def evidence(results):
    rows = []
    for r in results:
        ev = ", ".join(f"{a}.{b} = {c}" for a, b, c in r.evidence) or "no fields"
        rows.append(f'<tr><td>{e(CHECK_NAME.get(r.check, r.check))}</td><td><span class="st st-{r.status.lower()}">'
                    f'{r.status}</span></td><td class="evd">{e(clean(r.detail))}<div class="flds">{e(ev)}</div></td></tr>')
    return '<table class="evt"><thead><tr><th>Check</th><th>Status</th><th>Detail and fields read</th></tr></thead><tbody>' \
        + "".join(rows) + "</tbody></table>"


def badge(decision):
    return f'<span class="dec dec-{TIER[decision]}">{SHORT[decision]}</span>'


# ---------- signature visual: 2026 authority events against the six-month line ----------
Y0, Y1 = date(2026, 1, 1), date(2026, 12, 1)


def pct(d):
    return round(100 * (d - Y0).days / (Y1 - Y0).days, 2)


def timeline(today):
    line = date(today.year, today.month - 6, today.day)  # six months before the as-of date
    # (date, label, kind): kind mig = MOTUS migration row, grant = real grant, brk = real break
    rows = [
        ("Werner Enterprises", "Original grant 1992-04-24",
         [(date(2026, 6, 9), "Jun 9, admin adjustment to Inactive", "mig"), (date(2026, 6, 16), "Jun 16, re-grant", "mig")],
         "Naive: 5 months old, refused", "Full checks: migration rows ignored, active since 1992, ready"),
        ("Prosperity Trucking", "Legacy grant on file, no date",
         [(date(2026, 5, 28), "May 28, migration GRANTED stamp", "mig")],
         "Naive: 5 months old, refused", "Full checks: grant date unknown, a person confirms it"),
        ("Timewise Trucking", "Authority on file since 2008",
         [(date(2026, 8, 27), "Aug 27, voluntary suspension", "brk"), (date(2026, 9, 2), "Sep 2, reinstated", "grant")],
         "Naive: 2 months old, refused", "Full checks: a real break restarts the clock, refused"),
        ("Trash Panda Junk Removal", "New authority",
         [(date(2026, 11, 17), "Nov 17, granted", "grant")],
         "Naive: 0 months old, refused", "Full checks: 0 months old, refused"),
    ]
    months = "".join(
        f'<span style="left:{pct(date(2026, m, 1))}%">{date(2026, m, 1).strftime("%b")}</span>' for m in range(1, 13))
    out = [f'<div class="tl" role="img" aria-label="Authority events in 2026 for four carriers, against the six-month line at {line}">',
           f'<div class="tl-axis" aria-hidden="true">{months}</div>']
    for name, orig, evs, naive, full in rows:
        marks = "".join(f'<i class="mk mk-{k}" style="left:{pct(d)}%" title="{e(t)}"></i>' for d, t, k in evs)
        evtext = "; ".join(t for _, t, _ in evs)
        out.append(
            f'<div class="tl-row"><div class="tl-name"><b>{e(name)}</b> <span>{e(orig)}</span></div>'
            f'<div class="tl-track"><span class="tl-young" style="left:{pct(line)}%;width:{pct(today) - pct(line)}%"></span>'
            f'<span class="tl-asof" style="left:{pct(today)}%"></span>{marks}</div>'
            f'<div class="tl-ev">{e(evtext)}</div>'
            f'<div class="tl-calls"><span>{e(naive)}</span><span class="ok">{e(full)}</span></div></div>')
    out.append('</div><div class="tl-key"><span><i class="mk mk-mig"></i>Migration row (not a real change)</span>'
               '<span><i class="mk mk-grant"></i>Real grant or reinstatement</span>'
               '<span><i class="mk mk-brk"></i>Real break in authority</span>'
               f'<span><i class="key-young"></i>Under six months old on {today} (the broker refuses these)</span></div>')
    return "\n".join(out)


def build():
    full, today, rules = run(False)
    naive, _, _ = run(True)
    n = len(full)
    vfull, pfull = verdict_row("Full checks", "Ignores MOTUS migration rows, reads the legacy archive when needed", full)
    vnaive, pnaive = verdict_row("Naive authority age", "Reads the latest grant date in the live file", naive)
    counts = {t: sum(1 for _, d, _ in full if d == t) for t in SHORT}

    trs = []
    for (p, d, res), (_, dn, _) in zip(full, naive):
        name = NAMES.get(p["dot"], p["legal_name"])
        nk = "ok" if dn == p["expected"] else "bad"
        trs.append(
            f'<tr id="case-{p["case"]}" data-tier="{TIER[d]}"><td class="n">{p["case"]}</td>'
            f'<td class="tx"><b>{e(name)}</b> <span class="n">USDOT {p["dot"]}</span>'
            f'<div class="ch">{e(clean(p["what_it_tests"]))}</div></td>'
            f'<td>{badge(p["expected"])}</td>'
            f'<td>{badge(d)}<div class="why">{e(reasons(res))}</div>'
            f'<details><summary>Fields read</summary>{evidence(res)}</details></td>'
            f'<td class="v {nk}">{"Same call" if nk == "ok" else "Wrong: " + SHORT[dn]}</td></tr>')

    page = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Carrier onboarding checks</title>
<meta name="description" content="Checks new carriers against FMCSA public records and a broker's rules before TMS entry. Full checks match the expected call on {pfull} of {n} cases; naive authority logic gets {pnaive} of {n} because of 2026 MOTUS migration rows.">
<style>
{STARTER_CSS}
/* ---- page-specific rules ---- */
.strip.s10{{grid-template-columns:repeat(10,minmax(0,1fr));max-width:420px;gap:6px}}
.dec{{display:inline-block;font:500 12px/1.2 var(--mono);padding:5px 9px;border-radius:999px;white-space:nowrap}}
.dec-ready{{background:var(--green-wash);color:var(--green)}}
.dec-queue{{border:1.5px dashed var(--ink);color:var(--ink);padding:4px 8px}}
.dec-stop{{background:var(--ink);color:var(--paper)}}
.why{{max-width:340px}}
#cases td{{vertical-align:top}}
#cases details{{margin-top:8px;font-size:13px}}
#cases summary{{cursor:pointer;color:var(--green)}}
.evt{{border-collapse:collapse;margin-top:8px;font-size:12.5px;min-width:440px}}
.evt th,.evt td{{text-align:left;padding:5px 8px 5px 0;border-bottom:1px solid var(--rule-soft);vertical-align:top}}
.evt th{{font-weight:500;color:var(--ink-2)}}
.flds{{font:400 11.5px/1.45 var(--mono);color:var(--ink-2);margin-top:2px;word-break:break-word}}
.st{{font:500 11px/1 var(--mono);padding:3px 6px;border-radius:999px;border:1px solid var(--rule)}}
.st-pass{{color:var(--green)}}.st-review{{border:1.5px dashed var(--ink)}}.st-reject{{background:var(--ink);color:var(--paper);border-color:var(--ink)}}
.v.bad{{max-width:none}}
.v.bad:not(.crit)::before{{content:"";display:inline-block;width:9px;height:9px;border:1.5px solid var(--ink);border-radius:2px;margin-right:6px;vertical-align:1px}}
.tl{{border:1px solid var(--rule);border-radius:16px;background:#fbfaf6;padding:18px 22px 8px}}
.tl-axis{{position:relative;height:18px;margin-left:0;font:400 11px/1 var(--mono);color:var(--ink-2)}}
.tl-axis span{{position:absolute;top:0;transform:translateX(-2px)}}
.tl-row{{padding:14px 0;border-top:1px solid var(--rule-soft)}}
.tl-row:first-of-type{{border-top:0}}
.tl-name b{{font:400 18px/1.2 var(--serif)}}
.tl-name span{{color:var(--ink-2);font-size:13px;margin-left:6px}}
.tl-track{{position:relative;height:22px;margin:10px 0 6px;border-bottom:1px solid var(--rule)}}
.tl-young{{position:absolute;top:0;bottom:0;background:repeating-linear-gradient(135deg,var(--green-wash) 0 6px,transparent 6px 10px)}}
.tl-asof{{position:absolute;top:-4px;bottom:-4px;width:1.5px;background:var(--ink)}}
.mk{{position:absolute;top:50%;width:13px;height:13px;margin:-6.5px 0 0 -6.5px;border-radius:50%;display:block}}
.mk-mig{{background:var(--paper);border:2px dashed var(--ink);border-radius:3px}}
.mk-grant{{background:var(--green)}}
.mk-brk{{background:var(--ink)}}
.tl-ev{{font-size:13px;color:var(--ink-2)}}
.tl-calls{{display:flex;flex-wrap:wrap;gap:4px 18px;font-size:14px;margin-top:4px}}
.tl-calls .ok{{color:var(--green);font-weight:500}}
.tl-key{{display:flex;flex-wrap:wrap;gap:6px 20px;font-size:13px;color:var(--ink-2);margin-top:12px}}
.tl-key span{{display:inline-flex;align-items:center;gap:8px}}
.tl-key .mk{{position:static;margin:0}}
.key-young{{display:inline-block;width:22px;height:13px;background:repeating-linear-gradient(135deg,var(--green-wash) 0 6px,transparent 6px 10px);border:1px solid var(--rule)}}
.sum{{display:flex;flex-wrap:wrap;gap:8px 18px;padding:14px 24px;border-top:1px solid var(--rule);font-size:14px;color:var(--ink-2)}}
.sum span{{display:inline-flex;align-items:center;gap:8px}}
@media (max-width:640px){{.tl{{padding:14px 14px 6px}}.tl-axis span:nth-child(even){{display:none}}.sum{{padding:12px 18px}}}}
</style></head><body><main>

<div class="head">
<h1>Carrier onboarding checks</h1>
<p class="lead">Before a freight broker keys a new carrier into its TMS, this script checks the carrier against FMCSA's public records and the broker's carrier rules, then sorts it into ready for TMS entry, the exception queue, or do not set up. Every check logs the fields it read.</p>
</div>

<section class="verdict" aria-labelledby="verdict-h">
  <div class="vhead"><h2 id="verdict-h">Same {n} carrier packets, same broker rules</h2><p>Gate: <b>every call matches the expected decision</b></p></div>
  {vfull}
  {vnaive}
  <div class="sum"><span>Full checks sorted the {n} packets into</span><span>{badge("READY FOR TMS ENTRY")} {counts["READY FOR TMS ENTRY"]}</span><span>{badge("EXCEPTION QUEUE")} {counts["EXCEPTION QUEUE"]}</span><span>{badge("DO NOT SET UP")} {counts["DO NOT SET UP"]}</span></div>
  <div class="legend"><span><i class="pass"></i>Correct call</span><span><i class="fail"></i>Wrong call</span><span><i class="crit"></i>Critical: a carrier that should be stopped is marked ready</span><span>Each square is one packet. Select one to read it.</span></div>
</section>

<div class="layout">
<div class="content">
  <h2 id="why">Why it matters</h2>
  <p class="point">FMCSA moved operating-authority records to its new registration system (MOTUS) in 2026. In the live file, many long-standing carriers now show a <b>2026 grant date</b>, so a check that reads the latest grant calls them a few months old and refuses them under a six-month rule. The full checks treat those migration rows as noise, restart the clock only on a real break, and send a carrier to a person when the records cannot settle its grant date.</p>

  <h2 id="timeline">The 2026 grant dates</h2>
  <p class="note">Every carrier below has a grant or reinstatement dated 2026 in the live AuthHist file, so all four fall inside the six-month window. Only two of them are actually new.</p>
  {timeline(today)}

  <h2 id="detail">Every case</h2>
  <div class="seg" role="radiogroup" aria-label="Filter cases by the full checks' decision">
    <button type="button" role="radio" aria-checked="true" data-t="all">All&nbsp; <span>{n}</span></button>
    <button type="button" role="radio" aria-checked="false" data-t="ready">Ready&nbsp; <span>{counts["READY FOR TMS ENTRY"]}</span></button>
    <button type="button" role="radio" aria-checked="false" data-t="queue">Exception queue&nbsp; <span>{counts["EXCEPTION QUEUE"]}</span></button>
    <button type="button" role="radio" aria-checked="false" data-t="stop">Do not set up&nbsp; <span>{counts["DO NOT SET UP"]}</span></button>
  </div>
  <div class="scroll"><table class="t" id="cases"><thead><tr><th>#</th><th>Carrier and what the packet tests</th><th>Expected</th><th>Full checks</th><th>Naive</th></tr></thead><tbody>
  {"".join(trs)}
  </tbody></table></div>

  <h2 id="choices">Other choices</h2>
  <ul class="note">
    <li>Cargo is checked on the certificate only, because FMCSA does not hold cargo filings for general freight.</li>
    <li>Liability below the broker's ${rules["min_auto_liability"]:,} rule but at the federal minimum goes to a person when the certificate claims the higher limit, so the agent can confirm the excess policy.</li>
    <li>A contact mismatch never rejects. It routes the carrier to a person who calls back on the FMCSA phone number. Free-mail domains prove nothing, so for those only the phone counts.</li>
    <li>A suspension notice in the last {rules["recent_notice_months"]} months goes to a person even if the authority is active again.</li>
  </ul>
</div>

<aside class="side" aria-label="About this build">
  <nav aria-label="On this page"><a href="#why">Why it matters</a><a href="#timeline">The 2026 grant dates</a><a href="#detail">Every case</a><a href="#choices">Other choices</a></nav>
  <div><h3>Data</h3><p>FMCSA records for 8 real carriers from data.transportation.gov (Company Census, Motus Carrier, AuthHist, RevokeSuspend, Out of Service Orders) and the legacy AuthHist archive, captured {today}, emails masked. The packets (phone, email, certificate amounts) are constructed; cases 4 and 5 are deliberately altered and say nothing about those carriers. The rules are one broker's public carrier requirements. A decision reflects only FMCSA's files on that date against those rules, not a judgment of any carrier.</p></div>
  <div><h3>Run it yourself</h3><p>Python 3.9+, standard library only.</p><pre>python3 run_checks.py
python3 run_checks.py --naive
python3 run_checks.py --source live</pre></div>
  <div><a class="pill" href="https://github.com/pg2342-hub/{REPO}">Code on GitHub</a></div>
</aside>
</div>
</main>
<script>
const seg=[...document.querySelectorAll('.seg button')];
seg.forEach(b=>b.addEventListener('click',()=>{{
 seg.forEach(x=>x.setAttribute('aria-checked',String(x===b)));
 const t=b.dataset.t;document.querySelectorAll('#cases tbody tr').forEach(r=>r.hidden=!(t==='all'||r.dataset.tier===t));
}}));
document.querySelectorAll('.cell').forEach(c=>c.addEventListener('click',()=>{{
 seg.forEach(x=>x.setAttribute('aria-checked',String(x.dataset.t==='all')));
 document.querySelectorAll('#cases tbody tr').forEach(r=>r.hidden=false);
 document.querySelectorAll('#cases tr.lit').forEach(r=>r.classList.remove('lit'));
 const row=document.getElementById('case-'+c.dataset.case); row&&row.classList.add('lit');
}}));
</script></body></html>
"""
    for bad in ("—", "–"):
        assert bad not in page, "dash in page"
    os.makedirs(os.path.join(ROOT, "docs"), exist_ok=True)
    out = os.path.join(ROOT, "docs", "index.html")
    open(out, "w", encoding="utf-8").write(page)
    open(os.path.join(ROOT, "docs", ".nojekyll"), "w").close()
    subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "demo_chrome.py"), out, "--repo", REPO], check=True)
    print(f"wrote {out}: full {pfull}/{n}, naive {pnaive}/{n}")


STARTER_CSS = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "starter.css"), encoding="utf-8").read()

if __name__ == "__main__":
    build()
