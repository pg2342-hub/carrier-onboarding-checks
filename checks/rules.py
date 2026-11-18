"""Carrier onboarding checks against public FMCSA records.

Each check returns a Result with a status:
  PASS    the check is clean
  REVIEW  a person must look before the carrier is set up (goes to the exception queue)
  REJECT  the carrier cannot be set up as things stand
and the evidence it used (dataset, field, value), so every decision can be traced.
"""
import re
from dataclasses import dataclass, field
from datetime import date, datetime

PASS, REVIEW, REJECT = "PASS", "REVIEW", "REJECT"
RANK = {PASS: 0, REVIEW: 1, REJECT: 2}

PROPERTY_CARRIER = "Motor Carrier of Property (Except Household Goods)"

# MOTUS cutover. Legacy authorities were re-stamped with a GRANTED row dated
# 2026-05-28, and many then show an "Administrative status adjustment" and a
# fresh grant in June 2026. None of these mean the authority is new.
MOTUS_CUTOVER = date(2026, 5, 28)
MOTUS_CLEANUP_END = date(2026, 6, 30)
ADMIN_REASON = "administrative status adjustment"

# A shared free-mail domain proves nothing, so only the phone match counts for these.
FREE_MAIL = {"gmail.com", "yahoo.com", "aol.com", "outlook.com", "hotmail.com", "icloud.com"}


@dataclass
class Result:
    check: str
    status: str
    detail: str
    evidence: list = field(default_factory=list)


def d8(s):
    """'20260528' -> date"""
    return datetime.strptime(s, "%Y%m%d").date() if s else None


def dmdy(s):
    """'05/28/2026' -> date"""
    return datetime.strptime(s, "%m/%d/%Y").date() if s else None


def months_between(a, b):
    m = (b.year - a.year) * 12 + (b.month - a.month)
    if b.day < a.day:
        m -= 1
    return m


def money(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def norm_name(s):
    s = (s or "").upper()
    s = re.sub(r"[^A-Z0-9 ]", " ", s)
    s = re.sub(r"\b(INC|LLC|L L C|CO|CORP|CORPORATION|COMPANY|LTD|THE)\b", " ", s)
    return " ".join(s.split())


def digits(s):
    return re.sub(r"\D", "", s or "")[-10:]


def email_domain(s):
    return (s or "").split("@")[-1].lower().strip()


# ---------------------------------------------------------------- checks


def check_identity(packet, census):
    if not census:
        return Result("identity", REJECT, "USDOT number not found in the FMCSA census file",
                      [("census", "dot_number", packet["dot"])])
    c = census[0]
    ev = [("census", "status_code", c.get("status_code")),
          ("census", "legal_name", c.get("legal_name")),
          ("census", "dba_name", c.get("dba_name"))]
    if c.get("status_code") != "A":
        return Result("identity", REJECT, f"USDOT status is {c.get('status_code')!r}, not active", ev)
    names = {norm_name(c.get("legal_name")), norm_name(c.get("dba_name"))} - {""}
    if norm_name(packet["legal_name"]) not in names:
        return Result("identity", REVIEW,
                      f"Packet name {packet['legal_name']!r} does not match FMCSA legal or DBA name", ev)
    classdef = c.get("classdef", "")
    if "AUTHORIZED FOR HIRE" not in classdef:
        ev.append(("census", "classdef", classdef))
        return Result("identity", REVIEW, "Not registered as authorized for hire", ev)
    return Result("identity", PASS, "USDOT active and name matches", ev)


def check_contact(packet, census, carrier):
    """Impersonation guard: the packet's phone and email should match what the
    carrier registered with FMCSA. A mismatch is the common double-brokering
    pattern (someone sets up under a real carrier's DOT number)."""
    if not census:
        return Result("contact", REVIEW, "No census record to compare contact details", [])
    c = census[0]
    fm_phones = {digits(c.get("phone"))} | {digits(r.get("bus_telno")) for r in carrier}
    fm_phones.discard("")
    ev = [("census", "phone", c.get("phone")), ("census", "email_address", c.get("email_address"))]
    problems = []
    if digits(packet["phone"]) not in fm_phones:
        problems.append("phone differs from FMCSA")
    fm_dom = email_domain(c.get("email_address"))
    if fm_dom and fm_dom not in FREE_MAIL and email_domain(packet["email"]) != fm_dom:
        problems.append("email domain differs from FMCSA")
    if problems:
        return Result("contact", REVIEW,
                      "; ".join(problems) + ". Call the carrier back on the FMCSA phone number before setup", ev)
    if fm_dom in FREE_MAIL:
        return Result("contact", PASS, "Phone matches FMCSA (free-mail address, so the email domain is not used)", ev)
    return Result("contact", PASS, "Phone and email domain match FMCSA", ev)


def _property_authority(carrier, packet):
    rows = [r for r in carrier if r.get("op_auth_type") == PROPERTY_CARRIER]
    want = packet.get("mc", "").replace("-", "").upper()
    exact = [r for r in rows if r.get("docket_number", "").replace("-", "").upper() == want]
    return (exact or rows)


def check_authority_active(packet, carrier):
    rows = _property_authority(carrier, packet)
    if not rows:
        return Result("authority_active", REJECT, "No property carrier authority on file", [])
    r = rows[0]
    ev = [("motus_carrier", "docket_number", r.get("docket_number")),
          ("motus_carrier", "op_auth_status", r.get("op_auth_status"))]
    if r.get("op_auth_status") != "Active":
        return Result("authority_active", REJECT, f"Authority is {r.get('op_auth_status')}, not active", ev)
    return Result("authority_active", PASS, "Property carrier authority is active", ev)


def active_since_motus(events):
    """Date the authority has been continuously active, from Motus AuthHist,
    ignoring the MOTUS migration noise. Returns (date or None, used_noise_only)."""
    evs = sorted(events, key=lambda r: r.get("status_change_date", ""))
    noise_dates = set()
    for i, r in enumerate(evs):
        dt = d8(r.get("status_change_date"))
        reason = (r.get("reason") or "").lower()
        if reason == ADMIN_REASON:
            noise_dates.add(i)
            continue
        if dt == MOTUS_CUTOVER and reason == "granted":
            noise_dates.add(i)  # migration re-stamp of a legacy authority
            continue
        # a re-grant during the June 2026 clean-up that follows an admin adjustment
        if MOTUS_CUTOVER <= dt <= MOTUS_CLEANUP_END and i > 0 and (i - 1) in noise_dates \
                and (evs[i - 1].get("reason") or "").lower() == ADMIN_REASON:
            noise_dates.add(i)
    real = [r for i, r in enumerate(evs) if i not in noise_dates]
    since = None
    for r in real:
        status = r.get("op_auth_status")
        if status == "Active" and (r.get("reason") or "").upper() in ("GRANTED", "REINSTATED"):
            if since is None:
                since = d8(r["status_change_date"])
        elif status != "Active":
            since = None  # a real break (revoked, inactive) restarts the clock
    return since, (since is None and len(noise_dates) > 0)


def active_since_legacy(rows):
    """From the legacy AuthHist archive: earliest grant or reinstatement served
    after the last real revocation. Returns (date or None, legacy_grant_exists)."""
    last_revoked = date.min
    grants = []
    for r in rows:
        if (r.get("disp_action_desc") or "") == "REVOKED":
            last_revoked = max(last_revoked, dmdy(r.get("disp_served_date")) or date.min)
    exists = False
    for r in rows:
        if r.get("original_action_desc") in ("GRANTED", "REINSTATED") and \
                "CARRIER" in (r.get("mod_col_1") or "") and r.get("disp_action_desc") != "REVOKED":
            exists = True
            served = dmdy(r.get("orig_served_date"))
            if served and served > last_revoked:
                grants.append(served)
    return (min(grants) if grants else None), exists


def check_authority_age(packet, authhist, census, legacy_rows, rules, today, naive=False, docket=None):
    min_m = rules["min_authority_months"]
    events = [r for r in authhist if r.get("op_auth_type") == PROPERTY_CARRIER]
    if docket:
        key = docket.replace("-", "").upper()
        events = [r for r in events if r.get("docket_number", "").replace("-", "").upper() == key]
    if not events:
        return Result("authority_age", REJECT, "No authority history found", [])
    if naive:
        # What a first-pass script does: take the most recent grant in the live file.
        grants = [d8(r["status_change_date"]) for r in events
                  if (r.get("reason") or "").upper() in ("GRANTED", "REINSTATED")]
        since = max(grants) if grants else None
        ev = [("motus_authhist", "latest grant", str(since))]
        if since is None:
            return Result("authority_age", REJECT, "No grant found", ev)
        m = months_between(since, today)
        st = PASS if m >= min_m else REJECT
        return Result("authority_age", st, f"Granted {since}, {m} months ago (naive: latest grant)", ev)

    since, noise_only = active_since_motus(events)
    ev = [("motus_authhist", "events", len(events))]
    note = ""
    if since is None and noise_only:
        # Authority predates MOTUS; the live file only has migration rows. Use the legacy archive.
        lsince, exists = active_since_legacy(legacy_rows)
        ev.append(("legacy_authhist", "rows", len(legacy_rows)))
        if lsince:
            since, note = lsince, " (date from the legacy archive; the live file only shows the MOTUS migration)"
        elif exists:
            return Result("authority_age", REVIEW,
                          "Authority predates the MOTUS cutover (legacy grant on file) but neither file has the "
                          "original grant date; a person confirms it before setup", ev)
        else:
            return Result("authority_age", REVIEW,
                          "Only MOTUS migration rows and no legacy record; confirm the original grant date", ev)
    if since is None:
        return Result("authority_age", REJECT, "Authority has not been continuously active", ev)
    m = months_between(since, today)
    ev.append(("derived", "active_since", str(since)))
    if m < min_m:
        return Result("authority_age", REJECT,
                      f"Active since {since}, {m} months; rule is {min_m} months{note}", ev)
    return Result("authority_age", PASS, f"Active since {since}, {m} months{note}", ev)


def check_notices(revoke_rows, legacy_rows, rules, today):
    """Recent suspension or revocation notices (usually an insurance lapse)."""
    window = rules["recent_notice_months"]
    hits = []
    for r in revoke_rows:
        served = d8(r.get("order1_serve_date"))
        eff = d8(r.get("order1_effective_date"))
        desc = r.get("order1_type_desc", "")
        if served and months_between(served, today) < window:
            hits.append(f"{desc} served {served}" + (f", effective {eff}" if eff else ""))
    for r in legacy_rows:
        if r.get("original_action_desc") == "INVOLUNTARY REVOCATION":
            served = dmdy(r.get("orig_served_date"))
            if served and months_between(served, today) < window:
                hits.append(f"Involuntary revocation notice served {served} ({r.get('disp_action_desc', 'open')})")
    if hits:
        return Result("notices", REVIEW, "; ".join(hits), [("motus_revoke_suspend", "orders", len(revoke_rows))])
    return Result("notices", PASS, f"No suspension or revocation notices in the last {window} months",
                  [("motus_revoke_suspend", "orders", len(revoke_rows))])


def check_out_of_service(oos_rows, today):
    active = []
    for r in oos_rows:
        resc = r.get("rescind_date")
        if r.get("status") == "ACTIVE" and (not resc or resc > today.isoformat()):
            active.append(f"{r.get('oos_reason')} since {r.get('oos_date')}")
    if active:
        return Result("out_of_service", REJECT, "Active out-of-service order: " + "; ".join(active),
                      [("oos", "orders", len(oos_rows))])
    return Result("out_of_service", PASS, "No active out-of-service order", [("oos", "orders", len(oos_rows))])


def check_safety(census, rules):
    rating = (census[0] if census else {}).get("safety_rating", "") or ""
    ev = [("census", "safety_rating", rating or "(none)")]
    if rating in rules["safety_rating_reject"]:
        return Result("safety_rating", REJECT, "Unsatisfactory safety rating", ev)
    if rating in rules["safety_rating_review"]:
        return Result("safety_rating", REVIEW, "Conditional safety rating", ev)
    return Result("safety_rating", PASS, f"Safety rating {rating or 'none'}", ev)


def check_insurance(packet, carrier, rules):
    rows = _property_authority(carrier, packet)
    r = rows[0] if rows else {}
    bipd, fed_min = money(r.get("bipd_file")), money(r.get("min_cov_amount"))
    need = rules["min_auto_liability"]
    ev = [("motus_carrier", "bipd_file", r.get("bipd_file")),
          ("motus_carrier", "min_cov_amount", r.get("min_cov_amount")),
          ("packet", "coi_auto", packet.get("coi_auto")), ("packet", "coi_cargo", packet.get("coi_cargo")),
          ("packet", "coi_source", packet.get("coi_source"))]
    if bipd <= 0 or (fed_min and bipd < fed_min):
        return Result("insurance", REJECT, f"Liability on file with FMCSA ${bipd:,.0f} is below the federal minimum", ev)
    issues = []
    if bipd < need:
        if money(packet.get("coi_auto")) >= need:
            issues.append(f"FMCSA shows ${bipd:,.0f} on file; certificate claims ${money(packet.get('coi_auto')):,.0f}. "
                          f"Confirm the excess policy with the agent")
        else:
            return Result("insurance", REJECT, f"Auto liability ${bipd:,.0f} on file; rule is ${need:,.0f}", ev)
    if money(packet.get("coi_cargo")) < rules["min_cargo"]:
        issues.append(f"Cargo on certificate ${money(packet.get('coi_cargo')):,.0f}; rule is ${rules['min_cargo']:,.0f} "
                      f"(cargo is not filed with FMCSA for general freight, so the certificate is the only source)")
    if rules["coi_must_come_from_agent"] and packet.get("coi_source") != "agent":
        issues.append("Certificate was not sent by the insurance agent")
    if issues:
        return Result("insurance", REVIEW, "; ".join(issues), ev)
    return Result("insurance", PASS, f"${bipd:,.0f} on file with FMCSA; certificate meets the rule", ev)


def run_all(packet, src, rules, today, naive=False):
    dot = packet["dot"]
    census = src.fetch("census", dot)
    carrier = src.fetch("carrier", dot)
    authhist = src.fetch("authhist", dot)
    revoke = src.fetch("revoke_suspend", dot)
    oos = src.fetch("oos", dot)
    auth = _property_authority(carrier, packet)
    docket = (auth[0].get("docket_number") if auth else packet.get("mc", "")) or ""
    legacy = src.legacy(docket) if docket and len(docket.replace("-", "")) <= 9 else []
    results = [
        check_identity(packet, census),
        check_contact(packet, census, carrier),
        check_authority_active(packet, carrier),
        check_authority_age(packet, authhist, census, legacy, rules, today, naive=naive, docket=docket),
        check_notices(revoke, legacy, rules, today),
        check_out_of_service(oos, today),
        check_safety(census, rules),
        check_insurance(packet, carrier, rules),
    ]
    worst = max(results, key=lambda r: RANK[r.status]).status
    decision = {PASS: "READY FOR TMS ENTRY", REVIEW: "EXCEPTION QUEUE", REJECT: "DO NOT SET UP"}[worst]
    return decision, results, (census[0] if census else {}), (auth[0] if auth else {})
