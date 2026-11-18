# Carrier check report (full checks)

Source: snapshot (captured 2026-11-18) · as of 2026-11-18 · rules: m2_logistics.json

| Case | USDOT | Decision | Expected | Reasons |
|---|---|---|---|---|
| 1 | 53467 | READY FOR TMS ENTRY | READY FOR TMS ENTRY ✓ | all checks clean |
| 2 | 131895 | EXCEPTION QUEUE | EXCEPTION QUEUE ✓ | authority_age: Authority predates the MOTUS cutover (legacy grant on file) but neither file has the original grant date; a person confirms it before setup |
| 3 | 100002 | READY FOR TMS ENTRY | READY FOR TMS ENTRY ✓ | all checks clean |
| 4 | 100002 | EXCEPTION QUEUE | EXCEPTION QUEUE ✓ | contact: phone differs from FMCSA; email domain differs from FMCSA. Call the carrier back on the FMCSA phone number before setup |
| 5 | 131895 | EXCEPTION QUEUE | EXCEPTION QUEUE ✓ | authority_age: Authority predates the MOTUS cutover (legacy grant on file) but neither file has the original grant date; a person confirms it before setup; insurance: Cargo on certificate $50,000; rule is $100,000 (cargo is not filed with FMCSA for general freight, so the certificate is the only source); Certificate was not sent by the insurance agent |
| 6 | 3436760 | EXCEPTION QUEUE | EXCEPTION QUEUE ✓ | notices: Operating Authority Involuntary Suspension Notice served 2026-09-10, effective 2026-10-10; insurance: FMCSA shows $750,000 on file; certificate claims $1,000,000. Confirm the excess policy with the agent |
| 7 | 6951245 | DO NOT SET UP | DO NOT SET UP ✓ | authority_age: Active since 2026-11-17, 0 months; rule is 6 months; insurance: FMCSA shows $750,000 on file; certificate claims $1,000,000. Confirm the excess policy with the agent |
| 8 | 4144337 | DO NOT SET UP | DO NOT SET UP ✓ | authority_active: Authority is Pending, not active; authority_age: Authority has not been continuously active; insurance: Liability on file with FMCSA $0 is below the federal minimum |
| 9 | 1006607 | DO NOT SET UP | DO NOT SET UP ✓ | authority_age: Active since 2026-09-02, 2 months; rule is 6 months; notices: Operating Authority Involuntary Suspension Notice served 2026-05-21, effective 2026-06-20; Notice Of Operating Authority Voluntary Suspension served 2026-08-27 |
| 10 | 4499661 | DO NOT SET UP | DO NOT SET UP ✓ | authority_active: No property carrier authority on file; authority_age: No authority history found; insurance: Liability on file with FMCSA $0 is below the federal minimum |

Matches the expected decision on 10 of 10 cases.

