function res = coupled_grow(T0, srcb, srcm, Tb, Ttarget, max_nodes, recalc_every)
%COUPLED_GROW Grow a heat-seeking tree while the field reacts to it.
%   Vectorised MATLAB port of grow_coupled.py.
%
%   T0       initial field, already normalised (peak = Ttarget)
%   srcb     source term for interior cells (grid-2 x grid-2)
%   srcm     logical source mask (grid x grid)
%   max_nodes  node budget
%   recalc_every  re-solve the field every N growth steps
%
%   Returns struct: edges (ne x 2, 0-based indices), T_final, n_recalcs,
%   total_iters, and timing.

grid = size(T0,1);
n = grid*grid;
max_nodes = min(max_nodes, n);

inT = false(grid,grid);
T = T0;
edges = zeros(max_nodes-1, 2);
ne = 0;
nrecalc = 0; totiter = 0;

% seed: hottest cell (the source centre after normalisation)
[~,si] = max(T(:));
inT(si) = true;

touch = false(grid,grid);
tstart = tic;

while ne < max_nodes-1
    % frontier = cells touching the tree but not in it
    touch = inT;
    touch(2:end-1,2:end-1) = touch(2:end-1,2:end-1) | ...
        inT(3:end,2:end-1) | inT(1:end-2,2:end-1) | ...
        inT(2:end-1,3:end)   | inT(2:end-1,1:end-2);
    cand = touch & ~inT;

    Tf = T; Tf(~cand) = -inf;
    [v,vi] = max(Tf(:));
    if v == -inf, break; end
    [cy,cx] = ind2sub([grid grid], vi);

    % parent = hottest tree-neighbour (vectorised)
    nb = -inf(4,1); pi = 0;
    d = [cy-1 cx]; if cy>1   && inT(cy-1,cx), nb(1)=T(cy-1,cx); end
    d(2,:) = [cy+1 cx]; if cy<grid && inT(cy+1,cx), nb(2)=T(cy+1,cx); end
    d(3,:) = [cy cx-1]; if cx>1   && inT(cy,cx-1), nb(3)=T(cy,cx-1); end
    d(4,:) = [cy cx+1]; if cx<grid && inT(cy,cx+1), nb(4)=T(cy,cx+1); end
    [~,bi] = max(nb);
    switch bi
        case 1, pi = sub2ind([grid grid], cy-1, cx);
        case 2, pi = sub2ind([grid grid], cy+1, cx);
        case 3, pi = sub2ind([grid grid], cy, cx-1);
        case 4, pi = sub2ind([grid grid], cy, cx+1);
    end
    if pi == 0, continue; end

    inT(cy,cx) = true;
    ne = ne + 1;
    edges(ne,:) = [pi-1, vi-1];   % 0-based

    % --- the coupling ---
    if mod(ne, recalc_every) == 0
        pinned = inT & ~srcm;
        for k = 1:20000
            Tn2 = T;
            Tn2(2:end-1,2:end-1) = 0.25*(T(3:end,2:end-1)+T(1:end-2,2:end-1) ...
                + T(2:end-1,3:end) + T(2:end-1,1:end-2)) + srcb;
            Tn2(pinned) = Tb; Tn2(1,:)=Tb; Tn2(end,:)=Tb; Tn2(:,1)=Tb; Tn2(:,end)=Tb;
            if max(abs(Tn2(:)-T(:))) < 1e-6
                T = Tn2; totiter = totiter + k; break;
            end
            T = Tn2;
        end
        r = max(T(:)) - Tb;
        if r > 0, T = Tb + (T-Tb)*(Ttarget-Tb)/r; end
        nrecalc = nrecalc + 1;
    end
end

% final field with the whole tree pinned
pinned = inT & ~srcm;
for k = 1:20000
    Tn2 = T;
    Tn2(2:end-1,2:end-1) = 0.25*(T(3:end,2:end-1)+T(1:end-2,2:end-1) ...
        + T(2:end-1,3:end) + T(2:end-1,1:end-2)) + srcb;
    Tn2(pinned) = Tb; Tn2(1,:)=Tb; Tn2(end,:)=Tb; Tn2(:,1)=Tb; Tn2(:,end)=Tb;
    if max(abs(Tn2(:)-T(:))) < 1e-6, T = Tn2; totiter = totiter + k; break; end
    T = Tn2;
end

res.edges = edges(1:ne,:);
res.T_final = T;
res.pinned = pinned;
res.n_recalcs = nrecalc;
res.total_iters = totiter;
res.elapsed = toc(tstart);
end
