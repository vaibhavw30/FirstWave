from routers.ai_panel import ContextModel, _build_context_str


def test_context_uses_mean_seconds_saved_when_present():
    ctx = ContextModel(coverage={"pct_static": 56.7, "pct_staged": 66.8,
                                 "median_saved_sec": 0, "mean_saved_sec": 98.1})
    s = _build_context_str(ctx)
    assert "(98s mean saved)" in s
    assert "median saved" not in s


def test_context_falls_back_to_median_without_mean():
    ctx = ContextModel(coverage={"pct_static": 61.2, "pct_staged": 83.7, "median_saved_sec": 147})
    assert "(147s median saved)" in _build_context_str(ctx)
