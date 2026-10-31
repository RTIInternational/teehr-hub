import pytest

pytest.importorskip("teehr")

import ingests.nwps_rfc_streamflow_forecasts as nwps


class _FakeCrosswalks:
    def add_attributes(self, attr_list):
        return self

    def filter(self, filters):
        return self

    def to_sdf(self):
        return self

    def select(self, column):
        return self

    def collect(self):
        return [("nwpsrfc-abc",), ("nwpsrfc-def",), ("nwpsrfc-ghi",)]


class _FakeSpark:
    def stop(self):
        return None


class _FakeEvaluation:
    cache_dir = "/tmp/fake-cache"
    location_crosswalks = _FakeCrosswalks()
    spark = _FakeSpark()


class _FakeState:
    @staticmethod
    def is_completed():
        return True


class _FakeFuture:
    state = _FakeState()


def test_ingest_submits_every_endpoint(monkeypatch):
    submit_calls = []

    class _FakeFetchTask:
        @staticmethod
        def submit(**kwargs):
            submit_calls.append(kwargs["endpoint"]["RFC_lid"])
            return _FakeFuture()

    monkeypatch.setattr(nwps, "initialize_evaluation", lambda **kwargs: _FakeEvaluation())
    monkeypatch.setattr(nwps, "remove_dir_if_exists", lambda *args, **kwargs: None)
    monkeypatch.setattr(nwps, "query_last_reference_times", lambda **kwargs: {})
    monkeypatch.setattr(
        nwps,
        "generate_nwps_endpoints",
        lambda **kwargs: [{"RFC_lid": "abc"}, {"RFC_lid": "def"}, {"RFC_lid": "ghi"}],
    )
    monkeypatch.setattr(nwps, "fetch_nwps_rfc_fcst_to_cache", _FakeFetchTask())
    monkeypatch.setattr(nwps, "wait", lambda futures: (set(futures), set()))
    monkeypatch.setattr(nwps, "has_cache_data", lambda cache_dir: False)

    nwps.ingest_nwps_rfc_forecasts(temp_dir_path="/tmp", start_spark_cluster=False)

    assert submit_calls == ["abc", "def", "ghi"]
