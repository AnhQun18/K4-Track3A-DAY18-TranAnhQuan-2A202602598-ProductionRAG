from __future__ import annotations

import asyncio
import threading
import time

import httpx

from config import OPENAI_API_KEY, OPENAI_MODEL, OPENAI_REQUESTS_PER_MINUTE


class RequestPacer:
    def __init__(self, requests_per_minute: float):
        self.interval = 60.0 / requests_per_minute
        self.next_request = 0.0
        self.lock = threading.Lock()

    def delay(self) -> float:
        with self.lock:
            now = time.monotonic()
            scheduled = max(now, self.next_request)
            self.next_request = scheduled + self.interval
            return scheduled - now

    def cooldown(self, seconds: float) -> None:
        with self.lock:
            self.next_request = max(self.next_request, time.monotonic() + seconds)


PACER = RequestPacer(OPENAI_REQUESTS_PER_MINUTE)


def retry_delay(response: httpx.Response, attempt: int) -> float | None:
    if response.status_code not in (429, 502, 503, 504):
        return None
    if "per-day" in response.text or "daily" in response.text.lower():
        return None
    try:
        return max(60.0, float(response.headers.get("retry-after", "0")))
    except ValueError:
        return min(120.0, 60.0 * (attempt + 1))


class PacedTransport(httpx.HTTPTransport):
    def handle_request(self, request):
        for attempt in range(5):
            time.sleep(PACER.delay())
            response = super().handle_request(request)
            response.read()
            delay = retry_delay(response, attempt)
            if delay is None or attempt == 4:
                return response
            response.close()
            PACER.cooldown(delay)
            print(f"  OpenRouter retry after {delay:.0f}s", flush=True)


class AsyncPacedTransport(httpx.AsyncHTTPTransport):
    async def handle_async_request(self, request):
        for attempt in range(5):
            await asyncio.sleep(PACER.delay())
            response = await super().handle_async_request(request)
            await response.aread()
            delay = retry_delay(response, attempt)
            if delay is None or attempt == 4:
                return response
            await response.aclose()
            PACER.cooldown(delay)
            print(f"  OpenRouter retry after {delay:.0f}s", flush=True)


def get_openai_client():
    from openai import OpenAI

    return OpenAI(
        api_key=OPENAI_API_KEY,
        max_retries=0,
        http_client=httpx.Client(transport=PacedTransport(), timeout=120),
    )


def get_evaluation_llm():
    from langchain_openai import ChatOpenAI

    return ChatOpenAI(
        model=OPENAI_MODEL,
        temperature=0,
        max_tokens=1024,
        max_retries=0,
        http_client=httpx.Client(transport=PacedTransport(), timeout=120),
        http_async_client=httpx.AsyncClient(transport=AsyncPacedTransport(), timeout=120),
    )
