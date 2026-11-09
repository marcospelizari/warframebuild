"""numpy evaluator: the same model as `evaluate_py`, vectorised over events x enemies.

The timeline does not depend on the enemy, so every fight is a few matrix products and
cumulative sums: shield damage until the shield breaks (first index where the running
sum reaches it), then health damage until the kill. Run with `uv run --with numpy`; numpy
is not a project dependency (decided by this spike).
"""

from collections.abc import Sequence
from typing import Any

import numpy as np
import numpy.typing as npt

from app.domain.effects import DamageType
from bench.evaluate_py import MIN_REMOVED
from bench.timeline import ARMOR_CAP, HEAT_STEPS, blast_events, heat_start, offsets, shot_times
from bench.workload import CAP_S, Enemy, ShotModel

Array = npt.NDArray[Any]


def _amp(n: Array) -> Array:
    return np.where(n <= 0, 1.0, np.where(n < 1, 1 + n, 2 + 0.25 * (np.minimum(n, 10.0) - 1)))


def _corrosive_kept(n: Array) -> Array:
    return np.where(
        n <= 0, 1.0, np.where(n < 1, 1 - 0.26 * n, 1 - np.minimum(0.8, 0.26 + 0.06 * (n - 1)))
    )


def _heat_kept(elapsed: Array) -> Array:
    conditions = [elapsed <= 0] + [elapsed < below for below, _ in HEAT_STEPS]
    return np.select(conditions, [1.0] + [kept for _, kept in HEAT_STEPS], 0.5)


def timeline(model: ShotModel) -> tuple[tuple[DamageType, ...], Array, Array, Array, Array]:
    """types, times (N), armored (N x K), unarmored (N x K), state (3 x N: mag, vir, kept)."""
    o = offsets(model)
    shots_list = shot_times(model)
    shots = np.array(shots_list)
    arm, un = np.array(o.armored), np.array(o.unarmored)
    n_off, k = arm.shape
    times = (shots[:, None] + np.arange(n_off)[None, :]).ravel()
    keep = times <= CAP_S
    times = times[keep]
    arm_ev = np.broadcast_to(arm, (len(shots), n_off, k)).reshape(-1, k)[keep]
    un_ev = np.broadcast_to(un, (len(shots), n_off, k)).reshape(-1, k)[keep]
    blasts = blast_events(model, shots_list)
    if blasts:
        b = o.types.index(DamageType.BLAST)
        extra = np.zeros((len(blasts), k))
        extra[:, b] = [v for _, v in blasts]
        times = np.concatenate([times, [t for t, _ in blasts]])
        arm_ev = np.concatenate([arm_ev, extra])
        un_ev = np.concatenate([un_ev, np.zeros_like(extra)])
    order = np.argsort(times, kind="stable")
    times, arm_ev, un_ev = times[order], arm_ev[order], un_ev[order]
    active = np.searchsorted(shots, times, "left") - np.searchsorted(
        shots, times - model.duration, "left"
    )
    kept = _corrosive_kept(model.procs.get(DamageType.CORROSIVE, 0.0) * active)
    heat = heat_start(model, shots_list)
    if heat is not None:
        kept = kept * _heat_kept(times - heat)
    state = np.stack(
        [
            _amp(model.procs.get(DamageType.MAGNETIC, 0.0) * active),
            _amp(model.procs.get(DamageType.VIRAL, 0.0) * active),
            kept,
        ]
    )
    return o.types, times, arm_ev, un_ev, state


def costs(model: ShotModel, foes: Sequence[Enemy]) -> Array:
    types, times, arm, un, (mag, vir, kept) = timeline(model)
    fm = np.array([[e.faction[t] for t in types] for e in foes])
    bypass = np.array([[t == DamageType.TOXIN and e.toxin_bypass for t in types] for e in foes])
    fm_s, fm_b = fm * ~bypass, fm * bypass
    armor = np.array([e.armor for e in foes])
    shield = np.array([e.shield for e in foes])
    health = np.array([e.health for e in foes])
    af = 1 - np.minimum(ARMOR_CAP, 0.9 * np.sqrt(armor[None, :] * kept[:, None] / 2700))
    sp = ((arm + un) @ fm_s.T) * mag[:, None]
    h_nb = ((arm @ fm_s.T) * af + un @ fm_s.T) * vir[:, None]
    h_b = ((arm @ fm_b.T) * af + un @ fm_b.T) * vir[:, None]

    n = len(times)
    cum_sp = np.cumsum(sp, axis=0)
    broken = cum_sp >= shield[None, :]
    k = np.where(broken.any(axis=0), broken.argmax(axis=0), n)
    rows = np.arange(n)[:, None]
    w = (rows > k[None, :]).astype(np.float64)
    cols = np.flatnonzero((k < n) & (shield > 0))
    if cols.size:
        kk = k[cols]
        w[kk, cols] = (cum_sp[kk, cols] - shield[cols]) / sp[kk, cols]
    w[:, shield <= 0] = 1.0
    cum_h = np.cumsum(h_b + h_nb * w, axis=0)
    killed = cum_h >= health[None, :]
    any_kill = killed.any(axis=0)
    ttk = times[killed.argmax(axis=0)] + model.interval
    removed = (np.minimum(shield, cum_sp[-1]) + cum_h[-1]) / (shield + health)
    out: Array = np.where(any_kill, ttk, CAP_S / np.maximum(removed, MIN_REMOVED))
    return out


def score(model: ShotModel, foes: Sequence[Enemy]) -> float:
    return float(np.exp(np.log(costs(model, foes)).mean()))
