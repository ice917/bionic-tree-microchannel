function res = physarum_route()
%PHYSARUM_ROUTE  Physarum (slime mould) adaptive-network routing demo.
%   Grows a network connecting pins on a grid by evolving edge diameters under
%   a flux-adaptation rule, then extracts a tree and compares wire length
%   against Manhattan-MST and Hanan-RSMT baselines.
%
%   MODEL (Bonifaci-Mehlhorn-Varma, "Physarum Can Compute Shortest Paths",
%   arXiv:1106.0423, JTB 309:121-133, eq. (1)-(2)):
%     edge variable  D_e  (diameter, kept strictly positive)
%     resistance     R_e = L_e / D_e,  conductance  C_e = D_e / L_e
%     node equation  b_v = sum_u (p_v - p_u)/R_uv   <=>  L p = b
%                     with L = diag(rowsum(A)) - A,  A = W + W.',  W(e) = C_e
%     update         dD_e/dt = |Q_e| - D_e,   Q_e = C_e |p_u - p_v|
%
%   DISCRETISATION (Straszak-Vishnoi, arXiv:1601.02712, eq. (12)):
%     D^{k+1} = (1-h) D^k + h |Q^k|,  h in (0,1).
%     Keeps D^k > 0 for all k and makes ||D||_1 non-increasing (Lemma 5.6);
%     the undamped explicit Euler does not.
%
%   WHY A POST-PROCESSING STEP IS REQUIRED (this is documented, not a hack):
%     Multi-source / single-sink is formally a transportation problem, but BMV
%     prove only attraction to the *set* of equilibria (Thm 7); convergence to
%     a min-cost solution needs the extra hypothesis "no two equilibria have
%     the same cost" (Thm 8).  BMV list approximate Steiner-tree computation
%     as an open problem with "no theoretical analysis available".
%     Sun 2019 (arXiv:1903.08926, MS3-PO) states that for the multi-source
%     Physarum solver "there is no guarantee that the solution network ... is
%     a tree", and that connectivity is not guaranteed either -- so the
%     standard recipe is threshold + MST extraction on the saved network.
%     This demo does exactly that and reports BOTH the raw Physarum support
%     and the extracted tree, so the gap is visible.
%
%   LAPLACIAN ASSEMBLY WARNING:  L must be diag(rowsum(A)) - A with
%   A = W + W.'.  Using L = W + W.' assembles the *adjacency* matrix
%   (non-negative, rows summing to the degree): full rank, well conditioned,
%   solvable -- and it solves the wrong equation.  Every variant tried before
%   this fix produced a clean-looking solve of the wrong problem.

    rng(7);
    p = struct();

    %% ---- case 0: TWO terminals -- the regime BMV actually prove -----------
    %   This is the correctness anchor of the whole demo.  BMV Thm 2 says that
    %   when the shortest s-t path is unique the dynamics converge to the flow
    %   of value 1 along that path, so the network must collapse to exactly
    %   that path.  On an 8-neighbour n x n grid the unique shortest path is
    %   the (n-1)-step diagonal, euclidean length (n-1)*sqrt(2).
    p.validation = two_terminal_validation();

    %% ---- case 1: four corners of the square (sanity-checkable by hand) ----
    c1 = struct();
    c1.name = 'case1: 4 corners (4-pin)';
    c1.n = 20;
    c1.pins = [1 1; 1 20; 20 1; 20 20];
    c1.obstacles = false(c1.n);
    c1 = run_case(c1);
    p.cases = c1;

    %% ---- case 2: 5 pins + keep-out wall with a gate ----------------------
    %   The wall MUST leave the free graph connected, otherwise the Poisson
    %   system is singular: each component needs sum(b)=0 by Kirchhoff, and
    %   grounding one node in one component cannot balance the others.
    %   (Verified: a 3-row wall with a 3-cell gate splits the grid into 3
    %   components with per-component b = +2,+2,-4  ->  condest = Inf, NaN.)
    c2 = struct();
    c2.name = 'case2: 5 pins + wall (gated)';
    c2.n = 20;
    c2.pins = [2 2; 2 19; 19 2; 19 19; 10 10];
    obs = false(c2.n);
    obs(:, 10) = true;                  % single vertical wall, column x=10
    obs(10, 8:12) = false;              % 5-cell gate at y=8..12
    c2.obstacles = obs;
    c2 = run_case(c2);
    p.cases = [p.cases; c2];

    %% ---- case 3: random 6 pins -------------------------------------------
    c3 = struct();
    c3.name = 'case3: random 6 pins (rng 7)';
    c3.n = 20;
    c3.pins = [4 5; 17 4; 7 15; 14 13; 3 17; 16 18];
    c3.obstacles = false(c3.n);
    c3 = run_case(c3);
    p.cases = [p.cases; c3];

    %% ---- parameter sensitivity (on the case-1 configuration) -------------
    p.sensitivity = sensitivity_table();

    res = p;
end

%% =======================================================================
function c = run_case(c)
%RUN_CASE  Run the Physarum adaptation for one pin configuration.
%   The last pin is the sink absorbing the total supply of the other pins, so
%   sum(b) = 0 and every pin is a genuine terminal.

    [c, D, ei, ej, x1, y1, x2, y2, elen, resid] = evolve(c, 0.05);
    c = summarise(c, D, ei, ej, x1, y1, x2, y2, elen, resid, c.pins, c.obstacles, c.n);
end

%% =======================================================================
function [c, D, ei, ej, x1, y1, x2, y2, elen, resid] = evolve(c, hval)
%EVOLVE  Damped-Euler Physarum adaptation.  Self-contained: returns the final
%   diameters, the edge list, per-edge geometry and the fixed-point residual.

    n = c.n;
    pins = c.pins;
    np = size(pins, 1);
    obst = c.obstacles;

    idx = @(i, j) (j - 1) * n + i;
    [ei, ej] = grid_edges(n, obst);
    ne = numel(ei);

    % ---- node renumbering: only FREE cells become graph nodes ------------
    % Building the Laplacian on all n*n nodes would leave the obstacle cells
    % as degree-0 isolated nodes, each contributing a zero row/column; the
    % reduced matrix is then singular regardless of grounding, and the solve
    % returns NaN.  Verified on case 2 (n=20, one wall): rank(Lp) = 380 for
    % n^2 = 400, i.e. 20 components = 1 free component + 19 isolated obstacle
    % nodes, condest = Inf.  So compress to the free subgraph first.
    if ne == 0
        error('physarum_route:EmptyGraph', ...
              'the obstacle mask leaves no edges on the %dx%d grid', n, n);
    end
    free_cell = ~obst(:);
    nfree = sum(free_cell);
    compact = zeros(n * n, 1);
    compact(free_cell) = 1:nfree;
    cei = compact(ei);
    cej = compact(ej);

    % a disconnected free graph makes the Poisson system singular: each
    % component must independently satisfy sum(b) = 0 (Kirchhoff), and
    % grounding one node in one component cannot balance the others.
    adj0 = sparse(cei, cej, 1, nfree, nfree) + sparse(cej, cei, 1, nfree, nfree);
    c0 = graph_components_sparse(adj0);
    ncomp0 = numel(unique(c0));
    if ncomp0 > 1
        error('physarum_route:DisconnectedGrid', ...
              ['the obstacle mask disconnects the free grid into %d components; ', ...
               'the Poisson system is then singular (each component needs sum(b)=0)'], ...
              ncomp0);
    end

    % supplies: every pin but the last is a +1 source, the last is the sink
    b = zeros(nfree, 1);
    for k = 1:np - 1
        ii = compact(idx(pins(k, 1), pins(k, 2)));
        b(ii) = b(ii) + 1;
    end
    b(compact(idx(pins(np, 1), pins(np, 2)))) = ...
        b(compact(idx(pins(np, 1), pins(np, 2)))) - (np - 1);

    thresh = 0.5;
    max_iter = 6000;
    x1 = mod(ei - 1, n) + 1;
    y1 = floor((ei - 1) / n) + 1;
    x2 = mod(ej - 1, n) + 1;
    y2 = floor((ej - 1) / n) + 1;
    elen = hypot(x2 - x1, y2 - y1);

    % ground one zero-b node so that Lp(free,free) is non-singular
    g = find(b == 0, 1, 'first');
    free = true(nfree, 1); free(g) = false;
    bf = b(free);

    D = ones(ne, 1) * 0.5;
    nrm = nan(max_iter, 1);
    used = max_iter;
    tol = 1e-6;                 % relative fixed-point tolerance
    for it = 1:max_iter
        cond = D ./ elen;
        W = sparse(cei, cej, cond, nfree, nfree);
        A = W + W.';
        Lp = spdiags(sum(A, 2), 0, nfree, nfree) - A;   % the correct Laplacian
        pf = Lp(free, free) \ bf;
        pp = zeros(nfree, 1); pp(free) = pf;
        q = cond .* abs(pp(cej) - pp(cei));
        D = (1 - hval) * D + hval * q;
        nrm(it) = sum(D);

        % Stop on the fixed-point residual itself, not on a topology vote:
        % the support set keeps flipping long after the diameters settle, so
        % a topology-based stop returns a visibly unconverged state.
        if it > 100
            dmax = max(D);
            if dmax > 0 && max(abs(D - q)) / dmax < tol
                used = it; break;
            end
        end
    end

    % fixed-point residual: recompute |Q| at the final D
    cond = D ./ elen;
    W = sparse(cei, cej, cond, nfree, nfree);
    A = W + W.';
    Lp = spdiags(sum(A, 2), 0, nfree, nfree) - A;
    pf = Lp(free, free) \ bf;
    pp = zeros(nfree, 1); pp(free) = pf;
    q = cond .* abs(pp(cej) - pp(cei));
    resid = max(abs(D - q)) / max(D);

    c.h = hval;
    c.thresh = thresh;
    c.iters_used = used;
    c.dnorm_final = nrm(used);
    c.dnorm_monotone = all(diff(nrm(1:used)) <= 1e-9);
    c.fp_residual = resid;
    c.n = n;
    c.pins = pins;
    c.obstacles = obst;
end

%% =======================================================================
function c = summarise(c, D, ei, ej, x1, y1, x2, y2, elen, resid, pins, obst, n)
%SUMMARISE  Raw support metrics, MST-extracted tree metrics, baselines.

    np = size(pins, 1);
    thresh = c.thresh;
    keep = find(D > thresh);

    % ---------- raw Physarum support (before any post-processing) ----------
    c.n_edges_raw = numel(keep);
    c.len_euclid_raw = sum(elen(keep));
    c.len_manhattan_raw = sum(abs(x2(keep) - x1(keep)) + abs(y2(keep) - y1(keep)));
    [c.raw_connected, c.raw_components] = pin_connectivity(keep, ei, ej, pins, n);

    % ---------- MST extraction on the saved network (Sun 2019 recipe) ------
    [tree_len_eu, tree_len_mh, sel, covered] = mst_extract(keep, ei, ej, elen, n, pins);
    c.tree_len_euclid = tree_len_eu;
    c.tree_len_manhattan = tree_len_mh;
    c.n_edges_tree = numel(sel);
    c.tree_covers_pins = covered;
    tk = keep(sel);
    [c.tree_connected, ~, ~] = pin_connectivity(tk, ei, ej, pins, n);

    % ---------- obstacle respect (edges never touch obstacle cells) --------
    obs_lin = find(obst(:));
    c.obstacle_crossings = numel(intersect(obs_lin, unique([ei(keep); ej(keep)])));

    % ---------- baselines ---------------------------------------------------
    c.mst_manhattan = mst_length_manhattan(pins);
    if np <= 6
        c.rsmt_hanan = rsmt_hanan(pins);
    else
        c.rsmt_hanan = NaN;
    end
    c.tree_over_mst = c.tree_len_manhattan / c.mst_manhattan;

    % geometry of the extracted tree, for plotting
    c.edge_xi = x1(tk); c.edge_yi = y1(tk);
    c.edge_xj = x2(tk); c.edge_yj = y2(tk);
end

%% =======================================================================
function [conn, ncomp, comp] = pin_connectivity(keep, ei, ej, pins, n)
%PIN_CONNECTIVITY  Are all pins in one component of the kept-edge subgraph?
%   `ncomp` counts the DISTINCT components occupied by the pins themselves, so
%   a pin that is isolated (or absent from the support) is counted as its own
%   component -- counting only edge-bearing components would hide that.
    adj = sparse(double(ei(keep)), double(ej(keep)), 1, n * n, n * n);
    adj = adj + adj.';
    comp = graph_components_sparse(adj);
    np = size(pins, 1);
    pl = zeros(np, 1);
    for k = 1:np
        pl(k) = comp((pins(k, 2) - 1) * n + pins(k, 1));
    end
    u = unique(pl);
    ncomp = numel(u);
    conn = ncomp == 1;
end

%% =======================================================================
function [len_eu, len_mh, sel, covers_pins, start_node] = mst_extract(keep, ei, ej, elen, n, pins)
%MST_EXTRACT  Prim MST over the saved support graph.
%   Sun 2019 (arXiv:1903.08926): the multi-source Physarum solver's saved
%   network is not guaranteed to be a tree and not guaranteed to be connected,
%   so an MST pass is the documented post-processing step.
%   Prim starts from the support node that lies in the component containing
%   the MOST pins (ties broken by lowest node id), so the extracted tree is
%   the best available approximation to "the tree through all pins" rather
%   than an arbitrary component.  `covers_pins` then reports honestly whether
%   every pin actually ended up in that component.

    len_eu = 0; len_mh = 0; sel = []; covers_pins = false; start_node = 0;
    if isempty(keep)
        return;
    end
    sn = unique([ei(keep); ej(keep)]);
    K = numel(sn);
    pos = zeros(n * n, 1);
    pos(sn) = 1:K;
    a = pos(ei(keep));
    b2 = pos(ej(keep));
    w = elen(keep);
    ne = numel(keep);

    % component labels on the support graph
    supp_adj = sparse(a, b2, 1, K, K);
    supp_adj = supp_adj + supp_adj.';
    lab = graph_components_sparse(supp_adj);

    % pick the start node: component with the most pins, then lowest node id
    np = size(pins, 1);
    pl = zeros(np, 1);
    for k = 1:np
        pv = (pins(k, 2) - 1) * n + pins(k, 1);
        pl(k) = pos(pv);
    end
    best_lab = 0; best_cnt = -1;
    for k = 1:np
        if pl(k) == 0, continue; end
        cnt = sum(lab(pl(pl > 0)) == lab(pl(k)));
        if cnt > best_cnt || (cnt == best_cnt && sn(pl(k)) < start_node)
            best_cnt = cnt;
            best_lab = lab(pl(k));
        end
    end
    if best_lab == 0
        s = 1;                                   % no pin on the support at all
    else
        cand = find(lab == best_lab);
        [~, si] = min(sn(cand));
        s = cand(si);
    end
    start_node = sn(s);

    intree = false(K, 1);
    intree(s) = true;
    for k = 2:K
        best = inf; bi = 0;
        for e = 1:ne
            u = a(e); v = b2(e);
            if intree(u) ~= intree(v) && w(e) < best
                best = w(e); bi = e;
            end
        end
        if bi == 0
            break;                     % support is disconnected
        end
        len_eu = len_eu + best;
        sel(end + 1) = bi;             %#ok<AGROW>
        intree(a(bi)) = true;
        intree(b2(bi)) = true;
    end
    len_mh = 0;
    for e = sel
        i = keep(e);
        len_mh = len_mh + abs(mod(ej(i) - 1, n) + 1 - (mod(ei(i) - 1, n) + 1)) ...
                      + abs(floor((ej(i) - 1) / n) + 1 - (floor((ei(i) - 1) / n) + 1));
    end
    if nargin < 6 || isempty(pins)
        return;
    end
    covers_pins = all(pl > 0) && all(intree(pl));
end

%% =======================================================================
function L = mst_length_manhattan(pins)
%MST_LENGTH_MANHATTAN  Prim MST over the pins with L1 distances.
    np = size(pins, 1);
    D = zeros(np);
    for a = 1:np
        for bb = 1:np
            D(a, bb) = abs(pins(a, 1) - pins(bb, 1)) + ...
                       abs(pins(a, 2) - pins(bb, 2));
        end
    end
    intree = false(np, 1); intree(1) = true;
    L = 0;
    for kk = 2:np
        cols = find(~intree);
        d = D(intree, cols);
        [m, linidx] = min(d(:));
        L = L + m;
        [~, ci] = ind2sub(size(d), linidx);
        intree(cols(ci)) = true;
    end
end

%% =======================================================================
function L = rsmt_hanan(pins)
%RSMT_HANAN  Exact Steiner-tree length restricted to the Hanan grid.
%   Brute force over subsets of Hanan candidates of size <= 3.  This is an
%   UPPER bound on the true rectilinear Steiner length (the Hanan grid is a
%   restriction), and it ignores obstacles.
    xs = unique(pins(:, 1));
    ys = unique(pins(:, 2));
    [HX, HY] = meshgrid(xs, ys);
    cand = [HX(:), HY(:)];
    np = size(pins, 1);
    npt = size(cand, 1);
    best = inf;
    for kk = 0:min(np - 1, 3)
        if kk == 0
            best = min(best, mst_length_manhattan(pins));
            continue;
        end
        combos = nchoosek(1:npt, kk);
        for ci = 1:size(combos, 1)
            pts = [pins; cand(combos(ci, :), :)];
            best = min(best, mst_length_manhattan(pts));
        end
    end
    L = best;
end

%% =======================================================================
function [ei, ej] = grid_edges(n, obst)
%GRID_EDGES  8-neighbour edge list on an n x n grid, skipping obstacle cells.
    ei = [];
    ej = [];
    lin = @(i, j) (j - 1) * n + i;
    for j = 1:n
        for i = 1:n
            if obst(i, j)
                continue;
            end
            for di = 0:1
                for dj = -1:1
                    if di == 0 && dj <= 0
                        continue;
                    end
                    ni = i + di; nj = j + dj;
                    if ni < 1 || ni > n || nj < 1 || nj > n
                        continue;
                    end
                    if obst(ni, nj)
                        continue;
                    end
                    ei(end + 1) = lin(i, j);
                    ej(end + 1) = lin(ni, nj);
                end
            end
        end
    end
    ei = ei(:); ej = ej(:);
end

%% =======================================================================
function comp = graph_components_sparse(adj)
%GRAPH_COMPONENTS_SPARSE  Weakly-connected component labels (BFS).
    N = size(adj, 1);
    comp = zeros(N, 1);
    label = 0;
    for s = 1:N
        if comp(s) ~= 0
            continue;
        end
        label = label + 1;
        comp(s) = label;
        queue = s;
        while ~isempty(queue)
            u = queue(1); queue(1) = [];
            nbrs = find(adj(u, :));
            for v = nbrs
                if comp(v) == 0
                    comp(v) = label;
                    queue(end + 1) = v;
                end
            end
        end
    end
end

%% =======================================================================
function S = sensitivity_table()
%SENSITIVITY_TABLE  Damping-step sweep on the case-1 configuration.
    hs = [0.01, 0.05, 0.1, 0.2, 0.3, 0.5];
    S = [];
    for kk = 1:numel(hs)
        c = struct('name', sprintf('sens h=%.2f', hs(kk)), ...
                   'n', 16, 'pins', [1 1; 1 16; 16 1; 16 16], ...
                   'obstacles', false(16));
        [c, D, ei, ej, x1, y1, x2, y2, elen, resid] = evolve(c, hs(kk));
        c = summarise(c, D, ei, ej, x1, y1, x2, y2, elen, resid, c.pins, c.obstacles, c.n);
        S = [S; struct('h', hs(kk), ...
                       'n_edges_raw', c.n_edges_raw, ...
                       'n_edges_tree', c.n_edges_tree, ...
                       'tree_len_euclid', c.tree_len_euclid, ...
                       'tree_len_manhattan', c.tree_len_manhattan, ...
                       'tree_connected', c.tree_connected, ...
                       'iters_used', c.iters_used, ...
                       'dnorm_final', c.dnorm_final, ...
                       'dnorm_monotone', c.dnorm_monotone, ...
                       'fp_residual', c.fp_residual)]; %#ok<AGROW>
    end
end

%% =======================================================================
function V = two_terminal_validation()
%TWO_TERMINAL_VALIDATION  Correctness anchor: the one regime BMV prove.
%   BMV Thm 2 (arXiv:1106.0423): with exactly two terminals and a UNIQUE
%   shortest s-t path, the dynamics converge to the flow of value 1 along
%   that path.  On an 8-neighbour n x n grid with s=(1,1), t=(n,n) the unique
%   shortest path is the (n-1)-step diagonal, of euclidean length
%   (n-1)*sqrt(2), and every edge on it carries unit flux.  So the predicted
%   outcome is: exactly n-1 surviving edges, all diagonal, and
%   euclid = (n-1)*sqrt(2) to machine precision.  If this fails, nothing else
%   in the demo can be trusted.

    V = [];
    for n = [12, 20, 28]
        c = struct();
        c.name = sprintf('two-terminal n=%d', n);
        c.n = n;
        c.pins = [1 1; n n];            % exactly two terminals
        c.obstacles = false(n);
        [c, D, ei, ej, x1, y1, x2, y2, elen, resid] = evolve(c, 0.3);
        keep = find(D > 0.5);
        ideal = (n - 1) * sqrt(2);
        n_diag = sum(abs(x2(keep) - x1(keep)) == 1 & abs(y2(keep) - y1(keep)) == 1);
        V = [V; struct('n', n, ...
                       'iters_used', c.iters_used, ...
                       'fp_residual', c.fp_residual, ...
                       'n_edges_kept', numel(keep), ...
                       'n_expected', n - 1, ...
                       'len_euclid', sum(elen(keep)), ...
                       'ideal_euclid', ideal, ...
                       'abs_err', abs(sum(elen(keep)) - ideal), ...
                       'all_diagonal', n_diag == numel(keep), ...
                       'dnorm_monotone', c.dnorm_monotone)]; %#ok<AGROW>
    end
end
