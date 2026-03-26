"""Daily generative-art background for the launcher window.

Renders a decorative line pattern onto a tkinter Canvas.
The pattern is randomly chosen each launch from the enabled generators.
Colors are automatically derived from the active theme in theme.py.
"""

from __future__ import annotations

import math
import random

from gui.theme import Theme


def _get_line_colors() -> list[str]:
    """Get line colors from the current theme palette."""
    palette = Theme.palette
    return [palette.accent_primary, palette.accent_secondary, palette.accent_hover]


# ---------------------------------------------------------------------------
# Simple value-noise helpers (no external dependencies)
# ---------------------------------------------------------------------------

def _value_noise_grid(cols: int, rows: int, rng: random.Random) -> list[list[float]]:
    """Create a *cols* x *rows* grid of random floats in [0, 1]."""
    return [[rng.random() for _ in range(cols)] for _ in range(rows)]


def _smoothstep(t: float) -> float:
    return t * t * (3.0 - 2.0 * t)


def _sample_noise(grid: list[list[float]], x: float, y: float) -> float:
    """Bilinearly interpolate smooth noise from a value grid."""
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
# Generators
# ===================================================================


# ---------------------------------------------------------------------------
# 1. Topographic / contour rings
# ---------------------------------------------------------------------------

def _draw_topo_rings(canvas, w: int, h: int, rng: random.Random) -> None:
    """Multiple clusters of concentric noise-distorted contour rings."""
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
            pts: list[float] = []
            n_pts = 80
            for i in range(n_pts + 1):
                a = 2.0 * math.pi * i / n_pts
                nx = 5.5 + 4.5 * math.cos(a)
                ny = 5.5 + 4.5 * math.sin(a)
                noise = _sample_noise(grid, nx, ny)
                r = base_r * (0.7 + 0.6 * noise)
                pts.append(cx + math.cos(a) * r)
                pts.append(cy + math.sin(a) * r)
            canvas.create_line(*pts, fill=color, width=1, smooth=True)


# ---------------------------------------------------------------------------
# 2. Flow-field streamlines
# ---------------------------------------------------------------------------

def _draw_flow_field(canvas, w: int, h: int, rng: random.Random) -> None:
    """Dense streamlines following a noise-derived vector field."""
    grid = _value_noise_grid(10, 10, rng)
    n_lines = rng.randint(250, 350)
    steps = rng.randint(40, 70)
    step_sz = 3.0

    for _ in range(n_lines):
        color = rng.choice(_get_line_colors())
        x, y = rng.random() * w, rng.random() * h
        pts: list[float] = [x, y]
        for _ in range(steps):
            noise = _sample_noise(grid, x * 8.0 / w, y * 8.0 / h)
            a = noise * math.pi * 5.0
            x += math.cos(a) * step_sz
            y += math.sin(a) * step_sz
            if x < -30 or x > w + 30 or y < -30 or y > h + 30:
                break
            pts.extend((x, y))
        if len(pts) >= 6:
            canvas.create_line(*pts, fill=color, width=1, smooth=True)


# ---------------------------------------------------------------------------
# 3. Constellation / network graph
# ---------------------------------------------------------------------------

def _draw_network(canvas, w: int, h: int, rng: random.Random) -> None:
    """Dense random points connected by short edges -- constellation style."""
    n_pts = rng.randint(80, 120)
    points = [(rng.random() * w, rng.random() * h) for _ in range(n_pts)]
    max_d_sq = (min(w, h) * 0.22) ** 2

    for i in range(n_pts):
        color = rng.choice(_get_line_colors())
        for j in range(i + 1, n_pts):
            dx = points[j][0] - points[i][0]
            dy = points[j][1] - points[i][1]
            if dx * dx + dy * dy < max_d_sq:
                canvas.create_line(
                    points[i][0], points[i][1],
                    points[j][0], points[j][1],
                    fill=color, width=1,
                )
    for x, y in points:
        color = rng.choice(_get_line_colors())
        canvas.create_oval(x - 2, y - 2, x + 2, y + 2,
                           fill=color, outline="")


# ---------------------------------------------------------------------------
# 4. Spirograph / Lissajous curves
# ---------------------------------------------------------------------------

def _draw_spirograph(canvas, w: int, h: int, rng: random.Random) -> None:
    """Overlapping parametric curves with different frequency ratios."""
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
        pts: list[float] = []
        for i in range(n_pts + 1):
            t = 2.0 * math.pi * i / n_pts
            x = cx + rx * math.sin(a_freq * t + phase)
            y = cy + ry * math.cos(b_freq * t)
            pts.extend((x, y))
        canvas.create_line(*pts, fill=color, width=1, smooth=True)


# ---------------------------------------------------------------------------
# 5. Wave interference / moire rings
# ---------------------------------------------------------------------------

def _draw_moire(canvas, w: int, h: int, rng: random.Random) -> None:
    """Concentric rings from several centres that create moire interference."""
    n_sources = rng.randint(3, 5)
    sources = [(rng.random() * w, rng.random() * h) for _ in range(n_sources)]
    spacing = rng.uniform(14, 22)

    for sx, sy in sources:
        color = rng.choice(_get_line_colors())
        max_r = math.hypot(max(w - sx, sx), max(h - sy, sy))
        n_rings = int(max_r / spacing)
        for ring_i in range(1, n_rings + 1):
            r = ring_i * spacing
            canvas.create_oval(
                sx - r, sy - r, sx + r, sy + r,
                outline=color, width=1,
            )


# ---------------------------------------------------------------------------
# 6. Recursive subdivision / Mondrian
# ---------------------------------------------------------------------------

def _draw_mondrian(canvas, w: int, h: int, rng: random.Random) -> None:
    """Randomly subdivide the canvas into rectangles with line borders."""
    min_size = 30
    rects: list[tuple[float, float, float, float]] = [(0, 0, w, h)]
    iterations = rng.randint(5, 7)

    for _ in range(iterations):
        new_rects: list[tuple[float, float, float, float]] = []
        for x0, y0, x1, y1 in rects:
            rw, rh = x1 - x0, y1 - y0
            if rw < min_size * 2 and rh < min_size * 2:
                new_rects.append((x0, y0, x1, y1))
                continue
            if rng.random() < 0.15:
                new_rects.append((x0, y0, x1, y1))
                continue
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
        canvas.create_rectangle(x0, y0, x1, y1, outline=color, width=1)


# ---------------------------------------------------------------------------
# 7. Circle packing
# ---------------------------------------------------------------------------

def _draw_circle_packing(canvas, w: int, h: int, rng: random.Random) -> None:
    """Fill the canvas with non-overlapping circles of varying radii."""
    circles: list[tuple[float, float, float]] = []
    max_attempts = 1500
    min_r, max_r = 4, 50
    pad = 2

    for _ in range(max_attempts):
        cx = rng.random() * w
        cy = rng.random() * h
        r = rng.uniform(min_r, max_r)
        for existing_cx, existing_cy, existing_r in circles:
            dist = math.hypot(cx - existing_cx, cy - existing_cy)
            max_allowed = dist - existing_r - pad
            if max_allowed < min_r:
                r = 0
                break
            r = min(r, max_allowed)
        if r >= min_r:
            circles.append((cx, cy, r))

    for cx, cy, r in circles:
        color = rng.choice(_get_line_colors())
        canvas.create_oval(cx - r, cy - r, cx + r, cy + r,
                           outline=color, width=1)


# ---------------------------------------------------------------------------
# 8. Cross-hatching
# ---------------------------------------------------------------------------

def _draw_crosshatch(canvas, w: int, h: int, rng: random.Random) -> None:
    """Parallel lines at noise-varied angles and densities -- engraving feel."""
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
            x0 += (n0 - 0.5) * warp
            y0 += (n0 - 0.5) * warp
            x1 += (n1 - 0.5) * warp
            y1 += (n1 - 0.5) * warp
            canvas.create_line(x0, y0, x1, y1, fill=color, width=1)


# ---------------------------------------------------------------------------
# 9. Fractal branching / L-system trees
# ---------------------------------------------------------------------------

def _draw_fractal_trees(canvas, w: int, h: int, rng: random.Random) -> None:
    """Recursive branching structures growing from random root points."""
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
            canvas.create_line(bx, by, ex, ey, fill=color, width=1)
            offset = rng.uniform(-0.1, 0.1)
            stack.append((ex, ey, ba - spread + offset, bl * shrink, depth + 1))
            stack.append((ex, ey, ba + spread + offset, bl * shrink, depth + 1))


# ---------------------------------------------------------------------------
# 10. Delaunay triangulation mesh
# ---------------------------------------------------------------------------

def _draw_delaunay(canvas, w: int, h: int, rng: random.Random) -> None:
    """Triangulate random points into a mesh of edges (Bowyer-Watson)."""
    n_pts = rng.randint(60, 100)
    points = [(rng.random() * w, rng.random() * h) for _ in range(n_pts)]
    color = rng.choice(_get_line_colors())

    margin = max(w, h) * 3
    st = [(-margin, -margin), (2 * margin + w, -margin), (w / 2, 2 * margin + h)]
    triangles: list[tuple[int, int, int]] = [(0, 1, 2)]
    all_pts = list(st) + points

    def circumcircle_contains(tri: tuple[int, int, int], px: float, py: float) -> bool:
        ax, ay = all_pts[tri[0]]
        bx, by = all_pts[tri[1]]
        cx, cy = all_pts[tri[2]]
        d = 2 * (ax * (by - cy) + bx * (cy - ay) + cx * (ay - by))
        if abs(d) < 1e-10:
            return False
        ux = ((ax * ax + ay * ay) * (by - cy) + (bx * bx + by * by) * (cy - ay) + (cx * cx + cy * cy) * (ay - by)) / d
        uy = ((ax * ax + ay * ay) * (cx - bx) + (bx * bx + by * by) * (ax - cx) + (cx * cx + cy * cy) * (bx - ax)) / d
        r_sq = (ax - ux) ** 2 + (ay - uy) ** 2
        return (px - ux) ** 2 + (py - uy) ** 2 <= r_sq

    for pi in range(3, len(all_pts)):
        px, py = all_pts[pi]
        bad = [t for t in triangles if circumcircle_contains(t, px, py)]
        boundary: list[tuple[int, int]] = []
        for t in bad:
            for edge in ((t[0], t[1]), (t[1], t[2]), (t[2], t[0])):
                shared = False
                for other in bad:
                    if other is t:
                        continue
                    if edge[0] in other and edge[1] in other:
                        shared = True
                        break
                if not shared:
                    boundary.append(edge)
        for t in bad:
            triangles.remove(t)
        for e in boundary:
            triangles.append((e[0], e[1], pi))

    drawn: set[tuple[int, int]] = set()
    for t in triangles:
        if t[0] < 3 or t[1] < 3 or t[2] < 3:
            continue
        for a, b in ((t[0], t[1]), (t[1], t[2]), (t[2], t[0])):
            key = (min(a, b), max(a, b))
            if key not in drawn:
                drawn.add(key)
                canvas.create_line(
                    all_pts[a][0], all_pts[a][1],
                    all_pts[b][0], all_pts[b][1],
                    fill=color, width=1,
                )


# ---------------------------------------------------------------------------
# 11. Orbital trails
# ---------------------------------------------------------------------------

def _draw_orbital_trails(canvas, w: int, h: int, rng: random.Random) -> None:
    """Simulate particles under gravity attractors and draw their paths."""
    # Place attractors toward edges/corners so orbits sweep across canvas
    n_attractors = rng.randint(2, 4)
    attractors = []
    for _ in range(n_attractors):
        # Bias positions toward edges
        ax = rng.choice([rng.uniform(-0.2, 0.3), rng.uniform(0.7, 1.2)]) * w
        ay = rng.choice([rng.uniform(-0.2, 0.3), rng.uniform(0.7, 1.2)]) * h
        am = rng.uniform(400, 1000)  # Weaker attractors
        attractors.append((ax, ay, am))

    n_particles = rng.randint(50, 90)
    dt = 0.5
    steps = rng.randint(250, 450)

    for _ in range(n_particles):
        color = rng.choice(_get_line_colors())
        x = rng.random() * w
        y = rng.random() * h
        # Higher initial velocity for sweeping arcs
        vx = rng.uniform(-4, 4)
        vy = rng.uniform(-4, 4)
        pts: list[float] = [x, y]

        for _ in range(steps):
            ax_total, ay_total = 0.0, 0.0
            for gx, gy, gm in attractors:
                dx, dy = gx - x, gy - y
                dist_sq = dx * dx + dy * dy + 400  # More softening
                inv_dist = 1.0 / math.sqrt(dist_sq)
                force = gm * inv_dist * inv_dist
                ax_total += dx * inv_dist * force
                ay_total += dy * inv_dist * force
            vx += ax_total * dt
            vy += ay_total * dt
            speed = math.hypot(vx, vy)
            if speed > 10:
                vx *= 10 / speed
                vy *= 10 / speed
            x += vx * dt
            y += vy * dt
            if x < -50 or x > w + 50 or y < -50 or y > h + 50:
                break
            pts.extend((x, y))

        if len(pts) >= 6:
            canvas.create_line(*pts, fill=color, width=1, smooth=True)


# ===================================================================
# Generator registry -- comment/uncomment lines to enable/disable
# ===================================================================

_GENERATORS = [
    _draw_topo_rings,        # 1.  Topographic contour rings
    _draw_flow_field,        # 2.  Flow-field streamlines
    _draw_network,           # 3.  Constellation / network graph
    _draw_spirograph,        # 4.  Spirograph / Lissajous curves
    _draw_moire,             # 5.  Wave interference / moire rings
    _draw_mondrian,          # 6.  Recursive subdivision / Mondrian
    _draw_circle_packing,    # 7.  Circle packing
    _draw_crosshatch,        # 8.  Cross-hatching
    _draw_fractal_trees,     # 9.  Fractal branching / L-system trees
    _draw_delaunay,          # 10. Delaunay triangulation mesh
    _draw_orbital_trails,    # 11. Orbital trails
]


# ===================================================================
# Public API
# ===================================================================

def draw_background(canvas, width: int, height: int) -> None:
    """Pick a random generator and render the background art onto *canvas*.

    Uses a unique seed each launch so the pattern is different every time.
    """
    rng = random.Random()
    generator = rng.choice(_GENERATORS)
    generator(canvas, width, height, rng)
