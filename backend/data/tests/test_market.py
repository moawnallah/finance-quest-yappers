import datetime as dt

import pytest
import yaml

from series_store import SeriesStore
from sim import bootstrap, build_path, fictional, rebalance_trades, replay, run_portfolio, synthetic
from sim.portfolio import portfolio_metrics


def store_with(tmp_path, series: dict[str, list[float]], start=dt.date(2020, 1, 1)):
    catalog = {}
    (tmp_path / "data").mkdir()
    for sid, values in series.items():
        rows = []
        for i, v in enumerate(values):
            d = dt.date(start.year + (start.month - 1 + i) // 12, (start.month - 1 + i) % 12 + 1, 1)
            rows.append(f"{d.isoformat()},{v}")
        (tmp_path / "data" / f"{sid}.csv").write_text("date,value\n" + "\n".join(rows) + "\n", encoding="utf-8")
        catalog[sid] = {"name": sid, "unit": "index", "frequency": "monthly", "source": "Test",
                        "licence": "CC BY 4.0", "display": True}
    (tmp_path / "catalog.yaml").write_text(yaml.safe_dump(catalog), encoding="utf-8")
    return SeriesStore(tmp_path)


def test_replay_returns_by_hand(tmp_path):
    # The time machine shows these numbers as history; they must be the real changes, step by step.
    s = store_with(tmp_path, {"eq": [100, 110, 99, 99], "bd": [50, 50, 51, 51]})
    path = replay(s, {"shares": "eq", "bonds": "bd"}, "2020-01-01", 3)
    assert path.returns["shares"] == pytest.approx([0.10, -0.10, 0.0])
    assert path.returns["bonds"] == pytest.approx([0.0, 0.02, 0.0])
    assert path.dates == ["2020-02-01", "2020-03-01", "2020-04-01"] and path.synthetic is False
    with pytest.raises(ValueError):
        replay(s, {"shares": "eq"}, "2020-01-01", 4)  # only 3 returns exist


def test_bootstrap_keeps_rows_together():
    # Drawing the same historical row for every asset is what keeps their correlation.
    history = {"a": [0.01, 0.02, 0.03, 0.04, 0.05], "b": [0.10, 0.20, 0.30, 0.40, 0.50]}
    path = bootstrap(history, steps=12, block=2, seed=3)
    pairs = set(zip(history["a"], history["b"]))
    assert path.steps == 12 and all(p in pairs for p in zip(path.returns["a"], path.returns["b"]))
    assert path.returns == bootstrap(history, 12, 2, 3).returns


FICTIONAL = {
    "regimes": {"calm": {"mean": 0.01, "sd": 0.02}, "stress": {"mean": -0.03, "sd": 0.06},
                "calm_to_stress": 0.1, "stress_to_calm": 0.3},
    "assets": {"crocotech": {"label": "CrocoTech", "beta": 1.4, "noise": 0.03},
               "safebond": {"label": "SafeBond", "beta": 0.1, "noise": 0.005}},
    "events": [{"asset": "crocotech", "probability": 0.05, "shock": -0.25, "headline": "CrocoTech loses its CEO"}],
}


def test_fictional_market_is_deterministic_and_labelled():
    # Friends must be able to play the same market, so the same seed gives the same market.
    a, b = fictional(FICTIONAL, 120, seed=7), fictional(FICTIONAL, 120, seed=7)
    assert a.returns == b.returns and a.events == b.events and a.synthetic is True
    assert set(a.regimes) <= {"calm", "stress"} and a.labels["crocotech"] == "CrocoTech"
    assert all(e["headline"] == "CrocoTech loses its CEO" and e["shock"] == -0.25 for e in a.events)
    assert fictional(FICTIONAL, 120, seed=8).returns != a.returns


def test_build_path_dispatch():
    p = build_path({"kind": "synthetic", "asset": "shares", "seed": 5}, 6)
    assert p.assets == ["shares"] and p.steps == 6
    assert synthetic({"x": {}}, 4, 1).steps == 4
    with pytest.raises(ValueError):
        build_path({"kind": "crystal_ball"}, 6)


def test_rebalance_trades():
    trades = rebalance_trades({"shares": 50, "bonds": 50}, {"shares": 0.6, "bonds": 0.4})
    assert trades == pytest.approx({"bonds": -10, "shares": 10}) and sum(trades.values()) == pytest.approx(0)
    with pytest.raises(ValueError):
        rebalance_trades({"shares": 1}, {"shares": 0.7})


def test_portfolio_by_hand(tmp_path):
    # Rebalance to 50/50 at each step; shares +10%, bonds 0%, then shares -20%, bonds +10%.
    s = store_with(tmp_path, {"eq": [100, 110, 88], "bd": [100, 100, 110]})
    path = replay(s, {"shares": "eq", "bonds": "bd"}, "2020-01-01", 2)
    rows = run_portfolio(path, {"shares": 500, "bonds": 500}, lambda ctx: {"target": {"shares": 0.5, "bonds": 0.5}})
    assert rows[0]["value"] == pytest.approx(1050)           # 550 + 500
    assert rows[1]["value"] == pytest.approx(525 * 0.8 + 525 * 1.1)  # rebalanced to 525/525 first
    m = portfolio_metrics(rows, 1000)
    assert m["max_drawdown"] == pytest.approx(1 - rows[1]["value"] / 1050, abs=1e-4)
