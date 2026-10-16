"""A Matern field on a regular grid as a sparse Gaussian Markov random field: the SPDE approach (Lindgren, Rue
and Lindstrom 2011) with alpha = 2, which in two dimensions is the Matern covariance with smoothness nu = 1:

    C(d) = sigma^2 kappa d K_1(kappa d),   sigma^2 = 1 / (4 pi kappa^2 tau^2),   practical range sqrt(8) / kappa

    precision      Q = tau^2 h^2 (kappa^2 I - L)^T (kappa^2 I - L), L the five-point Laplacian on cells of side h
                   with zero-flux (Neumann) edges. Each cell has at most 13 non-zero entries: a field of a
                   hundred thousand cells is solved with a sparse factorisation instead of a dense n^3 one.
    krige          the posterior mean and (optionally, for chosen cells) variance of the field given noisy
                   observations at cells: Q_post = Q + A^T A / s^2, mean = Q_post^-1 A^T y / s^2 (mean 0; centre y
                   first)
    pad            the edges distort the field: within about one range of a zero-flux edge the variance grows
                   (about twice at an edge, four times at a corner). Extend the grid by a range or more on every
                   side and use only the inner part.

Only nu = 1 and a known sigma^2 and kappa here (the parameters are not estimated); the grid must be fine next
to the range (h well below 1 / kappa).
"""

import numpy as np
from scipy import sparse
from scipy.sparse.linalg import splu
from scipy.special import kv


def matern_nu1(d, sigma2, kappa):
    d = np.asarray(d, float)
    with np.errstate(invalid="ignore"):
        c = sigma2 * kappa * d * kv(1, kappa * d)
    return np.where(d > 0, c, sigma2)


def laplacian(nx, ny, h):
    """The five-point Laplacian with zero-flux edges, cells in row-major order (row = y, column = x)."""
    def one(n):
        if n == 1:  # no neighbours along this axis
            return sparse.csr_matrix((1, 1))
        main = -2.0 * np.ones(n)
        main[0] = main[-1] = -1.0  # Neumann: a missing neighbour contributes nothing
        return sparse.diags([np.ones(n - 1), main, np.ones(n - 1)], [-1, 0, 1])

    return (sparse.kron(sparse.identity(ny), one(nx)) + sparse.kron(one(ny), sparse.identity(nx))) / (h * h)


def precision(nx, ny, h, kappa, tau):
    K = kappa ** 2 * sparse.identity(nx * ny) - laplacian(nx, ny, h)
    return (tau ** 2 * h * h * (K.T @ K)).tocsc()


def tau_for(sigma2, kappa):
    return 1.0 / np.sqrt(4 * np.pi * kappa ** 2 * sigma2)


def covariance_column(Q, cell):
    """Column `cell` of Q^-1: the covariance of every cell with that one."""
    e = np.zeros(Q.shape[0])
    e[cell] = 1.0
    return splu(Q).solve(e)


def krige(Q, cells, y, noise_var, variance_cells=None):
    """cells: the observed cells' indices (repeats allowed); y: the values (mean 0). Returns the posterior mean
    over all cells and, for variance_cells, the posterior variances."""
    n = Q.shape[0]
    A = sparse.csr_matrix((np.ones(len(cells)), (np.arange(len(cells)), cells)), shape=(len(cells), n))
    Qp = (Q + (A.T @ A) / noise_var).tocsc()
    lu = splu(Qp)
    mean = lu.solve(np.asarray(A.T @ (np.asarray(y, float) / noise_var)).ravel())
    out = {"mean": mean}
    if variance_cells is not None:
        var = []
        for c in variance_cells:
            e = np.zeros(n)
            e[c] = 1.0
            var.append(lu.solve(e)[c])
        out["variance"] = np.array(var)
    return out
