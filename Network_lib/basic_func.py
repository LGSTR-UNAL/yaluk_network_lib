import numpy as np
from numpy.linalg import inv
from math import log, sqrt, pi, exp, ceil


# ============================================================
# LINE PARAMETERS
# ============================================================

def lineparam(Xi, hm, rc):
    """
    Calculate line parameters (Lm, Cm, Zc)

    Parameters
    ----------
    Xi, hm, rc : array_like
        Conductor horizontal position, height, radius

    Returns
    -------
    Lm, Cm, Zc : ndarray
    """
    Xi = np.asarray(Xi, dtype=float)
    hm = np.asarray(hm, dtype=float)
    rc = np.asarray(rc, dtype=float)

    cond = len(Xi)

    mu = 4 * pi * 1e-7
    c = 2.99792458e8
    e0 = 1 / (mu * c**2)

    Lm = np.zeros((cond, cond))

    for i in range(cond):
        for j in range(cond):
            s = sqrt((hm[i] - hm[j])**2 + (Xi[i] - Xi[j])**2)
            if i == j:
                Lm[i, i] = mu / (2 * pi) * log(2 * hm[i] / rc[i])
                
            else:
                Lm[i, j] = mu / (4 * pi) * log(1 + 4 * hm[i] * hm[j] / s**2)

    Cm = inv(Lm) * mu * e0
    Zc = Lm / sqrt(mu * e0)

    return Lm, Cm, Zc


# ============================================================
# BASIC MATRIX OPERATIONS
# ============================================================

def flipud(W):
    """Flip matrix upside down"""
    return np.flipud(W)


def mult(W, X):
    """Matrix multiplication"""
    return np.matmul(W, X)


# ============================================================
# NUMERICAL INTEGRATION (GAUSS–LEGENDRE)
# ============================================================

def gaussqj(fun, xlow, xhigh, gn):
    """Gauss-Legendre quadrature"""
    cb, cw = np.polynomial.legendre.leggauss(gn)
    jacob = (xhigh - xlow) / 2
    x = (cb + 1) * jacob + xlow
    return np.sum(cw * fun(x)) * jacob


def integral(fun, xlow, xhigh, tol=1e-6, gn1=8):
    """Adaptive Gauss quadrature"""
    mult = 1.7
    gn = max(4, ceil(gn1 / mult))

    integ_old = gaussqj(fun, xlow, xhigh, gn)

    for _ in range(10):
        gn = int(gn * mult)
        integ = gaussqj(fun, xlow, xhigh, gn)
        if abs(integ - integ_old) <= abs(tol * integ):
            return integ, gn
        integ_old = integ

    raise RuntimeError("Integral did not converge")


def integral2(fun, xlow, xhigh, var1, var2, tol=1e-6, gn1=8):
    """Integral with extra parameters"""

    def wrapped(x):
        return fun(x, var1, var2)

    return integral(wrapped, xlow, xhigh, tol, gn1)


# ============================================================
# BESSEL FUNCTIONS (APPROXIMATIONS)
# ============================================================

def besseli0(K1):
    if K1 <= 3.75:
        K = K1 / 3.75
        i1 = (
            1
            + 3.5156229 * K**2
            + 3.0899424 * K**4
            + 1.2067492 * K**6
            + 0.2659732 * K**8
            + 0.0360768 * K**10
            + 0.0045813 * K**12
        )
        return i1 * exp(-K1)
    else:
        K = K1 / 3.75
        i1 = (
            0.39894228
            + 0.01328592 * K**-1
            + 0.00225319 * K**-2
            - 0.00157565 * K**-3
            + 0.00916281 * K**-4
            - 0.02057706 * K**-5
            + 0.02635537 * K**-6
            - 0.01647633 * K**-7
            + 0.00392377 * K**-8
        )
        return i1 / sqrt(K1)


def besseli1(K1):
    if K1 <= 3.75:
        K = K1 / 3.75
        i1 = (
            0.5
            + 0.87890594 * K**2
            + 0.51498869 * K**4
            + 0.15084934 * K**6
            + 0.02658733 * K**8
            + 0.00301532 * K**10
            + 0.00032411 * K**12
        )
        return i1 * exp(-K1) * K1
    else:
        K = K1 / 3.75
        i1 = (
            0.39894228
            - 0.03988024 * K**-1
            - 0.00362018 * K**-2
            + 0.00163801 * K**-3
            - 0.01031555 * K**-4
            + 0.02282967 * K**-5
            - 0.02895312 * K**-6
            + 0.01787654 * K**-7
            - 0.00420059 * K**-8
        )
        return i1 / sqrt(K1)


# ============================================================
# INTERPOLATION
# ============================================================

def interp(vt, vx, tr):
    vt = np.asarray(vt)
    vx = np.asarray(vx)
    return np.interp(tr, vt, vx)


# ============================================================
# VECTOR COMPARISON
# ============================================================

def comparar(A, B):
    return np.array_equal(A, B)
