# -*- coding: utf-8 -*-
"""View de planos/assinatura — extraída do main_v2.py."""

from __future__ import annotations

import asyncio
from typing import Optional

import flet as ft

from config import CORES
from core.datetime_utils import _format_datetime_label
from core.error_monitor import log_exception
from core.ui_route_theme import _color
from core.helpers.ui_helpers import (
    backend_user_id,
    close_dialog_compat,
    launch_url_compat,
    show_dialog_compat,
)


def _build_placeholder_body(title: str, description: str, navigate, dark: bool):
    return ft.Container(
        expand=True,
        bgcolor=_color("fundo", dark),
        padding=20,
        content=ft.Column([
            ft.Text(title, size=28, weight=ft.FontWeight.BOLD, color=_color("texto", dark)),
            ft.Text(description, size=14, color=_color("texto_sec", dark)),
            ft.ElevatedButton("Voltar ao Inicio", on_click=lambda _: navigate("/home")),
        ], spacing=10),
    )


def build_plans_body(state: dict, navigate, dark: bool) -> ft.Control:
    user = state.get("usuario") or {}
    db = state.get("db")
    backend = state.get("backend")
    page = state.get("page")
    if not db or not user.get("id"):
        return _build_placeholder_body("Planos", "E necessario login para gerenciar assinatura.", navigate, dark)

    sub = db.get_subscription_status(user["id"])
    plan_code = str(sub.get("plan_code") or "free")
    premium_active = bool(sub.get("premium_active"))
    premium_until = sub.get("premium_until")
    trial_used = int(sub.get("trial_used") or 0)

    status_text = ft.Text("", size=12, color=_color("texto_sec", dark))
    plan_value_text = ft.Text("", size=20, weight=ft.FontWeight.BOLD, color=_color("texto", dark))
    validade_value_text = ft.Text("", size=16, weight=ft.FontWeight.W_600, color=_color("texto", dark))
    operation_ring = ft.ProgressRing(width=16, height=16, stroke_width=2, visible=False)
    op_busy = {"value": False}
    checkout_state = {
        "checkout_id": "", "auth_token": "", "payment_code": "",
        "amount_cents": 0, "currency": "BRL", "plan_code": "",
        "provider": "", "checkout_url": "",
    }
    tx_id_field = ft.TextField(label="ID da transacao", hint_text="Cole o identificador do pagamento", width=280, visible=False)
    payment_code_field = ft.TextField(label="Codigo de pagamento", read_only=True, width=280, visible=False)
    confirm_payment_button = ft.ElevatedButton("Confirmar pagamento", icon=ft.Icons.VERIFIED, visible=False)
    open_checkout_button = ft.ElevatedButton("Abrir pagamento", icon=ft.Icons.OPEN_IN_NEW, visible=False)
    refresh_payment_button = ft.OutlinedButton("Ja paguei, verificar status", icon=ft.Icons.REFRESH, visible=False)
    cancel_checkout_button = ft.TextButton("Cancelar checkout", icon=ft.Icons.CLOSE, visible=False)
    subscribe_monthly_button = ft.ElevatedButton("Assinar Mensal", icon=ft.Icons.PAYMENT)
    checkout_info_text = ft.Text("", size=12, color=_color("texto_sec", dark), visible=False)
    PAID_PLAN_CODES = {"premium_30"}

    def _set_status(message: str, tone: str = "info"):
        tone_map = {"info": _color("texto_sec", dark), "success": CORES["sucesso"], "warning": CORES["warning"], "error": CORES["erro"]}
        status_text.value = str(message or "")
        status_text.color = tone_map.get(tone, tone_map["info"])

    def _set_busy(value: bool):
        busy = bool(value)
        op_busy["value"] = busy
        operation_ring.visible = busy
        subscribe_monthly_button.disabled = busy
        confirm_payment_button.disabled = busy
        open_checkout_button.disabled = busy
        refresh_payment_button.disabled = busy
        cancel_checkout_button.disabled = busy
        if page:
            page.update()

    def _is_paid_plan_active() -> bool:
        code = str(plan_code or "").strip().lower()
        return bool(premium_active and code in PAID_PLAN_CODES)

    def _refresh_labels():
        if str(plan_code or "").strip().lower() == "trial" and premium_active:
            plano_atual = "Trial"
        elif _is_paid_plan_active():
            plano_atual = "Premium"
        else:
            plano_atual = "Free (trial usado)" if trial_used else "Free"
        validade_fmt = _format_datetime_label(str(premium_until or "")) if premium_until and premium_active else ""
        if premium_active and str(plan_code or "").strip().lower() == "trial":
            validade = f"Cortesia ate {validade_fmt}" if validade_fmt else "Cortesia ativa"
        elif premium_active:
            validade = f"Ate {validade_fmt}" if validade_fmt else "Premium ativo"
        else:
            validade = "Sem premium ativo"
        plan_value_text.value = plano_atual
        validade_value_text.value = validade
        validade_value_text.color = CORES["primaria"] if premium_active else _color("texto", dark)

    def _apply_status(s: dict):
        state["usuario"].update(s)
        nonlocal plan_code, premium_active, premium_until, trial_used
        plan_code = str(s.get("plan_code") or "free")
        premium_active = bool(s.get("premium_active"))
        premium_until = s.get("premium_until")
        trial_used = int(s.get("trial_used") or 0)
        _refresh_labels()
        if page:
            page.update()

    async def _fetch_backend_status_async() -> Optional[dict]:
        if not (backend and backend.enabled()):
            return None
        try:
            backend_uid = backend_user_id(user)
            if int(backend_uid or 0) <= 0:
                return None
            if int(user.get("backend_user_id") or 0) <= 0:
                await asyncio.to_thread(backend.upsert_user, backend_uid, user.get("nome", ""), user.get("email", ""))
            b = await asyncio.to_thread(backend.get_plan, backend_uid)
            return {
                "plan_code": b.get("plan_code", "free"),
                "premium_active": 1 if b.get("premium_active") else 0,
                "premium_until": b.get("premium_until"),
                "trial_used": 1 if b.get("plan_code") == "trial" else int(user.get("trial_used", 0) or 0),
            }
        except Exception as ex:
            log_exception(ex, "plans_view._fetch_backend_status_async")
            return None

    async def _refresh_status_async():
        remote = await _fetch_backend_status_async()
        if remote is not None:
            try:
                await asyncio.to_thread(db.sync_subscription_status, int(user["id"]), str(remote.get("plan_code") or "free"), remote.get("premium_until"), int(remote.get("trial_used") or 0))
            except Exception as ex:
                log_exception(ex, "plans_view._refresh_status_async.persist")
            _apply_status(remote)
            return
        _apply_status(db.get_subscription_status(user["id"]))

    def _refresh_status(_=None):
        if not page:
            return
        page.run_task(_refresh_status_async)

    def _set_checkout_visibility(visible: bool):
        manual_confirm = bool(visible and not checkout_state.get("checkout_url"))
        tx_id_field.visible = manual_confirm
        payment_code_field.visible = bool(visible)
        confirm_payment_button.visible = manual_confirm
        open_checkout_button.visible = bool(visible and checkout_state.get("checkout_url"))
        refresh_payment_button.visible = bool(visible)
        cancel_checkout_button.visible = bool(visible)
        checkout_info_text.visible = bool(visible)

    def _show_checkout_popup():
        if not page:
            return
        url = str(checkout_state.get("checkout_url") or "").strip()
        if not url:
            return
        link_field = ft.TextField(label="Link de pagamento", value=url, read_only=True, multiline=True, min_lines=2, max_lines=3)
        msg = ft.Text(f"Finalize o pagamento de {checkout_state.get('currency', 'BRL')} {(int(checkout_state.get('amount_cents') or 0) / 100):.2f} no Mercado Pago.")

        def _copy_link(_=None):
            try:
                page.set_clipboard(url)
                page.snack_bar = ft.SnackBar(content=ft.Text("Link copiado."), bgcolor=CORES["sucesso"], show_close_icon=True)
                page.snack_bar.open = True
                page.update()
            except Exception:
                pass

        dlg = ft.AlertDialog(
            modal=True, title=ft.Text("Checkout Mensal"),
            content=ft.Column([msg, link_field], tight=True, spacing=8),
            actions=[
                ft.TextButton("Copiar link", on_click=_copy_link),
                ft.TextButton("Fechar", on_click=lambda _: close_dialog_compat(page, dlg)),
                ft.ElevatedButton("Abrir pagamento", icon=ft.Icons.OPEN_IN_NEW, on_click=lambda _: (launch_url_compat(page, url, "plans.checkout_popup"), close_dialog_compat(page, dlg))),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        show_dialog_compat(page, dlg)

    def _clear_checkout():
        checkout_state.update({"checkout_id": "", "auth_token": "", "payment_code": "", "amount_cents": 0, "currency": "BRL", "plan_code": "", "provider": "", "checkout_url": ""})
        tx_id_field.value = ""
        payment_code_field.value = ""
        checkout_info_text.value = ""
        _set_checkout_visibility(False)

    async def _start_checkout_async(plano: str):
        if op_busy["value"]:
            return
        if not (backend and backend.enabled()):
            _set_status("Compra premium exige backend online. Configure BACKEND_URL.", "error")
            if page:
                page.update()
            return
        b_uid = backend_user_id(user)
        if int(b_uid or 0) <= 0:
            _set_status("Conta ainda nao vinculada ao backend. Faca login online novamente.", "error")
            if page:
                page.update()
            return
        _set_busy(True)
        try:
            resp = await asyncio.to_thread(backend.start_checkout, int(b_uid), plano, "mercadopago", str(user.get("nome") or ""), str(user.get("email") or ""))
            if not bool(resp.get("ok")):
                _set_status(str(resp.get("message") or "Falha ao iniciar checkout."), "error")
                if page:
                    page.update()
                return
            checkout_state["checkout_id"] = str(resp.get("checkout_id") or "")
            checkout_state["auth_token"] = str(resp.get("auth_token") or "")
            checkout_state["payment_code"] = str(resp.get("payment_code") or "")
            checkout_state["amount_cents"] = int(resp.get("amount_cents") or 0)
            checkout_state["currency"] = str(resp.get("currency") or "BRL")
            checkout_state["plan_code"] = str(resp.get("plan_code") or plano)
            checkout_state["provider"] = str(resp.get("provider") or "")
            checkout_state["checkout_url"] = str(resp.get("checkout_url") or "").strip()
            payment_code_field.value = checkout_state["payment_code"]
            if checkout_state["checkout_url"]:
                checkout_info_text.value = f"Checkout iniciado para {checkout_state['plan_code']}. Valor: {checkout_state['currency']} {checkout_state['amount_cents'] / 100:.2f}. Abra o pagamento, conclua no Mercado Pago e depois toque em verificar status."
            else:
                checkout_info_text.value = f"Checkout iniciado para {checkout_state['plan_code']}. Valor: {checkout_state['currency']} {checkout_state['amount_cents'] / 100:.2f}. Apos pagar, informe o ID da transacao e confirme."
            _set_checkout_visibility(True)
            _set_status("Checkout criado. Complete o pagamento para liberar premium.", "warning")
            if checkout_state["checkout_url"]:
                _show_checkout_popup()
                try:
                    launch_url_compat(page, checkout_state["checkout_url"], "plans.start_checkout")
                except Exception:
                    pass
        except Exception as ex:
            log_exception(ex, "plans_view._start_checkout")
            _set_status(f"Falha ao iniciar checkout: {ex}", "error")
        finally:
            _set_busy(False)
        if page:
            page.update()

    async def _confirm_checkout_async(_=None):
        if op_busy["value"]:
            return
        checkout_id = str(checkout_state.get("checkout_id") or "")
        auth_token = str(checkout_state.get("auth_token") or "")
        tx_id = str(tx_id_field.value or "").strip()
        if not checkout_id or not auth_token:
            _set_status("Nenhum checkout pendente.", "error")
            if page:
                page.update()
            return
        if not tx_id:
            _set_status("Informe o ID da transacao para confirmar.", "error")
            if page:
                page.update()
            return
        if not (backend and backend.enabled()):
            _set_status("Backend offline. Nao e possivel confirmar pagamento.", "error")
            if page:
                page.update()
            return
        b_uid = backend_user_id(user)
        if int(b_uid or 0) <= 0:
            _set_status("Conta ainda nao vinculada ao backend.", "error")
            if page:
                page.update()
            return
        _set_busy(True)
        ok = False
        msg = "Falha ao confirmar pagamento."
        try:
            resp = await asyncio.to_thread(backend.confirm_checkout, int(b_uid), checkout_id, auth_token, tx_id)
            ok = bool(resp.get("ok"))
            msg = str(resp.get("message") or ("Pagamento confirmado." if ok else msg))
        except Exception as ex:
            log_exception(ex, "plans_view._confirm_checkout")
            ok = False
            msg = f"Falha ao confirmar pagamento: {ex}"
        _set_status(msg, "success" if ok else "error")
        if ok:
            await _refresh_status_async()
            _clear_checkout()
        _set_busy(False)
        if page:
            page.update()

    def _open_checkout(_=None):
        url = str(checkout_state.get("checkout_url") or "").strip()
        if not url:
            _set_status("Checkout sem link de pagamento.", "error")
            if page:
                page.update()
            return
        if page:
            _show_checkout_popup()
            try:
                launch_url_compat(page, url, "plans.open_checkout")
            except Exception:
                pass

    async def _refresh_after_payment_async(_=None):
        if op_busy["value"]:
            return
        _set_busy(True)
        checkout_id = str(checkout_state.get("checkout_id") or "").strip()
        reconcile_msg = ""
        if checkout_id and backend and backend.enabled():
            try:
                b_uid = backend_user_id(user)
                if int(b_uid or 0) <= 0:
                    raise RuntimeError("conta_nao_vinculada_backend")
                rec = await asyncio.wait_for(asyncio.to_thread(backend.reconcile_checkout, int(b_uid), checkout_id), timeout=5.5)
                reconcile_msg = str(rec.get("message") or "").strip()
            except Exception as ex:
                log_exception(ex, "plans_view._refresh_after_payment.reconcile")
                reconcile_msg = str(ex or "").strip()
        await _refresh_status_async()
        if _is_paid_plan_active():
            _set_status(reconcile_msg or "Pagamento confirmado. Premium ativo.", "success")
            _clear_checkout()
        else:
            if str(plan_code or "").strip().lower() == "trial":
                _set_status(reconcile_msg or "Seu trial esta ativo, mas pagamento ainda nao foi confirmado.", "warning")
            else:
                _set_status(reconcile_msg or "Pagamento ainda nao confirmado. Aguarde alguns segundos e tente novamente.", "warning")
        _set_busy(False)
        if page:
            page.update()

    def _start_checkout(_=None):
        if page:
            page.run_task(_start_checkout_async, "premium_30")

    def _confirm_checkout(_=None):
        if page:
            page.run_task(_confirm_checkout_async)

    def _refresh_after_payment(_=None):
        if page:
            page.run_task(_refresh_after_payment_async)

    confirm_payment_button.on_click = _confirm_checkout
    open_checkout_button.on_click = _open_checkout
    refresh_payment_button.on_click = _refresh_after_payment
    cancel_checkout_button.on_click = lambda _=None: (_clear_checkout(), page.update() if page else None)
    subscribe_monthly_button.on_click = _start_checkout

    _refresh_labels()

    backend_status_text = "Online ativo" if (backend and backend.enabled()) else "Offline local"
    backend_status_color = CORES["acento"] if (backend and backend.enabled()) else _color("texto_sec", dark)

    result = ft.Container(
        expand=True, bgcolor=_color("fundo", dark), padding=20,
        content=ft.Column([
            ft.Text("Planos", size=28, weight=ft.FontWeight.BOLD, color=_color("texto", dark)),
            ft.Text("Gerencie seu acesso Free/Premium.", size=14, color=_color("texto_sec", dark)),
            ft.Text(f"Sincronizacao: {backend_status_text}", size=12, color=backend_status_color),
            ft.Card(elevation=1, content=ft.Container(padding=12, content=ft.Column([
                ft.Text("Fluxo de compra premium", size=16, weight=ft.FontWeight.BOLD, color=_color("texto", dark)),
                payment_code_field, tx_id_field, checkout_info_text,
                ft.Row([operation_ring], alignment=ft.MainAxisAlignment.START),
                ft.Row([open_checkout_button, refresh_payment_button, confirm_payment_button, cancel_checkout_button], wrap=True, spacing=8),
            ], spacing=8))),
            ft.ResponsiveRow(controls=[
                ft.Container(col={"sm": 6, "md": 4}, content=ft.Card(elevation=1, content=ft.Container(padding=12, content=ft.Column([
                    ft.Text("Plano atual", size=12, color=_color("texto_sec", dark)), plan_value_text,
                ], spacing=4)))),
                ft.Container(col={"sm": 6, "md": 8}, content=ft.Card(elevation=1, content=ft.Container(padding=12, content=ft.Column([
                    ft.Text("Validade", size=12, color=_color("texto_sec", dark)), validade_value_text,
                ], spacing=4)))),
            ], spacing=8, run_spacing=8),
            ft.Card(elevation=1, content=ft.Container(padding=12, content=ft.Column([
                ft.Text("Free", size=16, weight=ft.FontWeight.BOLD, color=_color("texto", dark)),
                ft.Text("Questoes e flashcards ilimitados em modo economico/lento.", size=12, color=_color("texto_sec", dark)),
                ft.Text("Biblioteca: upload de 1 arquivo por vez.", size=12, color=_color("texto_sec", dark)),
                ft.Text("Dissertativa: 1 correcao por dia.", size=12, color=_color("texto_sec", dark)),
            ], spacing=4))),
            ft.ResponsiveRow(controls=[
                ft.Container(col={"sm": 12, "md": 12}, content=ft.Card(elevation=1, content=ft.Container(padding=12, content=ft.Column([
                    ft.Text("Mensal", size=16, weight=ft.FontWeight.BOLD, color=_color("texto", dark)),
                    ft.Text("Mesmo recurso, melhor custo-beneficio.", size=12, color=_color("texto_sec", dark)),
                    ft.Text("Biblioteca: upload ilimitado por envio.", size=12, color=_color("texto_sec", dark)),
                    subscribe_monthly_button,
                ], spacing=8)))),
            ], spacing=8, run_spacing=8),
            status_text,
            ft.ElevatedButton("Voltar ao Inicio", on_click=lambda _: navigate("/home")),
        ], spacing=12, scroll=ft.ScrollMode.AUTO),
    )
    if backend and backend.enabled() and page:
        try:
            page.run_task(_refresh_status_async)
        except Exception:
            pass
    return result
