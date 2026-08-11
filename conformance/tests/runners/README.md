# Test runners

Deliberately misbehaving runners, so `harness run` can be shown to catch each
way a runner can be wrong. None of them implements any Q2D behaviour; the two
that answer correctly do so by carrying a hardcoded result for one fixture
vector, which is why they live here and not in `conformance/runners/`.
