from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

import numpy as np


Array = np.ndarray
ObjectiveGradient = Callable[[Array], tuple[float, Array]]


@dataclass
class ProjectedGradientResult:
    x: Array
    objective: float
    status: str
    iterations: int
    projected_gradient: float
    history: list[dict[str, float]] = field(default_factory=list)


def _project_box(x: Array, lower: Array, upper: Array) -> Array:
    return np.minimum(np.maximum(x, lower), upper)


def solve_projected_gradient(
    fun_grad: ObjectiveGradient,
    x0: Array,
    *,
    lower: float | Array = -np.inf,
    upper: float | Array = np.inf,
    max_iter: int = 1000,
    tol: float = 1e-6,
    step0: float = 1.0,
    step_min: float = 1e-10,
    armijo: float = 1e-4,
    accelerated: bool = False,
    verbose: bool = False,
) -> ProjectedGradientResult:
    """Projected gradient method for simple box constraints.

    The accelerated option uses the Nesterov/FISTA momentum pattern from
    Chapter 8. The non-accelerated option is the basic projected gradient
    method from Chapter 6.
    """
    x0 = np.asarray(x0, dtype=float)
    lower_arr = (
        np.full_like(x0, lower, dtype=float)
        if np.isscalar(lower)
        else np.asarray(lower, dtype=float)
    )
    upper_arr = (
        np.full_like(x0, upper, dtype=float)
        if np.isscalar(upper)
        else np.asarray(upper, dtype=float)
    )
    x = _project_box(x0, lower_arr, upper_arr)
    y = x.copy()
    momentum = 1.0
    step = float(step0)
    history: list[dict[str, float]] = []

    for iteration in range(1, max_iter + 1):
        f_y, g_y = fun_grad(y)
        projected = y - _project_box(y - g_y, lower_arr, upper_arr)
        pg_norm = float(np.linalg.norm(projected, ord=np.inf))
        history.append(
            {
                "iteration": float(iteration),
                "objective": float(f_y),
                "projected_gradient": pg_norm,
                "step": step,
            }
        )
        if verbose:
            print(
                f"inner={iteration:04d} obj={f_y:.6g} "
                f"pg={pg_norm:.2e} step={step:.2e}"
            )
        if pg_norm <= tol:
            return ProjectedGradientResult(
                x=y,
                objective=float(f_y),
                status="optimal",
                iterations=iteration,
                projected_gradient=pg_norm,
                history=history,
            )

        trial_step = step
        while True:
            x_new = _project_box(y - trial_step * g_y, lower_arr, upper_arr)
            delta = x_new - y
            f_new, _ = fun_grad(x_new)
            if f_new <= f_y + armijo * float(g_y @ delta) or trial_step <= step_min:
                break
            trial_step *= 0.5

        if accelerated:
            momentum_new = 0.5 * (1.0 + float(np.sqrt(1.0 + 4.0 * momentum * momentum)))
            y_new = x_new + ((momentum - 1.0) / momentum_new) * (x_new - x)
            f_current, _ = fun_grad(x)
            # Adaptive restart avoids bad momentum on ill-conditioned penalties.
            if f_new > f_current:
                y_new = x_new.copy()
                momentum_new = 1.0
        else:
            y_new = x_new.copy()
            momentum_new = 1.0

        x, y, momentum, step = x_new, y_new, momentum_new, min(1.5 * trial_step, step0)

    f, g = fun_grad(x)
    projected = x - _project_box(x - g, lower_arr, upper_arr)
    return ProjectedGradientResult(
        x=x,
        objective=float(f),
        status="max_iter",
        iterations=max_iter,
        projected_gradient=float(np.linalg.norm(projected, ord=np.inf)),
        history=history,
    )
