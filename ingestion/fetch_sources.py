"""Resilient openFDA client: timeout, bounded retries with backoff, pagination, no secrets in code.
The API key (optional) is read from the OPENFDA_API_KEY environment variable by the caller."""
from __future__ import annotations
import json, time, urllib.error, urllib.parse, urllib.request
from typing import Callable, Optional

BASE_URL = "https://api.fda.gov/drug/shortages.json"
MAX_SKIP = 25000  # openFDA paging limit; beyond this use the bulk download instead


class SourceUnavailable(RuntimeError):
    pass


def default_transport(url: str, timeout: float):
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return r.status, r.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise ConnectionError(str(e)) from e


class OpenFDAClient:
    def __init__(self, api_key: Optional[str] = None, transport: Callable = default_transport,
                 timeout: float = 30, max_retries: int = 3, backoff: float = 1.0,
                 sleep: Callable = time.sleep, base_url: str = BASE_URL):
        self.api_key, self.transport, self.timeout = api_key, transport, timeout
        self.max_retries, self.backoff, self.sleep, self.base_url = max_retries, backoff, sleep, base_url

    def _url(self, skip: int, limit: int, search: Optional[str]) -> str:
        q = {"limit": limit, "skip": skip}
        if search:
            q["search"] = search
        if self.api_key:
            q["api_key"] = self.api_key
        return f"{self.base_url}?{urllib.parse.urlencode(q)}"

    def _get(self, url: str) -> dict:
        last = "unknown error"
        for attempt in range(self.max_retries + 1):
            try:
                status, body = self.transport(url, self.timeout)
            except ConnectionError as e:
                status, body, last = None, "", f"network error: {e}"
            if status == 200:
                return json.loads(body)
            if status == 404:            # openFDA uses 404 for "no matches"
                return {"results": [], "meta": {"results": {"total": 0}}}
            if status is not None:
                last = f"HTTP {status}"
            if status is not None and status not in (429, 500, 502, 503, 504):
                break                    # non-retryable
            if attempt < self.max_retries:
                self.sleep(self.backoff * (2 ** attempt))
        # never include the URL (it may contain the api key) in the message
        raise SourceUnavailable(f"openFDA request failed after retries: {last}")

    def fetch_all(self, page_size: int = 1000, max_records: Optional[int] = None,
                  search: Optional[str] = None) -> list:
        out, skip = [], 0
        while True:
            if skip > MAX_SKIP:
                raise SourceUnavailable("openFDA skip limit reached; use the bulk download endpoint")
            data = self._get(self._url(skip, page_size, search))
            batch = data.get("results", [])
            out.extend(batch)
            total = data.get("meta", {}).get("results", {}).get("total", len(out))
            skip += page_size
            if not batch or len(out) >= total or (max_records and len(out) >= max_records):
                break
        return out[:max_records] if max_records else out
