# -*- coding: utf-8 -*-
# Flowxus/solver/runner/monitor.py

"""
Project: Flowxus
Author: Erfan Vaezi
Date: 9/23/2025 (Updated: 10/07/2025)

Purpose
-------
Small utilities for supervising solver output streams. Provide a fixed-size tail
snapshot for postmortems and a lightweight early-stop detector for common failure
signals (e.g., NaNs, floating-point exceptions) while streaming.

Main Tasks
----------
    1. Keep the last N lines from an arbitrary line iterator for concise summaries.
    2. Scan live output for case-insensitive error patterns and trigger early stop
       after a configurable number of hits.

Notes
-----
- Stateless helpers intended to be composed with subprocess pipes or file followers.
- Pattern matching is substring-based and case-insensitive by design (fast/robust).
"""

from __future__ import absolute_import
from typing import Iterable, Tuple
from collections import deque


def tail_lines(iter_lines: Iterable[str], n_tail: int = 25) -> str:
    """
    Return the last `n_tail` lines from a line iterator, joined by '\\n'.
    
    Args
    ----
    iter_lines : Iterable[str]
        Any iterable producing text lines (e.g., file handle, process stdout).
    n_tail : int, optional
        Number of trailing lines to retain (default: 25).

    Returns
    -------
    str
        The final `n_tail` lines joined by a single newline character.
    """
    dq = deque(maxlen=int(n_tail))
    for line in iter_lines:
        dq.append(line.rstrip("\n"))
    return "\n".join(dq)


def early_stop(iter_lines: Iterable[str],
               patterns: Tuple[str, ...] = ("nan", "floating point exception"),
               max_bad: int = 3) -> bool:
    """
    Detect repeated failure patterns in a stream and signal early termination.

    Performs a case-insensitive substring search for each pattern; increments a
    counter on every hit and returns True once `max_bad` hits have been observed.

    Args
    ----
    iter_lines : Iterable[str]
        Stream of lines to scan (e.g., live process output).
    patterns : Tuple[str, ...], optional
        Substrings to match case-insensitively (default: ("nan", "floating point exception")).
    max_bad : int, optional
        Number of matches required to trigger early stop (default: 3).

    Returns
    -------
    bool
        True if the number of matched lines reaches `max_bad`; False otherwise.
    """
    pats = [p.lower() for p in patterns]
    bad = 0
    for line in iter_lines:
        s = line.lower()
        if any(p in s for p in pats):
            bad += 1
            if bad >= int(max_bad):
                return True
    return False
