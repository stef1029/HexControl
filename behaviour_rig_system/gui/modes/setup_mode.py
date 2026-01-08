"""
Setup Mode - Configure and start a new session.

Shows:
    - Save location selection
    - Mouse ID selection  
    - Protocol selection and parameter configuration
    - Start button
"""

import tkinter as tk
from pathlib import Path
from tkinter import ttk
from typing import Callable

import yaml

from core.protocol_base import BaseProtocol
from protocols import get_available_protocols
from gui.parameter_widget import ParameterFormBuilder


class ProtocolTab(ttk.Frame):
    """Tab content for a single protocol with description and parameters."""
    
    def __init__(self, parent: tk.Widget, protocol_class: type[BaseProtocol]):
        super().__init__(parent)
        self.protocol_class = protocol_class
        self.form_builder: ParameterFormBuilder | None = None
        self._create_widgets()
    
    def _create_widgets(self) -> None:
        """Create the tab widgets."""
        # Protocol description
        desc_frame = ttk.Frame(self)
        desc_frame.pack(fill="x", padx=10, pady=10)
        
        description = self.protocol_class.get_description()
        desc_label = ttk.Label(desc_frame, text=description, wraplength=500, justify="left")
        desc_label.pack(anchor="w")
        
        ttk.Separator(self, orient="horizontal").pack(fill="x", padx=10, pady=5)
        
        # Parameter form in scrollable frame
        canvas = tk.Canvas(self, borderwidth=0, highlightthickness=0)
        scrollbar = ttk.Scrollbar(self, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
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
        
        # Reset button
        button_frame = ttk.Frame(self)
        button_frame.pack(fill="x", padx=10, pady=10)
        
        reset_button = ttk.Button(
            button_frame, text="Reset to Defaults",
            command=self._reset_to_defaults
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
    
    def __init__(self, parent: tk.Widget, rig_config: dict, on_start: Callable[[dict], None]):
        """
        Args:
            parent: Parent widget
            rig_config: Rig configuration dict
            on_start: Callback when start is clicked, receives session config dict
        """
        super().__init__(parent)
        self._rig_config = rig_config
        self._on_start = on_start
        self._cohort_folders = []
        self._mice = []
        
        self._load_session_options()
        self._create_widgets()
    
    def _load_session_options(self) -> None:
        """Load cohort folder and mouse options from config file."""
        config_path = self._rig_config.get("config_path")
        if not config_path:
            config_path = Path(__file__).parent.parent.parent / "config" / "rigs.yaml"
        
        try:
            with open(config_path) as f:
                config = yaml.safe_load(f)
        except Exception as e:
            print(f"Error loading config: {e}")
            config = {}
        
        self._cohort_folders = config.get("cohort_folders", [])
        if not self._cohort_folders:
            self._cohort_folders = [{"name": "default", "directory": "D:\\behaviour_data\\default"}]
        
        self._mice = config.get("mice", [])
        if not self._mice:
            self._mice = [{"id": "test", "description": "Test mouse"}]
    
    def _create_widgets(self) -> None:
        """Create the setup UI widgets."""
        # Session info panel
        session_frame = ttk.LabelFrame(self, text="Session Info", padding=(10, 5))
        session_frame.pack(fill="x", padx=10, pady=5)
        
        # Save Location
        cohort_frame = ttk.LabelFrame(session_frame, text="Save Location", padding=(5, 5))
        cohort_frame.pack(fill="x", padx=5, pady=(0, 5))
        
        first_cohort = self._cohort_folders[0].get("name", "") if self._cohort_folders else ""
        self.cohort_var = tk.StringVar(value=first_cohort)
        
        cohort_inner = ttk.Frame(cohort_frame)
        cohort_inner.pack(fill="x")
        
        for cohort in self._cohort_folders:
            name = cohort.get("name", "Unknown")
            directory = cohort.get("directory", "")
            
            rb_frame = ttk.Frame(cohort_inner)
            rb_frame.pack(fill="x", pady=1)
            
            rb = ttk.Radiobutton(
                rb_frame, text=name, variable=self.cohort_var,
                value=name, command=self._update_save_path_preview
            )
            rb.pack(side="left")
            
            if directory:
                path_label = ttk.Label(
                    rb_frame, text=f"  {directory}",
                    foreground="gray", font=("TkDefaultFont", 8)
                )
                path_label.pack(side="left")
        
        # Mouse ID
        mouse_frame = ttk.LabelFrame(session_frame, text="Mouse ID", padding=(5, 5))
        mouse_frame.pack(fill="x", padx=5, pady=(0, 5))
        
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
            
            rb_frame = ttk.Frame(mouse_inner)
            rb_frame.grid(row=row, column=col, sticky="w", padx=5, pady=1)
            
            rb = ttk.Radiobutton(
                rb_frame, text=mouse_id, variable=self.mouse_id_var,
                value=mouse_id, command=self._update_save_path_preview
            )
            rb.pack(side="left")
            
            if desc:
                desc_label = ttk.Label(
                    rb_frame, text=f"({desc})",
                    foreground="gray", font=("TkDefaultFont", 8)
                )
                desc_label.pack(side="left", padx=(2, 0))
        
        # Session path preview
        path_frame = ttk.Frame(session_frame)
        path_frame.pack(fill="x", padx=5, pady=(5, 0))
        
        ttk.Label(path_frame, text="Save to:", font=("TkDefaultFont", 9, "bold")).pack(side="left")
        self.save_path_var = tk.StringVar(value="")
        self.save_path_label = ttk.Label(
            path_frame, textvariable=self.save_path_var,
            foreground="blue", font=("TkDefaultFont", 9)
        )
        self.save_path_label.pack(side="left", padx=5)
        self._update_save_path_preview()
        
        # Protocol tabs
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True, padx=10, pady=5)
        
        self.protocol_tabs: dict[str, ProtocolTab] = {}
        for protocol_class in get_available_protocols():
            tab = ProtocolTab(self.notebook, protocol_class)
            protocol_name = protocol_class.get_name()
            self.notebook.add(tab, text=protocol_name)
            self.protocol_tabs[protocol_name] = tab
        
        # Start button
        button_frame = ttk.Frame(self)
        button_frame.pack(fill="x", padx=10, pady=10)
        
        self.start_button = ttk.Button(
            button_frame, text="Start Session",
            command=self._on_start_clicked
        )
        self.start_button.pack(side="right", padx=5)
    
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
    
    def _on_start_clicked(self) -> None:
        """Handle start button click."""
        tab = self.get_current_tab()
        
        # Validate parameters
        is_valid, errors = tab.validate()
        if not is_valid:
            from tkinter import messagebox
            error_msg = "\n".join(f"- {k}: {v}" for k, v in errors.items())
            messagebox.showerror("Validation Error", f"Please correct the following errors:\n{error_msg}")
            return
        
        # Build session config and call callback
        session_config = {
            "mouse_id": self.mouse_id_var.get(),
            "save_directory": self._get_selected_cohort_directory(),
            "protocol_name": tab.protocol_class.get_name(),
            "protocol_class": tab.protocol_class,
            "parameters": tab.get_parameters(),
        }
        
        self._on_start(session_config)
    
    def get_current_tab(self) -> ProtocolTab:
        """Get the currently selected protocol tab."""
        selection = self.notebook.select()
        tab_text = self.notebook.tab(selection, "text")
        return self.protocol_tabs[tab_text]
