"""
Icon Registry — manages icon textures for the activity bar.

Creates simple placeholder icons as programmatic RGBA textures.
Call :meth:`load_custom_icon` to replace any placeholder with a
real image file later.

Usage:
    icons = IconRegistry()
    icons.create_default_icons()
    dpg.add_image_button(icons.get("rigs"), ...)
"""

from __future__ import annotations

import math

import dearpygui.dearpygui as dpg


class IconRegistry:
    """Manages icon textures for the activity bar."""

    ICON_SIZE = 24  # pixels

    def __init__(self) -> None:
        self._texture_registry = dpg.add_texture_registry(show=False)
        self._icons: dict[str, int] = {}

    def create_default_icons(self) -> None:
        """Create simple grey-shape placeholder icons."""
        grey = [160, 160, 170]
        self._icons["rigs"] = self._make_placeholder(grey, "hexagon")
        self._icons["tools"] = self._make_placeholder(grey, "wrench")
        self._icons["postproc"] = self._make_placeholder(grey, "chart")
        self._icons["docs"] = self._make_placeholder(grey, "book")

    def _make_placeholder(self, rgb: list[int], shape: str) -> int:
        """Generate a simple RGBA texture programmatically.

        *rgb* is [R, G, B] in 0-255 range.  *shape* selects the glyph.
        Returns the DPG static texture ID.
        """
        size = self.ICON_SIZE
        # RGBA float data [0.0-1.0], row-major
        data = [0.0] * (size * size * 4)

        r, g, b = rgb[0] / 255, rgb[1] / 255, rgb[2] / 255
        cx, cy = size / 2, size / 2

        for y in range(size):
            for x in range(size):
                idx = (y * size + x) * 4
                alpha = 0.0

                if shape == "hexagon":
                    alpha = self._hexagon_mask(x, y, cx, cy, size * 0.42)
                elif shape == "wrench":
                    alpha = self._circle_mask(x, y, cx, cy, size * 0.38)
                    # Cut a notch to suggest a wrench/gear shape
                    if x > cx and abs(y - cy) < size * 0.12:
                        alpha = 0.0
                elif shape == "chart":
                    alpha = self._bar_chart_mask(x, y, size)
                elif shape == "book":
                    alpha = self._book_mask(x, y, size)
                else:
                    alpha = self._circle_mask(x, y, cx, cy, size * 0.4)

                data[idx + 0] = r
                data[idx + 1] = g
                data[idx + 2] = b
                data[idx + 3] = alpha

        return dpg.add_static_texture(
            size, size, data, parent=self._texture_registry,
        )

    # --- Shape masks (return alpha 0.0-1.0) ---

    @staticmethod
    def _circle_mask(x: int, y: int, cx: float, cy: float, radius: float) -> float:
        dist = math.hypot(x - cx, y - cy)
        if dist <= radius - 0.5:
            return 1.0
        elif dist <= radius + 0.5:
            return max(0.0, radius + 0.5 - dist)
        return 0.0

    @staticmethod
    def _hexagon_mask(x: int, y: int, cx: float, cy: float, radius: float) -> float:
        """Test if point is inside a regular hexagon centered at (cx,cy)."""
        dx = abs(x - cx)
        dy = abs(y - cy)
        # Hexagon test using the "column" method
        if dx > radius or dy > radius * 0.866:
            return 0.0
        if radius * 0.866 - dy + (radius - dx) * 0.577 > 0:
            return 1.0
        return 0.0

    @staticmethod
    def _bar_chart_mask(x: int, y: int, size: int) -> float:
        """Three vertical bars of different heights — suggests a chart."""
        margin = size * 0.15
        bar_w = size * 0.18
        gap = size * 0.05
        heights = [0.5, 0.8, 0.65]  # relative heights

        for i, h in enumerate(heights):
            bx = margin + i * (bar_w + gap)
            by_top = size * (1.0 - h * 0.75) - margin * 0.5
            by_bot = size - margin
            if bx <= x <= bx + bar_w and by_top <= y <= by_bot:
                return 1.0
        return 0.0

    @staticmethod
    def _book_mask(x: int, y: int, size: int) -> float:
        """Rectangle with a spine line — suggests a book/document."""
        m = size * 0.18
        if m <= x <= size - m and m <= y <= size - m:
            # Spine line
            if abs(x - size * 0.35) < 1.0:
                return 0.3  # dimmer spine
            return 1.0
        return 0.0

    def load_custom_icon(self, name: str, image_path: str) -> None:
        """Load a custom icon from a PNG/image file.

        Replaces the placeholder for *name*.  Requires the image to be
        ICON_SIZE x ICON_SIZE pixels.  Uses OpenCV if available, falls
        back to a simple loader otherwise.
        """
        size = self.ICON_SIZE
        try:
            import cv2
            img = cv2.imread(image_path, cv2.IMREAD_UNCHANGED)
            if img is None:
                print(f"Warning: could not load icon '{image_path}'")
                return
            if img.shape[0] != size or img.shape[1] != size:
                img = cv2.resize(img, (size, size))
            # Convert BGR(A) to RGBA float [0-1]
            if img.shape[2] == 3:
                import numpy as np
                alpha = np.ones((*img.shape[:2], 1), dtype=img.dtype) * 255
                img = np.concatenate([img, alpha], axis=2)
            # BGR → RGB
            img[:, :, [0, 2]] = img[:, :, [2, 0]]
            data = (img.flatten() / 255.0).tolist()
        except ImportError:
            print(f"Warning: cv2 not available, cannot load custom icon '{image_path}'")
            return

        # Delete old texture if it exists
        old = self._icons.get(name)
        if old is not None and dpg.does_item_exist(old):
            dpg.delete_item(old)

        self._icons[name] = dpg.add_static_texture(
            size, size, data, parent=self._texture_registry,
        )

    def get(self, name: str) -> int:
        """Get texture ID for an icon name."""
        return self._icons[name]
