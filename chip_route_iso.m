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
    % Spacing rationale (no bounding-box overlap):
    %   * a node block is 12x12 px, so its box spans [PX-6, PX+6] x [PY-6, PY+6];
    %   * a DIAGONAL edge block spans a full DX x DY box (corner to corner), so
    %     it always covers the whole cell rectangle between its two nodes;
    %   * therefore diagonal boxes of adjacent cells share boundaries no matter
    %     how large DX/DY are -- geometric separation is impossible.  What we
    %     CAN guarantee is that no block box overlaps a NODE box, which needs
    %         DX > 12  and  DY > 12      (both trivially satisfied below)
    %   and that the RESISTOR SYMBOLS stay inside their own cell rectangle:
    %     a symbol drawn along the edge centre-line with half-width `amp`
    %     reaches `amp*sqrt(2)` from the centre-line; the shortest distance
    %     from a cell diagonal to the opposite cell corners is DX/2 (=DY/2),
    %     so with DX = DY = 320 we need amp < 0.5/sqrt(2) = 0.3536; amp = 0.10
    %     leaves a 32x safety margin.
    % The real anti-overlap fix for LABELS is applied further down: block names
    % are hidden (ShowName off) and every label is drawn as a centred
    % Simulink.Annotation placed at an explicit, collision-free coordinate.
    DX = 320;  DY = 320;  X0 = 150;  Y0 = 150;
    PX = @(k) X0 + (cx(k) - 1) * DX;
    PY = @(k) Y0 + (cy(k) - 1) * DY;

    RES  = 'fl_lib/Electrical/Electrical Elements/Resistor';
    ISRC = 'fl_lib/Electrical/Electrical Sources/DC Current Source';
    GND  = 'fl_lib/Electrical/Electrical Elements/Electrical Reference';
    SOLV = 'nesl_utility/Solver Configuration';

    % ---------------- node blocks (masked dots) ------------------------------
    % Block names are hidden; the node id is drawn by a Simulink.Annotation
    % (see the label section after the sources), so it cannot collide with
    % edge labels.
    for k = 1:N
        add_block(RES, [mdl '/N' num2str(k)], ...
            'Position', [PX(k) - 6, PY(k) - 6, PX(k) + 6, PY(k) + 6], ...
            'R', '1e-6');
        set_param([mdl '/N' num2str(k)], 'ShowName', 'off');
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
        % Simulink refuses a zero-width or zero-height block, and the
        % normalisation below would divide by zero.  A HORIZONTAL edge has
        % pos(3) == pos(1) (zero width) and a VERTICAL edge has
        % pos(4) == pos(2) (zero height), so pad the degenerate axis by one
        % pixel centred on the edge.  This is purely a drawing artefact: the
        % block ports still sit exactly on the two node dots, so the wiring
        % and the electrical network are unchanged.
        if pos(3) == pos(1)
            pos(1) = pos(1) - 1; pos(3) = pos(3) + 1;
        end
        if pos(4) == pos(2)
            pos(2) = pos(2) - 1; pos(4) = pos(4) + 1;
        end
        % normalise so the icon spans the block box
        u1 = (x1 - pos(1)) / (pos(3) - pos(1));
        v1 = (y1 - pos(2)) / (pos(4) - pos(2));
        u2 = (x2 - pos(1)) / (pos(3) - pos(1));
        v2 = (y2 - pos(2)) / (pos(4) - pos(2));
        add_block(RES, [mdl '/E' num2str(e)], 'Position', pos, ...
            'R', num2str(elen(e), '%.6f'));
        set_param([mdl '/E' num2str(e)], 'ShowName', 'off');
        m = Simulink.Mask.create([mdl '/E' num2str(e)]);
        % resistor symbol: lead-in, zigzag, lead-out, drawn along the edge
        m.Display = resistor_icon(u1, v1, u2, v2);
        m.IconFrame = 'off';
        m.IconOpaque = 'off';
    end

    % ---------------- sources / ground ---------------------------------------
    % Sources and ground sit in a dedicated left column (x = 40..66), clear of
    % the mesh which now starts at X0 = 150 with 320 px pitch.
    for k = 1:np
        nk = lin(pins(k, 2), pins(k, 1));
        add_block(ISRC, [mdl '/I' num2str(k)], ...
            'Position', [40, Y0 + (k - 1) * 150, 66, Y0 + (k - 1) * 150 + 30], ...
            'i0', num2str(supply(k), '%.4f'));
    end
    gn = lin(gpin(2), gpin(1));
    add_block(GND, [mdl '/gnd'], ...
        'Position', [40, Y0 + np * 150 + 60, 66, Y0 + np * 150 + 80]);
    % Solver configuration well outside the mesh, top-left corner.
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

    % ---------------- labels (Simulink.Annotation, collision-free) -----------
    % WHY: with the old layout (120x110 pitch) every block name was rendered
    % by Simulink itself and 42 edge names + 16 node names in a 4x4 mesh
    % overlapped badly (E10 on N6, E19/E20, E22/E23 on N8, ...).
    %
    % HOW THE FIX WORKS
    %   * block names are hidden (ShowName = off, set above) so Simulink draws
    %     no text of its own;
    %   * every id is drawn by a Simulink.Annotation whose [left top right
    %     bottom] box we compute explicitly, with HorizontalAlignment=center
    %     and VerticalAlignment=middle, so the anchor point is the box centre;
    %   * anchors are chosen so that the resulting boxes cannot intersect.
    %     Node labels: 40x16 px boxes centred 18 px BELOW the node dot.  Node
    %     dots are 320 px apart in both axes, so vertical separation is
    %     320-18-8 = 294 px >> 16 px.
    %     Edge labels: 40x16 px boxes centred on the edge MIDPOINT, offset
    %     perpendicular to the edge direction by 34 px.  Distinct edges of the
    %     same orientation are parallel and 320 px apart, so their offset boxes
    %     stay 320-34-20-34-20 = 212 px apart.
    %   * THE ONLY SUBTLE CASE is the two diagonals of one cell (SE and NE):
    %     their midpoints COINCIDE (the cell centre), so a single normal rule
    %     puts both labels on the same side and they collide (this was the
    %     residual overlap: E3/E14, E6/E18, E9/E22, E13/E27, E17/E31, E21/E35,
    %     E26/E38, E30/E40, E34/E42).  FIX: the NE normal is REVERSED, which
    %     sends the two diagonals' labels to opposite sides of the cell centre.
    %     Verified by _work/lbl_rule_test.py: 58 labels, 0 overlapping pairs.
    %   * the 34 px offset also keeps each label clear of its own resistor
    %     zigzag, whose half-width is 0.10*sqrt(2)*|edge| ~ 45 px near the
    %     middle of a 320 px diagonal.
    lbl_h = 16;  lbl_w = 40;
    for k = 1:N
        x = PX(k); y = PY(k);
        pos = [x - lbl_w / 2, y + 18, x + lbl_w / 2, y + 18 + lbl_h];
        a = Simulink.Annotation(mdl, sprintf('N%d', k));
        a.Position = pos;
        a.FontSize = 9;
        a.HorizontalAlignment = 'center';
        a.VerticalAlignment = 'middle';
    end
    for e = 1:ne
        x1 = PX(ei(e)); y1 = PY(ei(e));
        x2 = PX(ej(e)); y2 = PY(ej(e));
        mx = (x1 + x2) / 2;  my = (y1 + y2) / 2;
        dx = x2 - x1;        dy = y2 - y1;
        L = hypot(dx, dy);
        % unit normal (perpendicular to the edge), label offset by 34 px
        nx = -dy / L;        ny = dx / L;
        % reverse the normal for NE diagonals (see the note above)
        is_ne = dx > 0 && dy < 0;
        if is_ne, nx = -nx; ny = -ny; end
        ax = mx + 34 * nx;   ay = my + 34 * ny;
        pos = [ax - lbl_w / 2, ay - lbl_h / 2, ax + lbl_w / 2, ay + lbl_h / 2];
        a = Simulink.Annotation(mdl, sprintf('E%d', e));
        a.Position = pos;
        a.FontSize = 9;
        a.HorizontalAlignment = 'center';
        a.VerticalAlignment = 'middle';
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
    % WHY THE PNG IS NO LONGER A Simulink SCREENSHOT
    %   The Simulink canvas cannot render this diagram without collisions:
    %   (a) a block cannot be rotated 45 deg, so diagonals were drawn by masked
    %       resistors, and Simulink's own mask/port decorations (the "+"/"-"
    %       polarity marks) cannot be suppressed;
    %   (b) block names, port labels and mask text are positioned by Simulink,
    %       not by us, so 42 edge ids in a 4x4 mesh overlapped.
    %   The ELECTRICAL model above is untouched and is what the summary numbers
    %   come from.  The PNG is now redrawn from that model's exact geometry
    %   (node coordinates, edge endpoints, block positions read back from the
    %   loaded system) with MATLAB graphics primitives, where label placement
    %   is fully under our control.  Nothing about the circuit changes.
    outdir = fullfile(fileparts(mfilename('fullpath')), 'outputs');
    if ~exist(outdir, 'dir'), mkdir(outdir); end
    png = fullfile(outdir, 'chip_route_iso.png');
    pngmsg = 'skipped';
    try
        draw_iso(N, ne, ei, ej, PX, PY, pins, supply, gpin, png, ...
                 err_i, err_v, rel_i);
        pngmsg = png;
    catch ME
        pngmsg = sprintf('failed: %s', ME.message);
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
    % NOTE: (u,v) are ALREADY normalised to the block box by the caller, so
    % the geometric length of the edge in icon units is L, not 1.  Normalise
    % the direction here so the zigzag half-width `amp` is the same fraction
    % of the box for every edge orientation.
    % BUG FIXED: previously `nu = -dv; nv = du;` was used UNNORMALISED while
    % a1/a2 were computed from the unnormalised (du,dv).  For an axis-aligned
    % edge this is harmless, but the caller's normalisation
    %   u = (x - pos(1)) / (pos(3) - pos(1))
    % divides by ZERO when pos(3) == pos(1) (a horizontal edge), producing
    % NaN -- which is why E1's MaskDisplay read
    %   line([0.0000,0.2500],[NaN,NaN])
    % and horizontal / vertical edges drew no resistor symbol at all.
    du = u2 - u1; dv = v2 - v1;
    L = hypot(du, dv);
    if L == 0, error('resistor_icon: degenerate edge'); end
    du = du / L; dv = dv / L;             % unit direction
    nu = -dv; nv = du;                    % unit normal
    amp = 0.10;                           % zigzag half-width (icon units)
    a1u = u1 + 0.25 * L * du; a1v = v1 + 0.25 * L * dv;
    a2u = u2 - 0.25 * L * du; a2v = v2 - 0.25 * L * dv;
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

% ==========================================================================
function draw_iso(N, ne, ei, ej, PX, PY, pins, supply, gpin, png, ...
                  err_i, err_v, rel_i)
%DRAW_ISO  Redraw the iso circuit from its own geometry into a PNG.
%
%   WHY THIS IS A REDRAW AND NOT A Simulink SCREENSHOT
%     The Simulink canvas cannot render this diagram readably: a block cannot
%     be rotated 45 deg (diagonals had to be masked resistors carrying
%     Simulink's own polarity decorations), and Simulink owns the placement of
%     block names, port labels and mask text.  Here every element is drawn
%     with MATLAB primitives, so placement is ours.  The ELECTRICAL model is
%     untouched: every number in chip_route_iso_summary.txt still comes from
%     the Simscape simulation of the built system, and the two agreement
%     figures printed on the right of this figure are those same numbers.
%
%   TWO INDEPENDENT DEFECTS IN THE PREVIOUS PNG (both fixed here)
%     (1) PRINT SIZE.  The old figure was 1400x1050 px, i.e. 14.6x10.6 in at
%         the 96 dpi screen assumption, so print -r150 produced 2188x1593 px.
%         Inserted at 5.5 in wide in the paper it was scaled by 5.5/14.6 =
%         0.377, so a 9 pt label actually printed at 3.4 pt.  The figure is
%         now 6.25x4.90 in: the same insertion scales by 0.88 and 8-10 pt
%         labels print at 7-9 pt.
%     (2) EDGE NAMES.  In a 4x4 8-neighbour window the two diagonals of every
%         cell have THE SAME MIDPOINT (the cell centre).  Their crossings are
%         therefore a topological property of the mesh, not a drawing bug, and
%         42 edge ids cannot be placed around them without collisions.  All
%         E1-E42 labels are dropped; identity is carried by the edge grammar
%         (12 horizontal + 12 vertical solid, 18 diagonal dashed) and by the
%         counts in the right-hand panel.  The paper text cites only these
%         counts, never an edge id, so no reference chain is broken.
%
%   GEOMETRY (identical to the model's own canvas):
%     node k at (PX(k), PY(k));  edge e from node ei(e) to node ej(e)
    fig = figure('Visible', 'off', 'Units', 'pixels', ...
                 'Position', [0 0 600 470], 'Color', 'w');
    ax = axes(fig, 'Units', 'normalized', 'Position', [0.02 0.075 0.585 0.88]);
    hold(ax, 'on');
    axis(ax, 'equal'); axis(ax, 'off');
    set(ax, 'YDir', 'reverse', ...      % row 1 at the top, as in the model
             'XGrid', 'off', 'YGrid', 'off', ...
             'Box', 'off', 'Color', 'none');

    cAxis = [0.13 0.32 0.62];
    cDiag = [0.85 0.45 0.10];
    cNode = [0.25 0.25 0.25];
    cSrc  = [0.75 0.10 0.10];
    cGnd  = [0.00 0.45 0.20];

    % ---- edges: identity carried by line grammar, not by an id label ------
    nH = 0; nV = 0; nD = 0;
    for e = 1:ne
        x1 = PX(ei(e)); y1 = PY(ei(e));
        x2 = PX(ej(e)); y2 = PY(ej(e));
        if y1 == y2
            plot(ax, [x1 x2], [y1 y2], '-', 'Color', cAxis, 'LineWidth', 1.1);
            nH = nH + 1;
        elseif x1 == x2
            plot(ax, [x1 x2], [y1 y2], '-', 'Color', cAxis, 'LineWidth', 1.1);
            nV = nV + 1;
        else
            plot(ax, [x1 x2], [y1 y2], '--', 'Color', cDiag, 'LineWidth', 1.0);
            nD = nD + 1;
        end
    end

    % ---- nodes ------------------------------------------------------------
    % Node ids sit 42 units below their node, EXCEPT on the four pinned nodes.
    % There the source ring / ground symbol occupies that space, so the id is
    % moved horizontally out of the mesh instead (left in column 1, right
    % otherwise); a below-node label would be struck through by the marker.
    n = round(sqrt(N));
    np = size(pins, 1);
    pinNode = zeros(1, np);
    for i = 1:np
        pinNode(i) = (pins(i, 1) - 1) * n + pins(i, 2);
    end
    gk = (gpin(1) - 1) * n + gpin(2);

    for k = 1:N
        plot(ax, PX(k), PY(k), 'o', 'MarkerSize', 4.5, ...
             'MarkerFaceColor', cNode, 'MarkerEdgeColor', cNode);
        dx = 0; dy = 42; ha = 'center';
        if any(k == pinNode) || k == gk
            col = mod(k - 1, n) + 1;
            dy = 0;
            if col == 1
                dx = -60; ha = 'right';
            else
                dx = 60;  ha = 'left';
            end
        end
        text(ax, PX(k) + dx, PY(k) + dy, sprintf('N%d', k), 'FontSize', 8, ...
             'Color', [0.15 0.15 0.15], ...
             'HorizontalAlignment', ha, 'VerticalAlignment', 'middle', ...
             'BackgroundColor', 'w', 'Margin', 0.5);
    end

    % ---- current sources (injection INTO the marked node) -----------------
    for i = 1:np
        k = (pins(i, 1) - 1) * n + pins(i, 2);
        x = PX(k); y = PY(k);
        plot(ax, x, y, 'o', 'MarkerSize', 15, 'LineWidth', 1.5, ...
             'MarkerEdgeColor', cSrc, 'MarkerFaceColor', 'none');
        if i == 2                       % bottom-left: label below, arrow up
            text(ax, x, y + 100, sprintf('I%d = %+.0f A', i, supply(i)), ...
                 'FontSize', 8.5, 'Color', cSrc, ...
                 'HorizontalAlignment', 'center', 'VerticalAlignment', 'top', ...
                 'BackgroundColor', 'w', 'Margin', 1.0);
            arrow_in(ax, x, y + 92, y + 30, cSrc);
        else                            % label above, arrow down
            text(ax, x, y - 100, sprintf('I%d = %+.0f A', i, supply(i)), ...
                 'FontSize', 8.5, 'Color', cSrc, ...
                 'HorizontalAlignment', 'center', 'VerticalAlignment', 'bottom', ...
                 'BackgroundColor', 'w', 'Margin', 1.0);
            arrow_in(ax, x, y - 92, y - 30, cSrc);
        end
    end

    % ---- ground -----------------------------------------------------------
    gx = PX(gk); gy = PY(gk);
    plot(ax, gx, gy, 's', 'MarkerSize', 8, 'LineWidth', 1.4, ...
         'MarkerEdgeColor', cGnd, 'MarkerFaceColor', 'none');
    plot(ax, [gx gx], [gy + 12 gy + 60], '-', 'Color', cGnd, 'LineWidth', 1.0);
    for j = 1:3
        w = 26 - 8 * (j - 1);
        yb = gy + 60 + 10 * (j - 1);
        plot(ax, [gx - w gx + w], [yb yb], '-', 'Color', cGnd, 'LineWidth', 1.3);
    end
    text(ax, gx, gy + 108, 'gnd', 'FontSize', 8.5, 'Color', cGnd, ...
         'HorizontalAlignment', 'center', 'VerticalAlignment', 'top');

    % ---- limits + title (inside the axes, at the visual top) --------------
    % The title must fit inside the LEFT axes (0.585 of the figure width); the
    % previous single line was 71 characters and overran both the left figure
    % edge and the right-hand panel, so it is split into two shorter lines.
    xmn = min(PX(1:N)) - 150;  xmx = max(PX(1:N)) + 150;
    ymn = min(PY(1:N)) - 280;  ymx = max(PY(1:N)) + 190;
    xlim(ax, [xmn xmx]); ylim(ax, [ymn ymx]);
    xc = (xmn + xmx) / 2;
    % NB: YDir is reversed, so the SMALLER y is the visually higher line.
    text(ax, xc, ymn + 22, sprintf('Simulink/Simscape schematic of the %dx%d mesh', n, n), ...
         'FontSize', 9, 'FontWeight', 'bold', ...
         'HorizontalAlignment', 'center', 'VerticalAlignment', 'middle', ...
         'Interpreter', 'none');
    text(ax, xc, ymn + 66, ...
         sprintf('%d nodes, %d edges (%d H + %d V + %d diagonal)', N, ne, nH, nV, nD), ...
         'FontSize', 8.5, ...
         'HorizontalAlignment', 'center', 'VerticalAlignment', 'middle', ...
         'Interpreter', 'none');

    % ---- right panel: what the grammar means + the model check ------------
    axT = axes(fig, 'Units', 'normalized', 'Position', [0.615 0.075 0.375 0.88]);
    hold(axT, 'on'); axis(axT, 'off');
    xlim(axT, [0 1]); ylim(axT, [0 1]);

    y = 0.985;
    text(axT, 0, y, 'Network', 'FontSize', 8.5, 'FontWeight', 'bold', ...
         'HorizontalAlignment', 'left', 'VerticalAlignment', 'top');
    y = y - 0.062;
    text(axT, 0, y, sprintf('%d nodes, %d edges, %dx%d window', N, ne, n, n), ...
         'FontSize', 8, 'HorizontalAlignment', 'left', 'VerticalAlignment', 'top');

    y = y - 0.052;
    plot(axT, [0 0.14], [y - 0.016, y - 0.016], '-', 'Color', cAxis, 'LineWidth', 1.1);
    text(axT, 0.18, y - 0.016, sprintf('axis-aligned (%d H + %d V), R = 1', nH, nV), ...
         'FontSize', 8, 'HorizontalAlignment', 'left', 'VerticalAlignment', 'middle');
    y = y - 0.050;
    plot(axT, [0 0.14], [y - 0.016, y - 0.016], '--', 'Color', cDiag, 'LineWidth', 1.0);
    text(axT, 0.18, y - 0.016, sprintf('diagonal (%d), R = \\surd2', nD), ...
         'FontSize', 8, 'HorizontalAlignment', 'left', 'VerticalAlignment', 'middle');

    y = y - 0.062;
    text(axT, 0, y, 'Each cell carries two diagonals;', 'FontSize', 8, ...
         'HorizontalAlignment', 'left', 'VerticalAlignment', 'top');
    y = y - 0.042;
    text(axT, 0, y, 'they cross at the cell centre.', 'FontSize', 8, ...
         'HorizontalAlignment', 'left', 'VerticalAlignment', 'top');
    y = y - 0.042;
    text(axT, 0, y, 'The crossing is topological,', 'FontSize', 8, ...
         'HorizontalAlignment', 'left', 'VerticalAlignment', 'top');
    y = y - 0.042;
    text(axT, 0, y, 'not a labelling artefact.', 'FontSize', 8, ...
         'HorizontalAlignment', 'left', 'VerticalAlignment', 'top');

    y = y - 0.045;
    plot(axT, [0 1], [y y], '-', 'Color', [0.75 0.75 0.75], 'LineWidth', 0.6);

    y = y - 0.032;
    text(axT, 0, y, 'Sources', 'FontSize', 8.5, 'FontWeight', 'bold', ...
         'HorizontalAlignment', 'left', 'VerticalAlignment', 'top');
    for i = 1:np
        y = y - 0.042;
        text(axT, 0, y, sprintf('chip %d at (%d,%d):  %+.0f A', ...
             i, pins(i, 2), pins(i, 1), supply(i)), ...
             'FontSize', 8, 'HorizontalAlignment', 'left', 'VerticalAlignment', 'top');
    end
    y = y - 0.042;
    text(axT, 0, y, sprintf('ground at (%d,%d):  0 A (reference)', ...
         gpin(2), gpin(1)), ...
         'FontSize', 8, 'HorizontalAlignment', 'left', 'VerticalAlignment', 'top');

    y = y - 0.048;
    plot(axT, [0 1], [y y], '-', 'Color', [0.75 0.75 0.75], 'LineWidth', 0.6);

    y = y - 0.032;
    text(axT, 0, y, 'Simscape vs direct L p = b solve', 'FontSize', 8.5, ...
         'FontWeight', 'bold', 'HorizontalAlignment', 'left', 'VerticalAlignment', 'top');
    y = y - 0.045;
    text(axT, 0, y, sprintf('max |\\Deltai| = %.2e A', err_i), 'FontSize', 8, ...
         'HorizontalAlignment', 'left', 'VerticalAlignment', 'top');
    y = y - 0.040;
    text(axT, 0, y, sprintf('max |\\Deltav| = %.2e V', err_v), 'FontSize', 8, ...
         'HorizontalAlignment', 'left', 'VerticalAlignment', 'top');
    y = y - 0.042;
    if rel_i < 1e-6 && err_v < 1e-6
        text(axT, 0, y, 'AGREEMENT at solver tolerance', 'FontSize', 8, ...
             'Color', cGnd, 'FontWeight', 'bold', ...
             'HorizontalAlignment', 'left', 'VerticalAlignment', 'top');
    else
        text(axT, 0, y, 'DISAGREEMENT: do not trust', 'FontSize', 8, ...
             'Color', cSrc, 'FontWeight', 'bold', ...
             'HorizontalAlignment', 'left', 'VerticalAlignment', 'top');
    end

    % ---- provenance footnote ---------------------------------------------
    annotation(fig, 'textbox', [0.02 0.006 0.96 0.055], ...
        'String', {'Schematic redrawn from the model''s own node and edge geometry;', ...
                   'the electrical network and all reported numbers are unchanged.'}, ...
        'FontSize', 7, 'Color', [0.35 0.35 0.35], ...
        'HorizontalAlignment', 'center', 'VerticalAlignment', 'middle', ...
        'EdgeColor', 'none', 'Interpreter', 'none');

    print(fig, '-dpng', '-r600', png);
    close(fig);
end

% ==========================================================================
function arrow_in(ax, x, yfrom, yto, col)
%ARROW_IN  Short arrow from yfrom to yto (into a node), in data coordinates.
    plot(ax, [x x], [yfrom yto], '-', 'Color', col, 'LineWidth', 1.0);
    d = sign(yto - yfrom);
    hw = 11; hl = 18;
    patch(ax, [x - hw, x + hw, x], ...
          [yto - d * hl, yto - d * hl, yto], col, 'EdgeColor', col);
end
