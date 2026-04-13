"""
Modern Theme Configuration for Behaviour Rig System GUI (DearPyGui).

Provides a consistent, professional appearance across all windows with:
- Dark/light color palette with accent colors
- DearPyGui theme objects for all widget types
- Consistent fonts and spacing
- Status color coding (success, warning, error)

Available palettes:
- LIGHT_PALETTE: Modern blue theme - professional and clean
- DARK_PALETTE: Dark theme - easy on the eyes for long sessions
- DARK_GREEN_PALETTE: Hacker green - classic Matrix terminal style
- DARK_RED_PALETTE: Hacker red - cyberpunk danger style

Usage:
    from gui.theme import apply_theme, Theme

    Theme.palette = DARK_GREEN_PALETTE
    apply_theme()
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import NamedTuple

import dearpygui.dearpygui as dpg

# Icon path (relative to this file)
_ICON_PATH = Path(__file__).parent / "favicon.ico"


# =========================================================================
# Color palette definition (pure data — no toolkit dependency)
# =========================================================================

class ColorPalette(NamedTuple):
    """Color palette for the theme."""
    # Fonts
    font_family: str         # Primary UI font family
    font_family_mono: str    # Monospace font family
    font_special: str        # Display/title font (e.g. launcher header)

    # Main colors
    bg_primary: str          # Main background
    bg_secondary: str        # Secondary background (cards, frames)
    bg_tertiary: str         # Tertiary (input fields)
    bg_header: str           # Header/title bar background

    # Text colors
    text_primary: str        # Main text
    text_secondary: str      # Secondary/muted text
    text_disabled: str       # Disabled text
    text_inverse: str        # Text on dark backgrounds

    # Accent colors
    accent_primary: str      # Primary accent (buttons, highlights)
    accent_secondary: str    # Secondary accent
    accent_hover: str        # Hover state
    accent_active: str       # Active/pressed state

    # Status colors
    success: str             # Success/correct
    success_light: str       # Light success background
    warning: str             # Warning/caution
    warning_light: str       # Light warning background
    error: str               # Error/incorrect
    error_light: str         # Light error background
    info: str                # Information
    info_light: str          # Light info background

    # Border colors
    border_light: str        # Light borders
    border_medium: str       # Medium borders
    border_dark: str         # Dark borders

    # Special colors
    rig_selected: str        # Selected rig button
    rig_open: str            # Open rig button


# =========================================================================
# Palette definitions
# =========================================================================
#
# Design rules for DPG palettes:
#   1. 3-tier depth: bg_primary (deepest) < bg_secondary (panels) < bg_tertiary (inputs)
#      Each tier must be visibly distinct so panels/inputs don't disappear.
#   2. text_primary must be legible on ALL 3 bg tiers.
#   3. text_inverse must be legible on accent_primary (used for button labels).
#   4. For monochrome themes where accent == text, use a darker accent for buttons
#      so text_inverse (dark) is readable, and keep text_primary bright for body text.
#   5. bg_header should be darker than bg_primary (used for activity bar, info bar).

# Modern blue — professional and clean
LIGHT_PALETTE = ColorPalette(
    font_family="Segoe UI", font_family_mono="Consolas", font_special="Old English Text MT",
    bg_primary="#eaecf0",          # Light grey viewport
    bg_secondary="#f5f7fa",        # Slightly lighter panels
    bg_tertiary="#ffffff",         # White inputs (brightest)
    bg_header="#2c3e50",           # Dark header bar
    text_primary="#1a2530",        # Dark text on all light bgs
    text_secondary="#5a6b7d",      # Muted
    text_disabled="#9ca8b5",       # Greyed
    text_inverse="#ffffff",        # White on blue buttons
    accent_primary="#3498db",      # Blue buttons
    accent_secondary="#2980b9",
    accent_hover="#5dade2",
    accent_active="#21618c",
    success="#27ae60", success_light="#d4efdf",
    warning="#f39c12", warning_light="#fdebd0",
    error="#e74c3c", error_light="#fadbd8",
    info="#3498db", info_light="#d6eaf8",
    border_light="#dce1e8", border_medium="#ced4da", border_dark="#8fa0b0",
    rig_selected="#58d68d", rig_open="#95a5a6",
)

# Dark blue — easy on the eyes
DARK_PALETTE = ColorPalette(
    font_family="Segoe UI", font_family_mono="Consolas", font_special="Old English Text MT",
    bg_primary="#1a1a2e",          # Deep blue-grey
    bg_secondary="#252540",        # Mid panels
    bg_tertiary="#30304a",         # Input frames
    bg_header="#12121f",           # Deepest
    text_primary="#e0e0ef",        # Light text
    text_secondary="#8888a8",
    text_disabled="#555570",
    text_inverse="#1a1a2e",        # Dark on bright buttons
    accent_primary="#5b9bd5",      # Muted blue
    accent_secondary="#4a89c8",
    accent_hover="#74b3e8",
    accent_active="#3570a5",
    success="#4caf79", success_light="#1e3d2b",
    warning="#e5a832", warning_light="#3d3520",
    error="#e05555", error_light="#3d1e1e",
    info="#5b9bd5", info_light="#1e2d3d",
    border_light="#3a3a55", border_medium="#50506b", border_dark="#6a6a85",
    rig_selected="#3d8c5c", rig_open="#3a3a55",
)

# Matrix green — neon on black
DARK_GREEN_PALETTE = ColorPalette(
    font_family="Lucida Console", font_family_mono="Lucida Console", font_special="Old English Text MT",
    bg_primary="#080808",          # Near black
    bg_secondary="#101810",        # Slight green tint
    bg_tertiary="#182818",         # Visible green-black
    bg_header="#040604",           # Deepest
    text_primary="#00ff41",        # Bright green text
    text_secondary="#00bb33",
    text_disabled="#004d1a",
    text_inverse="#050505",        # Black on green buttons
    accent_primary="#00cc33",      # Slightly darker than text so text_inverse is readable
    accent_secondary="#00aa28",
    accent_hover="#33ff66",
    accent_active="#008820",
    success="#00ff41", success_light="#0a1f0f",
    warning="#ccff00", warning_light="#1a1f0a",
    error="#ff3333", error_light="#1f0a0a",
    info="#00ffcc", info_light="#0a1f1a",
    border_light="#0a2a0a", border_medium="#0f3f0f", border_dark="#1a5a1a",
    rig_selected="#00cc33", rig_open="#0a2a0a",
)

# Cyberpunk red — neon on black
DARK_RED_PALETTE = ColorPalette(
    font_family="Lucida Console", font_family_mono="Lucida Console", font_special="Old English Text MT",
    bg_primary="#080808",          # Near black
    bg_secondary="#180808",        # Slight red tint
    bg_tertiary="#281010",         # Visible red-black
    bg_header="#040202",           # Deepest
    text_primary="#ff4444",        # Bright red text
    text_secondary="#cc3030",
    text_disabled="#4d1414",
    text_inverse="#050505",        # Black on red buttons
    accent_primary="#cc2929",      # Darker than text for readable button labels
    accent_secondary="#aa2020",
    accent_hover="#ff6666",
    accent_active="#881818",
    success="#33ff77", success_light="#0a1f10",
    warning="#ffcc00", warning_light="#1f1a0a",
    error="#ff4444", error_light="#1f0a0a",
    info="#ff6699", info_light="#1f0a10",
    border_light="#2a0a0a", border_medium="#3f0f0f", border_dark="#5a1a1a",
    rig_selected="#cc2929", rig_open="#2a0a0a",
)

# Monochrome — white on black
DARK_BW_PALETTE = ColorPalette(
    font_family="Lucida Console", font_family_mono="Lucida Console", font_special="Old English Text MT",
    bg_primary="#0a0a0a",          # Black
    bg_secondary="#151515",        # Dark grey panels
    bg_tertiary="#222222",         # Input frames
    bg_header="#050505",           # Deepest
    text_primary="#e8e8e8",        # Off-white text
    text_secondary="#999999",
    text_disabled="#444444",
    text_inverse="#0a0a0a",        # Black on white buttons
    accent_primary="#cccccc",      # Light grey buttons (not pure white)
    accent_secondary="#aaaaaa",
    accent_hover="#e0e0e0",
    accent_active="#888888",
    success="#33ff77", success_light="#0a1f10",
    warning="#ffcc00", warning_light="#1f1a0a",
    error="#ff3333", error_light="#1f0a0a",
    info="#66ccff", info_light="#0a1520",
    border_light="#252525", border_medium="#383838", border_dark="#555555",
    rig_selected="#aaaaaa", rig_open="#252525",
)

# Corporate blue — professional, no frills
BORING_PALETTE = ColorPalette(
    font_family="Segoe UI", font_family_mono="Consolas", font_special="Segoe UI",
    bg_primary="#e8e8e8",          # Light grey viewport
    bg_secondary="#f2f2f2",        # Slightly lighter panels
    bg_tertiary="#ffffff",         # White inputs
    bg_header="#333333",           # Dark header
    text_primary="#222222",        # Dark text
    text_secondary="#666666",
    text_disabled="#999999",
    text_inverse="#ffffff",        # White on blue buttons
    accent_primary="#0066cc",      # Corporate blue
    accent_secondary="#004c99",
    accent_hover="#3388dd",
    accent_active="#003d80",
    success="#2e7d32", success_light="#e8f5e9",
    warning="#f57c00", warning_light="#fff3e0",
    error="#c62828", error_light="#ffebee",
    info="#0066cc", info_light="#e3f2fd",
    border_light="#d0d0d0", border_medium="#bbbbbb", border_dark="#888888",
    rig_selected="#4caf50", rig_open="#cccccc",
)

# Neon magenta — purple-pink on black
DARK_MAGENTA_PALETTE = ColorPalette(
    font_family="Lucida Console", font_family_mono="Lucida Console", font_special="Old English Text MT",
    bg_primary="#080808",          # Near black
    bg_secondary="#140818",        # Slight magenta tint
    bg_tertiary="#201028",         # Visible magenta-black
    bg_header="#040206",           # Deepest
    text_primary="#ff55ff",        # Bright magenta text
    text_secondary="#cc33cc",
    text_disabled="#4d144d",
    text_inverse="#050505",        # Black on magenta buttons
    accent_primary="#cc29cc",      # Darker than text for readable labels
    accent_secondary="#aa20aa",
    accent_hover="#ff66ff",
    accent_active="#881888",
    success="#33ff77", success_light="#0a1f10",
    warning="#ffcc00", warning_light="#1f1a0a",
    error="#ff3333", error_light="#1f0a0a",
    info="#cc66ff", info_light="#1a0a1f",
    border_light="#200a20", border_medium="#3f0f3f", border_dark="#5a1a5a",
    rig_selected="#cc29cc", rig_open="#200a20",
)

# Soft pink — rose on white
LIGHT_PINK_PALETTE = ColorPalette(
    font_family="Segoe UI", font_family_mono="Consolas", font_special="Old English Text MT",
    bg_primary="#f5e6ee",          # Soft pink base
    bg_secondary="#fdf0f5",        # Lighter panels
    bg_tertiary="#ffffff",         # White inputs
    bg_header="#880e4f",           # Deep rose header
    text_primary="#33111a",        # Dark text
    text_secondary="#7a4a5a",
    text_disabled="#bda0aa",
    text_inverse="#ffffff",        # White on pink buttons
    accent_primary="#e91e63",      # Rose pink
    accent_secondary="#c2185b",
    accent_hover="#f06292",
    accent_active="#ad1457",
    success="#2e7d32", success_light="#e8f5e9",
    warning="#f57c00", warning_light="#fff3e0",
    error="#c62828", error_light="#ffebee",
    info="#e91e63", info_light="#fce4ec",
    border_light="#f0c0d5", border_medium="#e8a0be", border_dark="#d080a5",
    rig_selected="#f06292", rig_open="#e0c0d0",
)

PALETTES = {
    "light": LIGHT_PALETTE,
    "dark": DARK_PALETTE,
    "dark_green": DARK_GREEN_PALETTE,
    "dark_red": DARK_RED_PALETTE,
    "dark_bw": DARK_BW_PALETTE,
    "dark_magenta": DARK_MAGENTA_PALETTE,
    "light_pink": LIGHT_PINK_PALETTE,
    "boring": BORING_PALETTE,
}


# =========================================================================
# Hex → RGBA conversion
# =========================================================================

def hex_to_rgba(hex_color: str, alpha: int = 255) -> list[int]:
    """Convert '#RRGGBB' to [R, G, B, alpha]."""
    hex_color = hex_color.lstrip("#")
    r = int(hex_color[0:2], 16)
    g = int(hex_color[2:4], 16)
    b = int(hex_color[4:6], 16)
    return [r, g, b, alpha]


# =========================================================================
# Theme class
# =========================================================================

class Theme:
    """Theme configuration and utilities."""

    palette: ColorPalette = DARK_RED_PALETTE

    FONT_FAMILY = palette.font_family
    FONT_FAMILY_MONO = palette.font_family_mono
    FONT_SPECIAL = palette.font_special

    FONT_SIZE_TITLE = 18
    FONT_SIZE_HEADING = 14
    FONT_SIZE_SUBHEADING = 12
    FONT_SIZE_BODY = 10
    FONT_SIZE_SMALL = 9
    FONT_SIZE_TINY = 8

    # Spacing (compact)
    PAD_SMALL = 3
    PAD_MEDIUM = 6
    PAD_LARGE = 10
    PAD_XLARGE = 14

    # Widget dimensions
    BUTTON_HEIGHT = 26
    ENTRY_HEIGHT = 24

    # DPG font IDs (populated by apply_theme)
    _font_default: int | None = None
    _font_mono: int | None = None
    _font_heading: int | None = None
    _font_title: int | None = None
    _font_small: int | None = None

    # DPG named themes (populated by apply_theme)
    _global_theme: int | None = None
    primary_button_theme: int | None = None
    disabled_button_theme: int | None = None
    secondary_button_theme: int | None = None
    danger_button_theme: int | None = None
    success_button_theme: int | None = None
    activity_bar_theme: int | None = None
    icon_button_theme: int | None = None
    sidebar_theme: int | None = None
    info_bar_theme: int | None = None

    @classmethod
    def set_palette(cls, palette: ColorPalette) -> None:
        """Set the active palette and update derived font attributes."""
        cls.palette = palette
        cls.FONT_FAMILY = palette.font_family
        cls.FONT_FAMILY_MONO = palette.font_family_mono
        cls.FONT_SPECIAL = palette.font_special

    # ----- Font accessors (DPG font IDs) -----

    @classmethod
    def font(cls, size: int | None = None, weight: str = "normal"):
        """Get the default font ID.  *size* and *weight* are accepted for
        API compatibility but DPG fonts are pre-loaded at fixed sizes."""
        return cls._font_default

    @classmethod
    def font_mono(cls, size: int | None = None, weight: str = "normal"):
        return cls._font_mono

    @classmethod
    def font_special(cls, size: int = 24):
        return cls._font_title  # best available approximation

    @classmethod
    def font_title(cls):
        return cls._font_title

    @classmethod
    def font_heading(cls):
        return cls._font_heading

    @classmethod
    def font_subheading(cls):
        return cls._font_heading

    @classmethod
    def font_body(cls):
        return cls._font_default

    @classmethod
    def font_small(cls):
        return cls._font_small

    @classmethod
    def font_tiny(cls):
        return cls._font_small


# =========================================================================
# Font loading
# =========================================================================

# Bundled font files (shipped with the project)
_FONTS_DIR = Path(__file__).parent / "fonts"

# Map font family names to bundled .ttf filenames
_FONT_FILES = {
    "segoe ui":            ("segoeui.ttf",     "segoeuib.ttf"),
    "consolas":            ("consola.ttf",     "consolab.ttf"),
    "lucida console":      ("lucon.ttf",       "lucon.ttf"),
    "cascadia mono":       ("CascadiaMono.ttf", "CascadiaMono.ttf"),
    "old english text mt": ("OLDENGL.TTF",     "OLDENGL.TTF"),
}


def _resolve_font(family: str, bold: bool = False) -> str | None:
    """Resolve a font family name to a bundled .ttf file path."""
    key = family.lower()
    if key in _FONT_FILES:
        regular, bold_name = _FONT_FILES[key]
        path = _FONTS_DIR / (bold_name if bold else regular)
        if path.exists():
            return str(path)

    # Fallback: try Segoe UI
    if key != "segoe ui":
        return _resolve_font("Segoe UI", bold)

    return None


def _load_fonts() -> None:
    """Register fonts with DPG.  Called once by apply_theme()."""
    import logging
    _log = logging.getLogger(__name__)

    palette = Theme.palette

    body_path = _resolve_font(palette.font_family)
    bold_path = _resolve_font(palette.font_family, bold=True) or body_path
    mono_path = _resolve_font(palette.font_family_mono) or body_path
    special_path = _resolve_font(palette.font_special) or bold_path

    if body_path is None:
        _log.warning(
            f"No bundled font found for '{palette.font_family}'. "
            "Using DPG built-in font. Check hexcontrol/gui/fonts/ directory."
        )
        return

    _log.info(f"Loading fonts from {_FONTS_DIR}")

    with dpg.font_registry():
        # Load fonts at 2x target size for sharp rendering on high-DPI.
        # Use set_global_font_scale(0.5) as baseline to compensate.
        Theme._font_default = dpg.add_font(body_path, 26)
        Theme._font_small = dpg.add_font(body_path, 22)
        Theme._font_heading = dpg.add_font(bold_path, 28)
        Theme._font_title = dpg.add_font(special_path or bold_path, 52)
        Theme._font_mono = dpg.add_font(mono_path, 26)

    if Theme._font_default is not None:
        dpg.bind_font(Theme._font_default)
        # Scale down from 2x rasterized size to target display size
        dpg.set_global_font_scale(0.5)


# =========================================================================
# Theme application
# =========================================================================

def apply_theme() -> None:
    """Create DPG theme objects from the active palette and bind globally.

    Must be called once after :func:`dpg_app.create_app`.
    """
    _load_fonts()
    palette = Theme.palette

    bg = hex_to_rgba(palette.bg_primary)
    bg2 = hex_to_rgba(palette.bg_secondary)
    bg3 = hex_to_rgba(palette.bg_tertiary)
    txt = hex_to_rgba(palette.text_primary)
    txt2 = hex_to_rgba(palette.text_secondary)
    txt_dis = hex_to_rgba(palette.text_disabled)
    accent = hex_to_rgba(palette.accent_primary)
    accent2 = hex_to_rgba(palette.accent_secondary)
    accent_h = hex_to_rgba(palette.accent_hover)
    accent_a = hex_to_rgba(palette.accent_active)
    border = hex_to_rgba(palette.border_light)
    border_m = hex_to_rgba(palette.border_medium)

    # --- Global theme ---
    with dpg.theme() as global_theme:
        with dpg.theme_component(dpg.mvAll):
            # Window / frame backgrounds
            dpg.add_theme_color(dpg.mvThemeCol_WindowBg, bg)
            dpg.add_theme_color(dpg.mvThemeCol_ChildBg, bg2)
            dpg.add_theme_color(dpg.mvThemeCol_PopupBg, bg2)
            dpg.add_theme_color(dpg.mvThemeCol_MenuBarBg, bg)

            # Text
            dpg.add_theme_color(dpg.mvThemeCol_Text, txt)
            dpg.add_theme_color(dpg.mvThemeCol_TextDisabled, txt_dis)

            # Borders
            dpg.add_theme_color(dpg.mvThemeCol_Border, border)
            dpg.add_theme_color(dpg.mvThemeCol_BorderShadow, [0, 0, 0, 0])

            # Frame (input) backgrounds
            dpg.add_theme_color(dpg.mvThemeCol_FrameBg, bg3)
            dpg.add_theme_color(dpg.mvThemeCol_FrameBgHovered, border)
            dpg.add_theme_color(dpg.mvThemeCol_FrameBgActive, border_m)

            # Title bar
            dpg.add_theme_color(dpg.mvThemeCol_TitleBg, hex_to_rgba(palette.bg_header))
            dpg.add_theme_color(dpg.mvThemeCol_TitleBgActive, hex_to_rgba(palette.bg_header))
            dpg.add_theme_color(dpg.mvThemeCol_TitleBgCollapsed, hex_to_rgba(palette.bg_header))

            # Buttons
            dpg.add_theme_color(dpg.mvThemeCol_Button, accent)
            dpg.add_theme_color(dpg.mvThemeCol_ButtonHovered, accent_h)
            dpg.add_theme_color(dpg.mvThemeCol_ButtonActive, accent_a)

            # Headers (collapsing headers, tree nodes)
            dpg.add_theme_color(dpg.mvThemeCol_Header, bg3)
            dpg.add_theme_color(dpg.mvThemeCol_HeaderHovered, border)
            dpg.add_theme_color(dpg.mvThemeCol_HeaderActive, border_m)

            # Tabs
            dpg.add_theme_color(dpg.mvThemeCol_Tab, bg3)
            dpg.add_theme_color(dpg.mvThemeCol_TabHovered, accent_h)
            dpg.add_theme_color(dpg.mvThemeCol_TabActive, accent)
            dpg.add_theme_color(dpg.mvThemeCol_TabUnfocused, bg3)
            dpg.add_theme_color(dpg.mvThemeCol_TabUnfocusedActive, accent2)

            # Scrollbar
            dpg.add_theme_color(dpg.mvThemeCol_ScrollbarBg, bg)
            dpg.add_theme_color(dpg.mvThemeCol_ScrollbarGrab, border_m)
            dpg.add_theme_color(dpg.mvThemeCol_ScrollbarGrabHovered, accent_h)
            dpg.add_theme_color(dpg.mvThemeCol_ScrollbarGrabActive, accent)

            # Slider
            dpg.add_theme_color(dpg.mvThemeCol_SliderGrab, accent)
            dpg.add_theme_color(dpg.mvThemeCol_SliderGrabActive, accent_a)

            # Checkbox
            dpg.add_theme_color(dpg.mvThemeCol_CheckMark, accent)

            # Separator
            dpg.add_theme_color(dpg.mvThemeCol_Separator, border)

            # Resize grip
            dpg.add_theme_color(dpg.mvThemeCol_ResizeGrip, border)
            dpg.add_theme_color(dpg.mvThemeCol_ResizeGripHovered, accent_h)
            dpg.add_theme_color(dpg.mvThemeCol_ResizeGripActive, accent)

            # Table
            dpg.add_theme_color(dpg.mvThemeCol_TableHeaderBg, bg3)
            dpg.add_theme_color(dpg.mvThemeCol_TableBorderStrong, border_m)
            dpg.add_theme_color(dpg.mvThemeCol_TableBorderLight, border)
            dpg.add_theme_color(dpg.mvThemeCol_TableRowBg, [0, 0, 0, 0])
            dpg.add_theme_color(dpg.mvThemeCol_TableRowBgAlt, [
                border[0], border[1], border[2], 40])

            # Text selection
            dpg.add_theme_color(dpg.mvThemeCol_TextSelectedBg, [
                accent[0], accent[1], accent[2], 90])

            # Style
            dpg.add_theme_style(dpg.mvStyleVar_FrameRounding, 3)
            dpg.add_theme_style(dpg.mvStyleVar_WindowRounding, 4)
            dpg.add_theme_style(dpg.mvStyleVar_ChildRounding, 3)
            dpg.add_theme_style(dpg.mvStyleVar_GrabRounding, 3)
            dpg.add_theme_style(dpg.mvStyleVar_TabRounding, 3)
            dpg.add_theme_style(dpg.mvStyleVar_FramePadding, 4, 3)
            dpg.add_theme_style(dpg.mvStyleVar_ItemSpacing, 6, 3)

        # Plot colors need their own theme component with mvThemeCat_Plots category
        with dpg.theme_component(0):
            dpg.add_theme_color(dpg.mvPlotCol_PlotBg, bg2, category=dpg.mvThemeCat_Plots)
            dpg.add_theme_color(dpg.mvPlotCol_PlotBorder, border_m, category=dpg.mvThemeCat_Plots)
            dpg.add_theme_color(dpg.mvPlotCol_FrameBg, bg3, category=dpg.mvThemeCat_Plots)

    dpg.bind_theme(global_theme)
    Theme._global_theme = global_theme

    # --- Button variant themes ---

    with dpg.theme() as primary_btn:
        with dpg.theme_component(dpg.mvButton):
            dpg.add_theme_color(dpg.mvThemeCol_Button, accent)
            dpg.add_theme_color(dpg.mvThemeCol_ButtonHovered, accent_h)
            dpg.add_theme_color(dpg.mvThemeCol_ButtonActive, accent_a)
            dpg.add_theme_color(dpg.mvThemeCol_Text, hex_to_rgba(palette.text_inverse))
            dpg.add_theme_color(dpg.mvThemeCol_TextDisabled, hex_to_rgba(palette.text_disabled))
    Theme.primary_button_theme = primary_btn

    with dpg.theme() as disabled_btn:
        with dpg.theme_component(dpg.mvButton):
            dpg.add_theme_color(dpg.mvThemeCol_Button, bg3)
            dpg.add_theme_color(dpg.mvThemeCol_ButtonHovered, bg3)
            dpg.add_theme_color(dpg.mvThemeCol_ButtonActive, bg3)
            dpg.add_theme_color(dpg.mvThemeCol_Text, txt2)
    Theme.disabled_button_theme = disabled_btn

    with dpg.theme() as secondary_btn:
        with dpg.theme_component(dpg.mvButton):
            dpg.add_theme_color(dpg.mvThemeCol_Button, bg2)
            dpg.add_theme_color(dpg.mvThemeCol_ButtonHovered, bg3)
            dpg.add_theme_color(dpg.mvThemeCol_ButtonActive, border)
            dpg.add_theme_color(dpg.mvThemeCol_Text, accent)
    Theme.secondary_button_theme = secondary_btn

    with dpg.theme() as danger_btn:
        with dpg.theme_component(dpg.mvButton):
            dpg.add_theme_color(dpg.mvThemeCol_Button, hex_to_rgba(palette.error))
            dpg.add_theme_color(dpg.mvThemeCol_ButtonHovered, hex_to_rgba("#c0392b"))
            dpg.add_theme_color(dpg.mvThemeCol_ButtonActive, hex_to_rgba("#922b21"))
            dpg.add_theme_color(dpg.mvThemeCol_Text, hex_to_rgba(palette.text_inverse))
            dpg.add_theme_color(dpg.mvThemeCol_TextDisabled, hex_to_rgba(palette.text_secondary))
    Theme.danger_button_theme = danger_btn

    with dpg.theme() as success_btn:
        with dpg.theme_component(dpg.mvButton):
            dpg.add_theme_color(dpg.mvThemeCol_Button, hex_to_rgba(palette.success))
            dpg.add_theme_color(dpg.mvThemeCol_ButtonHovered, hex_to_rgba("#2ecc71"))
            dpg.add_theme_color(dpg.mvThemeCol_ButtonActive, hex_to_rgba("#1e8449"))
            dpg.add_theme_color(dpg.mvThemeCol_Text, hex_to_rgba(palette.text_inverse))
            dpg.add_theme_color(dpg.mvThemeCol_TextDisabled, hex_to_rgba(palette.text_secondary))
    Theme.success_button_theme = success_btn

    # --- Layout component themes ---

    with dpg.theme() as activity_bar_theme:
        with dpg.theme_component(0):
            dpg.add_theme_color(dpg.mvThemeCol_ChildBg, hex_to_rgba(palette.bg_header))
            dpg.add_theme_style(dpg.mvStyleVar_ChildRounding, 0)
            dpg.add_theme_style(dpg.mvStyleVar_WindowPadding, 4, 8)
            dpg.add_theme_style(dpg.mvStyleVar_ItemSpacing, 4, 8)
    Theme.activity_bar_theme = activity_bar_theme

    with dpg.theme() as icon_btn_theme:
        with dpg.theme_component(dpg.mvImageButton):
            dpg.add_theme_color(dpg.mvThemeCol_Button, [0, 0, 0, 0])
            dpg.add_theme_color(dpg.mvThemeCol_ButtonHovered, [255, 255, 255, 25])
            dpg.add_theme_color(dpg.mvThemeCol_ButtonActive, [255, 255, 255, 50])
            dpg.add_theme_style(dpg.mvStyleVar_FramePadding, 4, 4)
            dpg.add_theme_style(dpg.mvStyleVar_FrameRounding, 4)
    Theme.icon_button_theme = icon_btn_theme

    # Sidebar: slightly lighter than main bg for subtle differentiation
    sidebar_bg = [(bg2[i] + bg3[i]) // 2 for i in range(4)]
    with dpg.theme() as sidebar_theme:
        with dpg.theme_component(0):
            dpg.add_theme_color(dpg.mvThemeCol_ChildBg, sidebar_bg)
            dpg.add_theme_style(dpg.mvStyleVar_ChildRounding, 0)
            dpg.add_theme_style(dpg.mvStyleVar_WindowPadding, 8, 6)
    Theme.sidebar_theme = sidebar_theme

    with dpg.theme() as info_bar_theme:
        with dpg.theme_component(0):
            dpg.add_theme_color(dpg.mvThemeCol_ChildBg, hex_to_rgba(palette.bg_header))
            dpg.add_theme_style(dpg.mvStyleVar_ChildRounding, 0)
            dpg.add_theme_style(dpg.mvStyleVar_WindowPadding, 10, 4)
    Theme.info_bar_theme = info_bar_theme

    # Set viewport background
    dpg.set_viewport_clear_color(bg)


# =========================================================================
# Helper: rig button themes  (replaces style_rig_button / create_rig_button)
# =========================================================================

_rig_button_themes: dict[str, int] = {}


def _ensure_rig_button_themes() -> None:
    """Lazily create the three rig-button theme variants."""
    if _rig_button_themes:
        return
    palette = Theme.palette

    with dpg.theme() as normal:
        with dpg.theme_component(dpg.mvButton):
            dpg.add_theme_color(dpg.mvThemeCol_Button, hex_to_rgba(palette.bg_tertiary))
            dpg.add_theme_color(dpg.mvThemeCol_ButtonHovered, hex_to_rgba(palette.border_light))
            dpg.add_theme_color(dpg.mvThemeCol_ButtonActive, hex_to_rgba(palette.border_medium))
            dpg.add_theme_color(dpg.mvThemeCol_Text, hex_to_rgba(palette.text_primary))
    _rig_button_themes["normal"] = normal

    with dpg.theme() as selected:
        with dpg.theme_component(dpg.mvButton):
            dpg.add_theme_color(dpg.mvThemeCol_Button, hex_to_rgba(palette.rig_selected))
            dpg.add_theme_color(dpg.mvThemeCol_ButtonHovered, hex_to_rgba(palette.accent_hover))
            dpg.add_theme_color(dpg.mvThemeCol_ButtonActive, hex_to_rgba(palette.accent_active))
            # Use text_inverse (dark) on bright selected bg
            dpg.add_theme_color(dpg.mvThemeCol_Text, hex_to_rgba(palette.text_inverse))
    _rig_button_themes["selected"] = selected

    with dpg.theme() as opened:
        with dpg.theme_component(dpg.mvButton):
            dpg.add_theme_color(dpg.mvThemeCol_Button, hex_to_rgba(palette.rig_open))
            dpg.add_theme_color(dpg.mvThemeCol_ButtonHovered, hex_to_rgba(palette.rig_open))
            dpg.add_theme_color(dpg.mvThemeCol_ButtonActive, hex_to_rgba(palette.rig_open))
            # Use text_secondary (muted but visible) on disabled bg
            dpg.add_theme_color(dpg.mvThemeCol_Text, hex_to_rgba(palette.text_secondary))
    _rig_button_themes["open"] = opened


def style_rig_button(
    button_id: int | str,
    is_selected: bool = False,
    is_open: bool = False,
) -> None:
    """Apply the appropriate rig-button theme to *button_id*."""
    _ensure_rig_button_themes()

    if is_open:
        dpg.bind_item_theme(button_id, _rig_button_themes["open"])
        dpg.configure_item(button_id, enabled=False)
    elif is_selected:
        dpg.bind_item_theme(button_id, _rig_button_themes["selected"])
        dpg.configure_item(button_id, enabled=True)
    else:
        dpg.bind_item_theme(button_id, _rig_button_themes["normal"])
        dpg.configure_item(button_id, enabled=True)


def create_rig_button(parent, text: str, command, **kwargs) -> int:
    """Create a rig selection button and return its DPG item ID."""
    _ensure_rig_button_themes()
    btn = dpg.add_button(label=text, callback=lambda: command(), parent=parent,
                         width=-1, height=44, **kwargs)
    dpg.bind_item_theme(btn, _rig_button_themes["normal"])
    return btn


# =========================================================================
# Color utility functions
# =========================================================================

def get_status_color(status: str) -> str:
    """Get the appropriate hex color for a status string."""
    palette = Theme.palette
    status_lower = status.lower()
    if status_lower in ("running", "started", "active"):
        return palette.success
    elif status_lower in ("completed", "success", "done"):
        return "#1e8449"
    elif status_lower in ("stopped", "paused", "warning"):
        return palette.warning
    elif status_lower in ("error", "failed"):
        return palette.error
    elif status_lower in ("idle", "waiting", "ready"):
        return palette.info
    else:
        return palette.text_secondary


def get_accuracy_color(accuracy: float) -> str:
    """Get a hex color based on accuracy percentage."""
    palette = Theme.palette
    if accuracy >= 70:
        return palette.success
    elif accuracy >= 50:
        return palette.warning
    else:
        return palette.error


# =========================================================================
# Legacy API stubs (no-ops for smooth migration)
# =========================================================================

def enable_mousewheel_scrolling(canvas=None) -> None:
    """No-op — DPG child windows handle scrolling automatically."""
    pass


def style_scrolled_text(widget=None, log_style: bool = False) -> None:
    """No-op — DPG does not use ScrolledText widgets."""
    pass
