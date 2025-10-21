# valutatrade_hub/decorators.py
from __future__ import annotations

import functools
import logging
from time import perf_counter
from typing import Any, Callable, Optional

actions_logger = logging.getLogger("vth.actions")

def log_action(action: str, verbose: bool = False):
    """
    Логирует операции.
    Формат:
      INFO 2025-10-09T12:05:22 BUY user='alice' currency='BTC' amount=0.0500 rate=59300.00 base='USD' result=OK
    При исключении: result=ERROR type=... msg=...

    verbose=True: добавляет контекст (before/after из result['portfolio_changes'] если есть).
    """
    def _wrap(fn: Callable[..., Any]):
        @functools.wraps(fn)
        def inner(*args, **kwargs):
            t0 = perf_counter()
            username = kwargs.get("username") or ""
            currency = kwargs.get("currency") or kwargs.get("frm") or kwargs.get("to") or ""
            amount = kwargs.get("amount") or ""

            try:
                res = fn(*args, **kwargs)
                dt = perf_counter() - t0
                line = f"{action} user='{username}' currency='{currency}' amount={amount}"
                if isinstance(res, dict):
                    base = res.get("base")
                    rate = res.get("rate_used") or res.get("rate")
                    if base: line += f" base='{base}'"
                    if rate: line += f" rate={rate}"
                line += " result=OK"

                if verbose and isinstance(res, dict):
                    ch = res.get("portfolio_changes")
                    if isinstance(ch, dict):
                        # добавим в лог ключевые изменения
                        parts = []
                        for k, v in ch.items():
                            parts.append(f"{k}: {v.get('before')}→{v.get('after')}")
                        if parts:
                            line += " changes=[" + "; ".join(parts) + "]"

                actions_logger.info(line + f" time={dt:.3f}s")
                return res

            except Exception as e:
                dt = perf_counter() - t0
                actions_logger.error(f"{action} result=ERROR type={type(e).__name__} msg='{e}' time={dt:.3f}s")
                raise
        return inner
    return _wrap