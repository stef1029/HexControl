"""
Setup Mode - Configure and start a new session.

Shows:
    - Save location selection
    - Mouse ID selection  
    - Protocol selection and parameter configuration
    - Start button
"""

import logging
import tkinter as tk
from pathlib import Path
from tkinter import ttk
from typing import Callable

logger = logging.getLogger(__name__)

from core.protocol_base import BaseProtocol
from protocols import get_available_protocols
from gui.parameter_widget import ParameterFormBuilder
from gui.theme import Theme, enable_mousewheel_scrolling
from simulation.mouse_parameters import MOUSE_PARAMETERS


class ProtocolTab(ttk.Frame):
    """Tab content for a single protocol with description and parameters."""
    
    def __init__(self, parent: tk.Widget, protocol_class: type[BaseProtocol]):
        super().__init__(parent)
        self.protocol_class = protocol_class
        self.form_builder: ParameterFormBuilder | None = None
        self._create_widgets()
    
    def _create_widgets(self) -> None:
        """Create the tab widgets."""
        palette = Theme.palette
        
        # Protocol description
        desc_frame = ttk.Frame(self)
        desc_frame.pack(fill="x", padx=10, pady=8)
        
        description = self.protocol_class.get_description()
        desc_label = ttk.Label(
            desc_frame, text=description, 
            wraplength=520, justify="left",
            foreground=palette.text_secondary,
            font=Theme.font_small()
        )
        desc_label.pack(anchor="w")
        
        ttk.Separator(self, orient="horizontal").pack(fill="x", padx=10, pady=3)
        
        # Parameter form in scrollable frame
        canvas = tk.Canvas(
            self, borderwidth=0, highlightthickness=0,
            background=palette.bg_secondary
        )
        scrollbar = ttk.Scrollbar(self, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas, style="Card.TFrame")
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all")),
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        parameters = self.protocol_class.get_parameters()
        self.form_builder = ParameterFormBuilder(scrollable_frame, parameters)
        self.form_builder.build()
        self.form_builder.pack(fill="both", expand=True)
        
        canvas.pack(side="left", fill="both", expand=True, padx=10)
        scrollbar.pack(side="right", fill="y")
        enable_mousewheel_scrolling(canvas)

        # Reset button
        button_frame = ttk.Frame(self)
        button_frame.pack(fill="x", padx=10, pady=8)
        
        reset_button = ttk.Button(
            button_frame, text="Reset to Defaults",
            command=self._reset_to_defaults,
            style="Secondary.TButton"
        )
        reset_button.pack(side="right")
    
    def _reset_to_defaults(self) -> None:
        """Reset parameters to defaults."""
        if self.form_builder:
            self.form_builder.reset_to_defaults()
    
    def get_parameters(self) -> dict:
        """Get current parameter values."""
        if self.form_builder is None:
            return {}
        return self.form_builder.get_converted_values()
    
    def validate(self) -> tuple[bool, dict[str, str]]:
        """Validate parameter values."""
        if self.form_builder is None:
            return True, {}
        return self.form_builder.validate()


class SetupMode(ttk.Frame):
    """
    Setup mode - configure session parameters and start.
    """
    
    def __init__(
        self,
        parent: tk.Widget,
        rig_config,
        on_start: Callable[[dict], None],
        claim_mouse_fn=None,
        get_claimed_mice_fn=None,
        cohort_folders: tuple = (),
        mice: tuple = (),
    ):
        """
        Args:
            parent: Parent widget
            rig_config: RigConfig instance
            on_start: Callback when start is clicked, receives session config dict
            claim_mouse_fn: Optional callback to claim a mouse for this rig
            get_claimed_mice_fn: Optional callback returning {mouse_id: rig_name}
            cohort_folders: Tuple of CohortFolder from the config file
            mice: Tuple of MouseEntry from the config file
        """
        super().__init__(parent)
        self._rig_config = rig_config
        self._on_start = on_start
        self._claim_mouse_fn = claim_mouse_fn
        self._get_claimed_mice_fn = get_claimed_mice_fn
        self._simulate = rig_config.simulate if rig_config else False
        self._cohort_folders = cohort_folders
        self._mice_typed = mice
        self._cohort_folders = []
        self._mice = []
        self._mouse_form: ParameterFormBuilder | None = None
        self._mouse_buttons: dict[str, tk.Button] = {}
        self._cohort_buttons: dict[str, tk.Button] = {}
        self._mouse_default_cohorts: dict[str, str] = {}

        self._load_session_options()
        self._create_widgets()

        # Refresh greyed-out mice when the window gets focus
        self.bind("<FocusIn>", lambda e: self._refresh_mouse_availability())
    
    def _load_session_options(self) -> None:
        """Load cohort folder and mouse options from config data."""
        # Convert typed tuples to dicts for the existing widget code
        if self._cohort_folders:
            self._cohort_folders = [
                {"name": c.name, "directory": c.directory, "description": c.description}
                for c in self._cohort_folders
            ]
        else:
            self._cohort_folders = [{"name": "default", "directory": "D:\\behaviour_data\\default"}]

        if self._mice_typed:
            self._mice = [
                {"id": m.id, "description": m.description, "default_cohort": m.default_cohort}
                for m in self._mice_typed
            ]
        else:
            self._mice = [{"id": "test", "description": "Test mouse"}]

        # Build mouse → default cohort lookup
        self._mouse_default_cohorts = {
            m["id"]: m["default_cohort"]
            for m in self._mice
            if m.get("default_cohort")
        }
    
    def _create_widgets(self) -> None:
        """Create the setup UI widgets."""
        palette = Theme.palette

        # Start button (packed first so it's always visible at the bottom)
        button_frame = ttk.Frame(self)
        button_frame.pack(side="bottom", fill="x", padx=10, pady=8)

        self.start_button = ttk.Button(
            button_frame, text="Start Session",
            command=self._on_start_clicked,
            style="Success.TButton"
        )
        self.start_button.pack(side="right", padx=3)

        # Resizable paned area for session info and protocol tabs
        self._paned = ttk.PanedWindow(self, orient="vertical")
        self._paned.pack(fill="both", expand=True, padx=10, pady=6)

        # --- Pane 1: Session Info ---
        session_frame = ttk.LabelFrame(self._paned, text="Session Info", padding=(10, 6))
        
        # Save Location
        cohort_frame = ttk.LabelFrame(session_frame, text="Save Location", padding=(8, 4))
        cohort_frame.pack(fill="x", padx=3, pady=(0, 5))

        first_cohort = self._cohort_folders[0].get("name", "") if self._cohort_folders else ""
        self.cohort_var = tk.StringVar(value=first_cohort)

        cohort_inner = ttk.Frame(cohort_frame)
        cohort_inner.pack(fill="x")

        for cohort in self._cohort_folders:
            name = cohort.get("name", "Unknown")
            directory = cohort.get("directory", "")

            label = f"{name}  —  {directory}" if directory else name
            btn = tk.Button(
                cohort_inner, text=label, anchor="w",
                relief="flat", padx=8, pady=2,
                font=("Segoe UI", 9),
                cursor="hand2",
                command=lambda n=name: self._select_cohort(n),
            )
            btn.pack(fill="x", pady=1)
            self._cohort_buttons[name] = btn

        self._style_cohort_buttons()
        
        # Mouse ID
        mouse_frame = ttk.LabelFrame(session_frame, text="Mouse ID", padding=(8, 4))
        mouse_frame.pack(fill="x", padx=3, pady=(0, 5))

        first_mouse = self._mice[0].get("id", "test") if self._mice else "test"
        self.mouse_id_var = tk.StringVar(value=first_mouse)

        mouse_inner = ttk.Frame(mouse_frame)
        mouse_inner.pack(fill="x")
        mouse_inner.columnconfigure(0, weight=1)
        mouse_inner.columnconfigure(1, weight=1)
        mouse_inner.columnconfigure(2, weight=1)

        for i, mouse in enumerate(self._mice):
            mouse_id = mouse.get("id", "Unknown")
            desc = mouse.get("description", "")

            col = i % 3
            row = i // 3

            label = f"{mouse_id}\n({desc})" if desc else mouse_id
            btn = tk.Button(
                mouse_inner, text=label, anchor="center",
                relief="flat", padx=6, pady=2,
                font=("Segoe UI", 9),
                cursor="hand2",
                command=lambda mid=mouse_id: self._select_mouse(mid),
            )
            btn.grid(row=row, column=col, sticky="ew", padx=2, pady=2)
            self._mouse_buttons[mouse_id] = btn

        self._style_mouse_buttons()
        
        # Session-level parameters (apply to all protocols)
        session_params_frame = ttk.LabelFrame(session_frame, text="Session Parameters", padding=(8, 4))
        session_params_frame.pack(fill="x", padx=3, pady=(0, 5))
        
        # Mouse weight
        weight_frame = ttk.Frame(session_params_frame)
        weight_frame.pack(fill="x", pady=2)
        ttk.Label(weight_frame, text="Mouse Weight (g):").pack(side="left")
        self.mouse_weight_var = tk.StringVar(value="18.0")
        self.mouse_weight_entry = ttk.Entry(weight_frame, textvariable=self.mouse_weight_var, width=12)
        self.mouse_weight_entry.pack(side="left", padx=6)
        
        # Number of trials
        trials_frame = ttk.Frame(session_params_frame)
        trials_frame.pack(fill="x", pady=2)
        ttk.Label(trials_frame, text="Number of Trials:").pack(side="left")
        self.num_trials_var = tk.StringVar(value="1000")
        self.num_trials_entry = ttk.Entry(trials_frame, textvariable=self.num_trials_var, width=12)
        self.num_trials_entry.pack(side="left", padx=6)

        # Max session duration
        duration_frame = ttk.Frame(session_params_frame)
        duration_frame.pack(fill="x", pady=2)
        ttk.Label(duration_frame, text="Max Duration (min, 0=no limit):").pack(side="left")
        self.max_duration_var = tk.StringVar(value="0")
        self.max_duration_entry = ttk.Entry(duration_frame, textvariable=self.max_duration_var, width=12)
        self.max_duration_entry.pack(side="left", padx=6)
        
        # Session path preview
        path_frame = ttk.Frame(session_frame)
        path_frame.pack(fill="x", padx=3, pady=(4, 0))
        
        ttk.Label(path_frame, text="Save to:", style="Subheading.TLabel").pack(side="left")
        self.save_path_var = tk.StringVar(value="")
        self.save_path_label = ttk.Label(
            path_frame, textvariable=self.save_path_var,
            foreground=palette.accent_primary,
            font=Theme.font_small()
        )
        self.save_path_label.pack(side="left", padx=6)
        self._update_save_path_preview()
        
        # Simulated mouse settings (only shown in simulate mode)
        if self._simulate:
            self._create_mouse_panel(session_frame)

        self._paned.add(session_frame, weight=1)

        # --- Pane 2: Protocol Tabs ---
        self.notebook = ttk.Notebook(self._paned)

        self.protocol_tabs: dict[str, ProtocolTab] = {}
        for protocol_class in get_available_protocols():
            tab = ProtocolTab(self.notebook, protocol_class)
            protocol_name = protocol_class.get_name()
            self.notebook.add(tab, text=protocol_name)
            self.protocol_tabs[protocol_name] = tab

        self._paned.add(self.notebook, weight=3)
    
    def _create_mouse_panel(self, parent) -> None:
        """Create the simulated mouse settings panel (simulate mode only)."""
        palette = Theme.palette

        mouse_frame = ttk.LabelFrame(
            parent, text="Simulated Mouse", padding=(10, 4)
        )
        mouse_frame.pack(fill="x", padx=3, pady=(0, 5))

        # Scrollable container with fixed max height
        canvas = tk.Canvas(
            mouse_frame, borderwidth=0, highlightthickness=0,
            background=palette.bg_secondary, height=180,
        )
        scrollbar = ttk.Scrollbar(mouse_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas, style="Card.TFrame")

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all")),
        )

        canvas_window = canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")

        # Make inner frame match canvas width
        def _on_canvas_configure(e):
            canvas.itemconfig(canvas_window, width=e.width)
        canvas.bind("<Configure>", _on_canvas_configure)

        canvas.configure(yscrollcommand=scrollbar.set)

        self._mouse_form = ParameterFormBuilder(scrollable_frame, MOUSE_PARAMETERS)
        self._mouse_form.build()
        self._mouse_form.pack(fill="both", expand=True)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        enable_mousewheel_scrolling(canvas)

    def _select_cohort(self, name: str) -> None:
        """Handle cohort toggle-button click."""
        self.cohort_var.set(name)
        self._style_cohort_buttons()
        self._update_save_path_preview()

    def _select_mouse(self, mouse_id: str) -> None:
        """Handle mouse toggle-button click."""
        self.mouse_id_var.set(mouse_id)
        # Auto-switch cohort if this mouse has a default
        default_cohort = self._mouse_default_cohorts.get(mouse_id)
        if default_cohort:
            if default_cohort in self._cohort_buttons:
                self._select_cohort(default_cohort)
            else:
                print(f"Warning: Mouse '{mouse_id}' has default_cohort '{default_cohort}' "
                      f"which is not a configured cohort folder — ignoring.")
        self._style_mouse_buttons()
        self._update_save_path_preview()

    def _style_cohort_buttons(self) -> None:
        """Restyle cohort buttons to reflect current selection."""
        palette = Theme.palette
        selected = self.cohort_var.get()
        for name, btn in self._cohort_buttons.items():
            if name == selected:
                btn.configure(
                    bg=palette.accent_primary,
                    fg=palette.text_inverse,
                    activebackground=palette.accent_hover,
                    activeforeground=palette.text_inverse,
                )
            else:
                btn.configure(
                    bg=palette.bg_tertiary,
                    fg=palette.text_primary,
                    activebackground=palette.accent_hover,
                    activeforeground=palette.text_inverse,
                )

    def _style_mouse_buttons(self) -> None:
        """Restyle mouse buttons to reflect current selection."""
        palette = Theme.palette
        selected = self.mouse_id_var.get()
        for mouse_id, btn in self._mouse_buttons.items():
            if btn.cget("state") == "disabled":
                continue
            if mouse_id == selected:
                btn.configure(
                    bg=palette.accent_primary,
                    fg=palette.text_inverse,
                    activebackground=palette.accent_hover,
                    activeforeground=palette.text_inverse,
                )
            else:
                btn.configure(
                    bg=palette.bg_tertiary,
                    fg=palette.text_primary,
                    activebackground=palette.accent_hover,
                    activeforeground=palette.text_inverse,
                )

    def _update_save_path_preview(self) -> None:
        """Update the save path preview label."""
        cohort_name = self.cohort_var.get()
        mouse_id = self.mouse_id_var.get()
        
        directory = self._get_selected_cohort_directory()
        
        if directory and mouse_id:
            # Show the multi-session folder structure: directory/<datetime>/<datetime>_mouseID
            preview = f"{directory}\\<datetime>\\<datetime>_{mouse_id}"
        else:
            preview = "<select save location>"
        
        self.save_path_var.set(preview)
    
    def _get_selected_cohort_directory(self) -> str:
        """Get the directory for the selected cohort."""
        cohort_name = self.cohort_var.get()
        for cf in self._cohort_folders:
            if cf.get("name") == cohort_name:
                return cf.get("directory", "")
        return ""
    
    def _refresh_mouse_availability(self) -> None:
        """Grey out mice that are claimed by other rigs."""
        palette = Theme.palette
        get_claimed = self._get_claimed_mice_fn
        if not get_claimed:
            return
        rig_name = self._rig_config.name if self._rig_config else ""
        claimed = get_claimed()
        for mouse_id, btn in self._mouse_buttons.items():
            if mouse_id in claimed and claimed[mouse_id] != rig_name:
                btn.configure(
                    state="disabled",
                    bg=palette.bg_secondary,
                    fg=palette.text_disabled,
                    disabledforeground=palette.text_disabled,
                )
            else:
                btn.configure(state="normal")
        self._style_mouse_buttons()

    def _on_start_clicked(self) -> None:
        """Handle start button click."""
        tab = self.get_current_tab()
        
        # Validate session-level parameters
        try:
            mouse_weight = float(self.mouse_weight_var.get())
            if mouse_weight <= 0:
                raise ValueError("Mouse weight must be positive")
        except ValueError as e:
            from tkinter import messagebox
            logger.error(f"[Setup] Invalid mouse weight: {e}")
            messagebox.showerror("Validation Error", f"Invalid mouse weight: {e}")
            return

        try:
            num_trials = int(self.num_trials_var.get())
            if num_trials <= 0:
                raise ValueError("Number of trials must be positive")
        except ValueError as e:
            from tkinter import messagebox
            logger.error(f"[Setup] Invalid number of trials: {e}")
            messagebox.showerror("Validation Error", f"Invalid number of trials: {e}")
            return

        try:
            max_duration = float(self.max_duration_var.get())
            if max_duration < 0:
                raise ValueError("Max duration cannot be negative")
        except ValueError as e:
            from tkinter import messagebox
            logger.error(f"[Setup] Invalid max duration: {e}")
            messagebox.showerror("Validation Error", f"Invalid max duration: {e}")
            return
        
        # Check mouse is not claimed by another rig
        mouse_id = self.mouse_id_var.get()
        if self._claim_mouse_fn:
            rig_name = self._rig_config.name if self._rig_config else "Unknown"
            if not self._claim_mouse_fn(mouse_id, rig_name):
                from tkinter import messagebox
                claimed = self._get_claimed_mice_fn() if self._get_claimed_mice_fn else {}
                other_rig = claimed.get(mouse_id, "another rig")
                logger.error(f"[Setup] Mouse '{mouse_id}' is already in use by {other_rig}")
                messagebox.showerror(
                    "Mouse Already Selected",
                    f"Mouse '{mouse_id}' is already in use by {other_rig}."
                )
                return

        # Validate protocol parameters
        is_valid, errors = tab.validate()
        if not is_valid:
            from tkinter import messagebox
            error_msg = "\n".join(f"- {k}: {v}" for k, v in errors.items())
            logger.error(f"[Setup] Validation errors: {error_msg}")
            messagebox.showerror("Validation Error", f"Please correct the following errors:\n{error_msg}")
            return
        
        # Get protocol parameters and inject session-level values
        protocol_params = tab.get_parameters()
        protocol_params["mouse_weight"] = mouse_weight
        protocol_params["num_trials"] = num_trials
        protocol_params["max_duration_minutes"] = max_duration
        protocol_params["mouse_id"] = self.mouse_id_var.get()
        protocol_params["save_directory"] = self._get_selected_cohort_directory()
        
        # Build mouse params if in simulate mode
        mouse_params = None
        if self._mouse_form is not None:
            mouse_params = self._mouse_form.get_values()

        # Build session config and call callback
        session_config = {
            "mouse_id": self.mouse_id_var.get(),
            "save_directory": self._get_selected_cohort_directory(),
            "protocol_name": tab.protocol_class.get_name(),
            "protocol_class": tab.protocol_class,
            "parameters": protocol_params,
            "mouse_params": mouse_params,
        }

        self._on_start(session_config)
    
    def get_current_tab(self) -> ProtocolTab:
        """Get the currently selected protocol tab."""
        selection = self.notebook.select()
        tab_text = self.notebook.tab(selection, "text")
        return self.protocol_tabs[tab_text]
