import pandas as pd
import pytest

from growthpulse import attribution as A


@pytest.mark.parametrize("model", A.MODELS)
@pytest.mark.parametrize("n", [1, 2, 3, 5, 9])
def test_credit_sums_to_one(model, n):
    assert sum(A.credit_for_journey(n, model)) == pytest.approx(1.0)


def test_known_credit_patterns():
    assert A.credit_for_journey(3, "first_touch") == [1, 0, 0]
    assert A.credit_for_journey(3, "last_touch") == [0, 0, 1]
    assert A.credit_for_journey(4, "linear") == [0.25] * 4
    assert A.credit_for_journey(4, "position_based") == pytest.approx([0.4, 0.1, 0.1, 0.4])
    assert A.credit_for_journey(2, "position_based") == [0.5, 0.5]
    assert A.credit_for_journey(1, "position_based") == [1.0]


def test_invalid_inputs():
    with pytest.raises(ValueError):
        A.credit_for_journey(0, "linear")
    with pytest.raises(ValueError):
        A.credit_for_journey(2, "magic")


def test_channel_credit_difference_between_models():
    t = pd.DataFrame({"customer_id": ["a", "a", "a", "b"], "session_ts": [1, 2, 3, 1],
                      "channel_name": ["paid_search", "email", "direct", "display"]})
    assert A.channel_credit(t, "first_touch")["paid_search"] == 1
    assert A.channel_credit(t, "last_touch")["direct"] == 1
    pb = A.channel_credit(t, "position_based")
    assert pb["email"] == pytest.approx(0.2) and pb["display"] == pytest.approx(1.0)


def test_revenue_weighted_credit():
    t = pd.DataFrame({"customer_id": ["a", "a"], "session_ts": [1, 2], "channel_name": ["x", "y"]})
    out = A.channel_credit(t, "linear", value=pd.Series({"a": 100.0}))
    assert out["x"] == 50 and out["y"] == 50
