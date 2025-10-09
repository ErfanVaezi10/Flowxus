# -*- coding: utf-8 -*-
# Flowxus/solver/ops/utils.py

"""
Project: Flowxus
Author: Erfan Vaezi
Date: 9/15/2025 (Updated: 10/09/2025)

Purpose
-------
Provide small, dependency-free utilities used by plotting and post-processing:
residual header categorization (NS vs turbulence) and simple smoothing kernels
(centered moving average and exponential moving average).

Main Tasks
----------
    1. Split canonical residual headers into (NS, turbulence) groups.
    2. Provide `moving_average` for quick denoising of series (odd window).
    3. Provide `ema` (exponential moving average) with α∈(0,1].

Notes
-----
- Header logic assumes prior normalization to upper-case SU2-style keys.
- Smoothers are intentionally simple; window/alpha handling is defensive.
"""

from __future__ import absolute_import
from typing import List, Tuple, Sequence

# Canonical NS residual headers (upper-case), as used by interface.history normalization.
_NS_SET = {"RES_RHO", "RES_RHO_U", "RES_RHO_V", "RES_RHO_W", "RES_RHO_E"}


def split_residual_headers(headers: Sequence[str]) -> Tuple[List[str], List[str]]:
    """
    Split residual headers into (ns, turb) lists based on canonical names.

    Anything starting with 'RES_' and not in the NS set is considered turbulence.

    Args
    ----
    headers : Sequence[str]
        Header tokens (already normalized to upper case is ideal, but we guard).

    Returns
    -------
    Tuple[List[str], List[str]]
        Two lists preserving the input order: (ns_headers, turb_headers).
    """
    ns, turb = [], []
    for h in headers:
        H = (h or "").strip().upper()
        if not H.startswith("RES_"):
            continue
        if H in _NS_SET:
            ns.append(H)
        else:
            turb.append(H)
    # Keep a stable order as they appear in the input header list
    return ns, turb


def moving_average(y: Sequence[float], k: int = 5) -> List[float]:
    """
    Centered moving average with an enforced odd window size.

    If an even `k` is provided, it is incremented by 1 to maintain symmetry.

    Args
    ----
    y : Sequence[float]
        Input series.
    k : int, optional
        Window size (default: 5). Coerced to at least 1 and made odd.

    Returns
    -------
    List[float]
        Smoothed series of the same length as `y`.
    """
    k = max(1, int(k))
    if k % 2 == 0:
        k += 1
    n = len(y)
    out: List[float] = []
    half = k // 2
    for i in range(n):
        j0 = max(0, i - half)
        j1 = min(n, i + half + 1)
        out.append(sum(y[j0:j1]) / float(j1 - j0))
    return out


def ema(y: Sequence[float], alpha: float = 0.2) -> List[float]:
    """
    Exponential moving average (EMA).

    Args
    ----
    y : Sequence[float]
        Input series.
    alpha : float, optional
        Smoothing coefficient in (0, 1]; values ≤0 are clamped to 1e-4,
        values >1 are clamped to 1.0.

    Returns
    -------
    List[float]
        EMA-smoothed series (same length as `y`).
    """
    a = float(alpha)
    a = 0.0001 if a <= 0 else (1.0 if a > 1.0 else a)
    out: List[float] = []
    s = None
    for v in y:
        s = v if s is None else a * v + (1.0 - a) * s
        out.append(float(s))
    return out
