
from __future__ import annotations

import signal
import threading
import time
from typing import Optional, Sequence

from valutatrade_hub.logging_config import setup_logging
from valutatrade_hub.core.exceptions import ApiRequestError
from .api_clients import CoinGeckoClient, ExchangeRateApiClient
from .storage import RatesStorage
from .updater import RatesUpdater

__all__ = ["ParserScheduler", "run_once"]

logger = setup_logging()

class ParserScheduler:
    """
    Планировщик периодического опроса внешних API для обновления курсов валют. 
    Запускает фоновый поток, который по таймеру вызывает RatesUpdater.
    :param interval_seconds: Интервал между обновлениями в секундах (по умолчанию 300).
    :param sources: Источники данных: "coingecko", "exchangerate". По умолчанию оба.
    :param storage: Хранилище курсов валют.
    """

    def __init__(
        self,
        interval_seconds: int = 300,
        sources: Optional[Sequence[str]] = None,
        storage: Optional[RatesStorage] = None,
    ) -> None:
        self.interval_seconds = int(max(1, interval_seconds))
        self.sources = tuple((sources or ("coingecko", "exchangerate")))
        self.storage = storage or RatesStorage()
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run_loop, name="vth.parser.scheduler", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()

    def join(self, timeout: Optional[float] = None) -> None:
        t = self._thread
        if t is not None:
            t.join(timeout)

    def run_once(self) -> dict:
        updater = self._build_updater()
        return updater.run_update(sources=self.sources)

    def _run_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                self.run_once()
            except ApiRequestError as e:
                logger.error("Parser update failed: %s", e)
            except Exception as e:
                logger.exception("Unexpected error in parser scheduler: %s", e)
            self._stop_event.wait(self.interval_seconds)

    def _build_updater(self) -> RatesUpdater:
        clients = []
        if "coingecko" in self.sources:
            clients.append(CoinGeckoClient())
        if "exchangerate" in self.sources:
            clients.append(ExchangeRateApiClient())
        return RatesUpdater(clients=clients, storage=self.storage)

def run_once(sources: Optional[Sequence[str]] = None) -> dict:
    """Запускает однократное обновление курсов из указанных источников.
    :param sources: Источники данных: "coingecko", "exchangerate". По умолчанию оба.
    :return: Результат обновления в виде словаря.
    """
    sch = ParserScheduler(interval_seconds=0, sources=sources)
    return sch.run_once()

def _install_signal_handlers(s: ParserScheduler) -> None:
    def _handler(signum, frame):  
        logger.info("Stopping parser scheduler on signal %s", signum)
        s.stop()
    try:
        signal.signal(signal.SIGINT, _handler)
        signal.signal(signal.SIGTERM, _handler)
    except Exception:
        pass

if __name__ == "__main__":
    sched = ParserScheduler()
    _install_signal_handlers(sched)
    logger.info("Starting parser scheduler with interval=%ss sources=%s", sched.interval_seconds, ",".join(sched.sources))
    sched.start()
    try:
        while True:
            time.sleep(1)
            if not sched._thread or not sched._thread.is_alive():
                break
    finally:
        sched.stop()
        sched.join(5.0)
        logger.info("Parser scheduler stopped")