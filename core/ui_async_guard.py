# -*- coding: utf-8 -*-
"""Guard universal para acoes async de UI (loading/cancel/error)."""

from __future__ import annotations

import asyncio
from typing import Awaitable, Callable, Optional


class AsyncActionGuard:
    """Evita execucao concorrente da mesma acao e garante cleanup."""

    def __init__(self):
        self._running: set[str] = set()

    def is_running(self, key: str) -> bool:
        return str(key or "") in self._running

    async def run(
        self,
        key: str,
        action: Callable[[], Awaitable[None]] | Awaitable[None],
        *,
        timeout_s: Optional[float] = None,
        on_start: Optional[Callable[[], None]] = None,
        on_cancel: Optional[Callable[[], None]] = None,
        on_timeout: Optional[Callable[[], None]] = None,
        on_error: Optional[Callable[[Exception], None]] = None,
        on_finish: Optional[Callable[[], None]] = None,
    ) -> bool:
        action_key = str(key or "").strip() or "default"
        if action_key in self._running:
            return False

        self._running.add(action_key)
        try:
            if callable(on_start):
                on_start()

            task = action() if callable(action) else action
            if timeout_s and timeout_s > 0:
                await asyncio.wait_for(task, timeout=float(timeout_s))
            else:
                await task
            return True
        except asyncio.CancelledError:
            if callable(on_cancel):
                on_cancel()
            return False
        except asyncio.TimeoutError as ex:
            if callable(on_timeout):
                on_timeout()
            elif callable(on_error):
                on_error(ex)
            return False
        except Exception as ex:
            if callable(on_error):
                on_error(ex)
            return False
        finally:
            self._running.discard(action_key)
            if callable(on_finish):
                on_finish()


def state_async_guard(state: Optional[dict]) -> AsyncActionGuard:
    if not isinstance(state, dict):
        return AsyncActionGuard()
    guard = state.get('async_guard')
    if isinstance(guard, AsyncActionGuard):
        return guard
    guard = AsyncActionGuard()
    state['async_guard'] = guard
    return guard
