function res = coupled_grow_multi(T0, srcb, srcm, Tb, Ttarget, max_nodes, recalc_every, r0)
%COUPLED_GROW_MULTI Coupled heat-seeking tree growth for N heat-source chips.
%   Multi-source extension of coupled_grow.m (single source). Identical
%   growth rule: seed at the globally hottest cell, repeatedly absorb the
%   hottest tree-adjacent cell and attach it to its hottest in-tree
%   neighbour (Prim variant on the temperature field).
%
%   Coupling: after every recalc_every absorbed cells the field is re-solved
%   by Jacobi (warm start from the current field) with all tree cells pinned
%   at Tb EXCEPT cells inside chip blocks (exemption rule), then the peak is
%   renormalised to Ttarget so growth decisions stay on a fixed scale and
%   the warm start stays cheap (anti-drift, as in grow_coupled.py).
%
%   Inputs
%     T0            initial field, already normalised (peak = Ttarget)
%     srcb          interior source term, (grid-2 x grid-2), q*h^2/(4k) per cell
%     srcm          logical source mask (grid x grid), N chip blocks
%     Tb            coolant / boundary temperature [C]
%     Ttarget       normalisation peak [C]
%     max_nodes     node budget (tree cells incl. those inside chip blocks)
%     recalc_every  re-solve the field every N growth steps
%     r0            Murray base radius [mm] (default 0.5)
%
%   Returns the growth record (edges 0-based, T_final, timing, recalcs,
%   iterations, seed) plus the full metric set of tree_stats_multi: thermal
%   metrics, per-chip connectivity, morphology, Murray radii, dp, material.

if nargin < 8, r0 = 0.5; end
grid = size(T0, 1);
n = grid * grid;
max_nodes = min(max_nodes, n);

inT = false(grid, grid);
T = T0;
edges = zeros(max_nodes - 1, 2);
ne = 0; nrecalc = 0; totiter = 0;

[~, si] = max(T(:));            % seed = globally hottest cell
inT(si) = true;
[sy, sx] = ind2sub([grid grid], si);

tstart = tic;
while ne < max_nodes - 1
    % frontier = cells touching the tree but not in it
    touch = inT;
    touch(2:end-1, 2:end-1) = touch(2:end-1, 2:end-1) | ...
        inT(3:end, 2:end-1) | inT(1:end-2, 2:end-1) | ...
        inT(2:end-1, 3:end)   | inT(2:end-1, 1:end-2);
    cand = touch & ~inT;

    Tf = T; Tf(~cand) = -inf;
    [v, vi] = max(Tf(:));
    if v == -inf, break; end
    [cy, cx] = ind2sub([grid grid], vi);

    % parent = hottest tree-neighbour
    nb = -inf(4, 1); pnode = 0;
    if cy > 1    && inT(cy-1, cx), nb(1) = T(cy-1, cx); end
    if cy < grid && inT(cy+1, cx), nb(2) = T(cy+1, cx); end
    if cx > 1    && inT(cy, cx-1), nb(3) = T(cy, cx-1); end
    if cx < grid && inT(cy, cx+1), nb(4) = T(cy, cx+1); end
    [~, bi] = max(nb);
    switch bi
        case 1, pnode = sub2ind([grid grid], cy-1, cx);
        case 2, pnode = sub2ind([grid grid], cy+1, cx);
        case 3, pnode = sub2ind([grid grid], cy, cx-1);
        case 4, pnode = sub2ind([grid grid], cy, cx+1);
    end
    if pnode == 0, continue; end

    inT(cy, cx) = true;
    ne = ne + 1;
    edges(ne, :) = [pnode - 1, vi - 1];     % 0-based

    % --- the coupling: the field reacts to the tree ---
    if mod(ne, recalc_every) == 0
        pinned = inT & ~srcm;
        [T, k] = jacobi_local(T, srcb, pinned, Tb, 1e-6, 20000);
        totiter = totiter + k;
        rr = max(T(:)) - Tb;                % renormalise peak -> Ttarget
        if rr > 0, T = Tb + (T - Tb) * (Ttarget - Tb) / rr; end
        nrecalc = nrecalc + 1;
    end
end

% final field with the whole tree pinned (chip cells exempt)
pinned = inT & ~srcm;
[T, k] = jacobi_local(T, srcb, pinned, Tb, 1e-6, 20000);
totiter = totiter + k;
elapsed = toc(tstart);

res.grid = grid;
res.recalc_every = recalc_every;
res.seed = [sy - 1, sx - 1];                % 0-based (y, x)
res.edges = edges(1:ne, :);                 % 0-based
res.T_growth = T;                           % raw-scale final field (tol 1e-6)
res.pinned = pinned;
res.n_recalcs = nrecalc;
res.total_iters = totiter;
res.elapsed = elapsed;

% full metric set (polishes the field to tol 1e-7, verify.apply_channels conv.)
s = tree_stats_multi(T, pinned, res.edges, srcm, srcb, Tb, r0);
fns = fieldnames(s);
for ii = 1:numel(fns)
    res.(fns{ii}) = s.(fns{ii});
end
res.T_final = s.T;
end

% --------------------------------------------------------------------------
function [T, iters, conv] = jacobi_local(T, srcb, pinned, Tb, tol, maxit)
% Jacobi iteration with Dirichlet boundary + pinned channel cells (warm start).
Tn = T; iters = 0; conv = false;
for it = 1:maxit
    Tn = T;
    Tn(2:end-1, 2:end-1) = 0.25 * (T(3:end, 2:end-1) + T(1:end-2, 2:end-1) ...
        + T(2:end-1, 3:end) + T(2:end-1, 1:end-2)) + srcb;
    Tn(pinned) = Tb;
    Tn(1, :) = Tb; Tn(end, :) = Tb; Tn(:, 1) = Tb; Tn(:, end) = Tb;
    d = max(abs(Tn(:) - T(:)));
    T = Tn; iters = it;
    if d < tol, conv = true; break; end
end
end
