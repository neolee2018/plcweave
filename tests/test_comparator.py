from plcweave.testing import compare

def test_missing_data_is_unverified_and_never_zero():
    assert compare({}, {"D1":0})[0]["kind"] == "UNVERIFIED"

def test_range_and_first_wrong_device():
    assert compare({"D1":50},{"D1":{"min":0,"max":50}}) == []
    assert compare({"D1":51},{"D1":{"min":0,"max":50}})[0]["kind"] == "PROGRAM_FAIL"
