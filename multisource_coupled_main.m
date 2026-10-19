function out = multisource_coupled_main(mode)
%MULTISOURCE_COUPLED_MAIN Does coupled growth help when there are N chips?
%   Part A  single-source regression with the ORIGINAL coupled_grow.m
%           (heat_tree.py config: source (y,x)=(25,25) 0-based, budget 400,
%           recalc_every=1). Must reproduce T_max = 27.5962 C and the shape
%           stats recorded in outputs/matlab_coupled_summary.txt /
%           outputs/scan_recalc_frequency.txt.
%   Part B  3 chips in the triangle layout of multi_source.py LAYOUTS
%           ("3 chips, triangle" = (15,15),(35,15),(25,35) 0-based (y,x)),
%           budget 600 nodes, coupled growth with recalc_every in {1,5}.
%   Part C  comparison against the Python static multi-source tree grown on
%           the same budget (outputs/multi_source_results.csv, row
%           "3 chips, triangle | budget 600") and the radial control.
%           Pinned-count rule identical to Python: cells inside chip blocks
%           are exempt from pinning; both groups use a 600-node budget.
%
%   Writes outputs/matlab_multisource_coupled_summary.txt,
%           outputs/multisource_coupled_results.csv and, if graphics work,
%           outputs/step7_coupled_multisource.png.
%
%   mode: 'regression' -> Part A only, nothing written; 'full' -> all parts.

if nargin < 1, mode = 'full'; end
thisdir = fileparts(mfilename('fullpath'));
addpath(thisdir);                       % make coupled_grow*/tree_stats* resolvable
outdir = fullfile(thisdir, 'outputs');

grid = 50; Tb = 25.0; Ttarget = 100.0; r0 = 0.5;

%% ================= Part A: single-source regression =================
srcm1 = make_srcm_local(grid, [25 25]);
srcb1 = 0.25 * srcm1(2:end-1, 2:end-1);          % q=1, h=1 mm, k=1 (field.py)
[T1raw, it_cold1] = solve_poisson_local(srcb1, grid, Tb, 1e-6, 20000);
T01 = normalize_local(T1raw, Tb, Ttarget);
r1 = coupled_grow(T01, srcb1, srcm1, Tb, Ttarget, 400, 1);   % ORIGINAL function
reg = tree_stats_multi(r1.T_final, r1.pinned, r1.edges, srcm1, srcb1, Tb, r0);
reg.it_cold = it_cold1;
reg.n_recalcs = r1.n_recalcs;
reg.total_iters = r1.total_iters;
reg.elapsed = r1.elapsed;
reg.T_max_ref = 27.5962;
reg.pass = abs(reg.T_max - reg.T_max_ref) < 1e-3;

%% ================= recorded references (Python outputs) ==============
% Source: outputs/multi_source_results.csv, row "3 chips, triangle | budget 600"
ref = struct();
ref.row = '3 chips, triangle | budget 600';
ref.nodes = 600;      ref.pinned = 525;      ref.T_max = 27.5962;
ref.T_mean = 25.0633; ref.hotspot = 75.0;    ref.dp = 649.305;
ref.material = 1369.633; ref.maxdist = 0;    ref.blocks_cells = 600 - 525;
ref.ctrl_pinned = 509;   ref.ctrl_T_max = 30.2932; ref.ctrl_T_mean = 25.9438;
ref.ctrl_hotspot = 587.0; ref.ctrl_dp = 0.1055;

if strcmp(mode, 'regression')
    out = struct('reg', reg, 'ref', ref);
    print_regression(reg);
    return;
end

%% ================= Part B: 3 chips triangle, budget 600 ==============
centers = [15 15; 35 15; 25 35];        % (y,x) 0-based, multi_source.py LAYOUTS
srcm3 = make_srcm_local(grid, centers);
srcb3 = 0.25 * srcm3(2:end-1, 2:end-1);
[T3raw, it_cold3] = solve_poisson_local(srcb3, grid, Tb, 1e-6, 20000);
T03 = normalize_local(T3raw, Tb, Ttarget);

rsl = [1 5];
cc = cell(1, numel(rsl));
for ii = 1:numel(rsl)
    cc{ii} = coupled_grow_multi(T03, srcb3, srcm3, Tb, Ttarget, 600, rsl(ii), r0);
    cc{ii}.dT_max     = cc{ii}.T_max        - ref.T_max;
    cc{ii}.dT_mean    = cc{ii}.T_mean_solid - ref.T_mean;
    cc{ii}.d_hotspot  = cc{ii}.hotspot_mm2  - ref.hotspot;
    cc{ii}.d_pinned   = cc{ii}.pinned_cells - ref.pinned;
    cc{ii}.dp_ratio_vs_static = cc{ii}.dp / ref.dp;
end

%% ============================ outputs ================================
txt = build_summary(reg, ref, cc, centers, it_cold1, it_cold3);
disp(txt);
fid = fopen(fullfile(outdir, 'matlab_multisource_coupled_summary.txt'), 'w');
fprintf(fid, '%s', txt); fclose(fid);

write_csv(fullfile(outdir, 'multisource_coupled_results.csv'), reg, ref, cc);

figmsg = make_figure(fullfile(outdir, 'step7_coupled_multisource.png'), cc, rsl, centers);

out = struct('reg', reg, 'ref', ref, 'coupled', {cc}, ...
    'it_cold1', it_cold1, 'it_cold3', it_cold3, 'figure', figmsg);
end

% ==========================================================================
function print_regression(reg)
fprintf('regression: T_max=%.4f (ref %.4f) pass=%d | nodes=%d forks=%d deg=%d/%d/%d/%d\n', ...
    reg.T_max, reg.T_max_ref, reg.pass, reg.n_nodes, reg.forks, ...
    reg.deg1, reg.deg2, reg.deg3, reg.deg4);
end

% ==========================================================================
function txt = build_summary(reg, ref, cc, centers, it_cold1, it_cold3)
sep = repmat('=', 1, 80);
ln = repmat('-', 1, 80);
L = {};
L{end+1} = sep; %#ok<AGROW>
L{end+1} = 'MATLAB multi-source coupled-growth experiment (coupled_grow_multi.m)'; %#ok<AGROW>
L{end+1} = sprintf('grid %dx%d (50 mm plate) | pitch 1 mm | q=1 per source cell, k=1 | Tb=%.0f C', 50, 50, 25); %#ok<AGROW>
L{end+1} = 'protocol: tree cells inside chip blocks EXEMPT from pinning (both groups);'; %#ok<AGROW>
L{end+1} = '          coupled runs use the same 600-node budget as the Python static tree;'; %#ok<AGROW>
L{end+1} = '          fields normalised to peak 100 C before growth, metrics on raw scale;'; %#ok<AGROW>
L{end+1} = '          metric fields polished to Jacobi tol 1e-7 (verify.apply_channels conv.);'; %#ok<AGROW>
L{end+1} = '          Murray radii r0=0.5 mm, leaf demand 1, r=r0*flow^(1/3) (radius.py).'; %#ok<AGROW>
L{end+1} = sep; %#ok<AGROW>

% ---- Part A ----
L{end+1} = ''; L{end+1} = '[Part A] single-source regression -- ORIGINAL coupled_grow.m, budget 400, rs=1'; %#ok<AGROW>
L{end+1} = ln; %#ok<AGROW>
L{end+1} = sprintf('  source center (y,x) 0-based = (25,25) | cold field solve iters = %d', reg.it_cold); %#ok<AGROW>
L{end+1} = sprintf('  T_max              = %.4f C   (reference 27.5962)                  -> %s', reg.T_max, passstr(reg.pass)); %#ok<AGROW>
L{end+1} = sprintf('  T_mean_solid       = %.4f C   (REPORT coupled ref 25.0196)', reg.T_mean_solid); %#ok<AGROW>
L{end+1} = sprintf('  hotspot area       = %.1f mm2 (threshold %.4f C)', reg.hotspot_mm2, reg.hotspot_threshold); %#ok<AGROW>
L{end+1} = sprintf('  pinned cells       = %d (single 5x5 chip: tree-in-block cells = %d)', reg.pinned_cells, reg.tree_cells_in_blocks); %#ok<AGROW>
L{end+1} = sprintf('  dp (Poiseuille)    = %.3f     (REPORT coupled ref 583.54, older radius code)', reg.dp); %#ok<AGROW>
L{end+1} = sprintf('  material           = %.3f mm2 (summary ref 656.6744)', reg.material_mm2); %#ok<AGROW>
L{end+1} = sprintf('  nodes / edges      = %d / %d  (ref 400 / 399)', reg.n_nodes, reg.n_edges); %#ok<AGROW>
L{end+1} = sprintf('  degree histogram   = %d/%d/%d/%d/%d (summary ref 39/326/33/2/0)', ...
    reg.deg1, reg.deg2, reg.deg3, reg.deg4, reg.deg5p); %#ok<AGROW>
L{end+1} = sprintf('  forks / leaves     = %d / %d  (ref 35 / 39)', reg.forks, reg.leaves); %#ok<AGROW>
L{end+1} = sprintf('  bbox x/y (0-based) = [%d %d] / [%d %d]  (summary [1 48]/[1 46], scan [1 48]/[1 45])', ...
    reg.bbox_x(1), reg.bbox_x(2), reg.bbox_y(1), reg.bbox_y(2)); %#ok<AGROW>
L{end+1} = sprintf('  centroid (x,y) 0b  = %.4f / %.4f  (summary 23.8675/18.4275, scan 23.867/17.953)', ...
    reg.centroid(1), reg.centroid(2)); %#ok<AGROW>
L{end+1} = sprintf('  radius min/max/mean= %.4f / %.4f / %.4f  (summary 0.5/1.6956/0.6393)', ...
    reg.radius_min, reg.radius_max, reg.radius_mean); %#ok<AGROW>
L{end+1} = sprintf('  frac_capillary<=0.6= %.4f  (summary 0.5450, scan 0.885 -- both from older inline radius code)', ...
    reg.frac_capillary_le_0p6); %#ok<AGROW>
L{end+1} = sprintf('  root flow (=leaves)= %d | Murray max rel err = %.3e', reg.flow_root, reg.murray_max_rel_err); %#ok<AGROW>
L{end+1} = sprintf('  recalcs = %d | total Jacobi iters = %d | elapsed = %.2f s', ...
    reg.n_recalcs, reg.total_iters, reg.elapsed); %#ok<AGROW>
L{end+1} = '  (scan_recalc_frequency.txt rs=1 ref: recalcs 399, iters 261157, t 3.92 s)'; %#ok<AGROW>
L{end+1} = sprintf('  REGRESSION %s', passstr(reg.pass)); %#ok<AGROW>

% ---- Part B ----
L{end+1} = ''; L{end+1} = '[Part B] 3 chips, triangle layout, budget 600, coupled growth'; %#ok<AGROW>
L{end+1} = ln; %#ok<AGROW>
L{end+1} = sprintf('  chip centres (y,x) 0-based: (%d,%d) (%d,%d) (%d,%d) | cold field iters = %d', ...
    centers(1,1), centers(1,2), centers(2,1), centers(2,2), centers(3,1), centers(3,2), it_cold3); %#ok<AGROW>
for ii = 1:numel(cc)
    c = cc{ii};
    L{end+1} = sprintf('  -- recalc_every = %d --', c.recalc_every); %#ok<AGROW>
    L{end+1} = sprintf('    seed (y,x) 0b = (%d,%d) | nodes/edges = %d/%d | pinned = %d (static ref 525)', ...
        c.seed(1), c.seed(2), c.n_nodes, c.n_edges, c.pinned_cells); %#ok<AGROW>
    L{end+1} = sprintf('    T_max         = %.4f C  (static 27.5962, dT_max %+.4f)', c.T_max, c.dT_max); %#ok<AGROW>
    L{end+1} = sprintf('    T_mean_solid  = %.6f C  (static 25.0633, dT_mean %+.2e)', c.T_mean_solid, c.dT_mean); %#ok<AGROW>
    L{end+1} = sprintf('    hotspot       = %.1f mm2 (static 75.0, d%+.1f) | threshold %.4f C', ...
        c.hotspot_mm2, c.d_hotspot, c.hotspot_threshold); %#ok<AGROW>
    L{end+1} = sprintf('    dp            = %.3f (static 649.305, ratio %.2f) | material %.3f mm2 (static 1369.633)', ...
        c.dp, c.dp_ratio_vs_static, c.material_mm2); %#ok<AGROW>
    L{end+1} = sprintf('    chip dists    = %s (max %d) | tree cells in blocks = %d (per chip %s)', ...
        fmt_dists(c.chip_dists), c.max_chip_to_tree_dist, c.tree_cells_in_blocks, ...
        fmt_dists(c.chip_tree_cells)); %#ok<AGROW>
    L{end+1} = sprintf('    bbox x/y (0b) = [%d %d] / [%d %d] | centroid (%.2f, %.2f)', ...
        c.bbox_x(1), c.bbox_x(2), c.bbox_y(1), c.bbox_y(2), c.centroid(1), c.centroid(2)); %#ok<AGROW>
    L{end+1} = sprintf('    forks/leaves  = %d/%d | deg %d/%d/%d/%d/%d | root flow %d', ...
        c.forks, c.leaves, c.deg1, c.deg2, c.deg3, c.deg4, c.deg5p, c.flow_root); %#ok<AGROW>
    L{end+1} = sprintf('    radius min/max/mean = %.4f/%.4f/%.4f | frac_cap<=0.6 = %.4f | Murray err %.3e', ...
        c.radius_min, c.radius_max, c.radius_mean, c.frac_capillary_le_0p6, c.murray_max_rel_err); %#ok<AGROW>
    L{end+1} = sprintf('    recalcs = %d | total iters = %d | elapsed = %.2f s', ...
        c.n_recalcs, c.total_iters, c.elapsed); %#ok<AGROW>
end

% ---- Part C ----
L{end+1} = ''; L{end+1} = '[Part C] coupled (MATLAB) vs static tree (Python, same 600-node budget)'; %#ok<AGROW>
L{end+1} = ln; %#ok<AGROW>
L{end+1} = sprintf('  %-28s %10s %10s %10s %10s %12s %10s', ...
    'case', 'T_max', 'T_mean', 'hotspot', 'pinned', 'dp', 'maxdist'); %#ok<AGROW>
L{end+1} = sprintf('  %-28s %10.4f %10.4f %10.1f %10d %12.3f %10d', ...
    'static tree (Python ref)', ref.T_max, ref.T_mean, ref.hotspot, ref.pinned, ref.dp, ref.maxdist); %#ok<AGROW>
L{end+1} = sprintf('  %-28s %10.4f %10.4f %10.1f %10d %12.3f %10d', ...
    'radial control (Python ref)', ref.ctrl_T_max, ref.ctrl_T_mean, ref.ctrl_hotspot, ...
    ref.ctrl_pinned, ref.ctrl_dp, 0); %#ok<AGROW>
for ii = 1:numel(cc)
    c = cc{ii};
    L{end+1} = sprintf('  %-28s %10.4f %10.4f %10.1f %10d %12.3f %10d', ...
        sprintf('coupled rs=%d (MATLAB)', c.recalc_every), c.T_max, c.T_mean_solid, ...
        c.hotspot_mm2, c.pinned_cells, c.dp, c.max_chip_to_tree_dist); %#ok<AGROW>
end
L{end+1} = ''; %#ok<AGROW>
for ii = 1:numel(cc)
    c = cc{ii};
    L{end+1} = sprintf('  rs=%d vs static: dT_max %+.2e C, dT_mean %+.2e C, dHotspot %+.1f mm2, dPinned %+.0f, dp x%.2f', ...
        c.recalc_every, c.dT_max, c.dT_mean, c.d_hotspot, c.d_pinned, c.dp_ratio_vs_static); %#ok<AGROW>
end
L{end+1} = ''; %#ok<AGROW>
L{end+1} = 'Notes:'; %#ok<AGROW>
L{end+1} = ' * Static-tree reference numbers are recorded outputs of'; %#ok<AGROW>
L{end+1} = '   outputs/multi_source_results.csv ("3 chips, triangle | budget 600"), not recomputed here.'; %#ok<AGROW>
L{end+1} = ' * Pinned counts differ between coupled and static only if the two trees'; %#ok<AGROW>
L{end+1} = '   occupy different numbers of chip-block cells (exemption rule identical).'; %#ok<AGROW>
L{end+1} = ' * Single-source summary/scan radius columns came from an older inline stats'; %#ok<AGROW>
L{end+1} = '   script; this run uses the radius.py scheme (Python canonical) throughout.'; %#ok<AGROW>
L{end+1} = ' * Edge indices are MATLAB-linear-1 (i = y + x*grid); bbox/centroid are decoded'; %#ok<AGROW>
L{end+1} = '   accordingly. The recorded single-source summary/scan files used the'; %#ok<AGROW>
L{end+1} = '   transposed decode (their bbox_x/bbox_y and cx/cy equal our bbox_y/bbox_x'; %#ok<AGROW>
L{end+1} = '   and cy/cx). The cell set is identical -- only the axis labels swap, which'; %#ok<AGROW>
L{end+1} = '   is unobservable for the centred single source but was fixed here for the'; %#ok<AGROW>
L{end+1} = '   asymmetric 3-chip layout (chip-distance correctness was verified against'; %#ok<AGROW>
L{end+1} = '   a direct block-membership check).'; %#ok<AGROW>
L{end+1} = sep; %#ok<AGROW>
txt = strjoin(L, newline); 
txt = [txt, newline];
end

% ==========================================================================
function str = passstr(ok)
if ok, str = 'PASS'; else, str = 'FAIL'; end
end

function str = fmt_dists(v)
str = sprintf('%d/', v);
str = str(1:end-1);
end

% ==========================================================================
function write_csv(path, reg, ref, cc)
fid = fopen(path, 'w');
hdr = {'case','n_nodes','n_edges','pinned','T_max_C','T_mean_solid_C', ...
    'hotspot_mm2','dp','material_mm2','max_chip_to_tree_dist','chip_dists', ...
    'tree_cells_in_blocks','bbox_x','bbox_y','centroid_x','centroid_y', ...
    'deg1','deg2','deg3','deg4','deg5p','forks','leaves','flow_root', ...
    'radius_min','radius_max','radius_mean','frac_cap_le_0p6', ...
    'murray_max_rel_err','n_recalcs','total_iters','elapsed_s','note'};
fprintf(fid, '%s\n', strjoin(hdr, ','));
% regression row
fprintf(fid, '%s,%d,%d,%d,%.4f,%.4f,%.1f,%.3f,%.3f,%d,%s,%d,%s,%s,%.4f,%.4f,%d,%d,%d,%d,%d,%d,%d,%d,%.4f,%.4f,%.4f,%.4f,%.6e,%d,%d,%.2f,%s\n', ...
    'single_source_regression_rs1', reg.n_nodes, reg.n_edges, reg.pinned_cells, ...
    reg.T_max, reg.T_mean_solid, reg.hotspot_mm2, reg.dp, reg.material_mm2, ...
    reg.max_chip_to_tree_dist, fmt_dists(reg.chip_dists), reg.tree_cells_in_blocks, ...
    fmt_bbox(reg.bbox_x), fmt_bbox(reg.bbox_y), reg.centroid(1), reg.centroid(2), ...
    reg.deg1, reg.deg2, reg.deg3, reg.deg4, reg.deg5p, reg.forks, reg.leaves, ...
    reg.flow_root, reg.radius_min, reg.radius_max, reg.radius_mean, ...
    reg.frac_capillary_le_0p6, reg.murray_max_rel_err, reg.n_recalcs, ...
    reg.total_iters, reg.elapsed, 'computed_matlab_this_run');
% static python reference row
fprintf(fid, '%s,%d,%d,%d,%.4f,%.4f,%.1f,%.3f,%.3f,%d,%s,%d,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s\n', ...
    'static_tree_python_ref', ref.nodes, 599, ref.pinned, ref.T_max, ref.T_mean, ...
    ref.hotspot, ref.dp, ref.material, ref.maxdist, '0/0/0', ref.blocks_cells, ...
    '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', ...
    'recorded outputs/multi_source_results.csv');
for ii = 1:numel(cc)
    c = cc{ii};
    fprintf(fid, '%s,%d,%d,%d,%.4f,%.4f,%.1f,%.3f,%.3f,%d,%s,%d,%s,%s,%.4f,%.4f,%d,%d,%d,%d,%d,%d,%d,%d,%.4f,%.4f,%.4f,%.4f,%.6e,%d,%d,%.2f,%s\n', ...
        sprintf('coupled_3chip_triangle_600_rs%d', c.recalc_every), c.n_nodes, ...
        c.n_edges, c.pinned_cells, c.T_max, c.T_mean_solid, c.hotspot_mm2, ...
        c.dp, c.material_mm2, c.max_chip_to_tree_dist, fmt_dists(c.chip_dists), ...
        c.tree_cells_in_blocks, fmt_bbox(c.bbox_x), fmt_bbox(c.bbox_y), ...
        c.centroid(1), c.centroid(2), c.deg1, c.deg2, c.deg3, c.deg4, c.deg5p, ...
        c.forks, c.leaves, c.flow_root, c.radius_min, c.radius_max, ...
        c.radius_mean, c.frac_capillary_le_0p6, c.murray_max_rel_err, ...
        c.n_recalcs, c.total_iters, c.elapsed, 'computed_matlab_this_run');
end
fclose(fid);
end

function str = fmt_bbox(b)
str = sprintf('[%d %d]', b(1), b(2));
end

% ==========================================================================
function msg = make_figure(path, cc, rsl, centers)
msg = 'skipped';
try
    fig = figure('Visible', 'off', 'Position', [80 80 1150 480], 'Color', 'w');
    for ii = 1:numel(cc)
        c = cc{ii};
        subplot(1, numel(cc), ii);
        imagesc(c.T_final); axis xy equal; colorbar; hold on;
        E = c.edges;                          % MATLAB-linear-1: i = y + x*grid
        px = floor(E / 50) + 1;               % grid col -> plot x
        py = mod(E, 50) + 1;                  % grid row -> plot y
        plot([px(:,1) px(:,2)]', [py(:,1) py(:,2)]', '-', ...
            'Color', [0 0.85 1], 'LineWidth', 0.6);
        for kk = 1:size(centers, 1)
            rectangle('Position', [centers(kk,2)-1.5, centers(kk,1)-1.5, 5, 5], ...
                'EdgeColor', 'w', 'LineStyle', '--', 'LineWidth', 1.0);
        end
        title(sprintf('coupled rs=%d: T_{max}=%.4f C, pinned=%d', ...
            rsl(ii), c.T_max, c.pinned_cells));
        xlabel('x [mm]'); ylabel('y [mm]');
    end
    exportgraphics(fig, path, 'Resolution', 140);
    close(fig);
    msg = sprintf('saved %s', path);
catch ME
    msg = sprintf('figure failed: %s', ME.message);
end
end

% ==========================================================================
function srcm = make_srcm_local(grid, centers)
% Union of 5x5 source blocks (source_radius = 2), 0-based (y,x) centres.
[yy, xx] = ndgrid(0:grid-1, 0:grid-1);
srcm = false(grid, grid);
for kk = 1:size(centers, 1)
    srcm = srcm | (abs(yy - centers(kk,1)) <= 2 & abs(xx - centers(kk,2)) <= 2);
end
end

function [T, iters, conv] = solve_poisson_local(srcb, grid, Tb, tol, maxit)
% Cold Jacobi solve from a uniform Tb field (field.py _solve_poisson).
T = Tb * ones(grid, grid);
iters = 0; conv = false;
for it = 1:maxit
    Tn = T;
    Tn(2:end-1, 2:end-1) = 0.25 * (T(3:end, 2:end-1) + T(1:end-2, 2:end-1) ...
        + T(2:end-1, 3:end) + T(2:end-1, 1:end-2)) + srcb;
    Tn(1, :) = Tb; Tn(end, :) = Tb; Tn(:, 1) = Tb; Tn(:, end) = Tb;
    d = max(abs(Tn(:) - T(:)));
    T = Tn; iters = it;
    if d < tol, conv = true; break; end
end
end

function Tn = normalize_local(T, Tb, Ttarget)
% Rescale a linear field so its peak is Ttarget (field.py normalize_field).
r = max(T(:)) - Tb;
if r <= 0
    Tn = T;
else
    Tn = Tb + (T - Tb) * (Ttarget - Tb) / r;
end
end
