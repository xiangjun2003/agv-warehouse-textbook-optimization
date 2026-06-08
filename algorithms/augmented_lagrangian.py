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
class AugmentedLagrangianResult:
    x: Array
    objective: float
    status: str
    outer_iterations: int
    inner_iterations: int
    equality_violation: float
    inequality_violation: float
    history: list[dict[str, float]] = field(default_factory=list)


def _solve_inner(
    fun_grad: ObjectiveGradient,
    x: Array,
    *,
    lower: float | Array,
    upper: float | Array,
    max_iter: int,
    tol: float,
    inner_solver: str,
):
    if inner_solver == "bb":
        return solve_projected_bb(
            fun_grad,
            x,
            lower=lower,
            upper=upper,
            max_iter=max_iter,
            tol=tol,
        )
    if inner_solver == "pg":
        return solve_projected_gradient(
            fun_grad,
            x,
            lower=lower,
            upper=upper,
            max_iter=max_iter,
            tol=tol,
            accelerated=False,
        )
    if inner_solver == "nesterov":
        return solve_projected_gradient(
            fun_grad,
            x,
            lower=lower,
            upper=upper,
            max_iter=max_iter,
            tol=tol,
            accelerated=True,
        )
    raise ValueError(f"unknown inner_solver {inner_solver!r}")


def solve_augmented_lagrangian(
    objective_grad: ObjectiveGradient,
    residuals: Residuals,
    jacobian_transpose: JacobianTranspose,
    x0: Array,
    *,
    lower: float | Array = -np.inf,
    upper: float | Array = np.inf,
    rho0: float = 10.0,
    rho_multiplier: float = 2.0,
    outer_iter: int = 20,
    inner_iter: int = 1000,
    tol: float = 1e-5,
    inner_solver: str = "bb",
    verbose: bool = False,
) -> AugmentedLagrangianResult:
    """Augmented Lagrangian method for h(x)=0 and g(x)<=0.

    Inequalities use the standard nonnegative multiplier update
    mu <- max(0, mu + rho g(x)). Box constraints are enforced by projection in
    the inner first-order solver.
    """
    x = np.asarray(x0, dtype=float)
    h0, g0 = residuals(x)
    lam = np.zeros_like(h0, dtype=float)
    mu = np.zeros_like(g0, dtype=float)
    rho = float(rho0)
    total_inner = 0
    history: list[dict[str, float]] = []

    for outer in range(1, outer_iter + 1):
        def augmented_fun_grad(z: Array) -> tuple[float, Array]:
            base_value, base_grad = objective_grad(z)
            h, g = residuals(z)
            shifted_g = g + mu / rho if g.size else g
            positive_g = np.maximum(shifted_g, 0.0) if g.size else g
            value = (
                base_value
                + float(lam @ h)
                + 0.5 * rho * float(h @ h)
                + 0.5 * rho * float(positive_g @ positive_g)
            )
            grad = base_grad + jacobian_transpose(
                z,
                lam + rho * h,
                rho * positive_g,
            )
            return float(value), grad

        inner = _solve_inner(
            augmented_fun_grad,
            x,
            lower=lower,
            upper=upper,
            max_iter=inner_iter,
            tol=max(tol / max(rho, 1.0), 1e-8),
            inner_solver=inner_solver,
        )
        x = inner.x
        total_inner += int(inner.iterations)
        h, g = residuals(x)
        eq_violation = float(np.linalg.norm(h, ord=np.inf)) if h.size else 0.0
        ineq_violation = float(np.max(np.maximum(g, 0.0))) if g.size else 0.0
        base_value, _ = objective_grad(x)
        history.append(
            {
                "outer": float(outer),
                "rho": rho,
                "objective": float(base_value),
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
            return AugmentedLagrangianResult(
                x=x,
                objective=float(base_value),
                status="optimal",
                outer_iterations=outer,
                inner_iterations=total_inner,
                equality_violation=eq_violation,
                inequality_violation=ineq_violation,
                history=history,
            )
        lam += rho * h
        if g.size:
            mu = np.maximum(0.0, mu + rho * g)
        rho *= rho_multiplier

    base_value, _ = objective_grad(x)
    h, g = residuals(x)
    eq_violation = float(np.linalg.norm(h, ord=np.inf)) if h.size else 0.0
    ineq_violation = float(np.max(np.maximum(g, 0.0))) if g.size else 0.0
    return AugmentedLagrangianResult(
        x=x,
        objective=float(base_value),
        status="max_iter",
        outer_iterations=outer_iter,
        inner_iterations=total_inner,
        equality_violation=eq_violation,
        inequality_violation=ineq_violation,
        history=history,
    )


def solve_lp_augmented_lagrangian(
    c: Array,
    A_eq: Array,
    b_eq: Array,
    x0: Array | None = None,
    *,
    lower: float | Array = 0.0,
    upper: float | Array = np.inf,
    rho0: float = 10.0,
    rho_multiplier: float = 2.0,
    outer_iter: int = 20,
    inner_iter: int = 1000,
    tol: float = 1e-5,
    inner_solver: str = "bb",
    verbose: bool = False,
) -> AugmentedLagrangianResult:
    A = np.asarray(A_eq, dtype=float)
    b = np.asarray(b_eq, dtype=float).reshape(-1)
    c = np.asarray(c, dtype=float).reshape(-1)
    if x0 is None:
        x0 = np.maximum(0.0, np.ones_like(c))

    def objective_grad(x: Array) -> tuple[float, Array]:
        return float(c @ x), c

    def residuals(x: Array) -> tuple[Array, Array]:
        return A @ x - b, np.zeros(0, dtype=float)

    def jacobian_transpose(x: Array, h_weight: Array, g_weight: Array) -> Array:
        return A.T @ h_weight

    return solve_augmented_lagrangian(
        objective_grad,
        residuals,
        jacobian_transpose,
        np.asarray(x0, dtype=float),
        lower=lower,
        upper=upper,
        rho0=rho0,
        rho_multiplier=rho_multiplier,
        outer_iter=outer_iter,
        inner_iter=inner_iter,
        tol=tol,
        inner_solver=inner_solver,
        verbose=verbose,
    )
