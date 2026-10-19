function out = bionic_placement(cmd, a, b)
%BIONIC_PLACEMENT  Chip-placement evaluation + bionic (evolutionary) search.
%
%   out = bionic_placement('eval', centers_xy, budget)
%       Evaluate one 3-chip layout. centers_xy is a 1x6 or 3x2 integer
%       design vector [x1 y1 x2 y2 x3 y3] (0-based grid cells). budget =
%       tree node budget (default 600). Returns the static-pipeline metrics.
%
%   out = bionic_placement('search', seed, budget)
%       Evolutionary search over the 3 chip centres. Population 12,
%       generations 12, elite top-4 kept, crossover = rounded mean of two
%       elite parents, Gaussian mutation with sigma annealed 6 -> 2
%       linearly over generations, objective = lexicographic
%       (T_max, T_mean_solid), illegal layouts penalised to the worst rank,
%       rng(seed) fixed. <= 200 evaluations per restart (actual: 100).
%
%   Static-growth pipeline, same rules as multi_source.py / field.py /
%   grow.py / radius.py / verify.py:
%     1. Jacobi solve of the 3-source field (q = 1 per source cell, k = 1,
%        pitch 1 mm, T_boundary = T_init = 25 C, tol 1e-6, max 20000 it)
%     2. affine normalisation of the peak to 100 C
%     3. static greedy heat-seeking growth to `budget` nodes (hottest
%        frontier cell; ties -> smallest python index y*grid + x; parent =
%        hottest in-tree neighbour, first-found wins on ties)
%     4. Murray-law radii r = 0.5*flow^(1/3) + Poiseuille dP
%     5. re-solve with tree cells pinned at 25 C (tol 1e-7, max 20000 it);
%        chip-block cells are never pinned, tree cells inside a chip block
%        are exempt from pinning (same exemption rule as the Python code)
%     6. metrics: T_max, T_mean_solid, hotspot area (threshold 25 +
%        0.25*(T_max-25)), pinned count, worst chip-centroid-to-tree
%        manhattan distance (0 = tree enters every chip block)
%
%   Constraints: 4 <= x,y <= 45 (chip fully on plate, centre >= 4 cells
%   from each edge) and pairwise Chebyshev distance between centres >= 8.

if nargin < 3 || isempty(b), b = 600; end
switch lower(cmd)
    case 'eval'
        out = eval_layout_xy(reshape(a, 1, 6), b);
    case 'search'
        out = ea_search(a, b);
    otherwise
        error('bionic_placement:badcmd', 'cmd must be ''eval'' or ''search''.');
end
end

% ---------------------------------------------------------------------
%                            evaluation
% ---------------------------------------------------------------------
function r = eval_layout_xy(v, budget)
% design convention [x1 y1 x2 y2 x3 y3] -> code convention (y, x) rows
centers = [v(2), v(1); v(4), v(3); v(6), v(5)];
r = eval_layout_yx(centers, budget);
r.design = v;
end

function r = eval_layout_yx(centers, budget)
grid = 50;
src = source_mask_multi_m(grid, centers);
srcb = 0.25 * double(src(2:end-1, 2:end-1));   % q=1, k=1, pitch=1 mm

% --- 1. Jacobi solve, tol 1e-6 (field.py solve_heat_sources) ---
T = 25 * ones(grid, grid);
it1 = 0;
for it1 = 1:20000
    Tn = T;
    Tn(2:end-1,2:end-1) = 0.25*(T(3:end,2:end-1) + T(1:end-2,2:end-1) + ...
        T(2:end-1,3:end) + T(2:end-1,1:end-2)) + srcb;
    Tn([1 end], :) = 25;  Tn(:, [1 end]) = 25;
    dres = max(abs(Tn(:) - T(:)));
    T = Tn;
    if dres < 1e-6, break; end
end

% --- 2. normalise peak to 100 C (field.py normalize_field) ---
rise = max(T(:)) - 25;
T = 25 + (T - 25) * (100 - 25) / rise;

% --- 3. static greedy growth (grow.py grow_tree) ---
edges = grow_static(T, budget);

% --- 4-6. metrics (radius.py + verify.py tree_group) ---
M = tree_metrics(T, src, centers, edges, grid);

r = M;
r.field_iters = it1;
r.centers = centers;
r.edges = edges;
r.n_edges = size(edges, 1);
r.legal = true;
end

function src = source_mask_multi_m(grid, centers)
yy = 0:grid-1;  xx = 0:grid-1;
src = false(grid, grid);
for k = 1:size(centers, 1)
    src(abs(yy' - centers(k,1)) <= 2 & abs(xx - centers(k,2)) <= 2) = true;
end
end

function edges = grow_static(T, budget)
% Python-order greedy growth: hottest frontier cell, ties -> smallest
% python linear index (y*grid + x); parent = hottest in-tree neighbour,
% ties -> first found in order (y+1,x), (y-1,x), (x+1), (x-1).
grid = size(T, 1);
inT = false(grid, grid);
s = py_pick(T, grid);
inT(s) = true;
edges = zeros(budget - 1, 2);
ne = 0;
while ne < budget - 1
    P = false(grid + 2, grid + 2);
    P(2:end-1, 2:end-1) = inT;
    touch = P(1:end-2, 2:end-1) | P(3:end, 2:end-1) | ...
            P(2:end-1, 1:end-2) | P(2:end-1, 3:end);
    cand = touch & ~inT;
    if ~any(cand(:)), break; end
    Tf = T;  Tf(~cand) = -inf;
    vi = py_pick(Tf, grid);
    [cy, cx] = ind2sub([grid, grid], vi);
    inT(cy, cx) = true;                 % python marks before parent search
    best = -inf;  par = 0;
    if cy < grid && inT(cy+1, cx) && T(cy+1, cx) > best
        best = T(cy+1, cx);  par = sub2ind([grid, grid], cy+1, cx);
    end
    if cy > 1 && inT(cy-1, cx) && T(cy-1, cx) > best
        best = T(cy-1, cx);  par = sub2ind([grid, grid], cy-1, cx);
    end
    if cx < grid && inT(cy, cx+1) && T(cy, cx+1) > best
        best = T(cy, cx+1);  par = sub2ind([grid, grid], cy, cx+1);
    end
    if cx > 1 && inT(cy, cx-1) && T(cy, cx-1) > best
        best = T(cy, cx-1);  par = sub2ind([grid, grid], cy, cx-1);
    end
    if par == 0, continue; end
    ne = ne + 1;
    edges(ne, :) = [par, vi];
end
edges = edges(1:ne, :);
end

function i = py_pick(A, grid)
% argmax with python (row-major) tie-breaking: max value, smallest y*grid+x
v = max(A(:));
[rs, cs] = find(A == v);
p = (rs - 1) * grid + (cs - 1);
[~, k] = min(p);
i = sub2ind([grid, grid], rs(k), cs(k));
end

function M = tree_metrics(T, src, centers, edges, grid)
% Pinned re-solve + all reported metrics (verify.py tree_group / radius.py)
nodeMask = false(grid, grid);
nodeMask(edges(:)) = true;
srcb = 0.25 * double(src(2:end-1, 2:end-1));
pinMask = nodeMask & ~src;             % chip-block cells exempt from pinning

Tc = T;  Tc(pinMask) = 25;
it2 = 0;
for it2 = 1:20000
    Tn = Tc;
    Tn(2:end-1,2:end-1) = 0.25*(Tc(3:end,2:end-1) + Tc(1:end-2,2:end-1) + ...
        Tc(2:end-1,3:end) + Tc(2:end-1,1:end-2)) + srcb;
    Tn(pinMask) = 25;  Tn([1 end], :) = 25;  Tn(:, [1 end]) = 25;
    dres = max(abs(Tn(:) - Tc(:)));
    Tc = Tn;
    if dres < 1e-7, break; end
end

solid = ~pinMask;
M.T_max = max(Tc(:));
M.T_mean = mean(Tc(solid));
thresh = 25 + 0.25 * (M.T_max - 25);
M.hotspot_mm2 = sum(solid & (Tc > thresh), 'all');   % pitch = 1 mm
M.pinned = nnz(pinMask);
M.tree_cells = nnz(nodeMask);
M.pin_iters = it2;

% Murray-law flows/radii + Poiseuille dP (radius.py, verify.py poiseuille_dp)
n = grid * grid;
par = edges(:, 1);  ch = edges(:, 2);
root = par(1);
flow = ones(n, 1);
ispar = false(n, 1);  ispar(par) = true;
flow(ispar) = 0;                        % internal nodes accumulate children
depth = -ones(n, 1);  depth(root) = 0;
frontier = root;
while ~isempty(frontier)
    nxt = [];
    for f = frontier
        kids = (ch(par == f))';          % row vector (loop over elements)
        depth(kids) = depth(f) + 1;
        nxt = [nxt, kids];
    end
    frontier = nxt;
end
[~, ord] = sort(depth(ch), 'descend');
for i = ord(:)'
    flow(par(i)) = flow(par(i)) + flow(ch(i));
end
rad = 0.5 * flow.^(1.0/3.0);
dp = 0;
for i = 1:size(edges, 1)
    dp = dp + 8 * (flow(par(i)) / flow(root)) / ...
        (pi * min(rad(par(i)), rad(ch(i)))^4);
end
M.tree_dp = dp;

% connectivity: worst manhattan distance chip centroid -> nearest tree cell
idx = find(nodeMask);
ty = mod(idx - 1, grid);
tx = floor((idx - 1) / grid);
dmax = 0;
for k = 1:size(centers, 1)
    d = min(abs(ty - centers(k,1)) + abs(tx - centers(k,2)));
    dmax = max(dmax, d);
end
M.max_chip_dist = dmax;
end

% ---------------------------------------------------------------------
%                     constraints / lexicographic order
% ---------------------------------------------------------------------
function ok = is_legal(v)
% v = [x1 y1 x2 y2 x3 y3]; NOTE: explicit indexing -- reshape(v,3,2) would
% be column-major and scramble the pairs.
xs = v([1 3 5]);  ys = v([2 4 6]);
ok = all(xs >= 4 & xs <= 45) && all(ys >= 4 & ys <= 45);
if ok
    ok = max(abs([xs(1)-xs(2), ys(1)-ys(2)])) >= 8 && ...
         max(abs([xs(1)-xs(3), ys(1)-ys(3)])) >= 8 && ...
         max(abs([xs(2)-xs(3), ys(2)-ys(3)])) >= 8;
end
end

function lt = lexless(a, b)
% lexicographic (T_max, T_mean) with 1e-6 tie tolerance on T_max
if abs(a(1) - b(1)) > 1e-6
    lt = a(1) < b(1);
else
    lt = a(2) < b(2);
end
end

function ord = lexorder(F)
% insertion sort by lexless (stable, deterministic)
n = size(F, 1);
ord = (1:n)';
for i = 2:n
    j = i;
    while j > 1 && lexless(F(ord(j), :), F(ord(j-1), :))
        tmp = ord(j);  ord(j) = ord(j-1);  ord(j-1) = tmp;
        j = j - 1;
    end
end
end

% ---------------------------------------------------------------------
%                          EA search
% ---------------------------------------------------------------------
function out = ea_search(seed, budget)
P = 12;  G = 12;  E = 4;                 % population / generations / elites
SIG0 = 6;  SIG1 = 2;                     % sigma annealed 6 -> 2 linearly
rng(seed, 'twister');

pop = zeros(P, 6);
i = 0;
while i < P                              % rejection-sample legal initial pop
    cand = randi([4 45], 1, 6);
    if is_legal(cand)
        i = i + 1;  pop(i, :) = cand;
    end
end

fit = inf(P, 2);                         % [T_max, T_mean]
met = nan(P, 5);                         % [hotspot maxdist dp pinned cells]
done = false(P, 1);
cache = containers.Map('KeyType', 'char', 'ValueType', 'any');
neval = 0;  nlookup = 0;
t0 = tic;
hmat = zeros(G, 14);
bestrow = [];                            % [x1..y3 T_max T_mean hot dist dp]

for g = 1:G
    % evaluate new individuals (illegal ones penalised, no PDE run)
    for i = 1:P
        if done(i), continue; end
        if ~is_legal(pop(i, :))
            fit(i, :) = [inf, inf];  met(i, :) = nan(1, 5);
            done(i) = true;  continue;
        end
        nlookup = nlookup + 1;
        key = sprintf('%d_', pop(i, :));
        if isKey(cache, key)
            r = cache(key);
        else
            r = eval_layout_xy(pop(i, :), budget);
            cache(key) = r;  neval = neval + 1;
        end
        fit(i, :) = [r.T_max, r.T_mean];
        met(i, :) = [r.hotspot_mm2, r.max_chip_dist, r.tree_dp, r.pinned, r.tree_cells];
        done(i) = true;
    end

    ord = lexorder(fit);
    pop = pop(ord, :);  fit = fit(ord, :);  met = met(ord, :);  done = done(ord);

    prevbest = bestrow;
    if isempty(prevbest) || lexless(fit(1, :), prevbest(7:8))
        bestrow = [pop(1, :), fit(1, :), met(1, 1:3)];
    end
    if isempty(prevbest)
        bsf = 1;
    else
        bsf = double(~lexless(prevbest(7:8), fit(1, :)));
    end
    hmat(g, :) = [seed, g, pop(1, :), fit(1, :), met(1, 1:3), bsf];

    % breed next generation: elites kept, children fill the rest
    if g < G
        sigma = SIG0 - (SIG0 - SIG1) * (g - 1) / (G - 1);
        for k = 1:(P - E)
            ip = randi(E);  jp = randi(E);
            while jp == ip, jp = randi(E); end
            child = round((pop(ip, :) + pop(jp, :)) / 2);
            child = round(child + sigma * randn(1, 6));
            child = min(max(child, 4), 45);
            pop(E + k, :) = child;  done(E + k) = false;
        end
    end
end

out = struct();
out.seed = seed;  out.budget = budget;
out.pop = P;  out.gens = G;  out.elites = E;
out.sigma_start = SIG0;  out.sigma_end = SIG1;
out.hist = hmat;                          % per-generation best
out.best_design = bestrow(1:6);
out.best_T_max = bestrow(7);  out.best_T_mean = bestrow(8);
out.best_hotspot = bestrow(9);  out.best_dist = bestrow(10);
out.best_dp = bestrow(11);
out.n_evals = neval;                      % actual PDE solves (cached dups excluded)
out.n_lookups = nlookup;                  % total lookup attempts
out.elapsed = toc(t0);
end
