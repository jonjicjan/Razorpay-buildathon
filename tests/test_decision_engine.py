from app.services.decision_engine import DO_NOT_FIGHT, MANUAL_REVIEW, RECOMMEND_CONTEST, route


def test_low_winnability_routes_do_not_fight():
    d = route(0.1, delivery_confirmed=0, three_d_secure=0)
    assert d.action == DO_NOT_FIGHT


def test_high_winnability_routes_recommend_contest():
    d = route(0.9, delivery_confirmed=1, three_d_secure=1)
    assert d.action == RECOMMEND_CONTEST


def test_high_value_hard_stop():
    d = route(0.95, amount=30000)
    assert d.action == MANUAL_REVIEW
    assert d.hard_stop is True
