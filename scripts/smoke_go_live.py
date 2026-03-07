# -*- coding: utf-8 -*-
"""Smoke checks rapidos para pre-go-live."""

from __future__ import annotations

import argparse
import json
import os
import random
import string
import subprocess
import sys
import time
import urllib.error
import urllib.request


def _run_compile_checks() -> tuple[bool, str]:
    files = [
        "run.py",
        "main_v2.py",
        "core/backend_client.py",
        "backend/app/main.py",
        "backend/app/services.py",
    ]
    cmd = [sys.executable, "-m", "compileall", *files]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    ok = proc.returncode == 0
    out = (proc.stdout or "") + (proc.stderr or "")
    return ok, out.strip()


def _request(
    base_url: str,
    method: str,
    path: str,
    payload: dict | None = None,
    *,
    headers_extra: dict | None = None,
) -> dict:
    url = f"{base_url.rstrip('/')}{path}"
    data = None
    headers = {"Content-Type": "application/json"}
    if isinstance(headers_extra, dict):
        for k, v in headers_extra.items():
            if k and (v is not None):
                headers[str(k)] = str(v)
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url=url, method=method.upper(), data=data, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=12) as resp:
            raw = (resp.read() or b"").decode("utf-8", errors="ignore")
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as ex:
        body = ""
        try:
            body = (ex.read() or b"").decode("utf-8", errors="ignore")
        except Exception:
            body = ""
        raise RuntimeError(f"HTTP {getattr(ex, 'code', 0)} {path}: {body}") from ex


def _request_with_retry(
    base_url: str,
    method: str,
    path: str,
    payload: dict | None = None,
    headers_extra: dict | None = None,
    *,
    attempts: int = 3,
    wait_s: float = 0.6,
) -> dict:
    tries = max(1, int(attempts))
    last_error: Exception | None = None
    for i in range(1, tries + 1):
        try:
            kwargs = {}
            if headers_extra is not None:
                kwargs["headers_extra"] = headers_extra
            return _request(base_url, method, path, payload, **kwargs)
        except Exception as ex:
            last_error = ex
            msg = str(ex or "").lower()
            transient = (" 502 " in msg) or (" 503 " in msg) or (" 504 " in msg) or ("timed out" in msg)
            if (not transient) or i >= tries:
                raise
            time.sleep(max(0.0, float(wait_s)) * i)
    if last_error is not None:
        raise last_error
    raise RuntimeError(f"Falha em {path}")


def _random_suffix(size: int = 8) -> str:
    return "".join(random.choice(string.ascii_lowercase + string.digits) for _ in range(size))


def _run_backend_online_smoke(base_url: str, full: bool = False, allow_missing_ready: bool = False) -> list[str]:
    logs: list[str] = []
    health = _request_with_retry(base_url, "GET", "/health")
    if not bool(health.get("ok")):
        raise RuntimeError("Falha em /health")
    logs.append("OK /health")
    try:
        ready = _request_with_retry(base_url, "GET", "/health/ready")
        if not bool(ready.get("ok")):
            raise RuntimeError("Falha em /health/ready")
        logs.append("OK /health/ready")
    except Exception as ex:
        msg = str(ex or "")
        if allow_missing_ready and "404" in msg and "/health/ready" in msg:
            logs.append("SKIP /health/ready (endpoint indisponivel)")
        else:
            raise

    if not full:
        return logs

    suffix = _random_suffix()
    email = f"smoke_{suffix}@quizvance.local"
    password = "abc123456"
    name = f"Smoke {suffix}"

    reg = _request(
        base_url,
        "POST",
        "/auth/register",
        {"name": name, "email_id": email, "password": password},
    )
    user_id = int(reg.get("user_id") or 0)
    if user_id <= 0:
        raise RuntimeError("Falha no registro smoke")
    logs.append("OK /auth/register")

    login = _request(
        base_url,
        "POST",
        "/auth/login",
        {"email_id": email, "password": password},
    )
    if int(login.get("user_id") or 0) != user_id:
        raise RuntimeError("Falha no login smoke")
    access_token = str(login.get("access_token") or "").strip()
    if not access_token:
        raise RuntimeError("Falha no login smoke: token ausente")
    auth_headers = {"Authorization": f"Bearer {access_token}"}
    logs.append("OK /auth/login")

    plan = _request(base_url, "GET", f"/plans/me/{user_id}", headers_extra=auth_headers)
    if int(plan.get("user_id") or 0) != user_id:
        raise RuntimeError("Falha em /plans/me")
    logs.append("OK /plans/me/{user_id}")

    checkout = _request(
        base_url,
        "POST",
        "/billing/checkout/start",
        {
            "user_id": user_id,
            "plan_code": "premium_30",
            "provider": "manual",
            "name": name,
            "email_id": email,
        },
        headers_extra=auth_headers,
    )
    checkout_id = str(checkout.get("checkout_id") or "").strip()
    auth_token = str(checkout.get("auth_token") or "").strip()
    if not checkout_id or not auth_token:
        raise RuntimeError("Falha ao iniciar checkout manual smoke")
    logs.append("OK /billing/checkout/start")

    confirm = _request(
        base_url,
        "POST",
        "/billing/checkout/confirm",
        {
            "user_id": user_id,
            "checkout_id": checkout_id,
            "auth_token": auth_token,
            "tx_id": f"smoke-tx-{suffix}",
            "provider": "manual",
        },
        headers_extra=auth_headers,
    )
    if not bool(confirm.get("ok")):
        raise RuntimeError("Falha ao confirmar checkout manual smoke")
    logs.append("OK /billing/checkout/confirm")

    usage = _request(
        base_url,
        "POST",
        "/usage/consume",
        {
            "user_id": user_id,
            "feature_key": "smoke_feature",
            "limit_per_day": 1,
        },
        headers_extra=auth_headers,
    )
    if "allowed" not in usage:
        raise RuntimeError("Falha em /usage/consume")
    logs.append("OK /usage/consume")

    return logs


def main():
    parser = argparse.ArgumentParser(description="Smoke go-live (compile + backend opcional)")
    parser.add_argument("--backend-url", default=os.getenv("BACKEND_URL", "").strip(), help="URL do backend")
    parser.add_argument("--online", action="store_true", help="Executa verificacao online no backend")
    parser.add_argument("--full", action="store_true", help="Executa fluxo completo online (cria usuario e checkout)")
    parser.add_argument(
        "--allow-missing-ready",
        action="store_true",
        help="Permite seguir no smoke online quando /health/ready nao existir (legacy).",
    )
    args = parser.parse_args()

    checks: list[str] = []

    ok_compile, out_compile = _run_compile_checks()
    if not ok_compile:
        print(out_compile)
        raise SystemExit(1)
    checks.append("OK compileall")

    if args.online:
        backend_url = str(args.backend_url or "").strip().rstrip("/")
        if not backend_url:
            raise SystemExit("Defina --backend-url ou BACKEND_URL para smoke online.")
        online_logs = _run_backend_online_smoke(
            backend_url,
            full=bool(args.full),
            allow_missing_ready=bool(args.allow_missing_ready),
        )
        checks.extend(online_logs)

    print("SMOKE STATUS")
    for line in checks:
        print(f"- {line}")


if __name__ == "__main__":
    main()
