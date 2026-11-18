"""Read public FMCSA records from the DOT data portal (data.transportation.gov).

Two sources with the same interface:
- LiveSource queries the Socrata API (no key needed; add an app token with
  SOCRATA_APP_TOKEN to raise rate limits).
- SnapshotSource reads a JSON snapshot captured from the same endpoints, so the
  checks can be run and tested offline.
"""
import json
import os
import urllib.parse
import urllib.request

BASE = "https://data.transportation.gov/resource/"

# FMCSA moved operating-authority data to its new registration system (MOTUS)
# in 2026. The "Motus" files are the live ones; the legacy files are an archive
# that stopped updating on 2026-05-14.
DATASETS = {
    "census": ("az4n-8mr2", "dot_number"),          # Company Census File
    "carrier": ("inys-ebih", "usdot_number"),       # Motus Carrier - All With History
    "authhist": ("yu5v-wbh6", "usdot_number"),      # Motus AuthHist - All With History
    "revoke_suspend": ("wb4f-neki", "usdot_number"),# Motus RevokeSuspend - All With History
    "oos": ("p2mt-9ige", "dot_number"),             # Out of Service Orders
    "legacy_authhist": ("9mw4-x3tu", "docket_number"),  # legacy AuthHist archive
}


def legacy_docket(docket):
    """MC13739 -> MC013739 (the legacy archive pads docket numbers to six digits)."""
    prefix, digits = docket[:2], docket[2:].lstrip("-")
    return prefix + digits.zfill(6)


class LiveSource:
    name = "live"

    def __init__(self, timeout=30):
        self.timeout = timeout
        self.token = os.environ.get("SOCRATA_APP_TOKEN")

    def _get(self, dataset, params):
        ds_id, _ = DATASETS[dataset]
        url = BASE + ds_id + ".json?" + urllib.parse.urlencode(params)
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        if self.token:
            req.add_header("X-App-Token", self.token)
        with urllib.request.urlopen(req, timeout=self.timeout) as r:
            return json.load(r)

    def fetch(self, dataset, dot):
        _, key = DATASETS[dataset]
        return self._get(dataset, {key: str(dot), "$limit": 500})

    def legacy(self, docket):
        return self._get("legacy_authhist", {"docket_number": legacy_docket(docket), "$limit": 500})


class SnapshotSource:
    name = "snapshot"

    def __init__(self, path):
        with open(path) as f:
            self.data = json.load(f)
        self.captured_on = self.data.get("captured_on")

    def fetch(self, dataset, dot):
        rec = self.data["carriers"].get(str(dot))
        if rec is None:
            return []
        rows = rec.get(dataset, [])
        if isinstance(rows, dict) and "_error" in rows:
            raise RuntimeError(f"{dataset} for {dot}: {rows['_error']}")
        return rows

    def legacy(self, docket):
        return self.data.get("legacy_authhist", {}).get(legacy_docket(docket), [])
