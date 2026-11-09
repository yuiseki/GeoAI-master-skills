"""Hilbert-space approximate Gaussian process (HSGP) in two dimensions, in numpy.

A stationary kernel k on a box [-L1, L1] x [-L2, L2] is written with the eigenfunctions of the Laplacian there:

    k(x, x') ~ sum_j S(sqrt(lambda_j)) phi_j(x) phi_j(x')
    phi_j(x) = prod_d sin(pi j_d (x_d + L_d) / (2 L_d)) / sqrt(L_d),  sqrt(lambda_j) = |(pi j_d / (2 L_d))_d|

with S the kernel's spectral density, j_d = 1..m per axis (m^2 functions). The GP becomes a linear model with
m^2 weights, w_j ~ N(0, S(sqrt(lambda_j))), so the cost grows with n m^2 instead of n^3 (Solin and Sarkka 2020;
Riutort-Mayol et al., arXiv:2004.11408v2). The box must be wider than the points (c = L / S > 1, S the half
range) and m must grow as the length scale shrinks: `rule` gives the paper's minimum c and m.

Here: the basis, the spectral densities, the exact kernels, the approximate covariance, the posterior with the
parameters fixed (Bayesian linear regression) and the exact GP for comparison. The model with the parameters
inferred (NumPyro) is in hsgp_numpyro.py.
"""

from dataclasses import dataclass

import numpy as np
from scipy.special import gammaln

KINDS = ("se", "matern52", "matern32", "matern12")
_NU = {"matern12": 0.5, "matern32": 1.5, "matern52": 2.5}
# eq. 18-23 of Riutort-Mayol et al.: m = a c / (ell / S), c >= max(b ell / S, 1.2). Measured on 1-D inputs; the
# paper gives none for the exponential kernel (Matern 1/2).
_RULE = {"se": (1.75, 3.2), "matern52": (2.65, 4.1), "matern32": (3.42, 4.5)}


@dataclass
class Box:
    center: np.ndarray
    half: np.ndarray     # S: half the range of the points per axis
    c: float

    @property
    def L(self):
        return self.c * self.half

    @classmethod
    def around(cls, xy, c=None):
        lo, hi = xy.min(0), xy.max(0)
        return cls((lo + hi) / 2, (hi - lo) / 2, 1.0 if c is None else float(c))

    def inside(self, xy):
        """Whether points fall inside the box (the basis is 0 on its edge and meaningless outside)."""
        return np.all(np.abs(xy - self.center) < self.L, axis=1)


def rule(kind, ell, half):
    """Minimum boundary factor c and basis functions per axis m for a length scale ell and half range S."""
    if kind not in _RULE:
        raise ValueError(f"no rule for {kind}: the paper measured se, matern52 and matern32 only")
    a, b = _RULE[kind]
    ratio = ell / half
    c = max(b * ratio, 1.2)
    return c, int(np.ceil(a * c / ratio))


def _indices(m):
    j = np.arange(1, m + 1)
    return np.stack(np.meshgrid(j, j, indexing="ij"), -1).reshape(-1, 2)


def sqrt_eigenvalues(L, m):
    return np.linalg.norm(np.pi * _indices(m) / (2 * np.asarray(L)), axis=1)


def basis(x, L, m):
    """phi (n, m^2) at centred coordinates x (n, 2)."""
    L = np.asarray(L, float)
    j = _indices(m)
    arg = np.pi * j[None, :, :] * (x[:, None, :] + L) / (2 * L)
    return np.prod(np.sin(arg) / np.sqrt(L), axis=2)


def spectral_density(w, kind, sigma, ell, dim=2):
    """S(w) with k(r) = (2 pi)^-dim integral S(w) exp(i w r) dw."""
    w = np.asarray(w, float)
    if kind == "se":
        return sigma ** 2 * (2 * np.pi) ** (dim / 2) * ell ** dim * np.exp(-0.5 * (ell * w) ** 2)
    nu = _NU[kind]
    logc = (dim * np.log(2) + dim / 2 * np.log(np.pi) + gammaln(nu + dim / 2) + nu * np.log(2 * nu)
            - gammaln(nu) - 2 * nu * np.log(ell))
    return sigma ** 2 * np.exp(logc) * (2 * nu / ell ** 2 + w ** 2) ** -(nu + dim / 2)


def kernel(a, b, kind, sigma, ell):
    r = np.linalg.norm(a[:, None, :] - b[None, :, :], axis=2) / ell
    if kind == "se":
        k = np.exp(-0.5 * r ** 2)
    elif kind == "matern12":
        k = np.exp(-r)
    elif kind == "matern32":
        k = (1 + np.sqrt(3) * r) * np.exp(-np.sqrt(3) * r)
    elif kind == "matern52":
        k = (1 + np.sqrt(5) * r + 5 / 3 * r ** 2) * np.exp(-np.sqrt(5) * r)
    else:
        raise ValueError(kind)
    return sigma ** 2 * k


def _design(xy, box, m, kind, sigma, ell):
    phi = basis(xy - box.center, box.L, m)
    return phi, spectral_density(sqrt_eigenvalues(box.L, m), kind, sigma, ell)


def approx_cov(a, b, box, m, kind, sigma, ell):
    pa, s = _design(a, box, m, kind, sigma, ell)
    pb, _ = _design(b, box, m, kind, sigma, ell)
    return (pa * s) @ pb.T


def hsgp_posterior(xy, v, q, box, m, kind, sigma, ell, noise):
    """Mean and sd of the latent surface at q, parameters fixed, the mean of v taken as the constant mean."""
    if not box.inside(q).all():
        raise ValueError("prediction points outside the box: widen it (c) to cover them")
    mu0 = v.mean()
    phi, s = _design(xy, box, m, kind, sigma, ell)
    pq, _ = _design(q, box, m, kind, sigma, ell)
    A = phi.T @ phi / noise ** 2 + np.diag(1 / s)
    Lc = np.linalg.cholesky(A)
    w = np.linalg.solve(Lc.T, np.linalg.solve(Lc, phi.T @ (v - mu0) / noise ** 2))
    z = np.linalg.solve(Lc, pq.T)
    return mu0 + pq @ w, np.sqrt((z ** 2).sum(0))


def exact_gp(xy, v, q, kind, sigma, ell, noise):
    """The exact GP (simple kriging around the mean of v), O(n^3): for checking the approximation."""
    mu0 = v.mean()
    K = kernel(xy, xy, kind, sigma, ell) + noise ** 2 * np.eye(len(xy))
    Lc = np.linalg.cholesky(K)
    kq = kernel(xy, q, kind, sigma, ell)
    alpha = np.linalg.solve(Lc.T, np.linalg.solve(Lc, v - mu0))
    z = np.linalg.solve(Lc, kq)
    var = sigma ** 2 - (z ** 2).sum(0)
    return mu0 + kq.T @ alpha, np.sqrt(np.maximum(var, 0))
