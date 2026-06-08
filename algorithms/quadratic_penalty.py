from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

import numpy as np

from .projected_bb_gradient import solve_projected_bb
from .projected_gradient import solve_projected_gradient


Array = np.ndarray
ObjectiveGradient = Callable[[Array], tuple[float, Array]]
Residuals = Callable[[Array], tuple[Array, Array]]
JacobianTranspose = Callable[[Array, Array, Array], Array]


@dataclass
class PenaltyResult:
    x: Array
    objective: float
    status: str
    outer_iterations: int
    equality_violation: float
    inequality_violation: float
    history: list[dict[str, float]] = field(default_factory=list)


def solve_quadratic_penalty(
    objective_grad: ObjectiveGradient,
    residuals: Residuals,
    jacobian_transpose: JacobianTranspose,
    x0: Array,
    *,
    lower: float | Array = -np.inf,
    upper: float | Array = np.inf,
    rho0: float = 10.0,
    rho_multiplier: float = 10.0,
    outer_iter: int = 6,
    inner_iter: int = 1000,
    inner_solver: str = "bb",
    tol: float = 1e-5,
    verbose: bool = False,
) -> PenaltyResult:
    """Quadratic penalty method for h(x)=0 and g(x)<=0 constraints.

    The outer penalty loop follows Chapter 7. Each penalized subproblem is
    solved by the projected BB method from Chapter 6.
    """
    x = np.asarray(x0, dtype=float)
    rho = float(rho0)
    history: list[dict[str, float]] = []

    for outer in range(1, outer_iter + 1):
        def penalty_fun_grad(z: Array) -> tuple[float, Array]:
            base_value, base_grad = objective_grad(z)
            h, g = residuals(z)
            g_pos = np.maximum(g, 0.0)
            value = base_value + 0.5 * rho * (
                float(h @ h) + float(g_pos @ g_pos)
            )
            grad = base_grad + rho * jacobian_transpose(z, h, g_pos)
            return float(value), grad

        inner_tol = max(tol / max(rho, 1.0), 1e-8)
        if inner_solver == "bb":
            inner = solve_projected_bb(
                penalty_fun_grad,
                x,
                lower=lower,
                upper=upper,
                max_iter=inner_iter,
                tol=inner_tol,
                verbose=False,
            )
        elif inner_solver == "pg":
            inner = solve_projected_gradient(
                penalty_fun_grad,
                x,
                lower=lower,
                upper=upper,
                max_iter=inner_iter,
                tol=inner_tol,
                accelerated=False,
                verbose=False,
            )
        elif inner_solver == "nesterov":
            inner = solve_projected_gradient(
                penalty_fun_grad,
                x,
                lower=lower,
                upper=upper,
                max_iter=inner_iter,
                tol=inner_tol,
                accelerated=True,
                verbose=False,
            )
        else:
            raise ValueError(f"unknown inner_solver {inner_solver!r}")
        x = inner.x
        h, g = residuals(x)
        eq_violation = float(np.linalg.norm(h, ord=np.inf)) if h.size else 0.0
        ineq_violation = (
            float(np.max(np.maximum(g, 0.0))) if g.size else 0.0
        )
        base_value, _ = objective_grad(x)
        history.append(
            {
                "outer": float(outer),
                "rho": rho,
                "objective": float(base_value),
                "penalty_objective": float(inner.objective),
                "equality_violation": eq_violation,
                "inequality_violation": ineq_violation,
                "inner_iterations": float(inner.iterations),
            }
        )
        if verbose:
            print(
                f"outer={outer:02d} rho={rho:.2e} obj={base_value:.6g} "
                f"eq={eq_violation:.2e} ineq={ineq_violation:.2e}"
            )
        if max(eq_violation, ineq_violation) <= tol:
            return PenaltyResult(
                x=x,
                objective=float(base_value),
                status="optimal",
                outer_iterations=outer,
                equality_violation=eq_violation,
                inequality_violation=ineq_violation,
                history=history,
            )
        rho *= rho_multiplier

    h, g = residuals(x)
    eq_violation = float(np.linalg.norm(h, ord=np.inf)) if h.size else 0.0
    ineq_violation = float(np.max(np.maximum(g, 0.0))) if g.size else 0.0
    base_value, _ = objective_grad(x)
    return PenaltyResult(
        x=x,
        objective=float(base_value),
        status="max_iter",
        outer_iterations=outer_iter,
        equality_violation=eq_violation,
        inequality_violation=ineq_violation,
        history=history,
    )
