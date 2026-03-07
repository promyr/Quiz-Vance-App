# -*- coding: utf-8 -*-
"""
Guard de ações assíncronas — evita execução concorrente da mesma chave.

Uso:
    guard = AsyncActionGuard()
    ok = await guard.run("picker", _minha_coroutine, timeout_s=30,
                          on_start=..., on_timeout=..., on_error=..., on_finish=...)
"""

from __future__ import annotations

import asyncio
from typing import Any, Callable, Coroutine, Optional


class AsyncActionGuard:
    """Impede que a mesma chave de ação seja executada simultaneamente."""

    def __init__(self) -> None:
        self._running: set[str] = set()

    def is_running(self, key: str) -> bool:
        return key in self._running

    async def run(
        self,
        key: str,
        coro_fn: Callable[[], Coroutine[Any, Any, Any]],
        *,
        timeout_s: float = 60.0,
        on_start: Optional[Callable[[], Any]] = None,
        on_timeout: Optional[Callable[[], Any]] = None,
        on_error: Optional[Callable[[Exception], Any]] = None,
        on_finish: Optional[Callable[[], Any]] = None,
    ) -> bool:
        """
        Executa coro_fn sob a chave `key`.

        Retorna True se a execução completou (com ou sem erro), False se:
        - A chave já estava em execução (bloqueio concorrente), ou
        - Timeout foi atingido.
        """
        if key in self._running:
            return False

        self._running.add(key)

        if on_start is not None:
            try:
                on_start()
            except Exception:
                pass

        timed_out = False
        try:
            await asyncio.wait_for(coro_fn(), timeout=timeout_s)
        except asyncio.TimeoutError:
            timed_out = True
            if on_timeout is not None:
                try:
                    on_timeout()
                except Exception:
                    pass
        except Exception as exc:
            if on_error is not None:
                try:
                    on_error(exc)
                except Exception:
                    pass
        finally:
            self._running.discard(key)
            if on_finish is not None:
                try:
                    on_finish()
                except Exception:
                    pass

        return not timed_out


def state_async_guard(state: Optional[dict]) -> AsyncActionGuard:
    """Retorna (ou cria) o AsyncActionGuard armazenado em state['async_guard']."""
    if not isinstance(state, dict):
        return AsyncActionGuard()
    guard = state.get("async_guard")
    if isinstance(guard, AsyncActionGuard):
        return guard
    guard = AsyncActionGuard()
    state["async_guard"] = guard
    return guard
