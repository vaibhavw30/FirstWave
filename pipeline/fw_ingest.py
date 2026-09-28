"""Raw EMS CSV column checks for script 01."""

# The dataset renamed CAD_INCIDENT_ID -> INCIDENT_ID; accept either.
ID_COLUMN_CANDIDATES = ("INCIDENT_ID", "CAD_INCIDENT_ID")

REQUIRED_COLUMNS = (
    "INCIDENT_DATETIME",
    "INCIDENT_DISPATCH_AREA",
    "BOROUGH",
    "INCIDENT_RESPONSE_SECONDS_QY",
    "INCIDENT_TRAVEL_TM_SECONDS_QY",
    "DISPATCH_RESPONSE_SECONDS_QY",
    "FINAL_SEVERITY_LEVEL_CODE",
    "HELD_INDICATOR",
    "VALID_INCIDENT_RSPNS_TIME_INDC",
    "VALID_DISPATCH_RSPNS_TIME_INDC",
    "REOPEN_INDICATOR",
    "TRANSFER_INDICATOR",
    "STANDBY_INDICATOR",
)


def missing_columns(columns) -> list[str]:
    present = {c.upper() for c in columns}
    return [c for c in REQUIRED_COLUMNS if c not in present]


def pick_id_column(columns) -> str:
    by_upper = {c.upper(): c for c in columns}
    for candidate in ID_COLUMN_CANDIDATES:
        if candidate in by_upper:
            return by_upper[candidate]
    raise ValueError(f"no incident ID column; expected one of {ID_COLUMN_CANDIDATES}")
