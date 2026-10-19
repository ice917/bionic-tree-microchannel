function chip_route_iso()
%CHIP_ROUTE_ISO  Simulink circuit isomorphic to the 8-neighbour Physarum mesh.
%
%   WHY THIS FILE EXISTS
%   -------------------
%   The previous version (chip_physarum_circuit.m) dropped the diagonals and
%   drew a 4-neighbour Manhattan mesh.  That is NOT isomorphic to the mesh
%   physarum_route.m evolves, which is 8-neighbour: it has 4 edge directions
%   (0, 90, 45, 135 degrees) and diagonal edges are weighted sqrt(2).
%
%   A Simulink block cannot be rotated to 45 degrees (Orientation accepts only
%   right/left/up/down), and no linear map of the canvas can make all four
%   directions axis-aligned at once.  So the geometry is carried by MASK ICONS
%   instead: every resistor block is masked and its icon is drawn along the
%   real direction of its edge, with the block sized to the edge's bounding
%   box.  Electrically the network is unchanged; visually it is now the actual
%   8-neighbour mesh.
%
%   Node blocks are also masked and drawn as dots, so the diagram reads as a
%   mesh of nodes joined by resistors in the true directions.

    % The model name MUST differ from this function's name: a loaded model
    % shadows the .m file on the path, making the function uncallable.
    mdl = 'chip_route_iso_mdl';
    if bdIsLoaded(mdl), close_system(mdl, 0); end
    if bdIsLoaded('chip_route_iso'), close_system('chip_route_iso', 0); end
    if exist([mdl '.slx'], 'file'), delete([mdl '.slx']); end
    new_system(mdl);
    fprintf('[iso] model created: %s\n', mdl);

    n = 4;                                   % small window: keep the diagram legible
    pins = [1 1; 4 1; 2 4];                  % (y,x)
    np = size(pins, 1);
    I0 = 1.0;
    supply = [+1; +1; -(np - 1)] * I0;
    gpin = [4 4];

    lin = @(x, y) (y - 1) * n + x;
    ei = []; ej = [];
    % NOTE: `for d = M` iterates over the COLUMNS of M, not the rows, so the
    % step list must be indexed explicitly.
    steps = [1 0; 0 1; 1 1; 1 -1];           % E, S, SE, NE
    for y = 1:n
        for x = 1:n
            for s = 1:size(steps, 1)
                nx = x + steps(s, 1); ny = y + steps(s, 2);
                if nx < 1 || nx > n || ny < 1 || ny > n, continue; end
                ei(end + 1) = lin(x, y); ej(end + 1) = lin(nx, ny);
            end
        end
    end
    ei = ei(:); ej = ej(:);
    ne = numel(ei);
    N = n * n;

    cx = @(k) mod(k - 1, n) + 1;
    cy = @(k) floor((k - 1) / n) + 1;
    elen = arrayfun(@(e) hypot(cx(ej(e)) - cx(ei(e)), cy(ej(e)) - cy(ei(e))), 1:ne).';

    % ---------------- canvas ------------------------------------------------
    DX = 120;  DY = 110;  X0 = 150;  Y0 = 110;
    PX = @(k) X0 + (cx(k) - 1) * DX;
    PY = @(k) Y0 + (cy(k) - 1) * DY;

    RES  = 'fl_lib/Electrical/Electrical Elements/Resistor';
    ISRC = 'fl_lib/Electrical/Electrical Sources/DC Current Source';
    GND  = 'fl_lib/Electrical/Electrical Elements/Electrical Reference';
    SOLV = 'nesl_utility/Solver Configuration';

    % ---------------- node blocks (masked dots) ------------------------------
    for k = 1:N
        add_block(RES, [mdl '/N' num2str(k)], ...
            'Position', [PX(k) - 6, PY(k) - 6, PX(k) + 6, PY(k) + 6], ...
            'R', '1e-6');
        m = Simulink.Mask.create([mdl '/N' num2str(k)]);
        m.Display = sprintf('line([0.42,0.58],[0.5,0.5]);line([0.5,0.5],[0.42,0.58]);');
        m.IconFrame = 'off';
        m.IconOpaque = 'off';
    end

    % ---------------- edge blocks (masked, drawn along the true direction) ---
    for e = 1:ne
        x1 = PX(ei(e)); y1 = PY(ei(e));
        x2 = PX(ej(e)); y2 = PY(ej(e));
        pos = [min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2)];
        % normalise so the icon spans the block box
        u1 = (x1 - pos(1)) / (pos(3) - pos(1));
        v1 = (y1 - pos(2)) / (pos(4) - pos(2));
        u2 = (x2 - pos(1)) / (pos(3) - pos(1));
        v2 = (y2 - pos(2)) / (pos(4) - pos(2));
        add_block(RES, [mdl '/E' num2str(e)], 'Position', pos, ...
            'R', num2str(elen(e), '%.6f'));
        m = Simulink.Mask.create([mdl '/E' num2str(e)]);
        % resistor symbol: lead-in, zigzag, lead-out, drawn along the edge
        m.Display = resistor_icon(u1, v1, u2, v2);
        m.IconFrame = 'off';
        m.IconOpaque = 'off';
    end

    % ---------------- sources / ground ---------------------------------------
    for k = 1:np
        nk = lin(pins(k, 2), pins(k, 1));
        add_block(ISRC, [mdl '/I' num2str(k)], ...
            'Position', [40, Y0 + (k - 1) * 60, 66, Y0 + (k - 1) * 60 + 30], ...
            'i0', num2str(supply(k), '%.4f'));
    end
    gn = lin(gpin(2), gpin(1));
    add_block(GND, [mdl '/gnd'], 'Position', [40, Y0 + np * 60, 66, Y0 + np * 60 + 20]);
    add_block(SOLV, [mdl '/SolverConfig'], 'Position', [40 20 100 80]);

    % ---------------- wiring (star per node) ---------------------------------
    ports = cell(N, 1);
    for e = 1:ne
        h = get_param([mdl '/E' num2str(e)], 'PortHandles');
        ports{ei(e)}(end + 1) = h.LConn;
        ports{ej(e)}(end + 1) = h.RConn;
    end
    for k = 1:N
        h = get_param([mdl '/N' num2str(k)], 'PortHandles');
        ports{k}(end + 1) = h.LConn;
    end
    hG = get_param([mdl '/gnd'], 'PortHandles');
    ports{gn}(end + 1) = hG.LConn;
    for k = 1:np
        nk = lin(pins(k, 2), pins(k, 1));
        hI = get_param([mdl '/I' num2str(k)], 'PortHandles');
        ports{nk}(end + 1) = hI.RConn;
        ports{gn}(end + 1) = hI.LConn;
    end
    hS = get_param([mdl '/SolverConfig'], 'PortHandles');
    ports{gn}(end + 1) = hS.RConn;

    nl = 0;
    for k = 1:N
        p = ports{k};
        for j = 2:numel(p)
            add_line(mdl, p(1), p(j));
            nl = nl + 1;
        end
    end
    set_param(mdl, 'ZoomFactor', 'FitSystem');
    save_system(mdl);
    fprintf('[iso] built: %d nodes, %d edges (%d horizontal, %d vertical, %d diagonal), %d lines\n', ...
        N, ne, sum(cy(ei) == cy(ej)), sum(cx(ei) == cx(ej)), ...
        ne - sum(cy(ei) == cy(ej)) - sum(cx(ei) == cx(ej)), nl);

    % ---------------- simulate ----------------------------------------------
    set_param(mdl, 'StopTime', '1');
    set_param(mdl, 'SimscapeLogType', 'all');
    o = sim(mdl);
    sl = o.simlog;

    % ---------------- read back ---------------------------------------------
    i_meas = nan(ne, 1);
    for e = 1:ne
        d = sl.(['E' num2str(e)]).i.('series').values;
        i_meas(e) = abs(d(end));
    end
    v_node = nan(N, 1);
    for e = 1:ne
        Rb = sl.(['E' num2str(e)]);
        for side = {'p', 'n'}
            xv = Rb.(side{1}).v;
            if any(strcmp(properties(xv), 'series'))
                d = xv.('series').values;
                if side{1} == 'p', k = ei(e); else, k = ej(e); end
                v_node(k) = d(end);
            end
        end
    end

    % ---------------- reference solve ---------------------------------------
    [i_ref, p_ref, b, C, L] = iso_reference(n, ei, ej, elen, pins, supply, gpin);
    chip_nodes = arrayfun(@(k) lin(pins(k, 2), pins(k, 1)), 1:np);
    err_i = max(abs(i_meas - i_ref));
    rel_i = err_i / max(abs(i_ref));
    v_ref = p_ref(chip_nodes) - p_ref(gn);
    err_v = max(abs(abs(v_node(chip_nodes)) - abs(v_ref)));

    % ---------------- PNG + summary -----------------------------------------
    outdir = fullfile(fileparts(mfilename('fullpath')), 'outputs');
    if ~exist(outdir, 'dir'), mkdir(outdir); end
    png = fullfile(outdir, 'chip_route_iso.png');
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

    txt = iso_text(mdl, n, ne, np, pins, supply, gpin, ei, ej, elen, ...
        i_meas, i_ref, rel_i, err_i, err_v, v_node, v_ref, chip_nodes, pngmsg);
    disp(txt);
    fid = fopen(fullfile(outdir, 'chip_route_iso_summary.txt'), 'w');
    fprintf(fid, '%s', txt);
    fclose(fid);
end

% ==========================================================================
function [i, p, b, C, L] = iso_reference(n, ei, ej, elen, pins, supply, gpin)
%ISO_REFERENCE  The same 8-neighbour mesh solved directly as L p = b.
%   Identical in form to physarum_route.m: A = W + W.', L = diag(rowsum) - A.
    lin = @(x, y) (y - 1) * n + x;
    N = n * n;
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
function txt = iso_text(mdl, n, ne, np, pins, supply, gpin, ei, ej, elen, ...
    i_meas, i_ref, rel_i, err_i, err_v, v_node, v_ref, chip_nodes, pngmsg)
    sep = repmat('=', 1, 78);
    ln = repmat('-', 1, 78);
    nh = sum(cyv(ei, n) == cyv(ej, n));
    nv = sum(cxv(ei, n) == cxv(ej, n));
    nd = ne - nh - nv;
    Ls = {};
    Ls{end + 1} = sep; %#ok<AGROW>
    Ls{end + 1} = sprintf('Simulink circuit ISOMORPHIC to the 8-neighbour Physarum mesh (%s)', mdl); %#ok<AGROW>
    Ls{end + 1} = sprintf('%dx%d window: %d nodes, %d edges = %d horiz + %d vert + %d diagonal', ...
        n, n, n * n, ne, nh, nv, nd); %#ok<AGROW>
    Ls{end + 1} = sep; %#ok<AGROW>
    Ls{end + 1} = ''; %#ok<AGROW>
    Ls{end + 1} = 'ISOMORPHISM: identical node set, edge set and edge weights to'; %#ok<AGROW>
    Ls{end + 1} = 'physarum_route.m.  Diagonal edges are weighted sqrt(2), as there.'; %#ok<AGROW>
    Ls{end + 1} = 'Only the canvas coordinates differ: a Simulink block cannot be'; %#ok<AGROW>
    Ls{end + 1} = 'rotated 45 degrees, so each edge is drawn by a masked resistor'; %#ok<AGROW>
    Ls{end + 1} = 'whose icon follows the true direction of that edge.'; %#ok<AGROW>
    Ls{end + 1} = ln; %#ok<AGROW>
    Ls{end + 1} = ''; %#ok<AGROW>
    Ls{end + 1} = '[1] Sources'; %#ok<AGROW>
    for k = 1:np
        Ls{end + 1} = sprintf('  chip %d at (x,y) = (%d,%d)  I = %+.1f A', ...
            k, pins(k, 2), pins(k, 1), supply(k)); %#ok<AGROW>
    end
    Ls{end + 1} = sprintf('  ground at (x,y) = (%d,%d)   sum(supply) = %+.1f', ...
        gpin(2), gpin(1), sum(supply)); %#ok<AGROW>
    Ls{end + 1} = ''; %#ok<AGROW>
    Ls{end + 1} = '[2] Simscape vs direct L p = b solve'; %#ok<AGROW>
    Ls{end + 1} = sprintf('  max |i_simscape - i_reference| = %.3e A', err_i); %#ok<AGROW>
    Ls{end + 1} = sprintf('  relative current error          = %.3e', rel_i); %#ok<AGROW>
    Ls{end + 1} = sprintf('  max |v_simscape - v_reference|  = %.3e V', err_v); %#ok<AGROW>
    if rel_i < 1e-6 && err_v < 1e-6
        Ls{end + 1} = '  => AGREEMENT: the circuit is the mesh, solved.'; %#ok<AGROW>
    else
        Ls{end + 1} = '  => DISAGREEMENT: do not trust these numbers.'; %#ok<AGROW>
    end
    Ls{end + 1} = ''; %#ok<AGROW>
    Ls{end + 1} = '[3] Edge count by direction (must match the 8-neighbour mesh)'; %#ok<AGROW>
    Ls{end + 1} = sprintf('  horizontal (len 1)      : %d', nh); %#ok<AGROW>
    Ls{end + 1} = sprintf('  vertical   (len 1)      : %d', nv); %#ok<AGROW>
    Ls{end + 1} = sprintf('  diagonal   (len sqrt 2) : %d', nd); %#ok<AGROW>
    Ls{end + 1} = sprintf('  expected for %dx%d      : %d horiz + %d vert + %d diag', ...
        n, n, 2 * n * (n - 1) / 2, 2 * n * (n - 1) / 2, 2 * (n - 1) * (n - 1)); %#ok<AGROW>
    Ls{end + 1} = ''; %#ok<AGROW>
    Ls{end + 1} = '[4] Chip-node potentials (magnitudes)'; %#ok<AGROW>
    for k = 1:np
        Ls{end + 1} = sprintf('  chip %d (node %2d): |v| = %10.6f V   (|ref| %10.6f V)', ...
            k, chip_nodes(k), abs(v_node(chip_nodes(k))), abs(v_ref(k))); %#ok<AGROW>
    end
    Ls{end + 1} = ''; %#ok<AGROW>
    Ls{end + 1} = '[5] Files'; %#ok<AGROW>
    Ls{end + 1} = sprintf('  model   : %s.slx', mdl); %#ok<AGROW>
    Ls{end + 1} = sprintf('  diagram : %s', pngmsg); %#ok<AGROW>
    Ls{end + 1} = sprintf('  summary : outputs\\chip_route_iso_summary.txt'); %#ok<AGROW>
    Ls{end + 1} = sep; %#ok<AGROW>
    txt = strjoin(Ls, newline);
    txt = [txt newline];
end

function k = cxv(node, n)
    k = mod(node - 1, n) + 1;
end

function k = cyv(node, n)
    k = floor((node - 1) / n) + 1;
end

function s = resistor_icon(u1, v1, u2, v2)
%RESISTOR_ICON  Mask Display string drawing a resistor along (u1,v1)-(u2,v2).
%   Mask Display only accepts `line(x,y)` for polylines: `plot` and `patch`
%   both reject vector arguments ("argument must be double"), verified by
%   probe_plot.m.  Numbers must be spelled out with no spaces.
    du = u2 - u1; dv = v2 - v1;
    nu = -dv; nv = du;                      % unit normal
    amp = 0.16;
    a1u = u1 + 0.25 * du; a1v = v1 + 0.25 * dv;
    a2u = u2 - 0.25 * du; a2v = v2 - 0.25 * dv;
    k = 7;
    zu = zeros(1, k + 2); zv = zeros(1, k + 2);
    zu(1) = a1u; zv(1) = a1v;
    for i = 1:k
        t = i / (k + 1);
        sgn = 1 - 2 * mod(i, 2);            % +1, -1, +1, ...
        zu(i + 1) = a1u + t * (a2u - a1u) + sgn * amp * nu;
        zv(i + 1) = a1v + t * (a2v - a1v) + sgn * amp * nv;
    end
    zu(k + 2) = a2u; zv(k + 2) = a2v;
    su = sprintf('%.4f,', zu); su(end) = '';
    sv = sprintf('%.4f,', zv); sv(end) = '';
    s = sprintf(['line([%.4f,%.4f],[%.4f,%.4f]);\n', ...
                 'line([%s],[%s]);\n', ...
                 'line([%.4f,%.4f],[%.4f,%.4f]);\n'], ...
                 u1, a1u, v1, a1v, su, sv, a2u, u2, a2v, v2);
end
