from unittest.mock import MagicMock

import pytest

from flowsint_core.analytics import (
    DetectionParams,
    TransactionAnalyticsService,
    TxEdge,
    detect_cycles,
    detect_fan,
    detect_pass_through,
    detect_structuring,
    load_transactions,
    run_detectors,
    summarize_accounts,
    trace_funds,
)

H = 3600
T0 = 1_700_000_000
_counter = iter(range(1, 10_000))


def tx(source, target, amount, hours=None, currency="XOF"):
    n = next(_counter)
    return TxEdge(
        id=f"e{n}",
        source=source,
        target=target,
        amount=amount,
        currency=currency,
        epoch=None if hours is None else T0 + int(hours * H),
        source_label=f"label-{source}",
        target_label=f"label-{target}",
    )


class TestFan:
    def test_fan_out_within_window(self):
        edges = [tx("hub", f"r{i}", 100, hours=i) for i in range(6)]
        alerts = detect_fan(edges, DetectionParams(fan_min_counterparties=5))

        assert [a.type for a in alerts] == ["fan_out"]
        alert = alerts[0]
        assert alert.details["counterparties"] == 6
        assert alert.details["totals"] == {"XOF": 600}
        assert alert.node_ids[0] == "hub"
        assert len(alert.edge_ids) == 6
        assert alert.title == "label-hub sent to 6 accounts within 24h"

    def test_spread_out_transfers_are_not_a_fan(self):
        edges = [tx("hub", f"r{i}", 100, hours=i * 30) for i in range(6)]
        assert detect_fan(edges, DetectionParams(fan_min_counterparties=5)) == []

    def test_repeated_counterparty_counts_once(self):
        edges = [tx("hub", "same", 100, hours=i) for i in range(10)]
        assert detect_fan(edges, DetectionParams(fan_min_counterparties=2)) == []

    def test_fan_in(self):
        edges = [tx(f"s{i}", "collector", 50, hours=i) for i in range(5)]
        alerts = detect_fan(edges, DetectionParams(fan_min_counterparties=5))
        assert [a.type for a in alerts] == ["fan_in"]

    def test_undated_edges_ignored(self):
        edges = [tx("hub", f"r{i}", 100) for i in range(10)]
        assert detect_fan(edges, DetectionParams()) == []


class TestPassThrough:
    ONE_EVENT = DetectionParams(pass_through_min_events=1)

    def test_mule_forwards_most_of_what_it_receives(self):
        edges = [
            tx("victim1", "mule", 1000, hours=0),
            tx("mule", "boss1", 500, hours=2),
            tx("mule", "boss2", 450, hours=5),
            tx("victim2", "mule", 2000, hours=24),
            tx("mule", "boss1", 1900, hours=30),
        ]
        alerts = detect_pass_through(edges, DetectionParams())

        assert len(alerts) == 1
        alert = alerts[0]
        assert alert.details["account"] == "mule"
        assert alert.details["events"] == 2
        assert alert.details["received"] == 3000
        assert alert.details["forwarded"] == 2850
        assert set(alert.node_ids) == {"mule", "victim1", "victim2", "boss1", "boss2"}
        assert alert.details["forwarded_share"] == 0.95
        assert alert.score == 0.95

    def test_single_forward_needs_min_events_1(self):
        edges = [tx("a", "b", 1000, hours=0), tx("b", "c", 1000, hours=1)]
        assert detect_pass_through(edges, DetectionParams()) == []
        assert len(detect_pass_through(edges, self.ONE_EVENT)) == 1

    def test_one_outflow_cannot_explain_several_inflows(self):
        edges = [
            tx("s1", "b", 1000, hours=0),
            tx("s2", "b", 1000, hours=1),
            tx("s3", "b", 1000, hours=2),
            tx("b", "c", 1000, hours=3),
        ]
        params = DetectionParams(pass_through_min_events=1, pass_through_min_share=0)
        alerts = detect_pass_through(edges, params)
        # Only the oldest inflow is covered by the single outflow
        assert alerts[0].details["events"] == 1

    def test_busy_account_forwarding_a_small_share_is_not_a_mule(self):
        edges = [tx(f"s{i}", "shop", 1000, hours=i * 24) for i in range(10)]
        edges += [
            tx("shop", "supplier", 1000, hours=1),
            tx("shop", "supplier", 1000, hours=49),
        ]
        # 2 of 10 inflows forwarded: 20% of the money
        assert detect_pass_through(edges, DetectionParams()) == []

    def test_money_kept_is_not_pass_through(self):
        edges = [tx("a", "b", 1000, hours=0), tx("b", "c", 100, hours=1)]
        assert detect_pass_through(edges, self.ONE_EVENT) == []

    def test_outflow_before_inflow_does_not_count(self):
        edges = [tx("b", "c", 1000, hours=0), tx("a", "b", 1000, hours=1)]
        assert detect_pass_through(edges, self.ONE_EVENT) == []

    def test_outflow_after_window_does_not_count(self):
        edges = [tx("a", "b", 1000, hours=0), tx("b", "c", 1000, hours=100)]
        assert detect_pass_through(edges, self.ONE_EVENT) == []

    def test_currencies_are_not_mixed(self):
        edges = [
            tx("a", "b", 1000, hours=0, currency="XOF"),
            tx("b", "c", 1000, hours=1, currency="EUR"),
        ]
        assert detect_pass_through(edges, self.ONE_EVENT) == []


class TestStructuring:
    def params(self, **kw):
        return DetectionParams(structuring_threshold=1_000_000, **kw)

    def test_amounts_just_under_threshold(self):
        edges = [
            tx("smurf", "bank", 990_000, hours=0),
            tx("smurf", "bank", 950_000, hours=10),
            tx("smurf", "other", 999_999, hours=20),
            tx("smurf", "bank", 1_000_000, hours=21),  # at threshold: not counted
            tx("smurf", "bank", 500_000, hours=22),  # far below: not counted
        ]
        alerts = [
            a
            for a in detect_structuring(edges, self.params())
            if a.details["role"] == "source"
        ]

        assert len(alerts) == 1
        assert alerts[0].details["count"] == 3
        assert alerts[0].details["total"] == 2_939_999

    def test_disabled_without_threshold(self):
        edges = [tx("a", "b", 990_000, hours=i) for i in range(5)]
        assert detect_structuring(edges, DetectionParams()) == []

    def test_currency_filter(self):
        edges = [tx("a", "b", 990_000, hours=i, currency="EUR") for i in range(5)]
        assert detect_structuring(edges, self.params(structuring_currency="XOF")) == []

    def test_outside_window(self):
        edges = [tx("a", "b", 990_000, hours=i * 100) for i in range(5)]
        assert detect_structuring(edges, self.params()) == []


class TestCycles:
    def test_round_trip_in_time_order(self):
        edges = [
            tx("a", "b", 1000, hours=0),
            tx("b", "c", 950, hours=1),
            tx("c", "a", 900, hours=2),
        ]
        alerts = detect_cycles(edges, DetectionParams())

        assert len(alerts) == 1
        alert = alerts[0]
        assert alert.details["length"] == 3
        assert alert.details["return_ratio"] == 0.9
        assert alert.score == 0.9
        assert sorted(alert.node_ids) == ["a", "b", "c"]

    def test_found_once_whatever_the_rotation(self):
        edges = [
            tx("b", "c", 950, hours=1),
            tx("c", "a", 900, hours=2),
            tx("a", "b", 1000, hours=0),
        ]
        assert len(detect_cycles(edges, DetectionParams())) == 1

    def test_backwards_in_time_is_not_a_cycle(self):
        edges = [
            tx("a", "b", 1000, hours=2),
            tx("b", "c", 950, hours=1),
            tx("c", "a", 900, hours=0),
        ]
        # Every rotation has a step going back in time
        assert detect_cycles(edges, DetectionParams()) == []

    def test_undated_edges_fit_anywhere(self):
        edges = [tx("a", "b", 10), tx("b", "a", 10)]
        assert len(detect_cycles(edges, DetectionParams())) == 1

    def test_max_length(self):
        nodes = ["a", "b", "c", "d", "e"]
        edges = [tx(nodes[i], nodes[(i + 1) % 5], 10, hours=i) for i in range(5)]
        assert detect_cycles(edges, DetectionParams(cycle_max_length=4)) == []
        assert len(detect_cycles(edges, DetectionParams(cycle_max_length=5))) == 1

    def test_window(self):
        edges = [tx("a", "b", 10, hours=0), tx("b", "a", 10, hours=100)]
        assert detect_cycles(edges, DetectionParams(cycle_window_hours=24)) == []

    def test_self_transfers_ignored(self):
        assert detect_cycles([tx("a", "a", 10, hours=0)], DetectionParams()) == []


class TestRunDetectors:
    def test_sorted_by_score_and_filterable(self):
        edges = [
            tx("a", "b", 1000, hours=0),
            tx("b", "a", 100, hours=1),  # cycle with low return -> 0.6
        ]
        alerts = run_detectors(edges)
        assert [a.type for a in alerts] == ["cycle"]
        assert run_detectors(edges, only=["fan"]) == []

    def test_unknown_detector(self):
        with pytest.raises(ValueError):
            run_detectors([], only=["nope"])


class TestTrace:
    def edges(self):
        return [
            tx("victim", "mule", 1000, hours=0),
            tx("mule", "boss", 900, hours=5),
            tx("boss", "exchange", 800, hours=10),
            tx("mule", "earlier", 10, hours=-5),  # before the money arrived
            tx("other", "mule", 50, hours=1),
        ]

    def test_downstream_respects_time(self):
        result = trace_funds(self.edges(), "victim")
        assert result.nodes["mule"]["hops"] == 1
        assert result.nodes["boss"]["hops"] == 2
        assert result.nodes["exchange"]["hops"] == 3
        assert "earlier" not in result.nodes
        assert "other" not in result.nodes
        assert result.nodes["exchange"]["label"] == "label-exchange"
        assert len(result.edge_ids) == 3

    def test_max_hops(self):
        result = trace_funds(self.edges(), "victim", max_hops=2)
        assert set(result.nodes) == {"victim", "mule", "boss"}

    def test_upstream(self):
        result = trace_funds(self.edges(), "boss", direction="upstream")
        assert result.nodes["mule"]["hops"] == 1
        assert result.nodes["victim"]["hops"] == 2
        assert result.nodes["other"]["hops"] == 2
        assert "exchange" not in result.nodes

    def test_since(self):
        result = trace_funds(self.edges(), "mule", since=T0)
        assert "earlier" not in result.nodes
        assert "boss" in result.nodes


class TestSummary:
    def test_volumes_per_account_and_currency(self):
        edges = [
            tx("a", "b", 100, hours=0),
            tx("a", "c", 50, hours=1),
            tx("c", "a", 30, hours=2),
            tx("a", "b", 5, hours=3, currency="EUR"),
        ]
        summary = {(s.node_id, s.currency): s for s in summarize_accounts(edges)}

        a = summary[("a", "XOF")]
        assert (a.inflow, a.outflow, a.net) == (30, 150, -120)
        assert (a.tx_in, a.tx_out, a.senders, a.receivers) == (1, 2, 1, 2)
        assert a.first_seen == T0
        assert a.last_seen == T0 + 2 * H
        assert summary[("a", "EUR")].outflow == 5
        assert summarize_accounts(edges)[0].node_id == "a"


class TestLoaderAndService:
    def graph(self, records):
        graph = MagicMock()
        graph.sketch_id = "sketch-1"
        graph.query.return_value = records
        return graph

    def test_load_transactions(self):
        graph = self.graph(
            [
                {
                    "id": "r1",
                    "source": "n1",
                    "target": "n2",
                    "amount": 10,
                    "currency": "XOF",
                    "epoch": T0,
                    "source_label": "A",
                    "target_label": "B",
                },
                {"id": "r2", "source": "n1", "target": "n2", "amount": None},
            ]
        )
        edges = load_transactions(graph)

        assert len(edges) == 1
        assert edges[0].amount == 10.0
        assert edges[0].epoch == T0
        assert graph.query.call_args.args[1] == {"sketch_id": "sketch-1"}

    def test_service_detect(self):
        records = [
            {"id": "r1", "source": "a", "target": "b", "amount": 10, "epoch": T0},
            {"id": "r2", "source": "b", "target": "a", "amount": 10, "epoch": T0 + 1},
        ]
        service = TransactionAnalyticsService(self.graph(records))
        assert [a.type for a in service.detect()] == ["cycle"]
        assert service.trace("a").nodes["b"]["hops"] == 1
        assert len(service.summary(limit=1)) == 1
