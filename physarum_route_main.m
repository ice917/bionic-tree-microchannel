function physarum_route_main()
%PHYSARUM_ROUTE_MAIN  Entry point: run the demo and write the deliverables.
    res = physarum_route();

    fprintf('=============== Physarum routing: sanity check ===============\n');

    fprintf('\n[VALIDATION: two terminals -- the regime BMV prove]\n');
    fprintf('  BMV Thm 2: unique shortest s-t path => D converges to the unit\n');
    fprintf('  flow on that path.  Prediction: n-1 edges, all diagonal,\n');
    fprintf('  euclid = (n-1)*sqrt(2) to machine precision.\n');
    fprintf('%5s %8s %10s %10s %12s %8s %8s\n', 'n', 'iters', ...
            'edges', 'expected', 'euclid', 'err', 'diag');
    allpass = true;
    for i = 1:numel(res.validation)
        v = res.validation(i);
        ok = (v.n_edges_kept == v.n_expected) && v.all_diagonal && ...
             (v.abs_err < 1e-9) && v.dnorm_monotone;
        if ~ok, allpass = false; end
        if ok, tag = 'PASS'; else, tag = 'FAIL'; end
        fprintf('%5d %8d %10d %10d %12.6f %8.1e %8d  %s\n', ...
                v.n, v.iters_used, v.n_edges_kept, v.n_expected, ...
                v.len_euclid, v.abs_err, v.all_diagonal, tag);
    end
    if allpass, verdict = 'ALL PASS'; else, verdict = 'FAILED'; end
    fprintf('  => two-terminal validation: %s\n', verdict);

    for i = 1:numel(res.cases)
        c = res.cases(i);
        fprintf('\n[%s]  n=%d  pins=%d\n', c.name, c.n, size(c.pins, 1));
        fprintf('  h=%.2f thresh=%.2f iters=%d  fp_resid=%.2e  ||D||1 mono=%d\n', ...
                c.h, c.thresh, c.iters_used, c.fp_residual, c.dnorm_monotone);
        fprintf('  RAW support : %d edges, euclid=%.4f, manh=%.4f, pins_conn=%d (%d comps)\n', ...
                c.n_edges_raw, c.len_euclid_raw, c.len_manhattan_raw, ...
                c.raw_connected, c.raw_components);
        fprintf('  TREE (MST)  : %d edges, euclid=%.4f, manh=%.4f, pins_conn=%d, covers_all=%d\n', ...
                c.n_edges_tree, c.tree_len_euclid, c.tree_len_manhattan, ...
                c.tree_connected, c.tree_covers_pins);
        fprintf('  baselines   : MST manh=%.4f   RSMT(hanan)=%.4f\n', ...
                c.mst_manhattan, c.rsmt_hanan);
        fprintf('  tree/MST    = %.4f   obstacle crossings = %d\n', ...
                c.tree_over_mst, c.obstacle_crossings);
    end

    fprintf('\n=============== damping-step sensitivity ===============\n');
    fprintf('%6s %8s %8s %10s %10s %6s %8s %8s %10s\n', 'h', ...
            'raw_e', 'tree_e', 'tree_eu', 'tree_mh', 'conn', 'iters', 'mono', 'fp_resid');
    for i = 1:numel(res.sensitivity)
        s = res.sensitivity(i);
        fprintf('%6.2f %8d %8d %10.4f %10.4f %6d %8d %8d %10.2e\n', ...
                s.h, s.n_edges_raw, s.n_edges_tree, s.tree_len_euclid, ...
                s.tree_len_manhattan, s.tree_connected, s.iters_used, ...
                s.dnorm_monotone, s.fp_residual);
    end

    % ---------------- write deliverables ----------------
    outdir = fullfile(fileparts(mfilename('fullpath')), 'outputs');
    if ~exist(outdir, 'dir'), mkdir(outdir); end

    fp = fopen(fullfile(outdir, 'physarum_route_summary.txt'), 'w');
    fprintf(fp, 'Physarum adaptive-network routing (MATLAB)\n');
    fprintf(fp, '==========================================\n\n');
    fprintf(fp, 'Model    : Bonifaci-Mehlhorn-Varma, "Physarum Can Compute Shortest\n');
    fprintf(fp, '           Paths", arXiv:1106.0423, JTB 309:121-133, eq.(1)-(2).\n');
    fprintf(fp, '           R_e = L_e/D_e, conductance C_e = D_e/L_e, dD_e/dt = |Q_e| - D_e,\n');
    fprintf(fp, '           Q_e = C_e |p_u - p_v|, node eq. L p = b with\n');
    fprintf(fp, '           L = diag(rowsum(A)) - A,  A = W + W.''.\n');
    fprintf(fp, 'Scheme   : Straszak-Vishnoi arXiv:1601.02712 eq.(12),\n');
    fprintf(fp, '           D^{k+1} = (1-h) D^k + h |Q^k|, h in (0,1).  Keeps D>0 and\n');
    fprintf(fp, '           makes ||D||_1 non-increasing (Lemma 5.6).\n');
    fprintf(fp, 'Post-proc: threshold D>thresh, then Prim MST on the saved network.\n');
    fprintf(fp, '           Required because multi-source/single-sink is only a\n');
    fprintf(fp, '           transportation problem: BMV Thm 7 gives attraction to the\n');
    fprintf(fp, '           equilibrium SET only, Thm 8 needs "no two equilibria with\n');
    fprintf(fp, '           equal cost"; Sun 2019 (arXiv:1903.08926) states the\n');
    fprintf(fp, '           multi-source solver saved network is not guaranteed to\n');
    fprintf(fp, '           be a tree nor connected, hence the MST pass.\n');
    fprintf(fp, 'Scope    : empirical demonstration only.  BMV leave approximate\n');
    fprintf(fp, '           Steiner-tree computation as an open problem with "no\n');
    fprintf(fp, '           theoretical analysis available", so nothing here is a\n');
    fprintf(fp, '           certified optimum.\n\n');
    fprintf(fp, '[VALIDATION: two terminals -- the only regime BMV prove]\n');
    fprintf(fp, '   n  iters   edges  expected     euclid       err  all_diag\n');
    allpass = true;
    for i = 1:numel(res.validation)
        v = res.validation(i);
        ok = (v.n_edges_kept == v.n_expected) && v.all_diagonal && ...
             (v.abs_err < 1e-9) && v.dnorm_monotone;
        if ~ok, allpass = false; end
        fprintf(fp, '%4d %6d %8d %9d %11.6f %9.1e %8d\n', ...
                v.n, v.iters_used, v.n_edges_kept, v.n_expected, ...
                v.len_euclid, v.abs_err, v.all_diagonal);
    end
    if allpass, verdict = 'ALL PASS'; else, verdict = 'FAILED'; end
    fprintf(fp, '  => two-terminal validation: %s\n', verdict);
    fprintf(fp, '  (BMV Thm 2 prediction: n-1 edges, all diagonal,\n');
    fprintf(fp, '   euclid = (n-1)*sqrt(2) to machine precision.)\n\n');
    for i = 1:numel(res.cases)
        c = res.cases(i);
        fprintf(fp, '[%s]\n', c.name);
        fprintf(fp, '  grid n=%d, pins=%d, h=%.2f, thresh=%.2f, iterations=%d\n', ...
                c.n, size(c.pins, 1), c.h, c.thresh, c.iters_used);
        fprintf(fp, '  fixed-point residual (rel max|D-|Q||) = %.3e\n', c.fp_residual);
        fprintf(fp, '  ||D||_1 final    = %.6f   monotone = %d\n', ...
                c.dnorm_final, c.dnorm_monotone);
        fprintf(fp, '  RAW Physarum support:\n');
        fprintf(fp, '    edges          = %d\n', c.n_edges_raw);
        fprintf(fp, '    euclidean      = %.6f\n', c.len_euclid_raw);
        fprintf(fp, '    manhattan      = %.6f\n', c.len_manhattan_raw);
        fprintf(fp, '    pins connected = %d  (components %d)\n', ...
                c.raw_connected, c.raw_components);
        fprintf(fp, '  EXTRACTED TREE (Prim MST on the support):\n');
        fprintf(fp, '    edges          = %d\n', c.n_edges_tree);
        fprintf(fp, '    euclidean      = %.6f\n', c.tree_len_euclid);
        fprintf(fp, '    manhattan      = %.6f\n', c.tree_len_manhattan);
        fprintf(fp, '    pins connected = %d\n', c.tree_connected);
        fprintf(fp, '    covers all pins= %d\n', c.tree_covers_pins);
        fprintf(fp, '  BASELINES:\n');
        fprintf(fp, '    MST (manhattan) = %.6f\n', c.mst_manhattan);
        fprintf(fp, '    RSMT (hanan)    = %.6f\n', c.rsmt_hanan);
        fprintf(fp, '    tree / MST      = %.6f\n', c.tree_over_mst);
        fprintf(fp, '    obstacle crossings = %d\n\n', c.obstacle_crossings);
    end
    fprintf(fp, '[damping-step sensitivity, 4 corners on n=16]\n');
    fprintf(fp, '   h   raw_e tree_e  tree_eu  tree_mh conn iters  mono fp_resid\n');
    for i = 1:numel(res.sensitivity)
        s = res.sensitivity(i);
        fprintf(fp, '%5.2f %6d %6d %8.4f %8.4f %5d %5d %5d %9.2e\n', ...
                s.h, s.n_edges_raw, s.n_edges_tree, s.tree_len_euclid, ...
                s.tree_len_manhattan, s.tree_connected, s.iters_used, ...
                s.dnorm_monotone, s.fp_residual);
    end
    fclose(fp);

    fc = fopen(fullfile(outdir, 'physarum_route_results.csv'), 'w');
    fprintf(fc, 'case,n,pins,h,thresh,iters,fp_residual,edges_raw,len_euclid_raw,len_manhattan_raw,raw_connected,raw_components,edges_tree,tree_len_euclid,tree_len_manhattan,tree_connected,tree_covers_pins,mst_manhattan,rsmt_hanan,tree_over_mst,obstacle_crossings,dnorm_final,dnorm_monotone\n');
    for i = 1:numel(res.validation)
        v = res.validation(i);
        ok = (v.n_edges_kept == v.n_expected) && v.all_diagonal && ...
             (v.abs_err < 1e-9) && v.dnorm_monotone;
        % validation rows are not comparable to the routing cases, so only the
        % columns that carry the same meaning are filled; the rest are NaN.
        fprintf(fc, '"validation:two-terminal n=%d",%d,2,0.30,0.50,%d,%.3e,%d,%.6f,%.6f,%d,%d,%.6f,%.6f,%.6f,%d,%d,%.6f,%.6f,%.6f,%d,%.6f,%d\n', ...
                v.n, v.n, v.iters_used, v.fp_residual, v.n_edges_kept, ...
                v.len_euclid, v.len_euclid, v.n_edges_kept == v.n_expected, ...
                1, NaN, NaN, NaN, v.n_edges_kept == v.n_expected, ok, ...
                v.len_euclid, NaN, NaN, 0, NaN, v.dnorm_monotone);
    end
    for i = 1:numel(res.cases)
        c = res.cases(i);
        fprintf(fc, '"%s",%d,%d,%.2f,%.2f,%d,%.3e,%d,%.6f,%.6f,%d,%d,%d,%.6f,%.6f,%d,%d,%.6f,%.6f,%.6f,%d,%.6f,%d\n', ...
                c.name, c.n, size(c.pins, 1), c.h, c.thresh, c.iters_used, ...
                c.fp_residual, c.n_edges_raw, c.len_euclid_raw, ...
                c.len_manhattan_raw, c.raw_connected, c.raw_components, ...
                c.n_edges_tree, c.tree_len_euclid, c.tree_len_manhattan, ...
                c.tree_connected, c.tree_covers_pins, c.mst_manhattan, ...
                c.rsmt_hanan, c.tree_over_mst, c.obstacle_crossings, ...
                c.dnorm_final, c.dnorm_monotone);
    end
    fclose(fc);

    fprintf('\nWrote:\n  %s\n  %s\n', ...
            fullfile(outdir, 'physarum_route_summary.txt'), ...
            fullfile(outdir, 'physarum_route_results.csv'));
end
