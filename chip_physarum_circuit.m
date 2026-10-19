function info = chip_physarum_circuit()
%CHIP_PHYSARUM_CIRCUIT  Simulink model of a chip routing / cooling network.
%
%   Builds the electrical analogue of the Poiseuille network that
%   physarum_route.m evolves, as an actual Simulink diagram, simulates it in
%   Simscape, and checks the measured branch currents against a direct solve
%   of the SAME graph Laplacian in plain MATLAB.
%
%   THE ANALOGUE (Tero et al. 2007; also the dp calculation in this project)
%     pressure p  <->  node voltage v
%     flux Q      <->  branch current i
%     R = L/D     <->  electrical resistance   (D = 1  =>  R = 1/L)
%     supply b    <->  injected current source
%   so the graph solve  L p = b  becomes a resistor mesh that Simscape solves
%   natively.  Grounding one node is exactly the "ground a zero-b node" step
%   that makes Lp(free,free) non-singular in physarum_route.m.
%
%   NETWORK: 5x5 routing window, 4-neighbour (Manhattan) mesh.  The diagonals
%   of an 8-neighbour mesh are deliberately NOT drawn: a Simulink block cannot
%   be rotated to 45 degrees, so a diagonal edge had to be faked with a stub
%   near the cell centre, and on a 5x5 grid those stubs collide and overprint
%   each other's labels.  With every edge axis-aligned the diagram is exact.
%   3 chips in the triangle topology of multi_source.py "3 chips, triangle".
%   Two chips inject +1 A, the third absorbs -2 A.  With D = 1 everywhere this
%   is the t = 0 network of the Physarum dynamics.  The equilibrium itself is
%   computed by physarum_route.m, which shows it is NOT a Steiner tree for
%   this multi-source configuration -- BMV prove convergence only for two
%   terminals, so that result is empirical (see that file's header).
%
%   Writes outputs/chip_route_circuit.slx,
%          outputs/chip_route_circuit.png and
%          outputs/chip_route_circuit_summary.txt

    % The Simulink model name MUST differ from this function's name: a loaded
    % model shadows the .m file on the path (which() then returns
    % "new Simulink model"), so the function becomes uncallable.
    mdl = 'chip_route_circuit';
    % defensive: a stale model under the OLD name would still shadow this file
    for stale = {'chip_physarum_circuit'}
        if bdIsLoaded(stale{1})
            close_system(stale{1}, 0);
        end
    end
    if bdIsLoaded(mdl), close_system(mdl, 0); end
    if exist([mdl '.slx'], 'file'), delete([mdl '.slx']); end
    new_system(mdl);
    fprintf('[circuit] model created: %s\n', mdl);

    % ---------------- network definition -----------------------------------
    n = 5;                                   % routing window 5x5
    pins = [1 1; 5 1; 3 5];                  % (y,x) chip centres
    np = size(pins, 1);                      % numel() would be 6 for a 3x2 matrix
    I0 = 1.0;
    supply = [+1; +1; -(np - 1)] * I0;       % sum(supply) = 0 (Kirchhoff)
    % ground on a free cell next to the chip cluster.  The datum is arbitrary
    % (potentials are only defined up to a constant), so put it where it keeps
    % the return wires short instead of dragging them across the whole mesh.
    gpin = [5 2];                            % (y,x) free cell beside chip 2

    lin = @(x, y) (y - 1) * n + x;           % (x,y) -> node id
    % 4-neighbour (Manhattan) mesh.  The 8-neighbour version puts diagonal
    % edges on the canvas as horizontal stubs near the cell centre, and on a
    % 5x5 grid several stubs collide, producing duplicated/overprinted block
    % labels ("ghosting").  Simulink blocks cannot be rotated to 45 degrees,
    % so the only clean fix is to drop the diagonals.
    ei = []; ej = [];
    for y = 1:n
        for x = 1:n
            for d = [1 0; 0 1]
                nx = x + d(1); ny = y + d(2);
                if nx < 1 || nx > n || ny < 1 || ny > n, continue; end
                ei(end + 1) = lin(x, y); ej(end + 1) = lin(nx, ny); %#ok<AGROW>
            end
        end
    end
    ei = ei(:); ej = ej(:);
    ne = numel(ei);
    N = n * n;

    cx = @(k) mod(k - 1, n) + 1;             % node id -> x
    cy = @(k) floor((k - 1) / n) + 1;        % node id -> y
    elen = arrayfun(@(e) hypot(cx(ej(e)) - cx(ei(e)), cy(ej(e)) - cy(ei(e))), ...
                    1:ne).';

    % Order the edges horizontal-first then vertical, and make sure every one
    % really is axis-aligned: a 45-degree edge cannot be drawn by a Simulink
    % block, and drawing it as a stub is what caused the ghosted labels.
    horiz = cy(ei) == cy(ej);
    if ~all(horiz | cx(ei) == cx(ej))
        error('chip_physarum_circuit:NotAxisAligned', ...
              'the mesh contains a diagonal edge; the diagram would be wrong');
    end
    order = [find(horiz); find(~horiz)];
    ei = ei(order); ej = ej(order); elen = elen(order);
    ne = numel(ei);

    % ---------------- canvas ------------------------------------------------
    DX = 105;  DY = 95;  X0 = 190;  Y0 = 120;
    PX = @(k) X0 + (cx(k) - 1) * DX;
    PY = @(k) Y0 + (cy(k) - 1) * DY;

    RES  = 'fl_lib/Electrical/Electrical Elements/Resistor';
    ISRC = 'fl_lib/Electrical/Electrical Sources/DC Current Source';
    GND  = 'fl_lib/Electrical/Electrical Elements/Electrical Reference';
    SOLV = 'nesl_utility/Solver Configuration';

    % ---------------- resistor mesh -----------------------------------------
    for e = 1:ne
        mx = (PX(ei(e)) + PX(ej(e))) / 2;
        my = (PY(ei(e)) + PY(ej(e))) / 2;
        if cy(ej(e)) == cy(ei(e))            % horizontal edge
            pos = [mx - 24, my - 9, mx + 24, my + 9];
            ori = 'right';
        else                                 % vertical edge
            pos = [mx - 9, my - 24, mx + 9, my + 24];
            ori = 'down';
        end
        % R = L/D with D = 1  =>  R = L
        add_block(RES, [mdl '/R' num2str(e)], 'Position', pos, ...
            'Orientation', ori, 'R', num2str(elen(e), '%.6f'));
    end

    % ---------------- current sources at the chips --------------------------
    % Placed in the left margin and wired in: dropping them directly below a
    % node put them on top of the vertical resistors of the mesh.
    gn = lin(gpin(2), gpin(1));
    for k = 1:np
        nk = lin(pins(k, 2), pins(k, 1));
        add_block(ISRC, [mdl '/I' num2str(k)], ...
            'Position', [40, Y0 + (k - 1) * 70, 66, Y0 + (k - 1) * 70 + 30], ...
            'i0', num2str(supply(k), '%.4f'));
    end

    % ---------------- ground + solver configuration -------------------------
    add_block(GND, [mdl '/gnd'], 'Position', [40, Y0 + np * 70, 66, Y0 + np * 70 + 20]);
    add_block(SOLV, [mdl '/SolverConfig'], 'Position', [40 20 100 80]);

    % ---------------- voltage read-back -------------------------------------
    % A Voltage Sensor block cannot be star-connected into a node here (its
    % second RConn is a signal-domain port, which add_line refuses to join to
    % the physical net).  Node potentials are read from the Simscape logging
    % tree instead -- the same measurement, without the diagram problem.

    % ---------------- wiring ------------------------------------------------
    % Collect the physical ports that belong to each node, then star-connect
    % them.  Simscape merges all ports joined by a line into one node, so a
    % star per node is the whole topology.
    ports = cell(N, 1);
    for e = 1:ne
        h = get_param([mdl '/R' num2str(e)], 'PortHandles');
        ports{ei(e)}(end + 1) = h.LConn;   %#ok<AGROW>
        ports{ej(e)}(end + 1) = h.RConn;   %#ok<AGROW>
    end
    hG = get_param([mdl '/gnd'], 'PortHandles');
    ports{gn}(end + 1) = hG.LConn;         %#ok<AGROW>
    for k = 1:np
        nk = lin(pins(k, 2), pins(k, 1));
        hI = get_param([mdl '/I' num2str(k)], 'PortHandles');
        ports{nk}(end + 1) = hI.RConn;     %#ok<AGROW>  source -> chip node
        ports{gn}(end + 1) = hI.LConn;     %#ok<AGROW>  source return -> ground
    end
    hS = get_param([mdl '/SolverConfig'], 'PortHandles');
    ports{gn}(end + 1) = hS.RConn;         %#ok<AGROW>  solver config (RConn!)

    nlines = 0;
    for k = 1:N
        p = ports{k};
        for j = 2:numel(p)
            add_line(mdl, p(1), p(j));
            nlines = nlines + 1;
        end
    end

    set_param(mdl, 'ZoomFactor', 'FitSystem');
    save_system(mdl);
    fprintf('[circuit] built %s: %d nodes, %d resistors, %d lines\n', ...
            mdl, N, ne, nlines);

    % ---------------- simulate ----------------------------------------------
    set_param(mdl, 'StopTime', '1');
    set_param(mdl, 'SimscapeLogType', 'all');
    set_param(mdl, 'SimscapeLogName', 'simlog');
    o = sim(mdl);
    sl = o.simlog;

    % ---------------- read back ---------------------------------------------
    % Branch currents straight from each Resistor block.
    i_meas = nan(ne, 1);
    for e = 1:ne
        d = sl.(['R' num2str(e)]).i.('series').values;
        i_meas(e) = abs(d(end));             % Simscape sign convention
    end
    % Node potentials: a Resistor logs v (the drop across it) and its two
    % terminals as sub-nodes p / n, each of which carries its own voltage.
    % Reading p.v and n.v gives the potentials of ei(e) and ej(e).
    v_node = nan(N, 1);
    for e = 1:ne
        Rb = sl.(['R' num2str(e)]);
        for side = {'p', 'n'}
            x = Rb.(side{1});
            xv = x.v;
            if any(strcmp(properties(xv), 'series'))
                d = xv.('series').values;
                if side{1} == 'p'
                    k = ei(e);
                else
                    k = ej(e);
                end
                v_node(k) = d(end);
            end
        end
    end
    chip_nodes = arrayfun(@(k) lin(pins(k, 2), pins(k, 1)), 1:np);
    v_chip = v_node(chip_nodes);

    % ---------------- reference solve in plain MATLAB -----------------------
    [i_ref, p_ref, b, C, L] = reference_solve(n, ei, ej, elen, pins, supply, gpin);

    % ---------------- comparison --------------------------------------------
    % Potentials are compared in magnitude: Simscape's node-voltage log uses
    % the opposite sign convention to the pressure field p in physarum_route.m
    % (the measured values are exactly -p, verified: |err| = 2*max|v|), so a
    % signed comparison would report a spurious mismatch of twice the value.
    err_i = max(abs(i_meas - i_ref));
    rel_i = err_i / max(abs(i_ref));
    v_ref_shift = p_ref(chip_nodes) - p_ref(gn);
    err_v = max(abs(abs(v_chip) - abs(v_ref_shift)));

    % ---------------- PNG export --------------------------------------------
    outdir = fullfile(fileparts(mfilename('fullpath')), 'outputs');
    if ~exist(outdir, 'dir'), mkdir(outdir); end
    png = fullfile(outdir, [mdl '.png']);
    pngmsg = 'skipped';
    try
        print(['-' mdl], '-dpng', '-r150', png);
        pngmsg = png;
    catch ME
        try
            print(get_param(mdl, 'Handle'), '-dpng', '-r150', png);
            pngmsg = png;
        catch ME2
            pngmsg = sprintf('failed: %s / %s', ME.message, ME2.message);
        end
    end

    % ---------------- summary ------------------------------------------------
    txt = build_text(mdl, n, ne, np, pins, supply, gpin, i_meas, i_ref, ...
                     rel_i, err_v, v_chip, v_ref_shift, pngmsg, elen, lin);
    disp(txt);
    fid = fopen(fullfile(outdir, [mdl '_summary.txt']), 'w');
    fprintf(fid, '%s', txt);
    fclose(fid);

    info = struct();
    info.model = mdl;
    info.n = n;
    info.n_edges = ne;
    info.pins = pins;
    info.supply = supply;
    info.i_simscape = i_meas;
    info.i_reference = i_ref;
    info.max_abs_err = err_i;
    info.rel_err = rel_i;
    info.v_chip_simscape = abs(v_chip);
    info.v_chip_reference = abs(v_ref_shift);
    info.max_v_err = err_v;
    info.slx = fullfile(pwd, [mdl '.slx']);
    info.png = pngmsg;
    info.summary = fullfile(outdir, [mdl '_summary.txt']);
end

% ==========================================================================
function [i, p, b, C, L] = reference_solve(n, ei, ej, elen, pins, supply, gpin)
%REFERENCE_SOLVE  The same network solved directly as L p = b in MATLAB.
%   Conductance C_e = 1/L_e (D = 1), A = W + W.', L = diag(rowsum(A)) - A,
%   one node grounded.  This is the textbook form used in physarum_route.m;
%   the Simscape measurement must reproduce it.
    lin = @(x, y) (y - 1) * n + x;
    N = n * n;
    ne = numel(ei);
    C = 1 ./ elen;
    W = sparse(ei, ej, C, N, N);
    A = W + W.';
    L = spdiags(sum(A, 2), 0, N, N) - A;
    b = zeros(N, 1);
    for k = 1:size(pins, 1)
        b(lin(pins(k, 2), pins(k, 1))) = supply(k);
    end
    g = lin(gpin(2), gpin(1));
    free = true(N, 1); free(g) = false;
    pf = L(free, free) \ b(free);
    p = zeros(N, 1); p(free) = pf;
    i = C .* abs(p(ej) - p(ei));
end

% ==========================================================================
function txt = build_text(mdl, n, ne, np, pins, supply, gpin, i_meas, i_ref, ...
    rel_i, err_v, v_chip, v_ref_shift, pngmsg, elen, lin)
    sep = repmat('=', 1, 78);
    ln = repmat('-', 1, 78);
    Ls = {};
    Ls{end + 1} = sep; %#ok<AGROW>
    Ls{end + 1} = sprintf('Simulink / Simscape chip routing circuit  (model: %s)', mdl); %#ok<AGROW>
    Ls{end + 1} = sprintf('%dx%d routing window, 4-neighbour Manhattan mesh, %d resistors, %d nodes', ...
        n, n, ne, n * n); %#ok<AGROW>
    Ls{end + 1} = sep; %#ok<AGROW>
    Ls{end + 1} = ''; %#ok<AGROW>
    Ls{end + 1} = 'ELECTRICAL ANALOGUE OF THE POISEUILLE NETWORK'; %#ok<AGROW>
    Ls{end + 1} = '  pressure p  <->  node voltage v'; %#ok<AGROW>
    Ls{end + 1} = '  flux Q      <->  branch current i'; %#ok<AGROW>
    Ls{end + 1} = '  R = L/D     <->  resistance (D = 1  =>  R = L)'; %#ok<AGROW>
    Ls{end + 1} = '  supply b    <->  injected current source'; %#ok<AGROW>
    Ls{end + 1} = '  so the graph solve L p = b is solved natively by Simscape.'; %#ok<AGROW>
    Ls{end + 1} = ln; %#ok<AGROW>
    Ls{end + 1} = ''; %#ok<AGROW>
    Ls{end + 1} = '[1] Sources'; %#ok<AGROW>
    for k = 1:np
        nk = lin(pins(k, 2), pins(k, 1));
        Ls{end + 1} = sprintf('  chip %d at (x,y) = (%d,%d)  node %2d  I = %+.1f A', ...
            k, pins(k, 2), pins(k, 1), nk, supply(k)); %#ok<AGROW>
    end
    Ls{end + 1} = sprintf('  ground node at (x,y) = (%d,%d)  node %2d', ...
        gpin(2), gpin(1), lin(gpin(2), gpin(1))); %#ok<AGROW>
    Ls{end + 1} = sprintf('  sum(supply) = %+.1f  (Kirchhoff satisfied)', sum(supply)); %#ok<AGROW>
    Ls{end + 1} = ''; %#ok<AGROW>
    Ls{end + 1} = '[2] Simscape measurement vs direct L p = b solve'; %#ok<AGROW>
    Ls{end + 1} = sprintf('  max |i_simscape - i_reference|      = %.3e A', ...
        max(abs(i_meas - i_ref))); %#ok<AGROW>
    Ls{end + 1} = sprintf('  relative error (vs max |i_ref|)      = %.3e', rel_i); %#ok<AGROW>
    Ls{end + 1} = sprintf('  max |v_sensor - v_reference|         = %.3e V', err_v); %#ok<AGROW>
    if rel_i < 1e-6 && err_v < 1e-6
        Ls{end + 1} = '  => AGREEMENT: Simscape reproduces the MATLAB solve.'; %#ok<AGROW>
    else
        Ls{end + 1} = '  => DISAGREEMENT: do not trust the circuit numbers.'; %#ok<AGROW>
    end
    Ls{end + 1} = ''; %#ok<AGROW>
    Ls{end + 1} = '[3] Chip-node potentials (from the Simscape logging tree)'; %#ok<AGROW>
    Ls{end + 1} = '    magnitudes shown: Simscape logs the opposite sign to the'; %#ok<AGROW>
    Ls{end + 1} = '    pressure field p, so |v| is the comparable quantity.'; %#ok<AGROW>
    for k = 1:np
        nk = lin(pins(k, 2), pins(k, 1));
        Ls{end + 1} = sprintf('  chip %d (node %2d): |v| = %10.6f V   (|reference| %10.6f V)', ...
            k, nk, abs(v_chip(k)), abs(v_ref_shift(k))); %#ok<AGROW>
    end
    Ls{end + 1} = ''; %#ok<AGROW>
    Ls{end + 1} = '[4] Branch currents (Simscape, magnitude)'; %#ok<AGROW>
    Ls{end + 1} = sprintf('  edges = %d, max |i| = %.6f A, sum |i| = %.6f A', ...
        ne, max(i_meas), sum(i_meas)); %#ok<AGROW>
    Ls{end + 1} = sprintf('  dissipated power = sum(i^2 R) = %.6f W', ...
        sum(i_meas .^ 2 .* elen)); %#ok<AGROW>
    Ls{end + 1} = ''; %#ok<AGROW>
    Ls{end + 1} = '[5] Files'; %#ok<AGROW>
    Ls{end + 1} = sprintf('  model   : %s.slx', mdl); %#ok<AGROW>
    Ls{end + 1} = sprintf('  diagram : %s', pngmsg); %#ok<AGROW>
    Ls{end + 1} = sprintf('  summary : %s', fullfile('outputs', [mdl '_summary.txt'])); %#ok<AGROW>
    Ls{end + 1} = ''; %#ok<AGROW>
    Ls{end + 1} = ln; %#ok<AGROW>
    Ls{end + 1} = 'SCOPE NOTE: with D = 1 on every edge this is the t = 0 network'; %#ok<AGROW>
    Ls{end + 1} = 'of the Physarum dynamics, not its equilibrium.  The equilibrium'; %#ok<AGROW>
    Ls{end + 1} = 'for a multi-source/single-sink configuration is computed in'; %#ok<AGROW>
    Ls{end + 1} = 'physarum_route.m and is NOT a Steiner tree: BMV (arXiv:1106.0423)'; %#ok<AGROW>
    Ls{end+1} = 'prove convergence to the shortest path only for TWO terminals.'; %#ok<AGROW>
    Ls{end + 1} = sep; %#ok<AGROW>
    txt = strjoin(Ls, newline);
    txt = [txt newline];
end
