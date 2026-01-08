"""
Post-Processing Window for Behaviour Rig System.

Provides a GUI for batch processing cohort data including:
- Recovering crashed sessions
- Processing videos (binary/BMP to AVI)
- Running behavioral analysis
- Processing electrophysiology data (optional)

Uses a mode-based UI that switches between Configuration and Progress views.
"""

import sys
import threading
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
from pathlib import Path
from typing import Optional, Callable
from enum import Enum, auto
import multiprocessing as mp
import yaml


class WindowMode(Enum):
    """The two modes of the post-processing window."""
    CONFIG = auto()
    PROGRESS = auto()


class TextRedirector:
    """Redirect stdout/stderr to a text widget with color coding."""

    def __init__(self, widget, tag="stdout"):
        self.widget = widget
        self.tag = tag
        self._setup_tags()

    def _setup_tags(self):
        """Configure text tags for color coding."""
        # Cohort header (===) - blue
        self.widget.tag_configure("header", foreground="#2196F3", font=("Courier", 9, "bold"))
        # Step headers (-----) - cyan
        self.widget.tag_configure("step", foreground="#00BCD4", font=("Courier", 9, "bold"))
        # Labels (COHORT:, DIRECTORY:, etc.) - green
        self.widget.tag_configure("label", foreground="#4CAF50")
        # Errors - red
        self.widget.tag_configure("error", foreground="#F44336")
        # Success messages - green bold
        self.widget.tag_configure("success", foreground="#4CAF50", font=("Courier", 9, "bold"))
        # Warnings - orange
        self.widget.tag_configure("warning", foreground="#FF9800")
        # Normal text
        self.widget.tag_configure("stdout", foreground="#E0E0E0")
        self.widget.tag_configure("stderr", foreground="#F44336")

    def _get_tag_for_line(self, line):
        """Determine the appropriate tag for a line of text."""
        line_stripped = line.strip()
        
        # Check for patterns
        if line_stripped.startswith("=" * 10) or line_stripped.endswith("=" * 10):
            return "header"
        if line_stripped.startswith("----- STEP"):
            return "step"
        if line_stripped.startswith(("COHORT:", "DIRECTORY:", "HAS EPHYS:")):
            return "label"
        if "Error" in line or "ERROR" in line or "error" in line:
            return "error"
        if "FATAL" in line:
            return "error"
        if "Warning" in line or "WARNING" in line:
            return "warning"
        if "ALL PROCESSING COMPLETE" in line or "COMPLETE" in line_stripped:
            return "success"
        if "cancelled" in line.lower():
            return "warning"
        
        return self.tag

    def write(self, string):
        self.widget.after(0, self._append_text, string)

    def _append_text(self, string):
        self.widget.configure(state="normal")
        
        # Process line by line for color coding
        lines = string.split('\n')
        for i, line in enumerate(lines):
            if i > 0:
                self.widget.insert("end", "\n")
            if line:
                tag = self._get_tag_for_line(line)
                self.widget.insert("end", line, tag)
        
        self.widget.see("end")
        self.widget.configure(state="disabled")

    def flush(self):
        pass


class PostProcessingWindow:
    """
    Window for post-processing cohort data.

    Allows selection of cohorts and processing steps, then executes
    them in a background thread with real-time progress display.
    """

    def __init__(self, parent: tk.Tk, config_path: Path):
        """
        Initialize the post-processing window.

        Args:
            parent: Parent Tk window (launcher)
            config_path: Path to rigs.yaml configuration file
        """
        self.parent = parent
        self.config_path = config_path

        # Create modal window
        self.window = tk.Toplevel(parent)
        self.window.title("Post-Processing")
        self.window.geometry("800x700")
        self.window.minsize(700, 600)

        # Make it modal
        self.window.transient(parent)
        self.window.grab_set()

        # Load cohort folders from config
        self.cohort_folders = self._load_cohort_folders()

        # Processing state
        self.is_processing = False
        self.cancel_requested = False
        self.processing_thread: Optional[threading.Thread] = None

        # Cohort checkboxes (select for processing)
        self.cohort_vars: dict[str, tk.BooleanVar] = {}
        # Cohort ephys checkboxes (whether cohort has ephys data)
        self.cohort_ephys_vars: dict[str, tk.BooleanVar] = {}

        # Processing option checkboxes
        self.recover_sessions_var = tk.BooleanVar(value=True)
        self.process_videos_var = tk.BooleanVar(value=True)
        self.run_analysis_var = tk.BooleanVar(value=True)
        self.refresh_analysis_var = tk.BooleanVar(value=False)

        # Ephys options (applied to cohorts marked as ephys)
        self.ephys_pin_var = tk.IntVar(value=0)
        self.ephys_force_var = tk.BooleanVar(value=False)

        self._create_widgets()
        self._show_mode(WindowMode.CONFIG)

        # Handle window close
        self.window.protocol("WM_DELETE_WINDOW", self._on_close)

    def _load_cohort_folders(self) -> list[dict]:
        """Load cohort folders from configuration file."""
        if not self.config_path.exists():
            return []

        with open(self.config_path) as f:
            config = yaml.safe_load(f)

        return config.get("cohort_folders", [])

    def _create_widgets(self) -> None:
        """Create the window widgets."""
        # Main container
        self.main_frame = ttk.Frame(self.window, padding="10")
        self.main_frame.pack(fill="both", expand=True)

        # Create the two mode frames
        self._create_config_mode()
        self._create_progress_mode()

    def _create_config_mode(self) -> None:
        """Create the configuration mode frame."""
        self.config_frame = ttk.Frame(self.main_frame)

        # Title
        title_label = ttk.Label(
            self.config_frame,
            text="Post-Processing",
            font=("Helvetica", 14, "bold")
        )
        title_label.pack(pady=(0, 10))

        # Content frame for cohorts and options
        content_frame = ttk.Frame(self.config_frame)
        content_frame.pack(fill="both", expand=True, pady=(0, 10))

        # --- Configuration Content ---
        self._create_config_content(content_frame)

        # --- Control Buttons ---
        button_frame = ttk.Frame(self.config_frame)
        button_frame.pack(fill="x", pady=(10, 0))

        self.start_button = ttk.Button(
            button_frame,
            text="Start Processing",
            command=self._on_start_click,
            width=20
        )
        self.start_button.pack(side="left", padx=5)

        close_button = ttk.Button(
            button_frame,
            text="Close",
            command=self._on_close,
            width=20
        )
        close_button.pack(side="right", padx=5)

    def _create_progress_mode(self) -> None:
        """Create the progress mode frame."""
        self.progress_frame = ttk.Frame(self.main_frame)

        # Title
        title_label = ttk.Label(
            self.progress_frame,
            text="Processing in Progress",
            font=("Helvetica", 14, "bold")
        )
        title_label.pack(pady=(0, 10))

        # Progress content
        self._create_progress_content(self.progress_frame)

        # --- Control Buttons ---
        button_frame = ttk.Frame(self.progress_frame)
        button_frame.pack(fill="x", pady=(10, 0))

        self.cancel_button = ttk.Button(
            button_frame,
            text="Cancel",
            command=self._on_cancel_click,
            width=20
        )
        self.cancel_button.pack(side="left", padx=5)

        self.back_button = ttk.Button(
            button_frame,
            text="Back to Configuration",
            command=self._on_back_click,
            state="disabled",
            width=20
        )
        self.back_button.pack(side="right", padx=5)

    def _show_mode(self, mode: WindowMode) -> None:
        """Switch to the specified mode."""
        # Hide all frames
        self.config_frame.pack_forget()
        self.progress_frame.pack_forget()

        # Show the requested frame
        if mode == WindowMode.CONFIG:
            self.config_frame.pack(fill="both", expand=True)
        elif mode == WindowMode.PROGRESS:
            self.progress_frame.pack(fill="both", expand=True)

    def _on_back_click(self) -> None:
        """Handle back button click to return to configuration."""
        self._show_mode(WindowMode.CONFIG)

    def _create_config_content(self, parent: ttk.Frame) -> None:
        """Create the configuration content."""
        # Cohort selection section
        cohort_label = ttk.Label(
            parent,
            text="Select Cohorts to Process:",
            font=("Helvetica", 10, "bold")
        )
        cohort_label.pack(anchor="w", pady=(0, 5))

        # Frame with scrollbar for cohorts
        cohort_canvas_frame = ttk.Frame(parent)
        cohort_canvas_frame.pack(fill="both", expand=True, pady=(0, 15))

        cohort_canvas = tk.Canvas(cohort_canvas_frame, height=150)
        cohort_scrollbar = ttk.Scrollbar(
            cohort_canvas_frame,
            orient="vertical",
            command=cohort_canvas.yview
        )
        cohort_inner_frame = ttk.Frame(cohort_canvas)

        cohort_inner_frame.bind(
            "<Configure>",
            lambda e: cohort_canvas.configure(scrollregion=cohort_canvas.bbox("all"))
        )

        cohort_canvas.create_window((0, 0), window=cohort_inner_frame, anchor="nw")
        cohort_canvas.configure(yscrollcommand=cohort_scrollbar.set)

        cohort_canvas.pack(side="left", fill="both", expand=True)
        cohort_scrollbar.pack(side="right", fill="y")

        # Header row
        header_frame = ttk.Frame(cohort_inner_frame)
        header_frame.pack(anchor="w", padx=10, pady=(5, 2), fill="x")
        ttk.Label(header_frame, text="Process", font=("Helvetica", 8, "bold")).pack(side="left", padx=(0, 10))
        ttk.Label(header_frame, text="Ephys", font=("Helvetica", 8, "bold")).pack(side="left", padx=(0, 10))
        ttk.Label(header_frame, text="Cohort", font=("Helvetica", 8, "bold")).pack(side="left")

        ttk.Separator(cohort_inner_frame, orient="horizontal").pack(fill="x", padx=10, pady=2)

        # Create checkbox for each cohort
        if not self.cohort_folders:
            no_cohorts_label = ttk.Label(
                cohort_inner_frame,
                text="No cohort folders configured in rigs.yaml",
                foreground="red"
            )
            no_cohorts_label.pack(anchor="w", padx=10, pady=10)
        else:
            for cohort in self.cohort_folders:
                name = cohort.get("name", "Unknown")
                directory = cohort.get("directory", "")
                description = cohort.get("description", "")

                # Row frame for this cohort
                row_frame = ttk.Frame(cohort_inner_frame)
                row_frame.pack(anchor="w", padx=10, pady=2, fill="x")

                # Process checkbox (default to checked)
                var = tk.BooleanVar(value=True)
                self.cohort_vars[name] = var
                process_cb = ttk.Checkbutton(row_frame, variable=var)
                process_cb.pack(side="left", padx=(12, 20))

                # Ephys checkbox
                ephys_var = tk.BooleanVar(value=False)
                self.cohort_ephys_vars[name] = ephys_var
                ephys_cb = ttk.Checkbutton(row_frame, variable=ephys_var)
                ephys_cb.pack(side="left", padx=(5, 15))

                # Cohort name label
                name_label = ttk.Label(row_frame, text=f"{name} ({directory})")
                name_label.pack(side="left")

                if description:
                    desc_label = ttk.Label(
                        cohort_inner_frame,
                        text=f"    {description}",
                        font=("Helvetica", 8),
                        foreground="gray"
                    )
                    desc_label.pack(anchor="w", padx=60, pady=(0, 5))

        # Processing options section
        ttk.Separator(parent, orient="horizontal").pack(fill="x", pady=10)

        options_label = ttk.Label(
            parent,
            text="Processing Steps:",
            font=("Helvetica", 10, "bold")
        )
        options_label.pack(anchor="w", pady=(0, 5))

        options_frame = ttk.Frame(parent)
        options_frame.pack(fill="x", pady=(0, 10))

        # Recover crashed sessions
        ttk.Checkbutton(
            options_frame,
            text="Recover crashed sessions",
            variable=self.recover_sessions_var
        ).pack(anchor="w", padx=10, pady=2)

        # Process videos
        ttk.Checkbutton(
            options_frame,
            text="Process videos (BMP/binary to AVI)",
            variable=self.process_videos_var
        ).pack(anchor="w", padx=10, pady=2)

        # Run analysis
        ttk.Checkbutton(
            options_frame,
            text="Run behavioral analysis",
            variable=self.run_analysis_var
        ).pack(anchor="w", padx=10, pady=2)

        # Refresh (reprocess already completed sessions)
        ttk.Checkbutton(
            options_frame,
            text="Refresh (reprocess already completed sessions)",
            variable=self.refresh_analysis_var
        ).pack(anchor="w", padx=10, pady=2)

        # Ephys options section (applies to cohorts marked as ephys above)
        ttk.Separator(parent, orient="horizontal").pack(fill="x", pady=10)

        ephys_label = ttk.Label(
            parent,
            text="Ephys Processing Options:",
            font=("Helvetica", 10, "bold")
        )
        ephys_label.pack(anchor="w", pady=(0, 5))

        ephys_note = ttk.Label(
            parent,
            text="(Applied to cohorts marked as 'Ephys' above)",
            font=("Helvetica", 8),
            foreground="gray"
        )
        ephys_note.pack(anchor="w", padx=10, pady=(0, 5))

        ephys_options_frame = ttk.Frame(parent)
        ephys_options_frame.pack(fill="x", pady=(0, 10))

        pin_frame = ttk.Frame(ephys_options_frame)
        pin_frame.pack(anchor="w", padx=10, pady=2)
        ttk.Label(pin_frame, text="Target pin:").pack(side="left", padx=(0, 5))
        pin_spinbox = ttk.Spinbox(
            pin_frame,
            from_=0,
            to=15,
            textvariable=self.ephys_pin_var,
            width=5
        )
        pin_spinbox.pack(side="left")

        ttk.Checkbutton(
            ephys_options_frame,
            text="Force reprocess existing ephys files",
            variable=self.ephys_force_var
        ).pack(anchor="w", padx=10, pady=2)

    def _create_progress_content(self, parent: ttk.Frame) -> None:
        """Create the progress mode content."""
        # Progress label
        self.progress_label = ttk.Label(
            parent,
            text="Ready to start processing",
            font=("Helvetica", 10)
        )
        self.progress_label.pack(anchor="w", pady=(0, 5))

        # Progress bar
        self.progress_bar = ttk.Progressbar(
            parent,
            mode="indeterminate",
            length=300
        )
        self.progress_bar.pack(fill="x", pady=(0, 10))

        # Log output
        log_label = ttk.Label(
            parent,
            text="Processing Log:",
            font=("Helvetica", 10, "bold")
        )
        log_label.pack(anchor="w", pady=(0, 5))

        self.log_text = scrolledtext.ScrolledText(
            parent,
            wrap="word",
            height=20,
            state="disabled",
            font=("Courier", 9),
            background="#1E1E1E",
            foreground="#E0E0E0",
            insertbackground="#E0E0E0"
        )
        self.log_text.pack(fill="both", expand=True)

    def _on_start_click(self) -> None:
        """Handle start button click."""
        # Validate selection
        selected_cohorts = [
            name for name, var in self.cohort_vars.items() if var.get()
        ]

        if not selected_cohorts:
            messagebox.showwarning(
                "No Cohorts Selected",
                "Please select at least one cohort to process."
            )
            return

        # Check if any cohort has ephys enabled
        any_ephys = any(
            self.cohort_ephys_vars.get(name, tk.BooleanVar(value=False)).get()
            for name in selected_cohorts
        )

        # Check if any processing step is selected
        if not (self.recover_sessions_var.get() or
                self.process_videos_var.get() or
                self.run_analysis_var.get() or
                any_ephys):
            messagebox.showwarning(
                "No Steps Selected",
                "Please select at least one processing step."
            )
            return

        # Start processing
        self._start_processing(selected_cohorts)

    def _start_processing(self, selected_cohorts: list[str]) -> None:
        """Start the processing in a background thread."""
        # Update UI state
        self.is_processing = True
        self.cancel_requested = False
        self.cancel_button.configure(state="normal")
        self.back_button.configure(state="disabled")
        self.progress_bar.start()

        # Switch to Progress mode
        self._show_mode(WindowMode.PROGRESS)

        # Clear log
        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.configure(state="disabled")

        # Redirect stdout/stderr to log
        sys.stdout = TextRedirector(self.log_text, "stdout")
        sys.stderr = TextRedirector(self.log_text, "stderr")

        # Start processing thread
        self.processing_thread = threading.Thread(
            target=self._process_cohorts,
            args=(selected_cohorts,),
            daemon=True
        )
        self.processing_thread.start()

    def _process_cohorts(self, selected_cohorts: list[str]) -> None:
        """Process the selected cohorts (runs in background thread)."""
        try:
            # Import processing functions (local copy)
            from behaviour_rig_system.post_processing.post_process_arduinoDAQ import (
                recover_crashed_sessions,
                process_ephys_data,
                process_cohort_directory,
                run_analysis_on_local
            )

            # Get cohort directories with ephys flag
            cohort_dirs = {
                c.get("name"): {
                    "directory": Path(c.get("directory")),
                    "has_ephys": self.cohort_ephys_vars.get(c.get("name"), tk.BooleanVar(value=False)).get()
                }
                for c in self.cohort_folders
                if c.get("name") in selected_cohorts
            }

            total_cohorts = len(cohort_dirs)

            for idx, (name, cohort_info) in enumerate(cohort_dirs.items(), 1):
                if self.cancel_requested:
                    print("\n\nProcessing cancelled by user.")
                    break

                directory = cohort_info["directory"]
                has_ephys = cohort_info["has_ephys"]

                self._update_progress(
                    f"Processing cohort {idx}/{total_cohorts}: {name}"
                )

                print(f"\n{'='*80}")
                print(f"COHORT: {name}")
                print(f"DIRECTORY: {directory}")
                print(f"HAS EPHYS: {has_ephys}")
                print(f"{'='*80}\n")

                # Step 1: Recover crashed sessions
                if self.recover_sessions_var.get() and not self.cancel_requested:
                    print("\n----- STEP 1: RECOVERING CRASHED SESSIONS -----")
                    try:
                        recover_crashed_sessions(directory, verbose=True, force=False)
                    except Exception as e:
                        print(f"Error recovering crashed sessions: {e}")

                # Step 2: Process ephys data (only if cohort is marked as ephys)
                if has_ephys and not self.cancel_requested:
                    print("\n----- STEP 2: PROCESSING EPHYS DATA -----")
                    try:
                        target_pin = self.ephys_pin_var.get()
                        force = self.ephys_force_var.get()
                        process_ephys_data(directory, target_pin=target_pin, force=force)
                    except Exception as e:
                        print(f"Error processing ephys data: {e}")

                # Step 3: Process videos
                if self.process_videos_var.get() and not self.cancel_requested:
                    print("\n----- STEP 3: PROCESSING VIDEOS -----")
                    try:
                        num_processes = mp.cpu_count()
                        process_cohort_directory(directory, num_processes=num_processes)
                    except Exception as e:
                        print(f"Error processing videos: {e}")

                # Step 4: Run analysis
                if self.run_analysis_var.get() and not self.cancel_requested:
                    print("\n----- STEP 4: RUNNING ANALYSIS -----")
                    try:
                        refresh = self.refresh_analysis_var.get()
                        run_analysis_on_local(directory, refresh=refresh, ephys_data=has_ephys)
                    except Exception as e:
                        print(f"Error running analysis: {e}")

            if not self.cancel_requested:
                print("\n\n" + "="*80)
                print("ALL PROCESSING COMPLETE")
                print("="*80)
                self._update_progress("Processing complete!")

        except Exception as e:
            print(f"\n\nFATAL ERROR: {e}")
            import traceback
            traceback.print_exc()
            self._update_progress("Processing failed - see log for details")

        finally:
            # Restore stdout/stderr
            sys.stdout = sys.__stdout__
            sys.stderr = sys.__stderr__

            # Update UI in main thread
            self.window.after(0, self._processing_complete)

    def _update_progress(self, message: str) -> None:
        """Update progress label (thread-safe)."""
        self.window.after(0, lambda: self.progress_label.configure(text=message))

    def _processing_complete(self) -> None:
        """Called when processing finishes (runs in main thread)."""
        self.is_processing = False
        self.progress_bar.stop()
        self.cancel_button.configure(state="disabled")
        self.back_button.configure(state="normal")

        if not self.cancel_requested:
            messagebox.showinfo(
                "Processing Complete",
                "All selected cohorts have been processed.\n\n"
                "See the log above for detailed results."
            )

    def _on_cancel_click(self) -> None:
        """Handle cancel button click."""
        result = messagebox.askyesno(
            "Cancel Processing",
            "Are you sure you want to cancel processing?\n\n"
            "The current operation will finish, then processing will stop.",
            icon="warning"
        )

        if result:
            self.cancel_requested = True
            self.cancel_button.configure(state="disabled")
            self._update_progress("Cancelling... (waiting for current operation to finish)")

    def _on_close(self) -> None:
        """Handle window close."""
        if self.is_processing:
            messagebox.showwarning(
                "Processing In Progress",
                "Cannot close window while processing is in progress.\n\n"
                "Please cancel processing first, or wait for it to complete."
            )
            return

        # Release modal grab
        self.window.grab_release()
        self.window.destroy()


def open_post_processing_window(parent: tk.Tk, config_path: Path) -> None:
    """
    Open the post-processing window.

    Args:
        parent: Parent Tk window (launcher)
        config_path: Path to rigs.yaml configuration file
    """
    PostProcessingWindow(parent, config_path)
