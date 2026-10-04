import httpx

from src.llm_client import RequestPacer, retry_delay


def test_pacer_reserves_request_slots(monkeypatch):
    monkeypatch.setattr("src.llm_client.time.monotonic", lambda: 100.0)
    pacer = RequestPacer(10)
    assert pacer.delay() == 0
    assert pacer.delay() == 6
    pacer.cooldown(60)
    assert pacer.delay() == 60


def test_retry_respects_retry_after():
    response = httpx.Response(429, headers={"Retry-After": "120"}, text="rate limited")
    assert retry_delay(response, 0) == 120


def test_daily_limit_is_not_retried():
    response = httpx.Response(429, text="free-models-per-day")
    assert retry_delay(response, 0) is None


def test_success_is_not_retried():
    assert retry_delay(httpx.Response(200, text="ok"), 0) is None
