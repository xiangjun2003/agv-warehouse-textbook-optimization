from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

import numpy as np


Array = np.ndarray
ObjectiveGradient = Callable[[Array], tuple[float, Array]]


@dataclass
class ProjectedBBResult:
    x: Array
    objective: float
    status: str
    iterations: int
    projected_gradient: float
    history: list[dict[str, float]] = field(default_factory=list)


def _project_box(x: Array, lower: Array, upper: Array) -> Array:
    return np.minimum(np.maximum(x, lower), upper)


def solve_projected_bb(
    fun_grad: ObjectiveGradient,
    x0: Array,
    *,
    lower: float | Array = -np.inf,
    upper: float | Array = np.inf,
    max_iter: int = 1000,
    tol: float = 1e-6,
    step_min: float = 1e-8,
    step_max: float = 1e8,
    armijo: float = 1e-4,
    verbose: bool = False,
) -> ProjectedBBResult:
    """Projected Barzilai-Borwein gradient method for box constraints.

    The BB step is the Chapter 6 gradient-method acceleration; the projection
    keeps the warehouse-layout relaxation inside 0 <= x <= 1.
    """
    x0 = np.asarray(x0, dtype=float)
    lower_arr = np.full_like(x0, lower, dtype=float) if np.isscalar(lower) else np.asarray(lower, dtype=float)
    upper_arr = np.full_like(x0, upper, dtype=float) if np.isscalar(upper) else np.asarray(upper, dtype=float)
    x = _project_box(x0, lower_arr, upper_arr)
    f, g = fun_grad(x)
    step = 1.0
    history: list[dict[str, float]] = []

    for iteration in range(1, max_iter + 1):
        projected = x - _project_box(x - g, lower_arr, upper_arr)
        pg_norm = float(np.linalg.norm(projected, ord=np.inf))
        history.append(
            {
                "iteration": float(iteration),
                "objective": float(f),
                "projected_gradient": pg_norm,
                "step": float(step),
            }
        )
        if verbose:
            print(
                f"inner={iteration:04d} obj={f:.6g} "
                f"pg={pg_norm:.2e} step={step:.2e}"
            )
        if pg_norm <= tol:
            return ProjectedBBResult(
                x=x,
                objective=float(f),
                status="optimal",
                iterations=iteration,
                projected_gradient=pg_norm,
                history=history,
            )

        trial_step = step
        while True:
            x_new = _project_box(x - trial_step * g, lower_arr, upper_arr)
            delta = x_new - x
            f_new, g_new = fun_grad(x_new)
            sufficient_decrease = f + armijo * float(g @ delta)
            if f_new <= sufficient_decrease or trial_step <= step_min:
                break
            trial_step *= 0.5

        s_vec = x_new - x
        y_vec = g_new - g
        sy = float(s_vec @ y_vec)
        if sy > 1e-14:
            if iteration % 2:
                step = float((s_vec @ s_vec) / sy)
            else:
                step = float(sy / max(y_vec @ y_vec, 1e-30))
            step = float(np.clip(step, step_min, step_max))
        else:
            step = min(step_max, max(step_min, trial_step * 0.5))

        x, f, g = x_new, f_new, g_new

    projected = x - _project_box(x - g, lower_arr, upper_arr)
    return ProjectedBBResult(
        x=x,
        objective=float(f),
        status="max_iter",
        iterations=max_iter,
        projected_gradient=float(np.linalg.norm(projected, ord=np.inf)),
        history=history,
    )
