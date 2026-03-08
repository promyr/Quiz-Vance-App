# -*- coding: utf-8 -*-
import json
import os
import urllib.request
import urllib.error
import threading
import time
from typing import Optional, Dict, Any


class BackendClient:
    def __init__(self):
        base = (
            os.getenv("BACKEND_URL")
            or os.getenv("QUIZ_VANCE_BACKEND_URL")
            or os.getenv("BACKEND_PUBLIC_URL")
            or "https://quiz-vance-backend.fly.dev"
        )
        self.base_url = str(base or "").strip().rstrip("/")
        self.app_secret = (os.getenv("APP_BACKEND_SECRET") or "").strip()
        self.access_token = (os.getenv("BACKEND_ACCESS_TOKEN") or "").strip()
        self.timeout = float(os.getenv("BACKEND_TIMEOUT", "3.2"))
        self.plan_timeout = float(os.getenv("BACKEND_PLAN_TIMEOUT", "4.5"))
        self._http_retries = max(0, int(os.getenv("BACKEND_HTTP_RETRIES", "1") or 1))
        self._plan_cache_ttl_s = max(0.0, float(os.getenv("BACKEND_PLAN_CACHE_TTL", "8")))
        self._plan_cache: Dict[int, tuple[float, Dict[str, Any]]] = {}
        self._plan_cache_lock = threading.Lock()

    def set_access_token(self, token: Optional[str]) -> None:
        self.access_token = str(token or "").strip()

    def clear_access_token(self) -> None:
        self.access_token = ""

    def enabled(self) -> bool:
        return bool(self.base_url and self.base_url.startswith("http"))

    def invalidate_plan_cache(self, user_id: Optional[int] = None) -> None:
        with self._plan_cache_lock:
            if user_id is None:
                self._plan_cache.clear()
                return
            self._plan_cache.pop(int(user_id), None)

    def _get_cached_plan(self, user_id: int) -> Optional[Dict[str, Any]]:
        if self._plan_cache_ttl_s <= 0:
            return None
        now = time.monotonic()
        with self._plan_cache_lock:
            cached = self._plan_cache.get(int(user_id))
            if not cached:
                return None
            ts, payload = cached
            if (now - ts) > self._plan_cache_ttl_s:
                self._plan_cache.pop(int(user_id), None)
                return None
            return dict(payload)

    def _get_cached_plan_stale(self, user_id: int) -> Optional[Dict[str, Any]]:
        with self._plan_cache_lock:
            cached = self._plan_cache.get(int(user_id))
            if not cached:
                return None
            _ts, payload = cached
            return dict(payload)

    def _set_cached_plan(self, user_id: int, payload: Dict[str, Any]) -> None:
        if self._plan_cache_ttl_s <= 0:
            return
        with self._plan_cache_lock:
            self._plan_cache[int(user_id)] = (time.monotonic(), dict(payload or {}))

    def _request(
        self,
        method: str,
        path: str,
        payload: Optional[Dict] = None,
        *,
        timeout: Optional[float] = None,
        retries: Optional[int] = None,
    ) -> Dict[str, Any]:
        if not self.enabled():
            raise RuntimeError("backend_disabled")
        url = f"{self.base_url}{path}"
        data = None
        headers = {"Content-Type": "application/json"}
        if self.app_secret:
            headers["X-App-Secret"] = self.app_secret
        if self.access_token:
            headers["Authorization"] = f"Bearer {self.access_token}"
        if payload is not None:
            data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        timeout_s = self.timeout if timeout is None else max(0.4, float(timeout))
        attempts = (self._http_retries if retries is None else max(0, int(retries))) + 1
        last_err: Optional[Exception] = None

        for attempt in range(1, attempts + 1):
            req = urllib.request.Request(url, data=data, headers=headers, method=method.upper())
            try:
                with urllib.request.urlopen(req, timeout=timeout_s) as resp:
                    raw = resp.read().decode("utf-8")
                    return json.loads(raw) if raw else {}
            except urllib.error.HTTPError as e:
                detail = ""
                code = int(getattr(e, "code", 0) or 0)
                try:
                    raw = (e.read() or b"").decode("utf-8", errors="ignore")
                    data_err = json.loads(raw) if raw else {}
                    detail = str(data_err.get("detail") or data_err.get("message") or "")
                except Exception:
                    detail = ""
                msg = detail or f"HTTP {getattr(e, 'code', 'erro')}"
                last_err = RuntimeError(msg)
                if code == 401:
                    self.clear_access_token()
                # Retry apenas para erros transientes.
                if code in {408, 429, 500, 502, 503, 504} and attempt < attempts:
                    time.sleep(0.12 * attempt)
                    continue
                raise last_err from e
            except urllib.error.URLError as e:
                last_err = RuntimeError(f"backend_unreachable: {e.reason}")
                if attempt < attempts:
                    time.sleep(0.12 * attempt)
                    continue
                raise last_err from e

        if last_err is not None:
            raise last_err
        raise RuntimeError("backend_request_failed")

    def register(self, name: str, email_id: str, password: str) -> Dict[str, Any]:
        resp = self._request(
            "POST",
            "/auth/register",
            {"name": str(name or ""), "email_id": str(email_id or "").lower(), "password": str(password or "")},
        )
        token = str(resp.get("access_token") or "").strip() if isinstance(resp, dict) else ""
        if token:
            self.set_access_token(token)
        return resp

    def login(self, email_id: str, password: str) -> Dict[str, Any]:
        resp = self._request(
            "POST",
            "/auth/login",
            {"email_id": str(email_id or "").lower(), "password": str(password or "")},
        )
        token = str(resp.get("access_token") or "").strip() if isinstance(resp, dict) else ""
        if token:
            self.set_access_token(token)
        return resp

    def upsert_user(self, user_id: int, name: str, email_id: str) -> Dict[str, Any]:
        return self._request(
            "POST",
            "/internal/upsert-user",
            {"user_id": int(user_id), "name": str(name or ""), "email_id": str(email_id or "").lower()},
        )

    def get_user_settings(self, user_id: int) -> Dict[str, Any]:
        uid = int(user_id)
        return self._request("GET", f"/internal/user-settings/{uid}", timeout=self.plan_timeout, retries=1)

    def upsert_user_settings(
        self,
        user_id: int,
        provider: str,
        model: str,
        api_key: Optional[str],
        economia_mode: bool,
        telemetry_opt_in: bool,
        api_key_gemini: Optional[str] = None,
        api_key_openai: Optional[str] = None,
        api_key_groq: Optional[str] = None,
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "user_id": int(user_id),
            "provider": str(provider or "gemini").strip().lower(),
            "model": str(model or "gemini-2.5-flash").strip(),
            "api_key": (str(api_key).strip() if api_key is not None else None),
            "economia_mode": bool(economia_mode),
            "telemetry_opt_in": bool(telemetry_opt_in),
        }
        if api_key_gemini is not None:
            payload["api_key_gemini"] = str(api_key_gemini).strip() or None
        if api_key_openai is not None:
            payload["api_key_openai"] = str(api_key_openai).strip() or None
        if api_key_groq is not None:
            payload["api_key_groq"] = str(api_key_groq).strip() or None
        return self._request(
            "POST",
            "/internal/user-settings",
            payload,
        )

    def get_plan(self, user_id: int) -> Dict[str, Any]:
        uid = int(user_id)
        cached = self._get_cached_plan(uid)
        if cached is not None:
            return cached
        stale = self._get_cached_plan_stale(uid)
        try:
            resp = self._request("GET", f"/plans/me/{uid}", timeout=self.plan_timeout, retries=1)
            if isinstance(resp, dict):
                self._set_cached_plan(uid, resp)
            return resp
        except Exception:
            if stale is not None:
                return stale
            raise

    def start_checkout(
        self,
        user_id: int,
        plan_code: str,
        provider: str = "mercadopago",
        name: str = "",
        email_id: str = "",
    ) -> Dict[str, Any]:
        uid = int(user_id)
        return self._request(
            "POST",
            "/billing/checkout/start",
            {
                "user_id": uid,
                "plan_code": str(plan_code),
                "provider": str(provider or "manual"),
                "name": str(name or ""),
                "email_id": str(email_id or "").lower(),
            },
        )

    def confirm_checkout(
        self,
        user_id: int,
        checkout_id: str,
        auth_token: str,
        tx_id: str,
        provider: str = "mercadopago",
    ) -> Dict[str, Any]:
        uid = int(user_id)
        resp = self._request(
            "POST",
            "/billing/checkout/confirm",
            {
                "user_id": uid,
                "checkout_id": str(checkout_id or ""),
                "auth_token": str(auth_token or ""),
                "tx_id": str(tx_id or ""),
                "provider": str(provider or "manual"),
            },
        )
        self.invalidate_plan_cache(uid)
        return resp

    def reconcile_checkout(self, user_id: int, checkout_id: str) -> Dict[str, Any]:
        uid = int(user_id)
        resp = self._request(
            "POST",
            "/billing/checkout/reconcile",
            {
                "user_id": uid,
                "checkout_id": str(checkout_id or ""),
            },
        )
        self.invalidate_plan_cache(uid)
        return resp

    def consume_usage(self, user_id: int, feature_key: str, limit_per_day: int) -> Dict[str, Any]:
        return self._request(
            "POST",
            "/usage/consume",
            {
                "user_id": int(user_id),
                "feature_key": str(feature_key),
                "limit_per_day": int(limit_per_day),
            },
        )

    def sync_quiz_stats_batch(self, user_id: int, events: list[Dict[str, Any]]) -> Dict[str, Any]:
        payload_events = []
        for ev in list(events or []):
            if not isinstance(ev, dict):
                continue
            event_id = str(ev.get("event_id") or "").strip()
            if not event_id:
                continue
            payload_events.append(
                {
                    "event_id": event_id,
                    "questoes_delta": int(ev.get("questoes_delta") or 0),
                    "acertos_delta": int(ev.get("acertos_delta") or 0),
                    "xp_delta": int(ev.get("xp_delta") or 0),
                    "correta": bool(ev.get("correta")),
                    "occurred_at": (str(ev.get("occurred_at")).strip() if ev.get("occurred_at") else None),
                }
            )
        return self._request(
            "POST",
            "/internal/stats/quiz/batch",
            {"user_id": int(user_id), "events": payload_events},
        )

    def get_quiz_stats_summary(self, user_id: int) -> Dict[str, Any]:
        import time as _time
        uid = int(user_id)
        # Calcular offset UTC do timezone local em horas (ex: -3.0 para Brasilia)
        local_offset_hours = round(-_time.timezone / 3600.0, 1) if not _time.daylight else round(-_time.altzone / 3600.0, 1)
        return self._request(
            "GET",
            f"/internal/stats/quiz/summary/{uid}?tz_offset_hours={local_offset_hours}",
            timeout=self.plan_timeout,
            retries=1,
        )
