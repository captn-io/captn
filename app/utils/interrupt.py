#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Cooperative interrupt handling for long-running captn operations."""

import signal
import threading

_interrupt_requested = threading.Event()


def install_interrupt_handlers() -> None:
    """Ensure SIGINT/SIGTERM raise KeyboardInterrupt in the main thread."""

    def handler(signum, frame):
        _interrupt_requested.set()
        raise KeyboardInterrupt

    signal.signal(signal.SIGINT, handler)
    signal.signal(signal.SIGTERM, handler)


def check_interrupted() -> None:
    """Raise KeyboardInterrupt when a shutdown signal was received."""
    if _interrupt_requested.is_set():
        raise KeyboardInterrupt
