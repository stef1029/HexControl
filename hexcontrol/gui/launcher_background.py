"""Daily generative-art background for the launcher window (DearPyGui).

Renders a decorative line pattern onto a DPG drawlist.
The pattern is randomly chosen each launch from the enabled generators.
Colors are automatically derived from the active theme.
"""

from __future__ import annotations

import math
import random

import dearpygui.dearpygui as dpg

from hexcontrol.gui.theme import Theme, hex_to_rgba


def _get_line_colors() -> list[list[int]]:
    """Get line colors from the current theme palette as RGBA lists."""
    palette = Theme.palette
    return [
        hex_to_rgba(palette.accent_primary),
        hex_to_rgba(palette.accent_secondary),
        hex_to_rgba(palette.accent_hover),
    ]


# ---------------------------------------------------------------------------
# Noise helpers
# ---------------------------------------------------------------------------

def _value_noise_grid(cols: int, rows: int, rng: random.Random) -> list[list[float]]:
    return [[rng.random() for _ in range(cols)] for _ in range(rows)]


def _smoothstep(t: float) -> float:
    return t * t * (3.0 - 2.0 * t)


def _sample_noise(grid: list[list[float]], x: float, y: float) -> float:
    rows = len(grid)
    cols = len(grid[0])
    xi = int(x) % cols
    yi = int(y) % rows
    xf = _smoothstep(x - int(x))
    yf = _smoothstep(y - int(y))
    top = grid[yi][xi] + (grid[yi][(xi + 1) % cols] - grid[yi][xi]) * xf
    bot = (
        grid[(yi + 1) % rows][xi]
        + (grid[(yi + 1) % rows][(xi + 1) % cols] - grid[(yi + 1) % rows][xi]) * xf
    )
    return top + (bot - top) * yf


# ===================================================================
# Generators (drawlist versions)
# ===================================================================

def _draw_topo_rings(dl, w, h, rng):
    grid = _value_noise_grid(12, 12, rng)
    n_clusters = rng.randint(3, 5)
    for _ in range(n_clusters):
        cx = rng.random() * w
        cy = rng.random() * h
        num_rings = rng.randint(12, 22)
        max_r = max(w, h) * rng.uniform(0.25, 0.55)
        color = rng.choice(_get_line_colors())
        for ring_i in range(num_rings):
            base_r = (ring_i + 1) * max_r / num_rings
            pts = []
            n_pts = 80
            for i in range(n_pts + 1):
                a = 2.0 * math.pi * i / n_pts
                nx = 5.5 + 4.5 * math.cos(a)
                ny = 5.5 + 4.5 * math.sin(a)
                noise = _sample_noise(grid, nx, ny)
                r = base_r * (0.7 + 0.6 * noise)
                pts.append([cx + math.cos(a) * r, cy + math.sin(a) * r])
            if len(pts) >= 2:
                dpg.draw_polyline(pts, color=color, thickness=1, parent=dl)


def _draw_flow_field(dl, w, h, rng):
    grid = _value_noise_grid(10, 10, rng)
    n_lines = rng.randint(250, 350)
    steps = rng.randint(40, 70)
    step_sz = 3.0
    for _ in range(n_lines):
        color = rng.choice(_get_line_colors())
        x, y = rng.random() * w, rng.random() * h
        pts = [[x, y]]
        for _ in range(steps):
            noise = _sample_noise(grid, x * 8.0 / w, y * 8.0 / h)
            a = noise * math.pi * 5.0
            x += math.cos(a) * step_sz
            y += math.sin(a) * step_sz
            if x < -30 or x > w + 30 or y < -30 or y > h + 30:
                break
            pts.append([x, y])
        if len(pts) >= 3:
            dpg.draw_polyline(pts, color=color, thickness=1, parent=dl)


def _draw_network(dl, w, h, rng):
    n_pts = rng.randint(80, 120)
    points = [(rng.random() * w, rng.random() * h) for _ in range(n_pts)]
    max_d_sq = (min(w, h) * 0.22) ** 2
    for i in range(n_pts):
        color = rng.choice(_get_line_colors())
        for j in range(i + 1, n_pts):
            dx = points[j][0] - points[i][0]
            dy = points[j][1] - points[i][1]
            if dx * dx + dy * dy < max_d_sq:
                dpg.draw_line(
                    p1=[points[i][0], points[i][1]],
                    p2=[points[j][0], points[j][1]],
                    color=color, thickness=1, parent=dl,
                )
    for x, y in points:
        color = rng.choice(_get_line_colors())
        dpg.draw_circle(center=[x, y], radius=2, fill=color, color=color, parent=dl)


def _draw_spirograph(dl, w, h, rng):
    n_curves = rng.randint(3, 5)
    cx, cy = w / 2, h / 2
    for _ in range(n_curves):
        color = rng.choice(_get_line_colors())
        a_freq = rng.randint(2, 7)
        b_freq = rng.randint(2, 7)
        phase = rng.random() * math.pi * 2
        rx = w * 0.5 * rng.uniform(0.7, 1.0)
        ry = h * 0.5 * rng.uniform(0.7, 1.0)
        n_pts = 360
        pts = []
        for i in range(n_pts + 1):
            t = 2.0 * math.pi * i / n_pts
            x = cx + rx * math.sin(a_freq * t + phase)
            y = cy + ry * math.cos(b_freq * t)
            pts.append([x, y])
        dpg.draw_polyline(pts, color=color, thickness=1, parent=dl)


def _draw_moire(dl, w, h, rng):
    n_sources = rng.randint(3, 5)
    sources = [(rng.random() * w, rng.random() * h) for _ in range(n_sources)]
    spacing = rng.uniform(14, 22)
    for sx, sy in sources:
        color = rng.choice(_get_line_colors())
        max_r = math.hypot(max(w - sx, sx), max(h - sy, sy))
        n_rings = int(max_r / spacing)
        for ring_i in range(1, n_rings + 1):
            r = ring_i * spacing
            dpg.draw_circle(center=[sx, sy], radius=r, color=color, thickness=1, parent=dl)


def _draw_mondrian(dl, w, h, rng):
    min_size = 30
    rects = [(0, 0, w, h)]
    iterations = rng.randint(5, 7)
    for _ in range(iterations):
        new_rects = []
        for x0, y0, x1, y1 in rects:
            rw, rh = x1 - x0, y1 - y0
            if rw < min_size * 2 and rh < min_size * 2:
                new_rects.append((x0, y0, x1, y1)); continue
            if rng.random() < 0.15:
                new_rects.append((x0, y0, x1, y1)); continue
            if rw >= rh and rw >= min_size * 2:
                split = x0 + rng.uniform(min_size, rw - min_size)
                new_rects.append((x0, y0, split, y1))
                new_rects.append((split, y0, x1, y1))
            elif rh >= min_size * 2:
                split = y0 + rng.uniform(min_size, rh - min_size)
                new_rects.append((x0, y0, x1, split))
                new_rects.append((x0, split, x1, y1))
            else:
                new_rects.append((x0, y0, x1, y1))
        rects = new_rects
    for x0, y0, x1, y1 in rects:
        color = rng.choice(_get_line_colors())
        dpg.draw_rectangle(pmin=[x0, y0], pmax=[x1, y1], color=color, thickness=1, parent=dl)


def _draw_circle_packing(dl, w, h, rng):
    circles = []
    max_attempts = 1500
    min_r, max_r = 4, 50
    pad = 2
    for _ in range(max_attempts):
        cx = rng.random() * w
        cy = rng.random() * h
        r = rng.uniform(min_r, max_r)
        for ecx, ecy, er in circles:
            dist = math.hypot(cx - ecx, cy - ecy)
            max_allowed = dist - er - pad
            if max_allowed < min_r:
                r = 0; break
            r = min(r, max_allowed)
        if r >= min_r:
            circles.append((cx, cy, r))
    for cx, cy, r in circles:
        color = rng.choice(_get_line_colors())
        dpg.draw_circle(center=[cx, cy], radius=r, color=color, thickness=1, parent=dl)


def _draw_crosshatch(dl, w, h, rng):
    grid = _value_noise_grid(8, 8, rng)
    n_passes = rng.randint(3, 5)
    diag = math.hypot(w, h)
    for _ in range(n_passes):
        color = rng.choice(_get_line_colors())
        base_angle = rng.uniform(0, math.pi)
        spacing = rng.uniform(12, 24)
        n_lines = int(diag / spacing) + 1
        cos_a = math.cos(base_angle)
        sin_a = math.sin(base_angle)
        for li in range(n_lines):
            offset = (li - n_lines / 2) * spacing
            x0 = w / 2 + cos_a * offset - sin_a * diag / 2
            y0 = h / 2 + sin_a * offset + cos_a * diag / 2
            x1 = w / 2 + cos_a * offset + sin_a * diag / 2
            y1 = h / 2 + sin_a * offset - cos_a * diag / 2
            n0 = _sample_noise(grid, x0 * 6 / w, y0 * 6 / h)
            n1 = _sample_noise(grid, x1 * 6 / w, y1 * 6 / h)
            warp = 12
            x0 += (n0 - 0.5) * warp; y0 += (n0 - 0.5) * warp
            x1 += (n1 - 0.5) * warp; y1 += (n1 - 0.5) * warp
            dpg.draw_line(p1=[x0, y0], p2=[x1, y1], color=color, thickness=1, parent=dl)


def _draw_fractal_trees(dl, w, h, rng):
    n_trees = rng.randint(4, 8)
    for _ in range(n_trees):
        color = rng.choice(_get_line_colors())
        root_x = rng.random() * w
        root_y = h * rng.uniform(0.95, 1.15)
        trunk_len = rng.uniform(120, 220)
        trunk_angle = -math.pi / 2 + rng.uniform(-0.4, 0.4)
        max_depth = rng.randint(8, 11)
        shrink = rng.uniform(0.62, 0.75)
        spread = rng.uniform(0.3, 0.6)
        stack = [(root_x, root_y, trunk_angle, trunk_len, 0)]
        while stack:
            bx, by, ba, bl, depth = stack.pop()
            if depth > max_depth or bl < 2:
                continue
            ex = bx + math.cos(ba) * bl
            ey = by + math.sin(ba) * bl
            dpg.draw_line(p1=[bx, by], p2=[ex, ey], color=color, thickness=1, parent=dl)
            offset = rng.uniform(-0.1, 0.1)
            stack.append((ex, ey, ba - spread + offset, bl * shrink, depth + 1))
            stack.append((ex, ey, ba + spread + offset, bl * shrink, depth + 1))


def _draw_delaunay(dl, w, h, rng):
    n_pts = rng.randint(60, 100)
    points = [(rng.random() * w, rng.random() * h) for _ in range(n_pts)]
    color = rng.choice(_get_line_colors())
    margin = max(w, h) * 3
    st = [(-margin, -margin), (2 * margin + w, -margin), (w / 2, 2 * margin + h)]
    triangles = [(0, 1, 2)]
    all_pts = list(st) + points

    def circumcircle_contains(tri, px, py):
        ax, ay = all_pts[tri[0]]; bx, by = all_pts[tri[1]]; cx, cy = all_pts[tri[2]]
        d = 2 * (ax * (by - cy) + bx * (cy - ay) + cx * (ay - by))
        if abs(d) < 1e-10: return False
        ux = ((ax*ax+ay*ay)*(by-cy)+(bx*bx+by*by)*(cy-ay)+(cx*cx+cy*cy)*(ay-by))/d
        uy = ((ax*ax+ay*ay)*(cx-bx)+(bx*bx+by*by)*(ax-cx)+(cx*cx+cy*cy)*(bx-ax))/d
        r_sq = (ax-ux)**2+(ay-uy)**2
        return (px-ux)**2+(py-uy)**2 <= r_sq

    for pi in range(3, len(all_pts)):
        px, py = all_pts[pi]
        bad = [t for t in triangles if circumcircle_contains(t, px, py)]
        boundary = []
        for t in bad:
            for edge in ((t[0],t[1]),(t[1],t[2]),(t[2],t[0])):
                shared = any(edge[0] in o and edge[1] in o for o in bad if o is not t)
                if not shared: boundary.append(edge)
        for t in bad: triangles.remove(t)
        for e in boundary: triangles.append((e[0], e[1], pi))

    drawn = set()
    for t in triangles:
        if t[0] < 3 or t[1] < 3 or t[2] < 3: continue
        for a, b in ((t[0],t[1]),(t[1],t[2]),(t[2],t[0])):
            key = (min(a,b), max(a,b))
            if key not in drawn:
                drawn.add(key)
                dpg.draw_line(
                    p1=[all_pts[a][0], all_pts[a][1]],
                    p2=[all_pts[b][0], all_pts[b][1]],
                    color=color, thickness=1, parent=dl,
                )


def _draw_orbital_trails(dl, w, h, rng):
    n_attractors = rng.randint(2, 4)
    attractors = []
    for _ in range(n_attractors):
        ax = rng.choice([rng.uniform(-0.2, 0.3), rng.uniform(0.7, 1.2)]) * w
        ay = rng.choice([rng.uniform(-0.2, 0.3), rng.uniform(0.7, 1.2)]) * h
        am = rng.uniform(400, 1000)
        attractors.append((ax, ay, am))
    n_particles = rng.randint(50, 90)
    dt = 0.5
    steps = rng.randint(250, 450)
    for _ in range(n_particles):
        color = rng.choice(_get_line_colors())
        x = rng.random() * w; y = rng.random() * h
        vx = rng.uniform(-4, 4); vy = rng.uniform(-4, 4)
        pts = [[x, y]]
        for _ in range(steps):
            ax_t, ay_t = 0.0, 0.0
            for gx, gy, gm in attractors:
                ddx, ddy = gx - x, gy - y
                dist_sq = ddx*ddx + ddy*ddy + 400
                inv_dist = 1.0 / math.sqrt(dist_sq)
                force = gm * inv_dist * inv_dist
                ax_t += ddx * inv_dist * force; ay_t += ddy * inv_dist * force
            vx += ax_t * dt; vy += ay_t * dt
            speed = math.hypot(vx, vy)
            if speed > 10: vx *= 10/speed; vy *= 10/speed
            x += vx * dt; y += vy * dt
            if x < -50 or x > w+50 or y < -50 or y > h+50: break
            pts.append([x, y])
        if len(pts) >= 3:
            dpg.draw_polyline(pts, color=color, thickness=1, parent=dl)


# ===================================================================
# Generator registry
# ===================================================================

_GENERATORS = [
    _draw_topo_rings,
    _draw_flow_field,
    _draw_network,
    _draw_spirograph,
    _draw_moire,
    _draw_mondrian,
    _draw_circle_packing,
    _draw_crosshatch,
    _draw_fractal_trees,
    _draw_delaunay,
    _draw_orbital_trails,
]


# ===================================================================
# Public API
# ===================================================================

def draw_background(drawlist_id: int | str, width: int, height: int) -> None:
    """Pick a random generator and render the background art onto *drawlist_id*."""
    rng = random.Random()
    generator = rng.choice(_GENERATORS)
    generator(drawlist_id, width, height, rng)
