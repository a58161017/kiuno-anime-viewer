"""Shared HTTP utilities: rate-limited GET/POST with retry + on-disk cache."""
from __future__ import annotations
import hashlib
import json
import time
from pathlib import Path
from typing import Any, Optional

import requests

from config import (
    CACHE_DIR, RATE_LIMITS, REQUEST_TIMEOUT, RETRY_MAX, RETRY_BACKOFF, USER_AGENT,
)

_last_call: dict[str, float] = {}


def _throttle(source: str) -> None:
    delay = RATE_LIMITS.get(source, 0.5)
    last = _last_call.get(source, 0.0)
    wait = (last + delay) - time.monotonic()
    if wait > 0:
        time.sleep(wait)
    _last_call[source] = time.monotonic()


def _cache_path(source: str, key: str) -> Path:
    safe = hashlib.sha1(key.encode("utf-8")).hexdigest()[:16]
    d = CACHE_DIR / source
    d.mkdir(parents=True, exist_ok=True)
    return d / f"{safe}.json"


def _read_cache(path: Path) -> Optional[Any]:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _write_cache(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def cached_request(
    source: str,
    method: str,
    url: str,
    *,
    params: Optional[dict] = None,
    json_body: Optional[dict] = None,
    headers: Optional[dict] = None,
    cache_key: Optional[str] = None,
    use_cache: bool = True,
) -> Optional[dict]:
    """Run an HTTP request with throttling, retry, and on-disk JSON cache.

    Returns the parsed JSON response (dict) or None on permanent failure.
    """
    key = cache_key or f"{method}|{url}|{json.dumps(params, sort_keys=True)}|{json.dumps(json_body, sort_keys=True)}"
    cpath = _cache_path(source, key)

    if use_cache:
        cached = _read_cache(cpath)
        if cached is not None:
            return cached

    h = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    if headers:
        h.update(headers)

    last_err: Optional[Exception] = None
    for attempt in range(RETRY_MAX):
        _throttle(source)
        try:
            resp = requests.request(
                method, url,
                params=params, json=json_body, headers=h,
                timeout=REQUEST_TIMEOUT,
            )
            if resp.status_code == 429:
                wait = float(resp.headers.get("Retry-After", RETRY_BACKOFF * (attempt + 1)))
                time.sleep(wait)
                continue
            if 500 <= resp.status_code < 600:
                time.sleep(RETRY_BACKOFF * (attempt + 1))
                last_err = RuntimeError(f"{resp.status_code}: {resp.text[:200]}")
                continue
            if resp.status_code == 404:
                _write_cache(cpath, {"_not_found": True})
                return None
            resp.raise_for_status()
            data = resp.json()
            _write_cache(cpath, data)
            return data
        except (requests.Timeout, requests.ConnectionError) as e:
            last_err = e
            time.sleep(RETRY_BACKOFF * (attempt + 1))
        except Exception as e:
            last_err = e
            break

    print(f"[http] {source} {method} {url} failed after {RETRY_MAX} attempts: {last_err}")
    return None


def is_cached_not_found(data: Optional[dict]) -> bool:
    return isinstance(data, dict) and data.get("_not_found") is True
