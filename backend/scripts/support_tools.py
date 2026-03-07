#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Ferramentas de suporte operacional para billing."""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from typing import Any

from app.database import SessionLocal
from app import models, services, mercadopago


def _json_default(value: Any):
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def _print_json(payload: dict):
    print(json.dumps(payload, ensure_ascii=False, indent=2, default=_json_default))


def _user_snapshot(user_id: int) -> dict:
    db = SessionLocal()
    try:
        user = db.query(models.User).filter(models.User.id == int(user_id)).first()
        if not user:
            return {"ok": False, "message": "Usuario nao encontrado", "user_id": int(user_id)}
        plan = services.ensure_plan_row(db, user.id)
        checkouts = (
            db.query(models.CheckoutSession)
            .filter(models.CheckoutSession.user_id == user.id)
            .order_by(models.CheckoutSession.created_at.desc())
            .limit(20)
            .all()
        )
        payments = (
            db.query(models.Payment)
            .filter(models.Payment.user_id == user.id)
            .order_by(models.Payment.created_at.desc())
            .limit(20)
            .all()
        )
        return {
            "ok": True,
            "user": {
                "id": user.id,
                "name": user.name,
                "email_id": user.email_id,
            },
            "plan": {
                "plan_code": plan.plan_code,
                "premium_until": plan.premium_until,
                "premium_active": services.premium_active(plan),
                "trial_used": int(plan.trial_used or 0),
            },
            "recent_checkouts": [
                {
                    "checkout_id": row.checkout_id,
                    "plan_code": row.plan_code,
                    "status": row.status,
                    "provider": row.provider,
                    "amount_cents": int(row.amount_cents or 0),
                    "created_at": row.created_at,
                    "confirmed_at": row.confirmed_at,
                    "expires_at": row.expires_at,
                }
                for row in checkouts
            ],
            "recent_payments": [
                {
                    "provider": row.provider,
                    "provider_tx_id": row.provider_tx_id,
                    "plan_code": row.plan_code,
                    "status": row.status,
                    "amount_cents": int(row.amount_cents or 0),
                    "currency": row.currency,
                    "created_at": row.created_at,
                    "paid_at": row.paid_at,
                }
                for row in payments
            ],
        }
    finally:
        db.close()


def _checkout_snapshot(checkout_id: str) -> dict:
    db = SessionLocal()
    try:
        checkout = (
            db.query(models.CheckoutSession)
            .filter(models.CheckoutSession.checkout_id == str(checkout_id).strip())
            .first()
        )
        if not checkout:
            return {"ok": False, "message": "Checkout nao encontrado", "checkout_id": str(checkout_id).strip()}
        user = db.query(models.User).filter(models.User.id == int(checkout.user_id)).first()
        return {
            "ok": True,
            "checkout": {
                "checkout_id": checkout.checkout_id,
                "user_id": int(checkout.user_id),
                "user_email": user.email_id if user else "",
                "plan_code": checkout.plan_code,
                "status": checkout.status,
                "provider": checkout.provider,
                "amount_cents": int(checkout.amount_cents or 0),
                "currency": checkout.currency,
                "created_at": checkout.created_at,
                "confirmed_at": checkout.confirmed_at,
                "expires_at": checkout.expires_at,
            },
        }
    finally:
        db.close()


def _reconcile_checkout(checkout_id: str) -> dict:
    db = SessionLocal()
    try:
        checkout = (
            db.query(models.CheckoutSession)
            .filter(models.CheckoutSession.checkout_id == str(checkout_id).strip())
            .first()
        )
        if not checkout:
            return {"ok": False, "message": "Checkout nao encontrado"}
        if str(checkout.provider or "").lower() not in {"mercadopago", "mp"}:
            return {"ok": False, "message": "Checkout nao e do Mercado Pago"}

        payment = mercadopago.search_latest_payment_by_external_reference(str(checkout.checkout_id))
        if not payment:
            return {"ok": False, "message": "Pagamento ainda nao localizado no Mercado Pago"}
        status = str(payment.get("status") or "").strip().lower()
        if status != "approved":
            return {"ok": False, "message": f"Pagamento ainda nao aprovado (status: {status or 'desconhecido'})"}
        tx_id = str(payment.get("id") or "").strip()
        if not tx_id:
            return {"ok": False, "message": "Pagamento aprovado sem id de transacao"}

        currency = str(payment.get("currency_id") or "BRL").strip() or "BRL"
        amount_cents = int(round(float(payment.get("transaction_amount") or 0) * 100))
        ok, msg, _payment = services.finalize_checkout_payment(
            db,
            checkout,
            provider="mercadopago",
            tx_id=tx_id,
            amount_cents=amount_cents,
            currency=currency,
            plan_code=str(checkout.plan_code or "premium_30"),
        )
        if not ok:
            return {"ok": False, "message": msg}
        return {"ok": True, "message": msg, "checkout_id": checkout.checkout_id, "provider_tx_id": tx_id}
    finally:
        db.close()


def main():
    parser = argparse.ArgumentParser(description="Suporte operacional Quiz Vance Billing")
    sub = parser.add_subparsers(dest="cmd", required=True)

    user_cmd = sub.add_parser("user", help="Mostra resumo completo de usuario/plano/pagamentos")
    user_cmd.add_argument("--user-id", type=int, required=True, help="ID do usuario")

    checkout_cmd = sub.add_parser("checkout", help="Mostra detalhes de um checkout")
    checkout_cmd.add_argument("--checkout-id", required=True, help="Checkout ID")

    rec_cmd = sub.add_parser("reconcile", help="Reprocessa checkout com consulta no Mercado Pago")
    rec_cmd.add_argument("--checkout-id", required=True, help="Checkout ID")

    args = parser.parse_args()
    if args.cmd == "user":
        _print_json(_user_snapshot(int(args.user_id)))
        return
    if args.cmd == "checkout":
        _print_json(_checkout_snapshot(str(args.checkout_id)))
        return
    if args.cmd == "reconcile":
        _print_json(_reconcile_checkout(str(args.checkout_id)))
        return


if __name__ == "__main__":
    main()
