import pytest

from fw_ingest import REQUIRED_COLUMNS, missing_columns, pick_id_column


def test_pick_id_column_prefers_current_name():
    assert pick_id_column(["INCIDENT_ID", "CAD_INCIDENT_ID"]) == "INCIDENT_ID"
    assert pick_id_column(["cad_incident_id"]) == "cad_incident_id"


def test_pick_id_column_missing():
    with pytest.raises(ValueError):
        pick_id_column(["BOROUGH"])


def test_missing_columns_case_insensitive():
    cols = [c.lower() for c in REQUIRED_COLUMNS]
    assert missing_columns(cols) == []
    assert missing_columns(cols[1:]) == [REQUIRED_COLUMNS[0]]
