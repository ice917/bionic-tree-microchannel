function bp_res = bionic_placement_main(seed_list, precomp)
%BIONIC_PLACEMENT_MAIN  Top-level entry for the chip-placement study.
%
%   bp_res = bionic_placement_main();
%
%   Optional: bionic_placement_main(seed_list, precomp) where seed_list is
%   the vector of EA restart seeds (default [42 43 44]) and precomp a cell
%   array of search results as returned by bionic_placement('search',...),
%   letting restarts be run stepwise. Writes
%     outputs/bionic_placement_results.csv   (per-generation best, all seeds)
%     outputs/bionic_placement_summary.txt   (validation, comparison, stability)
%   and returns everything in the bp_res struct. No clear/clc anywhere.

if nargin < 1 || isempty(seed_list), seed_list = [42 43 44]; end
if nargin < 2, precomp = {}; end
t_all = tic;
here = fileparts(mfilename('fullpath'));
outdir = fullfile(here, 'outputs');
if ~exist(outdir, 'dir'), mkdir(outdir); end
budget = 600;

% ---- hand-designed baselines (design vector = [x1 y1 x2 y2 x3 y3]) ----
fprintf('[main] evaluating baselines (budget %d) ...\n', budget);
tri = bionic_placement('eval', [15 15  15 35  35 25], budget);   % multi_source.py "3 chips, triangle" (cy,cx)=(15,15),(35,15),(25,35)
hor = bionic_placement('eval', [12 25  25 25  38 25], budget);   % equal-spaced row on y=25, dx=13

% ---- EA restarts ----
nseed = numel(seed_list);
runs = cell(1, nseed);
for s = 1:nseed
    if s <= numel(precomp) && ~isempty(precomp{s})
        runs{s} = precomp{s};
        fprintf('[main] seed %d: using precomputed restart (%d evals, %.1f s)\n', ...
            seed_list(s), runs{s}.n_evals, runs{s}.elapsed);
    else
        fprintf('[main] EA restart seed %d ...\n', seed_list(s));
        runs{s} = bionic_placement('search', seed_list(s), budget);
        fprintf('[main] seed %d: best T_max=%.4f T_mean=%.4f hot=%.1f design=[%s] (%d evals, %.1f s)\n', ...
            seed_list(s), runs{s}.best_T_max, runs{s}.best_T_mean, runs{s}.best_hotspot, ...
            sprintf('%d ', runs{s}.best_design), runs{s}.n_evals, runs{s}.elapsed);
    end
end

% ---- overall best across restarts (same lexicographic rule as the EA) ----
F = zeros(nseed, 2);
for s = 1:nseed, F(s, :) = [runs{s}.best_T_max, runs{s}.best_T_mean]; end
ibest = 1;
for s = 2:nseed
    if bp_lexless(F(s, :), F(ibest, :)), ibest = s; end
end
best_run = runs{ibest};
best = bionic_placement('eval', best_run.best_design, budget);  % re-eval via the same path

% ---- triangle reproduction check vs Python multi_source.py ----
pyref = struct('T_max', 27.5962, 'T_mean', 25.0633, 'hotspot', 75.0, ...
               'dp', 649.305, 'pinned', 525, 'dist', 0);
chk = [ ...
    tri.T_max,        pyref.T_max,   5e-4;
    tri.T_mean,       pyref.T_mean,  5e-4;
    tri.hotspot_mm2,  pyref.hotspot, 0.1;
    tri.tree_dp,      pyref.dp,      0.5;
    tri.pinned,       pyref.pinned,  0.5;
    tri.max_chip_dist, pyref.dist,   0.5];
ok = all(abs(chk(:,1) - chk(:,2)) <= chk(:,3));
if ok, msg = 'PASS'; else, msg = 'FAIL -- debug before trusting search results'; end
fprintf('[main] triangle reproduction check: %s\n', msg);

% ---- per-seed convergence generation (last strict improvement) ----
conv = zeros(1, nseed);
for s = 1:nseed
    H = runs{s}.hist;
    g = 1;
    for gg = 2:size(H, 1)
        if bp_lexless(H(gg, 9:10), H(gg-1, 9:10)), g = gg; end
    end
    conv(s) = g;
end

% ---- geometry descriptors (factual, for the mechanism note) ----
gtri = deal_geom([15 15 15 35 35 25]);
ghor = deal_geom([12 25 25 25 38 25]);
gbest = deal_geom(best_run.best_design);

% ---- write CSV: per-generation best for every restart ----
csv = fullfile(outdir, 'bionic_placement_results.csv');
fid = fopen(csv, 'w');
fprintf(fid, ['seed,gen,x1,y1,x2,y2,x3,y3,T_max_C,T_mean_solid_C,' ...
              'hotspot_mm2,max_chip_to_tree_dist,tree_dp,best_so_far\n']);
for s = 1:nseed
    H = runs{s}.hist;
    for g = 1:size(H, 1)
        fprintf(fid, '%d,%d,%d,%d,%d,%d,%d,%d,%.5f,%.8f,%.1f,%d,%.3f,%d\n', ...
            H(g,1), H(g,2), H(g,3), H(g,4), H(g,5), H(g,6), H(g,7), H(g,8), ...
            H(g,9), H(g,10), H(g,11), H(g,12), H(g,13), H(g,14));
    end
end
fclose(fid);

% ---- write summary txt ----
sumtxt = fullfile(outdir, 'bionic_placement_summary.txt');
fid = fopen(sumtxt, 'w');
fprintf(fid, 'Bionic chip placement + static cooling tree -- joint optimisation study\n');
fprintf(fid, ['generated %s | MATLAB %s | grid 50x50 (50 mm), Dirichlet 25 C\n' ...
              'pipeline: multi_source.py rules ported to MATLAB (static greedy growth)\n\n'], ...
        datestr(now, 'yyyy-mm-dd HH:MM:SS'), version('-release'));

fprintf(fid, '[1] Triangle reproduction check (MATLAB vs Python multi_source.py, budget 600)\n');
fprintf(fid, '    metric              MATLAB      Python     delta      tol     status\n');
names = {'T_max [C]'; 'T_mean_solid [C]'; 'hotspot [mm2]'; 'tree dp [a.u.]'; 'pinned cells'; 'chip-to-tree dist'};
for i = 1:size(chk, 1)
    if abs(chk(i,1) - chk(i,2)) <= chk(i,3), st = 'ok'; else, st = 'MISMATCH'; end
    fprintf(fid, '    %-18s %10.4f %10.4f %10.2e %8.1e  %s\n', ...
        names{i}, chk(i,1), chk(i,2), chk(i,1)-chk(i,2), chk(i,3), st);
end
fprintf(fid, '    overall: %s\n\n', msg);

fprintf(fid, '[2] Three-layout comparison (budget 600 nodes, identical pinning rules)\n');
fprintf(fid, '    layout       centres (x,y)                        T_max[C]  T_mean[C]  hotspot[mm2]  dp[a.u.]   pinned  chipdist\n');
fprintf(fid, '    %-12s %-36s %8.4f  %9.4f  %12.1f  %9.3f  %6d  %5d\n', ...
    'triangle',    fmt_design([15 15 15 35 35 25]), tri.T_max, tri.T_mean, tri.hotspot_mm2, tri.tree_dp, tri.pinned, tri.max_chip_dist);
fprintf(fid, '    %-12s %-36s %8.4f  %9.4f  %12.1f  %9.3f  %6d  %5d\n', ...
    'horizontal',  fmt_design([12 25 25 25 38 25]), hor.T_max, hor.T_mean, hor.hotspot_mm2, hor.tree_dp, hor.pinned, hor.max_chip_dist);
fprintf(fid, '    %-12s %-36s %8.4f  %9.4f  %12.1f  %9.3f  %6d  %5d\n', ...
    'bionic-best', fmt_design(best_run.best_design), best.T_max, best.T_mean, best.hotspot_mm2, best.tree_dp, best.pinned, best.max_chip_dist);
fprintf(fid, ['    (horizontal baseline = 3 chips on the y=25 line at x = 12/25/38, spacing 13;\n' ...
              '     bionic-best = EA winner, seed %d restart, re-evaluated through the same path)\n\n'], ...
        best_run.seed);

fprintf(fid, '[3] Search configuration\n');
fprintf(fid, ['    population 12, generations 12, elite top-4 kept, crossover = rounded\n' ...
              '    mean of two elite parents, Gaussian mutation sigma annealed 6 -> 2\n' ...
              '    linearly, objective = lexicographic (T_max, T_mean_solid), illegal\n' ...
              '    layouts (centre <4 cells from an edge, or pairwise Chebyshev <8)\n' ...
              '    penalised to the worst rank, rng(seed) fixed per restart.\n\n']);

fprintf(fid, '[4] Per-generation best-so-far (T_max/T_mean; T_mean decides where T_max saturates)\n');
for s = 1:nseed
    H = runs{s}.hist;
    fprintf(fid, '    seed %d: ', seed_list(s));
    for g = 1:size(H, 1)
        fprintf(fid, 'g%d=%.5f/%.8f ', g, H(g, 9), H(g, 10));
    end
    fprintf(fid, '-> best (T_max=%.5f, T_mean=%.8f), last strict improvement at gen %d, design=[%s]\n', ...
        runs{s}.best_T_max, runs{s}.best_T_mean, conv(s), sprintf('%d ', runs{s}.best_design));
end
fprintf(fid, '\n');

fprintf(fid, '[5] Restart stability (seeds %s)\n', sprintf('%d ', seed_list));
for s = 1:nseed
    fprintf(fid, '    seed %d: design=[%s] T_max=%.4f T_mean=%.4f hotspot=%.1f dp=%.3f (%d evals, %.1f s)\n', ...
        seed_list(s), fmt_design(runs{s}.best_design), runs{s}.best_T_max, ...
        runs{s}.best_T_mean, runs{s}.best_hotspot, runs{s}.best_dp, runs{s}.n_evals, runs{s}.elapsed);
end
tmean_spread = max(F(:,2)) - min(F(:,2));
same_design = true;
for s = 2:nseed
    same_design = same_design && isequal(runs{1}.best_design, runs{s}.best_design);
end
if same_design, sd_str = 'yes'; else, sd_str = 'no'; end
fprintf(fid, '    T_mean spread across restarts: %.2e C; identical winning design: %s\n', ...
    tmean_spread, sd_str);
fprintf(fid, '    restarts selected the same layout: %s\n\n', sd_str);

fprintf(fid, '[6] Winner geometry (factual descriptors)\n');
fprintf(fid, '    %-12s mean chip-to-edge dist = %5.1f cells, min pairwise Chebyshev = %2d, mean pairwise Euclid = %5.1f\n', ...
    'triangle', gtri(1), gtri(2), gtri(3));
fprintf(fid, '    %-12s mean chip-to-edge dist = %5.1f cells, min pairwise Chebyshev = %2d, mean pairwise Euclid = %5.1f\n', ...
    'horizontal', ghor(1), ghor(2), ghor(3));
fprintf(fid, '    %-12s mean chip-to-edge dist = %5.1f cells, min pairwise Chebyshev = %2d, mean pairwise Euclid = %5.1f\n', ...
    'bionic-best', gbest(1), gbest(2), gbest(3));
fprintf(fid, '\n');

fprintf(fid, '[7] Limitations\n');
fprintf(fid, ['    - Controls are hand-designed layouts (triangle, equal-spaced horizontal),\n' ...
              '      NOT optimised controls; improvements quoted here are vs hand layouts.\n' ...
              '      Percentage conclusions from other experiments (e.g. a "50.9%%" figure)\n' ...
              '      do NOT transfer to this experiment.\n' ...
              '    - Static growth only: the field is fixed while the tree grows (no\n' ...
              '      field-tree coupling as in grow_coupled.py).\n' ...
              '    - Single budget (600 nodes), single grid (50x50), idealised Dirichlet\n' ...
              '      coolant pinning (upper bound of convective cooling).\n' ...
              '    - Small EA budget (<=100 unique evaluations per restart): the winner is\n' ...
              '      a reproducible local optimum under the lexicographic objective, not a\n' ...
              '      proof of global optimality.\n\n']);

tot_evals = 3 + sum(cellfun(@(r) r.n_evals, runs));
tot_look = 3 + sum(cellfun(@(r) r.n_lookups, runs));
tot_time = toc(t_all);
fprintf(fid, '[8] Totals\n');
fprintf(fid, '    PDE evaluations: %d unique (baseline/re-eval 3 + search %d), %d lookup attempts\n', ...
    tot_evals, tot_evals - 3, tot_look);
fprintf(fid, '    wall time: %.1f s (search only: %.1f s)\n', tot_time, sum(cellfun(@(r) r.elapsed, runs)));
fclose(fid);

fprintf('\n[main] comparison (T_max / T_mean / hotspot):\n');
fprintf('  triangle   %8.4f %9.4f %8.1f\n', tri.T_max, tri.T_mean, tri.hotspot_mm2);
fprintf('  horizontal %8.4f %9.4f %8.1f\n', hor.T_max, hor.T_mean, hor.hotspot_mm2);
fprintf('  best       %8.4f %9.4f %8.1f  design=[%s]\n', best.T_max, best.T_mean, ...
    best.hotspot_mm2, sprintf('%d ', best_run.best_design));
fprintf('[main] triangle check: %s | evals=%d | time=%.1f s\n', msg, tot_evals, tot_time);
fprintf('[main] wrote:\n  %s\n  %s\n', csv, sumtxt);

% ---- return struct ----
bp_res = struct();
bp_res.budget = budget;
bp_res.triangle = tri;  bp_res.horizontal = hor;  bp_res.best = best;
bp_res.best_design = best_run.best_design;  bp_res.best_seed = best_run.seed;
bp_res.runs = runs;  bp_res.seed_list = seed_list;
bp_res.conv_gen = conv;
bp_res.check_pass = ok;
bp_res.total_evals = tot_evals;
bp_res.total_time_s = tot_time;
bp_res.csv_file = csv;  bp_res.summary_file = sumtxt;
end

% ---------------------------------------------------------------------
%                              helpers
% ---------------------------------------------------------------------
function lt = bp_lexless(a, b)
if abs(a(1) - b(1)) > 1e-6
    lt = a(1) < b(1);
else
    lt = a(2) < b(2);
end
end

function s = fmt_design(d)
s = sprintf('(%d,%d) (%d,%d) (%d,%d)', d(1), d(2), d(3), d(4), d(5), d(6));
end

function g = deal_geom(d)
xs = d([1 3 5]);  ys = d([2 4 6]);
ed = zeros(1, 3);
for k = 1:3
    ed(k) = min([xs(k), 49 - xs(k), ys(k), 49 - ys(k)]);
end
g(1) = mean(ed);
g(2) = min([max(abs(xs(1)-xs(2)), abs(ys(1)-ys(2))), ...
            max(abs(xs(1)-xs(3)), abs(ys(1)-ys(3))), ...
            max(abs(xs(2)-xs(3)), abs(ys(2)-ys(3)))]);
g(3) = mean([hypot(xs(1)-xs(2), ys(1)-ys(2)), ...
             hypot(xs(1)-xs(3), ys(1)-ys(3)), ...
             hypot(xs(2)-xs(3), ys(2)-ys(3))]);
end
