"""
Modern Theme Configuration for Behaviour Rig System GUI.

Provides a consistent, professional appearance across all windows with:
- Dark/light color palette with accent colors
- Custom ttk styles for all widget types
- Consistent fonts and spacing
- Status color coding (success, warning, error)

Available palettes:
- LIGHT_PALETTE: Modern blue theme - professional and clean
- DARK_PALETTE: Dark theme - easy on the eyes for long sessions
- DARK_GREEN_PALETTE: Hacker green - classic Matrix terminal style
- DARK_RED_PALETTE: Hacker red - cyberpunk danger style

Usage:
    from gui.theme import apply_theme, Theme
    
    root = tk.Tk()
    Theme.palette = DARK_GREEN_PALETTE  # Switch palette before applying
    apply_theme(root)  # Applies modern styling to all widgets
"""

from __future__ import annotations

import ctypes
import sys
import tkinter as tk
from pathlib import Path
from tkinter import ttk
from typing import NamedTuple

# Icon path (relative to this file)
_ICON_PATH = Path(__file__).parent / "favicon.ico"


class ColorPalette(NamedTuple):
    """Color palette for the theme."""
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


# Modern blue theme - professional and clean
LIGHT_PALETTE = ColorPalette(
    # Main backgrounds - light slate grey tones
    bg_primary="#f5f7fa",          # Light blue-grey
    bg_secondary="#ffffff",        # White for cards
    bg_tertiary="#eef2f7",         # Light input fields
    bg_header="#2c3e50",           # Dark blue-grey header
    
    # Text colors
    text_primary="#1a2530",        # Dark blue-grey
    text_secondary="#5a6b7d",      # Muted blue-grey
    text_disabled="#9ca8b5",       # Light grey
    text_inverse="#ffffff",        # White
    
    # Accent colors - professional blue
    accent_primary="#3498db",      # Clear blue
    accent_secondary="#2980b9",    # Darker blue
    accent_hover="#5dade2",        # Lighter blue
    accent_active="#21618c",       # Dark blue
    
    # Status colors
    success="#27ae60",             # Green
    success_light="#d4efdf",       # Light green
    warning="#f39c12",             # Orange
    warning_light="#fdebd0",       # Light orange
    error="#e74c3c",               # Red
    error_light="#fadbd8",         # Light red
    info="#3498db",                # Blue
    info_light="#d6eaf8",          # Light blue
    
    # Border colors
    border_light="#e8ecf1",        # Very light
    border_medium="#ced4da",       # Medium
    border_dark="#8fa0b0",         # Darker
    
    # Special colors
    rig_selected="#58d68d",        # Light green for selected
    rig_open="#95a5a6",            # Grey for open/disabled
)


# Dark theme - easy on the eyes for long sessions
DARK_PALETTE = ColorPalette(
    # Main backgrounds - dark blue-grey tones
    bg_primary="#1e1e2e",          # Dark base
    bg_secondary="#2a2a3d",        # Slightly lighter for cards
    bg_tertiary="#33334d",         # Input fields
    bg_header="#16162a",           # Deepest dark for headers

    # Text colors
    text_primary="#e0e0ef",        # Off-white
    text_secondary="#8888a8",      # Muted lavender-grey
    text_disabled="#555570",       # Dim grey
    text_inverse="#1e1e2e",        # Dark (for use on bright buttons)

    # Accent colors - softer blue
    accent_primary="#5b9bd5",      # Muted blue
    accent_secondary="#4a89c8",    # Slightly darker blue
    accent_hover="#74b3e8",        # Lighter blue hover
    accent_active="#3570a5",       # Pressed blue

    # Status colors
    success="#4caf79",             # Soft green
    success_light="#1e3d2b",       # Dark green tint
    warning="#e5a832",             # Amber
    warning_light="#3d3520",       # Dark amber tint
    error="#e05555",               # Soft red
    error_light="#3d1e1e",         # Dark red tint
    info="#5b9bd5",                # Matches accent
    info_light="#1e2d3d",          # Dark blue tint

    # Border colors
    border_light="#3a3a55",        # Subtle
    border_medium="#50506b",       # Medium
    border_dark="#6a6a85",         # Visible

    # Special colors
    rig_selected="#3d8c5c",        # Muted green for selected
    rig_open="#4a4a60",            # Dark grey for open/disabled
)


# Green theme
DARK_GREEN_PALETTE = ColorPalette(
    # Main backgrounds - pure black/dark charcoal
    bg_primary="#0a0a0a",          # Near black base
    bg_secondary="#0f0f0f",        # Slightly lighter for cards
    bg_tertiary="#161616",         # Input fields
    bg_header="#050505",           # Deepest black for headers

    # Text colors - neon green glow
    text_primary="#00ff41",        # Bright matrix green
    text_secondary="#00cc33",      # Dimmer green
    text_disabled="#004d1a",       # Dark muted green
    text_inverse="#0a0a0a",        # Black for text on bright buttons

    # Accent colors - phosphor green variants
    accent_primary="#00ff41",      # Bright neon green
    accent_secondary="#00cc33",    # Medium green
    accent_hover="#33ff66",        # Lighter hover green
    accent_active="#009926",       # Pressed darker green

    # Status colors
    success="#00ff41",             # Bright green
    success_light="#0a1f0f",       # Dark green tint
    warning="#ccff00",             # Yellow-green warning
    warning_light="#1a1f0a",       # Dark warning tint
    error="#ff3333",               # Red stands out
    error_light="#1f0a0a",         # Dark red tint
    info="#00ffcc",                # Cyan-green info
    info_light="#0a1f1a",          # Dark cyan tint

    # Border colors - subtle green glow
    border_light="#003314",        # Subtle dark green
    border_medium="#004d1a",       # Medium green
    border_dark="#006622",         # Brighter green

    # Special colors
    rig_selected="#00cc33",        # Selected green
    rig_open="#1a1a1a",            # Dark grey for open/disabled
)


# Red theme
DARK_RED_PALETTE = ColorPalette(
    # Main backgrounds - pure black/dark charcoal
    bg_primary="#0a0a0a",          # Near black base
    bg_secondary="#0f0f0f",        # Slightly lighter for cards
    bg_tertiary="#161616",         # Input fields
    bg_header="#050505",           # Deepest black for headers

    # Text colors - neon red glow
    text_primary="#ff3333",        # Bright neon red
    text_secondary="#cc2929",      # Dimmer red
    text_disabled="#4d1414",       # Dark muted red
    text_inverse="#0a0a0a",        # Black for text on bright buttons

    # Accent colors - crimson/neon red variants
    accent_primary="#ff3333",      # Bright neon red
    accent_secondary="#cc2929",    # Medium red
    accent_hover="#ff6666",        # Lighter hover red
    accent_active="#991f1f",       # Pressed darker red

    # Status colors
    success="#33ff77",             # Green still means success
    success_light="#0a1f10",       # Dark green tint
    warning="#ffcc00",             # Amber warning
    warning_light="#1f1a0a",       # Dark amber tint
    error="#ff3333",               # Red (matches theme)
    error_light="#1f0a0a",         # Dark red tint
    info="#ff6699",                # Pink info
    info_light="#1f0a10",          # Dark pink tint

    # Border colors - subtle red glow
    border_light="#331414",        # Subtle dark red
    border_medium="#4d1a1a",       # Medium red
    border_dark="#662222",         # Brighter red

    # Special colors
    rig_selected="#cc2929",        # Selected red
    rig_open="#1a1a1a",            # Dark grey for open/disabled
)


class Theme:
    """Theme configuration and utilities."""
    
    palette = DARK_GREEN_PALETTE
    
    # Font configurations
    # FONT_FAMILY = "Segoe UI"  # Modern Windows font
    # FONT_FAMILY_MONO = "Consolas"

    FONT_FAMILY = "Small Fonts"
    FONT_FAMILY_MONO = "Terminal"
    
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
    
    @classmethod
    def font(cls, size: int = None, weight: str = "normal") -> tuple:
        """Get a font tuple for standard fonts."""
        size = size or cls.FONT_SIZE_BODY
        return (cls.FONT_FAMILY, size, weight)
    
    @classmethod
    def font_mono(cls, size: int = None, weight: str = "normal") -> tuple:
        """Get a font tuple for monospace fonts."""
        size = size or cls.FONT_SIZE_BODY
        if weight == "normal":
            return (cls.FONT_FAMILY_MONO, size)
        return (cls.FONT_FAMILY_MONO, size, weight)
    
    @classmethod
    def font_title(cls) -> tuple:
        return (cls.FONT_FAMILY, cls.FONT_SIZE_TITLE, "bold")
    
    @classmethod
    def font_heading(cls) -> tuple:
        return (cls.FONT_FAMILY, cls.FONT_SIZE_HEADING, "bold")
    
    @classmethod
    def font_subheading(cls) -> tuple:
        return (cls.FONT_FAMILY, cls.FONT_SIZE_SUBHEADING, "bold")
    
    @classmethod
    def font_body(cls) -> tuple:
        return (cls.FONT_FAMILY, cls.FONT_SIZE_BODY)
    
    @classmethod
    def font_small(cls) -> tuple:
        return (cls.FONT_FAMILY, cls.FONT_SIZE_SMALL)
    
    @classmethod
    def font_tiny(cls) -> tuple:
        return (cls.FONT_FAMILY, cls.FONT_SIZE_TINY)


def apply_dark_title_bar(window: tk.Tk | tk.Toplevel) -> bool:
    """
    Apply dark mode to the Windows title bar using the DWM API.
    
    This uses the official DWMWA_USE_IMMERSIVE_DARK_MODE attribute
    available in Windows 10 build 18985+ and Windows 11.
    
    Args:
        window: The tkinter window to apply dark title bar to.
        
    Returns:
        True if dark title bar was applied, False if not supported.
    """
    if sys.platform != "win32":
        return False
    
    try:
        # Ensure window is created so we can get its handle
        window.update_idletasks()
        hwnd = ctypes.windll.user32.GetParent(window.winfo_id())
        
        # DWMWA_USE_IMMERSIVE_DARK_MODE = 20
        DWMWA_USE_IMMERSIVE_DARK_MODE = 20
        value = ctypes.c_int(1)  # 1 = enable dark mode
        
        result = ctypes.windll.dwmapi.DwmSetWindowAttribute(
            hwnd,
            DWMWA_USE_IMMERSIVE_DARK_MODE,
            ctypes.byref(value),
            ctypes.sizeof(value)
        )
        return result == 0  # S_OK = 0
    except Exception:
        return False


def apply_theme(root: tk.Tk | tk.Toplevel) -> None:
    """
    Apply the modern theme to a tkinter root window.
    
    This configures ttk styles and sets default options for standard
    tk widgets to provide a consistent modern appearance.
    
    Args:
        root: The root or toplevel window to theme.
    """
    palette = Theme.palette
    style = ttk.Style(root)
    
    # Use 'clam' as base theme - it's the most customizable
    style.theme_use("clam")
    
    # Configure root window
    root.configure(bg=palette.bg_primary)
    
    # Apply dark title bar on Windows
    apply_dark_title_bar(root)
    
    # Apply custom icon
    if _ICON_PATH.exists():
        try:
            root.iconbitmap(_ICON_PATH)
        except tk.TclError:
            pass  # Silently ignore if icon can't be loaded
    
    # =========================================================================
    # Frame Styles
    # =========================================================================
    
    style.configure(
        "TFrame",
        background=palette.bg_primary
    )
    
    style.configure(
        "Card.TFrame",
        background=palette.bg_secondary,
        relief="flat",
    )
    
    style.configure(
        "Header.TFrame",
        background=palette.bg_header
    )
    
    # =========================================================================
    # Label Styles
    # =========================================================================
    
    style.configure(
        "TLabel",
        background=palette.bg_primary,
        foreground=palette.text_primary,
        font=Theme.font_body()
    )
    
    style.configure(
        "Title.TLabel",
        background=palette.bg_primary,
        foreground=palette.text_primary,
        font=Theme.font_title()
    )
    
    style.configure(
        "Heading.TLabel",
        background=palette.bg_primary,
        foreground=palette.text_primary,
        font=Theme.font_heading()
    )
    
    style.configure(
        "Subheading.TLabel",
        background=palette.bg_primary,
        foreground=palette.text_primary,
        font=Theme.font_subheading()
    )
    
    style.configure(
        "Muted.TLabel",
        background=palette.bg_primary,
        foreground=palette.text_secondary,
        font=Theme.font_small()
    )
    
    style.configure(
        "Tiny.TLabel",
        background=palette.bg_primary,
        foreground=palette.text_secondary,
        font=Theme.font_tiny()
    )
    
    style.configure(
        "Card.TLabel",
        background=palette.bg_secondary,
        foreground=palette.text_primary,
        font=Theme.font_body()
    )
    
    # Status label styles
    style.configure(
        "Success.TLabel",
        foreground=palette.success,
        font=Theme.font(weight="bold")
    )
    
    style.configure(
        "Warning.TLabel",
        foreground=palette.warning,
        font=Theme.font(weight="bold")
    )
    
    style.configure(
        "Error.TLabel",
        foreground=palette.error,
        font=Theme.font(weight="bold")
    )
    
    style.configure(
        "Info.TLabel",
        foreground=palette.info,
        font=Theme.font(weight="bold")
    )
    
    # =========================================================================
    # Button Styles
    # =========================================================================
    
    style.configure(
        "TButton",
        background=palette.accent_primary,
        foreground=palette.text_inverse,
        bordercolor=palette.accent_secondary,
        lightcolor=palette.accent_hover,
        darkcolor=palette.accent_active,
        focuscolor=palette.accent_primary,
        font=Theme.font_body(),
        padding=(12, 5),
    )
    
    style.map(
        "TButton",
        background=[
            ("active", palette.accent_hover),
            ("pressed", palette.accent_active),
            ("disabled", palette.text_disabled)
        ],
        foreground=[
            ("disabled", palette.bg_secondary)
        ]
    )
    
    # Primary action button (more prominent)
    style.configure(
        "Primary.TButton",
        background=palette.accent_primary,
        foreground=palette.text_inverse,
        font=Theme.font(size=10, weight="bold"),
        padding=(14, 6),
    )
    
    style.map(
        "Primary.TButton",
        background=[
            ("active", palette.accent_hover),
            ("pressed", palette.accent_active),
            ("disabled", palette.text_disabled)
        ]
    )
    
    # Secondary/outline button
    style.configure(
        "Secondary.TButton",
        background=palette.bg_secondary,
        foreground=palette.accent_primary,
        bordercolor=palette.accent_primary,
        font=Theme.font_body(),
        padding=(12, 5),
    )
    
    style.map(
        "Secondary.TButton",
        background=[
            ("active", palette.bg_tertiary),
            ("pressed", palette.border_light),
        ],
        foreground=[
            ("disabled", palette.text_disabled)
        ]
    )
    
    # Danger button (for stop/cancel actions)
    style.configure(
        "Danger.TButton",
        background=palette.error,
        foreground=palette.text_inverse,
        font=Theme.font_body(),
        padding=(12, 5),
    )
    
    style.map(
        "Danger.TButton",
        background=[
            ("active", "#c0392b"),
            ("pressed", "#922b21"),
            ("disabled", palette.text_disabled)
        ]
    )
    
    # Success button
    style.configure(
        "Success.TButton",
        background=palette.success,
        foreground=palette.text_inverse,
        font=Theme.font_body(),
        padding=(12, 5),
    )
    
    style.map(
        "Success.TButton",
        background=[
            ("active", "#2ecc71"),
            ("pressed", "#1e8449"),
            ("disabled", palette.text_disabled)
        ]
    )
    
    # =========================================================================
    # Entry and Spinbox Styles
    # =========================================================================
    
    style.configure(
        "TEntry",
        fieldbackground=palette.bg_secondary,
        foreground=palette.text_primary,
        bordercolor=palette.border_medium,
        lightcolor=palette.bg_secondary,
        darkcolor=palette.border_medium,
        insertcolor=palette.text_primary,
        padding=3,
    )
    
    style.map(
        "TEntry",
        fieldbackground=[
            ("focus", palette.bg_secondary),
            ("disabled", palette.bg_tertiary),
        ],
        bordercolor=[
            ("focus", palette.accent_primary),
        ]
    )
    
    style.configure(
        "TSpinbox",
        fieldbackground=palette.bg_secondary,
        foreground=palette.text_primary,
        bordercolor=palette.border_medium,
        arrowcolor=palette.text_secondary,
        padding=3,
    )
    
    style.map(
        "TSpinbox",
        fieldbackground=[
            ("disabled", palette.bg_tertiary),
        ],
        bordercolor=[
            ("focus", palette.accent_primary),
        ]
    )
    
    # =========================================================================
    # Combobox Style
    # =========================================================================
    
    style.configure(
        "TCombobox",
        fieldbackground=palette.bg_secondary,
        background=palette.bg_secondary,
        foreground=palette.text_primary,
        bordercolor=palette.border_medium,
        arrowcolor=palette.text_secondary,
        padding=3,
    )
    
    style.map(
        "TCombobox",
        fieldbackground=[
            ("readonly", palette.bg_secondary),
            ("disabled", palette.bg_tertiary),
        ],
        bordercolor=[
            ("focus", palette.accent_primary),
        ],
        arrowcolor=[
            ("disabled", palette.text_disabled),
        ]
    )
    
    # Combobox dropdown listbox styling (requires option_add)
    root.option_add("*TCombobox*Listbox*Background", palette.bg_secondary)
    root.option_add("*TCombobox*Listbox*Foreground", palette.text_primary)
    root.option_add("*TCombobox*Listbox*selectBackground", palette.accent_primary)
    root.option_add("*TCombobox*Listbox*selectForeground", palette.text_inverse)
    
    # =========================================================================
    # Checkbutton and Radiobutton Styles
    # =========================================================================
    
    style.configure(
        "TCheckbutton",
        background=palette.bg_primary,
        foreground=palette.text_primary,
        font=Theme.font_body(),
    )
    
    style.map(
        "TCheckbutton",
        background=[
            ("active", palette.bg_primary),
        ],
        indicatorcolor=[
            ("selected", palette.accent_primary),
            ("!selected", palette.bg_secondary),
        ]
    )
    
    style.configure(
        "Card.TCheckbutton",
        background=palette.bg_secondary,
    )
    
    style.configure(
        "TRadiobutton",
        background=palette.bg_primary,
        foreground=palette.text_primary,
        font=Theme.font_body(),
    )
    
    style.map(
        "TRadiobutton",
        background=[
            ("active", palette.bg_primary),
        ],
        indicatorcolor=[
            ("selected", palette.accent_primary),
            ("!selected", palette.bg_secondary),
        ]
    )
    
    style.configure(
        "Card.TRadiobutton",
        background=palette.bg_secondary,
    )
    
    # =========================================================================
    # LabelFrame Style
    # =========================================================================
    
    style.configure(
        "TLabelframe",
        background=palette.bg_secondary,
        bordercolor=palette.border_light,
        lightcolor=palette.bg_secondary,
        darkcolor=palette.border_light,
        relief="solid",
    )
    
    style.configure(
        "TLabelframe.Label",
        background=palette.bg_secondary,
        foreground=palette.accent_secondary,
        font=Theme.font(size=10, weight="bold"),
    )
    
    # =========================================================================
    # Notebook (Tabs) Style
    # =========================================================================
    
    style.configure(
        "TNotebook",
        background=palette.bg_primary,
        bordercolor=palette.border_light,
        tabmargins=(5, 5, 0, 0),
    )
    
    style.configure(
        "TNotebook.Tab",
        background=palette.bg_tertiary,
        foreground=palette.text_secondary,
        bordercolor=palette.border_light,
        lightcolor=palette.bg_tertiary,
        padding=(10, 4),
        font=Theme.font_body(),
    )
    
    style.map(
        "TNotebook.Tab",
        background=[
            ("selected", palette.bg_secondary),
            ("active", palette.border_light),
        ],
        foreground=[
            ("selected", palette.accent_primary),
        ],
        expand=[
            ("selected", (0, 0, 2, 0)),
        ]
    )
    
    # =========================================================================
    # Progressbar Style
    # =========================================================================
    
    style.configure(
        "TProgressbar",
        background=palette.accent_primary,
        troughcolor=palette.bg_tertiary,
        bordercolor=palette.border_light,
        lightcolor=palette.accent_primary,
        darkcolor=palette.accent_secondary,
        thickness=20,
    )
    
    style.configure(
        "Success.TProgressbar",
        background=palette.success,
    )
    
    # =========================================================================
    # Separator Style
    # =========================================================================
    
    style.configure(
        "TSeparator",
        background=palette.border_light,
    )
    
    # =========================================================================
    # Scrollbar Style
    # =========================================================================
    
    style.configure(
        "TScrollbar",
        background=palette.bg_tertiary,
        bordercolor=palette.border_light,
        troughcolor=palette.bg_primary,
        arrowcolor=palette.text_secondary,
    )
    
    style.map(
        "TScrollbar",
        background=[
            ("active", palette.border_medium),
            ("pressed", palette.accent_primary),
        ]
    )
    
    # =========================================================================
    # Canvas (used for scrollable frames)
    # =========================================================================
    
    # Note: Canvas uses tk options, not ttk style
    root.option_add("*Canvas*Background", palette.bg_secondary)
    root.option_add("*Canvas*HighlightThickness", 0)


def enable_mousewheel_scrolling(canvas: tk.Canvas) -> None:
    """
    Bind mousewheel scrolling to a scrollable canvas.

    Activates when the mouse enters the canvas area and deactivates
    when it leaves, so only the hovered canvas scrolls.
    """
    def _on_mousewheel(event):
        canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    canvas.bind("<Enter>", lambda e: canvas.bind_all("<MouseWheel>", _on_mousewheel))
    canvas.bind("<Leave>", lambda e: canvas.unbind_all("<MouseWheel>"))


def style_scrolled_text(widget, log_style: bool = False) -> None:
    """
    Apply theme styling to a ScrolledText widget.
    
    Args:
        widget: The ScrolledText widget to style.
        log_style: If True, use dark log styling. If False, use light style.
    """
    palette = Theme.palette
    
    if log_style:
        # Dark terminal-like appearance for logs
        widget.configure(
            background="#1a1d21",
            foreground="#e8eaed",
            insertbackground="#e8eaed",
            selectbackground=palette.accent_primary,
            selectforeground=palette.text_inverse,
            font=Theme.font_mono(size=9),
            relief="flat",
            borderwidth=0,
            padx=10,
            pady=10,
        )
    else:
        # Light appearance for editable text
        widget.configure(
            background=palette.bg_secondary,
            foreground=palette.text_primary,
            insertbackground=palette.text_primary,
            selectbackground=palette.accent_primary,
            selectforeground=palette.text_inverse,
            font=Theme.font_mono(size=9),
            relief="flat",
            borderwidth=1,
            padx=8,
            pady=8,
        )


def create_card_frame(parent, **kwargs) -> ttk.Frame:
    """
    Create a card-style frame with subtle elevation effect.
    
    Args:
        parent: Parent widget
        **kwargs: Additional frame options
    
    Returns:
        A styled ttk.Frame widget
    """
    frame = ttk.Frame(parent, style="Card.TFrame", **kwargs)
    return frame


def create_header_label(parent, text: str, **kwargs) -> ttk.Label:
    """Create a styled header label."""
    return ttk.Label(parent, text=text, style="Heading.TLabel", **kwargs)


def create_title_label(parent, text: str, **kwargs) -> ttk.Label:
    """Create a styled title label."""
    return ttk.Label(parent, text=text, style="Title.TLabel", **kwargs)


def create_muted_label(parent, text: str, **kwargs) -> ttk.Label:
    """Create a styled muted/secondary label."""
    return ttk.Label(parent, text=text, style="Muted.TLabel", **kwargs)


def create_primary_button(parent, text: str, **kwargs) -> ttk.Button:
    """Create a primary action button."""
    return ttk.Button(parent, text=text, style="Primary.TButton", **kwargs)


def create_danger_button(parent, text: str, **kwargs) -> ttk.Button:
    """Create a danger/stop action button."""
    return ttk.Button(parent, text=text, style="Danger.TButton", **kwargs)


def create_success_button(parent, text: str, **kwargs) -> ttk.Button:
    """Create a success action button."""
    return ttk.Button(parent, text=text, style="Success.TButton", **kwargs)


# =========================================================================
# Rig Button Styling (uses tk.Button for full color control)
# =========================================================================

def style_rig_button(
    button: tk.Button,
    state: str = "normal",
    is_selected: bool = False,
    is_open: bool = False
) -> None:
    """
    Apply consistent styling to a rig selection button.
    
    Args:
        button: The tk.Button to style
        state: 'normal', 'selected', 'open', or 'disabled'
        is_selected: Whether the rig is selected for launch
        is_open: Whether the rig window is open
    """
    palette = Theme.palette
    
    base_config = {
        "font": Theme.font(size=13, weight="bold"),
        "relief": "flat",
        "borderwidth": 0,
        "cursor": "hand2",
        "padx": 16,
        "pady": 10,
    }
    
    if is_open:
        # Rig is open - greyed out
        open_config = {**base_config, "cursor": "arrow"}  # Override cursor
        button.configure(
            **open_config,
            state="disabled",
            bg=palette.rig_open,
            fg=palette.text_inverse,
            activebackground=palette.rig_open,
        )
    elif is_selected:
        # Rig is selected - highlighted
        button.configure(
            **base_config,
            state="normal",
            bg=palette.rig_selected,
            fg=palette.text_primary,
            activebackground="#7dcea0",
        )
    else:
        # Normal unselected state
        button.configure(
            **base_config,
            state="normal",
            bg=palette.bg_secondary,
            fg=palette.text_primary,
            activebackground=palette.bg_tertiary,
        )


def create_rig_button(parent, text: str, command, **kwargs) -> tk.Button:
    """
    Create a styled rig selection button.
    
    Args:
        parent: Parent widget
        text: Button text
        command: Button command
        **kwargs: Additional button options
    
    Returns:
        A styled tk.Button widget
    """
    palette = Theme.palette
    
    btn = tk.Button(
        parent,
        text=text,
        command=command,
        font=Theme.font(size=13, weight="bold"),
        relief="flat",
        borderwidth=0,
        cursor="hand2",
        bg=palette.bg_secondary,
        fg=palette.text_primary,
        activebackground=palette.bg_tertiary,
        padx=16,
        pady=10,
        **kwargs
    )
    
    return btn


# =========================================================================
# Color utility functions
# =========================================================================

def get_status_color(status: str) -> str:
    """Get the appropriate color for a status string."""
    palette = Theme.palette
    
    status_lower = status.lower()
    
    if status_lower in ("running", "started", "active"):
        return palette.success
    elif status_lower in ("completed", "success", "done"):
        return "#1e8449"  # Darker green
    elif status_lower in ("stopped", "paused", "warning"):
        return palette.warning
    elif status_lower in ("error", "failed"):
        return palette.error
    elif status_lower in ("idle", "waiting", "ready"):
        return palette.info
    else:
        return palette.text_secondary


def get_accuracy_color(accuracy: float) -> str:
    """Get a color based on accuracy percentage (green=good, red=poor)."""
    palette = Theme.palette
    
    if accuracy >= 70:
        return palette.success
    elif accuracy >= 50:
        return palette.warning
    else:
        return palette.error
