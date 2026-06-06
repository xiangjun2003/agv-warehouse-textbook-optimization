from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np


@dataclass
class LPResult:
    x: np.ndarray
    y: np.ndarray
    s: np.ndarray
    objective: float
    status: str
    iterations: int
    primal_residual: float
    dual_residual: float
    gap: float
    history: list[dict[str, float]] = field(default_factory=list)


def _step_length(values: np.ndarray, directions: np.ndarray, eta: float) -> float:
    negative = directions < 0.0
    if not np.any(negative):
        return 1.0
    return min(1.0, eta * float(np.min(-values[negative] / directions[negative])))


def _solve_normal_equations(
    matrix: np.ndarray,
    rhs: np.ndarray,
    regularization: float,
) -> np.ndarray:
    scale = max(1.0, float(np.mean(np.abs(np.diag(matrix)))))
    system = matrix + regularization * scale * np.eye(matrix.shape[0])
    try:
        return np.linalg.solve(system, rhs)
    except np.linalg.LinAlgError:
        return np.linalg.lstsq(system, rhs, rcond=1e-10)[0]


def _newton_direction(
    A: np.ndarray,
    x: np.ndarray,
    s: np.ndarray,
    rb: np.ndarray,
    rc: np.ndarray,
    rxs: np.ndarray,
    regularization: float,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    ratio = x / s
    inv_s_rxs = rxs / s
    normal = (A * ratio) @ A.T
    rhs = rb - A @ inv_s_rxs + A @ (ratio * rc)
    dy = _solve_normal_equations(normal, rhs, regularization)
    at_dy = A.T @ dy
    dx = inv_s_rxs - ratio * rc + ratio * at_dy
    ds = rc - at_dy
    return dx, dy, ds


def solve_lp_primal_dual(
    c: np.ndarray,
    A_eq: np.ndarray,
    b_eq: np.ndarray,
    *,
    max_iter: int = 80,
    tol: float = 1e-7,
    eta: float = 0.995,
    regularization: float = 1e-9,
    verbose: bool = False,
) -> LPResult:
    """Solve min c^T x s.t. A_eq x = b_eq, x >= 0.

    This is an infeasible-start primal-dual path-following method in the style
    of the linear-programming interior-point method from Chapter 7.
    """
    A = np.asarray(A_eq, dtype=float)
    b = np.asarray(b_eq, dtype=float).reshape(-1)
    c = np.asarray(c, dtype=float).reshape(-1)
    m, n = A.shape

    x = np.ones(n, dtype=float)
    y = np.zeros(m, dtype=float)
    s = np.maximum(1.0, np.abs(c))

    norm_b = 1.0 + np.linalg.norm(b)
    norm_c = 1.0 + np.linalg.norm(c)
    history: list[dict[str, float]] = []

    for iteration in range(1, max_iter + 1):
        rb = b - A @ x
        rc = c - A.T @ y - s
        mu = float(x @ s / n)
        primal_residual = float(np.linalg.norm(rb) / norm_b)
        dual_residual = float(np.linalg.norm(rc) / norm_c)
        gap = float((x @ s) / (1.0 + abs(c @ x)))
        objective = float(c @ x)
        history.append(
            {
                "iteration": float(iteration),
                "objective": objective,
                "primal_residual": primal_residual,
                "dual_residual": dual_residual,
                "gap": gap,
                "mu": mu,
            }
        )
        if verbose:
            print(
                f"iter={iteration:02d} obj={objective:.6g} "
                f"pres={primal_residual:.2e} dres={dual_residual:.2e} "
                f"gap={gap:.2e}"
            )
        if max(primal_residual, dual_residual, gap) <= tol:
            return LPResult(
                x=x,
                y=y,
                s=s,
                objective=objective,
                status="optimal",
                iterations=iteration,
                primal_residual=primal_residual,
                dual_residual=dual_residual,
                gap=gap,
                history=history,
            )

        dx_aff, dy_aff, ds_aff = _newton_direction(
            A,
            x,
            s,
            rb,
            rc,
            -x * s,
            regularization,
        )
        alpha_p_aff = _step_length(x, dx_aff, 1.0)
        alpha_d_aff = _step_length(s, ds_aff, 1.0)
        mu_aff = float(
            (x + alpha_p_aff * dx_aff) @ (s + alpha_d_aff * ds_aff) / n
        )
        sigma = float(np.clip((mu_aff / max(mu, 1e-30)) ** 3, 1e-4, 0.5))

        rxs = sigma * mu * np.ones(n) - x * s - dx_aff * ds_aff
        dx, dy, ds = _newton_direction(
            A,
            x,
            s,
            rb,
            rc,
            rxs,
            regularization,
        )
        alpha_p = _step_length(x, dx, eta)
        alpha_d = _step_length(s, ds, eta)
        x += alpha_p * dx
        y += alpha_d * dy
        s += alpha_d * ds
        x = np.maximum(x, 1e-14)
        s = np.maximum(s, 1e-14)

    rb = b - A @ x
    rc = c - A.T @ y - s
    primal_residual = float(np.linalg.norm(rb) / norm_b)
    dual_residual = float(np.linalg.norm(rc) / norm_c)
    gap = float((x @ s) / (1.0 + abs(c @ x)))
    return LPResult(
        x=x,
        y=y,
        s=s,
        objective=float(c @ x),
        status="max_iter",
        iterations=max_iter,
        primal_residual=primal_residual,
        dual_residual=dual_residual,
        gap=gap,
        history=history,
    )
