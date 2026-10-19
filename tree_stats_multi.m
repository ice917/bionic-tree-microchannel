function s = tree_stats_multi(T, pinned, edges0, srcm, srcb, Tb, r0)
%TREE_STATS_MULTI Metrics for a channel tree, mirroring the Python pipeline.
%   T        converged field (tree cells pinned at Tb, chip cells exempt)
%   pinned   boolean mask of cells held at Tb
%   edges0   ne x 2 edge list, 0-based cell indices (idx = y*grid + x)
%   srcm     source mask (chip blocks)
%   srcb     interior source term (needed for the metric polish solve)
%   Tb       coolant / boundary temperature [C]
%   r0       Murray base radius [mm]
%
%   Conventions follow verify.py (Group.from_field / poiseuille_dp /
%   tree_material_mm2) and radius.py (assign_radii):
%     * leaf demand = 1, internal flow = sum of children (root flow = #leaves)
%     * r = r0 * flow^(1/3); segment throat radius = min of the two ends
%     * material counts each node once with r = max(own, touching radii)
%     * hotspot threshold = Tb + 0.25*(T_max - Tb); area in mm^2 (pitch 1 mm)
%   The field is polished to Jacobi tol 1e-7 (verify.apply_channels) before
%   metrics so numbers are directly comparable with the Python outputs.
%   Chip connectivity: per chip (connected component of srcm), the minimum
%   Manhattan distance from any tree cell to the chip centroid; 0 means the
%   tree physically entered that chip's block.

grid = size(T, 1);
ne = size(edges0, 1);
ep = edges0(:, 1) + 1;          % 1-based parents
ec = edges0(:, 2) + 1;          % 1-based children
n = grid * grid;

% ---- metric polish (warm start, tol 1e-7 like verify.apply_channels) ----
pinned = pinned & ~srcm;        % exemption rule (safety no-op if already applied)
[T, polish_iters] = jacobi_local(T, srcb, pinned, Tb, 1e-7, 20000);

solid = ~pinned;
s.T = T;
s.pinned = pinned;
s.T_max = max(T(:));
s.T_mean_solid = mean(T(solid));
s.hotspot_threshold = Tb + 0.25 * (s.T_max - Tb);
s.hotspot_mm2 = nnz(solid & (T > s.hotspot_threshold)) * 1.0;   % pitch = 1 mm
s.pinned_cells = nnz(pinned);
s.polish_iters = polish_iters;

% ---- tree cells & shape ----
cells = unique([ep; ec])';
s.n_nodes = numel(cells);
s.n_edges = ne;
ys0 = mod(cells - 1, grid);             % 0-based y (grid row); edges are
xs0 = floor((cells - 1) / grid);        % MATLAB-linear-1, i.e. i = y + x*grid
s.bbox_x = [min(xs0) max(xs0)];
s.bbox_y = [min(ys0) max(ys0)];
s.centroid = [mean(xs0) mean(ys0)];

deg = accumarray([ep; ec], 1, [n 1]);
s.deg1 = nnz(deg == 1);
s.deg2 = nnz(deg == 2);
s.deg3 = nnz(deg == 3);
s.deg4 = nnz(deg == 4);
s.deg5p = nnz(deg >= 5);
s.forks = nnz(deg >= 3);
s.leaves = s.deg1;              % same convention as the recorded summaries

% ---- Murray radii ----
root = ep(1);
chil = cell(n, 1);
for e = 1:ne
    chil{ep(e)} = [chil{ep(e)}, ec(e)]; %#ok<AGROW>
end
depth = inf(n, 1);
depth(root) = 0;
queue = root; head = 1;
while head <= numel(queue)
    v = queue(head); head = head + 1;
    for c = chil{v}
        depth(c) = depth(v) + 1;
        queue(end+1) = c; %#ok<AGROW>
    end
end
flow = ones(n, 1);
[~, ord] = sort(depth, 'descend');
ord = ord(isfinite(depth(ord)));
for v = ord'
    if ~isempty(chil{v})
        flow(v) = sum(flow(chil{v}));
    end
end
rad = zeros(n, 1);
rad(cells) = r0 * flow(cells).^(1 / 3);
s.flow_root = flow(root);
s.radii = rad(cells);
s.radius_min = min(s.radii);
s.radius_max = max(s.radii);
s.radius_mean = mean(s.radii);
s.frac_capillary_le_0p6 = mean(s.radii <= 0.6);

% Murray conservation r_parent^3 == sum(r_child^3) at every fork
merr = 0;
for v = cells'
    ch = chil{v};
    if numel(ch) >= 2
        rhs = sum(rad(ch).^3);
        merr = max(merr, abs(rad(v)^3 - rhs) / rhs);
    end
end
s.murray_max_rel_err = merr;

% ---- material (each node counted once, max of touching radii) ----
r_at = rad;
for e = 1:ne
    p = ep(e); c = ec(e);
    r_at(p) = max(r_at(p), rad(c));
    r_at(c) = max(r_at(c), rad(p));
end
s.material_mm2 = sum(pi * r_at(cells).^2);

% ---- Poiseuille pressure drop ----
froot = flow(root);
dps = zeros(ne, 1);
for e = 1:ne
    p = ep(e); c = ec(e);
    Q = flow(p) / froot;
    r = min(rad(p), rad(c));
    dps(e) = 8.0 * 1.0 * 1.0 * Q / (pi * r^4);   % MU=1, L=pitch=1 mm
end
s.dp = sum(dps);

% ---- per-chip connectivity ----
[L, K] = chip_label_local(srcm);
treeMask = false(grid, grid);
treeMask(cells) = true;
s.n_chips = K;
s.chip_centers = zeros(K, 2);       % 0-based (y, x) float centroids
s.chip_dists = zeros(K, 1);         % min Manhattan dist tree->chip centroid
s.chip_tree_cells = zeros(K, 1);    % tree cells inside each chip block
for kk = 1:K
    idx = find(L == kk);
    [ry, rx] = ind2sub([grid grid], idx);
    cy0 = mean(ry) - 1;
    cx0 = mean(rx) - 1;
    s.chip_centers(kk, :) = [cy0 cx0];
    d = abs(ys0 - round(cy0)) + abs(xs0 - round(cx0));
    s.chip_dists(kk) = min(d);
    s.chip_tree_cells(kk) = nnz(L(cells) == kk);
end
s.max_chip_to_tree_dist = max(s.chip_dists);
s.tree_cells_in_blocks = nnz(srcm(treeMask));
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

% --------------------------------------------------------------------------
function [L, K] = chip_label_local(srcm)
% 4-neighbour connected components of the source mask, labelled 1..K.
m = srcm;
L = zeros(size(srcm));
K = 0;
gr = size(m, 1);
gc = size(m, 2);
while any(m(:))
    idx = find(m(:), 1);
    K = K + 1;
    L(idx) = K; m(idx) = false;
    stack = idx;
    while ~isempty(stack)
        v = stack(end); stack(end) = [];
        [ry, rx] = ind2sub([gr gc], v);
        nb = [];
        if ry > 1,  nb(end+1) = v - gr; end %#ok<AGROW>
        if ry < gr, nb(end+1) = v + gr; end %#ok<AGROW>
        if rx > 1,  nb(end+1) = v - 1;  end %#ok<AGROW>
        if rx < gc, nb(end+1) = v + 1;  end %#ok<AGROW>
        for w = nb
            if m(w)
                m(w) = false; L(w) = K;
                stack(end+1) = w; %#ok<AGROW>
            end
        end
    end
end
end
