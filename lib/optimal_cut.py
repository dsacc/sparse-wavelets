import math

import numpy as np
import networkx as nx
import scipy

from lib.graph_signal_proc import Node
import lib.graph_signal_proc as gsp


def sweep_opt(x, F, G, k, ind):
    """
        Sweep algorithm for sparse wavelets.
        Input:
            * x: continuous indicator vector
            * F: graph signal
            * G: graph
            * k: max number of edges to be cut
            * ind: vertex index v: unique integer
        Output:
            * vec: indicator vector
            * best_energy: max energy value
            * best_edges_cut: number of edges cut
    """
    sorted_x = np.argsort(x)
    part_one = set()
    N = nx.number_of_nodes(G)
    best_energy = 0.
    edges_cut = 0
    best_edges_cut = 0
    sum_one = 0     # sum of the graph signal values for the nodes in part_one
    sum_two = 0     # sum of the graph signal values for the nodes in part_two

    for v in G.nodes():
        sum_two += F[ind[v]]

    for i in range(N):
        part_one.add(G.nodes()[sorted_x[i]])
        sum_one += F[ind[G.nodes()[sorted_x[i]]]]
        sum_two -= F[ind[G.nodes()[sorted_x[i]]]]

        for v in G.neighbors(G.nodes()[sorted_x[i]]):
            if v not in part_one:
                edges_cut = edges_cut + 1
            else:
                edges_cut = edges_cut - 1

        den = N * len(part_one) * (N - len(part_one))
        if den > 0:
            energy = math.pow(sum_one * (N - len(part_one)) - sum_two *
                              len(part_one), 2) / den
        else:
            energy = 0

        if energy >= best_energy and edges_cut <= k:
            best_cand = i
            best_energy = energy
            best_edges_cut = edges_cut

    vec = np.array([-1. if i <= best_cand else 1. for i in sorted_x])

    return vec, best_energy, best_edges_cut


def fast_cac(G, F, ind):
    """
        Computes product C*A*C, where C is the Laplacian of a complete graph
        and A is a pairwise squared difference matrix.
        Input:
            * G: graph
            * F: graph signal
            * ind: vertex index v: unique integer
        Output:
            * CAC: matrix product
    """
    CAC = []
    for v in G.nodes():
        CAC.append([])
        for u in G.nodes():
            CAC[-1].append(F[ind[v]] * F[ind[u]])

    CAC = np.array(CAC)
    CAC = -2 * math.pow(nx.number_of_nodes(G), 2) * CAC

    return CAC


def power_method(mat, start, maxit):
    """
        Power method implementation.
        Input:
            * mat: matrix
            * start: initialization
            * maxit: number of iterations
        Output:
            * vec: largest eigenvector of mat
    """
    vec = np.copy(start)
    vec = vec / np.linalg.norm(vec)

    for i in range(maxit):
        vec = np.dot(vec, mat)

    return vec


def spectral_cut(CAC, L, C, A, start, F, G, beta, k, ind):
    """
        Spectral cut implementation.
        Input:
            * CAC: C*A*C where C is the Laplacian of a complete graph and
                 A is a pairwise squared difference matrix
            * L: graph laplacian matrix
            * C: laplacian complete graph
            * A: pairwise squared difference matrix
            * start: initialization
            * beta: regularization parameter
            * k: max edges cut
            * ind: vertex index vertex: unique integer
        Output:
            * res: dictionary with following fields:
                - x: indicator vector
                - size: number of edges cut
                - energy: cut energy
    """
    isqrtCL = gsp.sqrtmi(C + beta * L)
    M = np.dot(np.dot(isqrtCL, CAC), isqrtCL)

    (eigvals, eigvecs) = scipy.linalg.eigh(M, eigvals=(0, 0))
    x = np.asarray(np.dot(eigvecs[:, 0], isqrtCL))[0, :]

    (x, energy, size) = sweep_opt(x, F, G, k, ind)

    res = {}
    res["x"] = np.array(x)
    res["size"] = size
    res["energy"] = energy

    return res


def trans(L, min_v, max_v):
    """
        Chebyshev polynomial translation.
        Input:
            * L: Laplacian matrix
            * min_v: lower bound
            * max_v: upper bound
        Output:
            * translation
    """
    return (float(2.) / (max_v - min_v)) * L, -(float(max_v + min_v) /
                                                (max_v - min_v))


def fun(k, n, beta, min_v, max_v, x):
    """
        Function to be integrated in Chebyshev polynomial computation.
        Input:
            * k: coefficient number
            * n: number of polynomials
            * min_v: lower bound
            * max_v: upper bound
        Output:
            * function value
    """
    y = 0.5 * math.cos(x) * float(max_v - min_v) + (0.5 * (max_v + min_v))

    return math.cos(k * x) * (float(1.) / math.sqrt(beta * y))


def coef(k, n, beta, min_v, max_v):
    """
        Chebyshev polynomial coefficients.
        Input:
            * k: coefficient number
            * n: number of polynomials
            * min_v: lower bound
            * max_v: upper bound
        Output:
            * coefficient
    """
    return float(2. * scipy.integrate.quad(
        lambda x: fun(k, n, beta, min_v, max_v, x), 0., math.pi)[0]) / math.pi


def chebyshev_approx_2d(n, beta, X, L):
    """
        Approximates sqrt((L)^+)^T * X * sqrt((L)^+)^T using
        Chebyshev polynomials (twice)
        Input:
            * n: number of polynomials
            * beta: regularization parameter
            * X: matrix
            * L: Laplacian matrix
        Output:
            * P2: approximation
    """
    max_v = beta * L.shape[0]
    min_v = 1

    ts1, ts2 = trans(L, min_v, max_v)
    P1 = 0.5 * coef(0, L.shape[0], beta, min_v, max_v) * X
    tkm2 = X
    tkm1 = scipy.sparse.csr_matrix.dot(ts1, X) + ts2 * X
    P1 = P1 + coef(1, L.shape[0], beta, min_v, max_v) * tkm1

    for i in range(2, n):
        Tk = 2. * (scipy.sparse.csr_matrix.dot(ts1, tkm1) + ts2 * tkm1) - tkm2
        P1 = P1 + coef(i, L.shape[0], beta, min_v, max_v) * Tk
        tkm2 = tkm1
        tkm1 = Tk

    P1 = P1.transpose()
    P2 = 0.5 * coef(0, L.shape[0], beta, min_v, max_v) * P1
    tkm2 = P1
    tkm1 = scipy.sparse.csr_matrix.dot(ts1, P1) + ts2 * P1

    P2 = P2 + coef(1, L.shape[0], beta, min_v, max_v) * tkm1

    for i in range(2, n):
        Tk = 2. * (scipy.sparse.csr_matrix.dot(ts1, tkm1) + ts2 * tkm1) - tkm2
        P2 = P2 + coef(i, L.shape[0], beta, min_v, max_v) * Tk
        tkm2 = tkm1
        tkm1 = Tk

    return P2


def chebyshev_approx_1d(n, beta, x, L):
    """
        Approximates x*sqrt(L^+) using Chebyshev polynomials.
        Input:
            * n: number of polynomials
            * beta: regularization parameter
            * x: vector
            * L: graph Laplacian
        Output:
            * P: approximation

    """
    max_v = beta * L.shape[0]
    min_v = 1

    ts1, ts2 = trans(L, min_v, max_v)
    P = 0.5 * coef(0, L.shape[0], beta, min_v, max_v) * x
    tkm2 = x
    tkm1 = scipy.sparse.csr_matrix.dot(ts1, x) + ts2 * x
    P = P + coef(1, L.shape[0], beta, min_v, max_v) * tkm1

    for i in range(2, n):
        Tk = 2. * (scipy.sparse.csr_matrix.dot(ts1, tkm1) + ts2 * tkm1) - tkm2
        P = P + coef(i, L.shape[0], beta, min_v, max_v) * Tk
        tkm2 = tkm1
        tkm1 = Tk

    return P


def cheb_spectral_cut(CAC, start, F, G, beta, k, n, ind):
    """
        Fast spectral cut implementation using chebyshev polynomials.
        Input:
            * CAC: C*A*C where C is the Laplacian of a complete graph and
                A is a pairwise squared difference matrix
            * start: initialization
            * F: graph signal
            * G: graph
            * L: graph laplacian matrix
            * beta: regularization parameter
            * k: max edges cut
            * n: number of polynomials
            * ind: vertex index vertex: unique integer
        Output:
            * res: dictionary with following fields:
                - x: indicator vector
                - size: number of edges cut
                - energy: cut energy
    """
    L = nx.laplacian_matrix(G)
    M = chebyshev_approx_2d(n, beta, CAC, L)

    eigvec = power_method(-M, start, 10)
    x = chebyshev_approx_1d(n, beta, eigvec, L)

    (x, energy, size) = sweep_opt(x, F, G, k, ind)

    res = {}
    res["x"] = np.array(x)
    res["size"] = size
    res["energy"] = energy

    return res


def laplacian_complete(n):
    """
        Laplacian of a complete graph with n vertices.
        Input:
            * n: size
        Output:
            * C: Laplacian
    """
    C = np.ones((n, n))
    C = -1 * C
    D = np.diag(np.ones(n))
    C = (n) * D + C

    return C


def weighted_adjacency_complete(G, F, ind):
    """
        Computes weighted adjacency complete matrix (w(v)-w(u))^2
        Input:
            * G: graph
            * F: graph signal
            * ind: vertex index vertex: unique integer
        Output:
            * A: nxn matrix
    """
    A = []
    for v in G.nodes():
        A.append([])
        for u in G.nodes():
            A[-1].append(pow(F[ind[v]] - F[ind[u]], 2))

    return np.array(A)


def fast_search(G, F, k, n, ind):
    """
        Efficient version of cut computation.
        Does not perform 1-D search for beta.
        Input:
            * G: graph
            * F: graph signal
            * k: max edges to be cut
            * n: number of chebyshev polynomials
            * ind: vertex index vertex: unique integer
        Output:
            * cut
    """
    start = np.ones(nx.number_of_nodes(G))
    CAC = fast_cac(G, F, ind)

    return cheb_spectral_cut(CAC, start, F, G, 1., k, n, ind)


gr = (math.sqrt(5) - 1) / 2


def one_d_search(G, F, k, ind):
    """
        Cut computation. Perform 1-D search for beta using golden search.
        Input:
            * G: graph
            * F: graph signal
            * k: max edges to be cut
            * n: number of chebyshev polynomials
            * ind: vertex index vertex: unique integer
        Output:
            * cut
    """
    C = laplacian_complete(nx.number_of_nodes(G))
    A = weighted_adjacency_complete(G, F, ind)
    CAC = np.dot(np.dot(C, A), C)
    start = np.ones(nx.number_of_nodes(G))
    L = nx.laplacian_matrix(G).todense()

    # Upper and lower bounds for search
    a = 0.
    b = 1000.
    c = b - gr * (b - a)
    d = a + gr * (b - a)

    # Tolerance
    tol = 1.

    resab = {}
    resab["size"] = k + 1

    # golden search
    while abs(c - d) > tol or resab["size"] > k:
        resc = spectral_cut(CAC, L, C, A, start, F, G, c, k, ind)
        resd = spectral_cut(CAC, L, C, A, start, F, G, d, k, ind)

        if resc["size"] <= k:
            if resc["energy"] > resd["energy"]:
                start = np.array(resc["x"])
                b = d
                d = c
                c = b - gr * (b - a)
            else:
                start = np.array(resd["x"])
                a = c
                c = d
                d = a + gr * (b - a)
        else:
            start = np.array(resc["x"])
            a = c
            c = d
            d = a + gr * (b - a)

        resab = spectral_cut(CAC, L, C, A, start, F, G, (b + a) / 2, k, ind)

    return resab


def optimal_wavelet_basis(G, F, k, npol):
    """
        Computation of optimal graph wavelet basis.
        Input:
            * G: graph
            * F: graph signal
            * k: max edges to be cut
            * npol: number of chebyshev polynomials, if 0 run exact version
        Output:
            * root: tree root
            * ind: vertex index vertex: unique integer
            * size: number of edges cut
    """

    # Creating index
    ind = {}
    i = 0
    for v in G.nodes():
        ind[v] = i
        i = i + 1

    # First cut
    root = Node(None)
    size = 0
    cand_cuts = []

    if npol == 0:
        c = one_d_search(G, F, k, ind)
    else:
        c = fast_search(G, F, k, npol, ind)

    c["parent"] = root
    c["graph"] = G

    cand_cuts.append(c)

    # Recursively compute new cuts
    while size <= k and len(cand_cuts) > 0:
        best_cut = None
        b = 0

        for i in range(0, len(cand_cuts)):
            if cand_cuts[i]["size"] + size <= k and cand_cuts[i]["energy"] > 0:
                if (best_cut is None or
                        cand_cuts[i]["energy"] > best_cut["energy"]):
                    best_cut = cand_cuts[i]
                    b = i
        if best_cut is None:
            break
        else:
            # Compute cut on left and right side
            (G1, G2) = gsp.get_subgraphs(best_cut["graph"], best_cut["x"])
            best_cut["parent"].cut = best_cut["size"]
            size = size + best_cut["size"]

            if nx.number_of_nodes(G1) == 1:
                n = Node(ind[G1.nodes()[0]])
                best_cut["parent"].add_child(n)
            elif nx.number_of_nodes(G1) > 0:
                n = Node(None)

                if npol == 0:
                    c = one_d_search(G1, F, k, ind)
                else:
                    c = fast_search(G1, F, k, npol, ind)

                c["parent"] = n
                c["graph"] = G1
                cand_cuts.append(c)

                best_cut["parent"].add_child(n)

            if nx.number_of_nodes(G2) == 1:
                n = Node(ind[G2.nodes()[0]])
                best_cut["parent"].add_child(n)
            elif nx.number_of_nodes(G2) > 0:
                n = Node(None)

                if npol == 0:
                    c = one_d_search(G2, F, k, ind)
                else:
                    c = fast_search(G2, F, k, npol, ind)

                c["parent"] = n
                c["graph"] = G2
                cand_cuts.append(c)

                best_cut["parent"].add_child(n)

            del cand_cuts[b]

    # Compute remaining cuts using ratio cuts once budget is over (not optimal)
    for i in range(0, len(cand_cuts)):
        gsp.rc_recursive(cand_cuts[i]["parent"], cand_cuts[i]["graph"], ind)

    gsp.set_counts(root)

    return root, ind, size
