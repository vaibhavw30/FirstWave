import csv
import os
import pathlib
import subprocess
import sys

import pandas as pd

from fw_ingest import REQUIRED_COLUMNS

REPO = pathlib.Path(__file__).resolve().parents[2]

BASE = {
    "INCIDENT_DISPATCH_AREA": "K7", "BOROUGH": "BROOKLYN",
    "INCIDENT_RESPONSE_SECONDS_QY": "505", "INCIDENT_TRAVEL_TM_SECONDS_QY": "442",
    "DISPATCH_RESPONSE_SECONDS_QY": "63", "FINAL_SEVERITY_LEVEL_CODE": "2",
    "HELD_INDICATOR": "N", "VALID_INCIDENT_RSPNS_TIME_INDC": "Y",
    "VALID_DISPATCH_RSPNS_TIME_INDC": "Y", "REOPEN_INDICATOR": "N",
    "TRANSFER_INDICATOR": "N", "STANDBY_INDICATOR": "N",
}

ROWS = [  # (INCIDENT_ID, INCIDENT_DATETIME, overrides)
    ("1", "10/10/2025 08:05:00 PM", {}),                                   # kept, test, valid
    ("2", "10/10/2025 08:06:00 PM", {"VALID_INCIDENT_RSPNS_TIME_INDC": "N"}),  # kept, not valid
    ("3", "10/10/2025 08:07:00 PM", {"INCIDENT_RESPONSE_SECONDS_QY": "9000"}),  # kept, not valid
    ("4", "10/10/2025 08:08:00 PM", {"REOPEN_INDICATOR": "Y"}),              # dropped
    ("5", "10/10/2025 08:09:00 PM", {"INCIDENT_DISPATCH_AREA": "CW"}),       # dropped
    ("6", "10/10/2025 08:10:00 PM", {"BOROUGH": "BRONX", "INCIDENT_DISPATCH_AREA": "M7"}),  # dropped
    ("7", "11/30/2021 11:00:00 PM", {}),                                   # dropped: before window
    ("8", "12/15/2021 01:00:00 AM", {}),                                   # kept, history
    ("9", "07/01/2026 12:00:00 AM", {}),                                   # dropped: after window
    ("10", "2024-11-05T14:00:00", {}),                                     # kept, valid split, ISO format
    ("11", "03/02/2026 09:00:00 AM", {"BOROUGH": "RICHMOND / STATEN ISLAND",
                                      "INCIDENT_DISPATCH_AREA": "S1"}),     # kept, test_recent
    ("12", "05/05/2023 12:30:00 PM", {"VALID_DISPATCH_RSPNS_TIME_INDC": ""}),  # kept, train, not valid
]


def test_ingest_filters_and_flags(tmp_path):
    csv_path = tmp_path / "raw.csv"
    header = ["INCIDENT_ID", *REQUIRED_COLUMNS]
    with open(csv_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=header)
        w.writeheader()
        for iid, ts, over in ROWS:
            w.writerow({**BASE, **over, "INCIDENT_ID": iid, "INCIDENT_DATETIME": ts})

    env = {**os.environ, "FW_PIPELINE_DATA": str(tmp_path / "data")}
    r = subprocess.run([sys.executable, "pipeline/01_ingest_clean.py", "--csv", str(csv_path)],
                       cwd=REPO, env=env, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr

    out = pd.read_parquet(tmp_path / "data" / "incidents_cleaned.parquet").set_index("INCIDENT_ID")
    assert sorted(out.index, key=int) == ["1", "2", "3", "8", "10", "11", "12"]
    assert out.loc["1", "split"] == "test"
    assert out.loc["8", "split"] == "history"
    assert out.loc["10", "split"] == "valid"
    assert out.loc["11", "split"] == "test_recent"
    assert out.loc["12", "split"] == "train"
    assert out["is_valid_response"].to_dict() == {
        "1": 1, "2": 0, "3": 0, "8": 1, "10": 1, "11": 1, "12": 0}
    assert (out.loc["1", "dayofweek"], out.loc["1", "hour"]) == (4, 20)
    assert out.loc["1", "is_high_acuity"] == 1
