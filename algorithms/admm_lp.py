from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np


@dataclass
class ADMMResult:
    x: np.ndarray
    objective: float
    status: str
    iterations: int
    primal_residual: float
    dual_residual: float
    equality_residual: float
    history: list[dict[str, float]] = field(default_factory=list)


def _project_affine(
    A: np.ndarray,
    b: np.ndarray,
    normal: np.ndarray,
    v: np.ndarray,
) -> np.ndarray:
    rhs = A @ v - b
    try:
        correction = np.linalg.solve(normal, rhs)
    except np.linalg.LinAlgError:
        correction = np.linalg.lstsq(normal, rhs, rcond=1e-10)[0]
    return v - A.T @ correction


def solve_lp_admm(
    c: np.ndarray,
    A_eq: np.ndarray,
    b_eq: np.ndarray,
    *,
    rho: float = 20.0,
    max_iter: int = 2000,
    tol: float = 1e-5,
    lower: float | np.ndarray = 0.0,
    upper: float | np.ndarray = np.inf,
    regularization: float = 1e-9,
    verbose: bool = False,
) -> ADMMResult:
    """ADMM for min c^T x subject to A x = b and box constraints.

    The splitting is x = z, with x projected onto the box and z projected onto
    the affine equality set. It follows the operator-splitting viewpoint from
    Chapter 8 and is useful as a lightweight first-order baseline.
    """
    A = np.asarray(A_eq, dtype=float)
    b = np.asarray(b_eq, dtype=float).reshape(-1)
    c = np.asarray(c, dtype=float).reshape(-1)
    n = c.size
    lower_arr = (
        np.full(n, lower, dtype=float)
        if np.isscalar(lower)
        else np.asarray(lower, dtype=float)
    )
    upper_arr = (
        np.full(n, upper, dtype=float)
        if np.isscalar(upper)
        else np.asarray(upper, dtype=float)
    )
    normal = A @ A.T
    scale = max(1.0, float(np.mean(np.abs(np.diag(normal)))))
    normal = normal + regularization * scale * np.eye(normal.shape[0])

    x = np.maximum(lower_arr, np.zeros(n, dtype=float))
    z = _project_affine(A, b, normal, x)
    u = np.zeros(n, dtype=float)
    norm_b = 1.0 + np.linalg.norm(b)
    history: list[dict[str, float]] = []

    for iteration in range(1, max_iter + 1):
        z_old = z.copy()
        x = np.minimum(np.maximum(z - u - c / rho, lower_arr), upper_arr)
        z = _project_affine(A, b, normal, x + u)
        u += x - z

        primal_residual = float(np.linalg.norm(x - z) / (1.0 + np.linalg.norm(x)))
        dual_residual = float(rho * np.linalg.norm(z - z_old) / (1.0 + np.linalg.norm(u)))
        equality_residual = float(np.linalg.norm(A @ x - b) / norm_b)
        objective = float(c @ x)
        history.append(
            {
                "iteration": float(iteration),
                "objective": objective,
                "primal_residual": primal_residual,
                "dual_residual": dual_residual,
                "equality_residual": equality_residual,
            }
        )
        if verbose and (iteration == 1 or iteration % 100 == 0):
            print(
                f"iter={iteration:04d} obj={objective:.6g} "
                f"r={primal_residual:.2e} s={dual_residual:.2e} "
                f"eq={equality_residual:.2e}"
            )
        if max(primal_residual, dual_residual, equality_residual) <= tol:
            return ADMMResult(
                x=x,
                objective=objective,
                status="optimal",
                iterations=iteration,
                primal_residual=primal_residual,
                dual_residual=dual_residual,
                equality_residual=equality_residual,
                history=history,
            )

    return ADMMResult(
        x=x,
        objective=float(c @ x),
        status="max_iter",
        iterations=max_iter,
        primal_residual=primal_residual,
        dual_residual=dual_residual,
        equality_residual=equality_residual,
        history=history,
    )
