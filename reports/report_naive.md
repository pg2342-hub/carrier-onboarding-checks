# Carrier check report (naive authority logic)

Source: snapshot (captured 2026-11-18) · as of 2026-11-18 · rules: m2_logistics.json

| Case | USDOT | Decision | Expected | Reasons |
|---|---|---|---|---|
| 1 | 53467 | DO NOT SET UP | READY FOR TMS ENTRY ✗ | authority_age: Granted 2026-06-16, 5 months ago (naive: latest grant) |
| 2 | 131895 | DO NOT SET UP | EXCEPTION QUEUE ✗ | authority_age: Granted 2026-05-28, 5 months ago (naive: latest grant) |
| 3 | 100002 | READY FOR TMS ENTRY | READY FOR TMS ENTRY ✓ | all checks clean |
| 4 | 100002 | EXCEPTION QUEUE | EXCEPTION QUEUE ✓ | contact: phone differs from FMCSA; email domain differs from FMCSA. Call the carrier back on the FMCSA phone number before setup |
| 5 | 131895 | DO NOT SET UP | EXCEPTION QUEUE ✗ | authority_age: Granted 2026-05-28, 5 months ago (naive: latest grant); insurance: Cargo on certificate $50,000; rule is $100,000 (cargo is not filed with FMCSA for general freight, so the certificate is the only source); Certificate was not sent by the insurance agent |
| 6 | 3436760 | EXCEPTION QUEUE | EXCEPTION QUEUE ✓ | notices: Operating Authority Involuntary Suspension Notice served 2026-09-10, effective 2026-10-10; insurance: FMCSA shows $750,000 on file; certificate claims $1,000,000. Confirm the excess policy with the agent |
| 7 | 6951245 | DO NOT SET UP | DO NOT SET UP ✓ | authority_age: Granted 2026-11-17, 0 months ago (naive: latest grant); insurance: FMCSA shows $750,000 on file; certificate claims $1,000,000. Confirm the excess policy with the agent |
| 8 | 4144337 | DO NOT SET UP | DO NOT SET UP ✓ | authority_active: Authority is Pending, not active; authority_age: No grant found; insurance: Liability on file with FMCSA $0 is below the federal minimum |
| 9 | 1006607 | DO NOT SET UP | DO NOT SET UP ✓ | authority_age: Granted 2026-09-02, 2 months ago (naive: latest grant); notices: Operating Authority Involuntary Suspension Notice served 2026-05-21, effective 2026-06-20; Notice Of Operating Authority Voluntary Suspension served 2026-08-27 |
| 10 | 4499661 | DO NOT SET UP | DO NOT SET UP ✓ | authority_active: No property carrier authority on file; authority_age: No authority history found; insurance: Liability on file with FMCSA $0 is below the federal minimum |

Matches the expected decision on 7 of 10 cases.

Naive logic reads the most recent grant in the Motus AuthHist file, so carriers whose authority was re-stamped during the 2026 MOTUS migration look new.
