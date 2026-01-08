"""
Post-Processing Window for Behaviour Rig System.

Provides a GUI for batch processing cohort data including:
- Recovering crashed sessions
- Processing videos (binary/BMP to AVI)
- Running behavioral analysis
- Processing electrophysiology data (optional)
"""

import sys
import threading
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
from pathlib import Path
from typing import Optional, Callable
import multiprocessing as mp
import yaml


class TextRedirector:
    """Redirect stdout/stderr to a text widget."""

    def __init__(self, widget, tag="stdout"):
        self.widget = widget
        self.tag = tag

    def write(self, string):
        self.widget.after(0, self._append_text, string)

    def _append_text(self, string):
        self.widget.configure(state="normal")
        self.widget.insert("end", string, self.tag)
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

        # Cohort checkboxes
        self.cohort_vars: dict[str, tk.BooleanVar] = {}

        # Processing option checkboxes
        self.recover_sessions_var = tk.BooleanVar(value=True)
        self.process_videos_var = tk.BooleanVar(value=True)
        self.run_analysis_var = tk.BooleanVar(value=True)
        self.process_ephys_var = tk.BooleanVar(value=False)

        # Ephys options
        self.ephys_pin_var = tk.IntVar(value=0)
        self.ephys_force_var = tk.BooleanVar(value=False)

        self._create_widgets()

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
        main_frame = ttk.Frame(self.window, padding="10")
        main_frame.pack(fill="both", expand=True)

        # Title
        title_label = ttk.Label(
            main_frame,
            text="Post-Processing",
            font=("Helvetica", 14, "bold")
        )
        title_label.pack(pady=(0, 10))

        # Create notebook for organization
        notebook = ttk.Notebook(main_frame)
        notebook.pack(fill="both", expand=True, pady=(0, 10))

        # Configuration tab
        config_frame = ttk.Frame(notebook, padding="10")
        notebook.add(config_frame, text="Configuration")

        # Progress tab
        progress_frame = ttk.Frame(notebook, padding="10")
        notebook.add(progress_frame, text="Progress")

        # --- Configuration Tab ---
        self._create_config_tab(config_frame)

        # --- Progress Tab ---
        self._create_progress_tab(progress_frame)

        # --- Control Buttons ---
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill="x", pady=(10, 0))

        self.start_button = ttk.Button(
            button_frame,
            text="Start Processing",
            command=self._on_start_click,
            width=20
        )
        self.start_button.pack(side="left", padx=5)

        self.cancel_button = ttk.Button(
            button_frame,
            text="Cancel",
            command=self._on_cancel_click,
            state="disabled",
            width=20
        )
        self.cancel_button.pack(side="left", padx=5)

        close_button = ttk.Button(
            button_frame,
            text="Close",
            command=self._on_close,
            width=20
        )
        close_button.pack(side="right", padx=5)

    def _create_config_tab(self, parent: ttk.Frame) -> None:
        """Create the configuration tab content."""
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

                var = tk.BooleanVar(value=False)
                self.cohort_vars[name] = var

                cb = ttk.Checkbutton(
                    cohort_inner_frame,
                    text=f"{name} ({directory})",
                    variable=var
                )
                cb.pack(anchor="w", padx=10, pady=2)

                if description:
                    desc_label = ttk.Label(
                        cohort_inner_frame,
                        text=f"    {description}",
                        font=("Helvetica", 8),
                        foreground="gray"
                    )
                    desc_label.pack(anchor="w", padx=25, pady=(0, 5))

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

        # Process ephys (with sub-options)
        ephys_frame = ttk.Frame(options_frame)
        ephys_frame.pack(anchor="w", padx=10, pady=2)

        ttk.Checkbutton(
            ephys_frame,
            text="Process electrophysiology data",
            variable=self.process_ephys_var,
            command=self._on_ephys_toggle
        ).pack(side="left")

        # Ephys sub-options frame
        self.ephys_options_frame = ttk.Frame(options_frame)
        self.ephys_options_frame.pack(anchor="w", padx=30, pady=(2, 5))

        pin_frame = ttk.Frame(self.ephys_options_frame)
        pin_frame.pack(anchor="w", pady=2)
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
            self.ephys_options_frame,
            text="Force reprocess existing files",
            variable=self.ephys_force_var
        ).pack(anchor="w", pady=2)

        # Initially disable ephys options
        self._set_ephys_options_state("disabled")

    def _create_progress_tab(self, parent: ttk.Frame) -> None:
        """Create the progress tab content."""
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
            font=("Courier", 9)
        )
        self.log_text.pack(fill="both", expand=True)

    def _on_ephys_toggle(self) -> None:
        """Handle ephys checkbox toggle."""
        if self.process_ephys_var.get():
            self._set_ephys_options_state("normal")
        else:
            self._set_ephys_options_state("disabled")

    def _set_ephys_options_state(self, state: str) -> None:
        """Enable or disable ephys sub-options."""
        for child in self.ephys_options_frame.winfo_children():
            if isinstance(child, ttk.Frame):
                for subchild in child.winfo_children():
                    try:
                        subchild.configure(state=state)
                    except:
                        pass
            else:
                try:
                    child.configure(state=state)
                except:
                    pass

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

        # Check if any processing step is selected
        if not (self.recover_sessions_var.get() or
                self.process_videos_var.get() or
                self.run_analysis_var.get() or
                self.process_ephys_var.get()):
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
        self.start_button.configure(state="disabled")
        self.cancel_button.configure(state="normal")
        self.progress_bar.start()

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

            # Get cohort directories
            cohort_dirs = {
                c.get("name"): Path(c.get("directory"))
                for c in self.cohort_folders
                if c.get("name") in selected_cohorts
            }

            total_cohorts = len(cohort_dirs)

            for idx, (name, directory) in enumerate(cohort_dirs.items(), 1):
                if self.cancel_requested:
                    print("\n\nProcessing cancelled by user.")
                    break

                self._update_progress(
                    f"Processing cohort {idx}/{total_cohorts}: {name}"
                )

                print(f"\n{'='*80}")
                print(f"COHORT: {name}")
                print(f"DIRECTORY: {directory}")
                print(f"{'='*80}\n")

                # Step 1: Recover crashed sessions
                if self.recover_sessions_var.get() and not self.cancel_requested:
                    print("\n----- STEP 1: RECOVERING CRASHED SESSIONS -----")
                    try:
                        recover_crashed_sessions(directory, verbose=True, force=False)
                    except Exception as e:
                        print(f"Error recovering crashed sessions: {e}")

                # Step 2: Process ephys data
                if self.process_ephys_var.get() and not self.cancel_requested:
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
                        has_ephys = self.process_ephys_var.get()
                        run_analysis_on_local(directory, refresh=False, ephys_data=has_ephys)
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
        self.start_button.configure(state="normal")
        self.cancel_button.configure(state="disabled")

        if not self.cancel_requested:
            messagebox.showinfo(
                "Processing Complete",
                "All selected cohorts have been processed.\n\n"
                "Check the Progress tab for detailed results."
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
