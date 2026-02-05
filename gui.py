#!/usr/bin/env python3
"""
GUI for Document Processing Pipeline
Uses customtkinter for a modern interface.
"""

import os
import sys
import threading
import logging
import queue
import customtkinter as ctk
from pathlib import Path
from tkinter import filedialog, messagebox

# Import core logic
import main as pipeline
from config_manager import ConfigManager
from pdf2image.exceptions import PDFInfoNotInstalledError

# Set appearance mode
ctk.set_appearance_mode("System")
ctk.set_default_color_theme("blue")

def check_poppler_dependency():
    """
    Check if poppler is installed and available.
    Returns True if available, False otherwise.
    """
    try:
        from pdf2image import pdfinfo_from_path
        # We don't need a real file, just checking if the binary is callable
        # However, pdfinfo_from_path usually needs a file. 
        # Easier check: run a subprocess or just let the first call fail?
        # Better: pdf2image has a dedicated error for this.
        # We'll just wrap the whole app startup in a try/except block or check specifically.
        
        # Actually, let's verify by just checking if 'pdfinfo' is in PATH.
        import shutil
        if not shutil.which("pdfinfo"):
            return False
        return True
    except Exception:
        return False

if not check_poppler_dependency():
    # Show a simple tkinter alert before customtkinter takes over, or use CTk's functionality if init is safe
    # Using standard tkinter for maximum safety before dependencies might load fully
    import tkinter.messagebox
    root = tkinter.Tk()
    root.withdraw()
    tkinter.messagebox.showerror(
        "Missing Dependency: Poppler",
        "Poppler is required to run this application.\n\n"
        "Please install it:\n"
        "- macOS: brew install poppler\n"
        "- Windows: Download from GitHub/poppler-windows and add to PATH\n"
        "- Linux: sudo apt-get install poppler-utils"
    )
    sys.exit(1)

class QueueHandler(logging.Handler):
    """
    Thread-safe logging handler that pushes log records to a queue.
    """
    def __init__(self, log_queue):
        super().__init__()
        self.log_queue = log_queue

    def emit(self, record):
        msg = self.format(record)
        self.log_queue.put(msg)

class OCRApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Document OCR Pipeline")
        self.geometry("900x600")
        
        # State
        self.is_running = False
        self.stop_event = threading.Event()
        self.worker_thread = None
        self.input_dir = pipeline.INPUT_DIR
        self.output_dir = pipeline.OUTPUT_DIR
        
        # Load Configuration
        self.config_manager = ConfigManager()
        self.load_config_into_state()
        
        # Logging Setup
        self.log_queue = queue.Queue()
        self.setup_logging()

        # Layout Configuration
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # Create sidebar
        self.create_sidebar()
        
        # Create main area
        self.create_main_area()
        
        # Start log poller
        self.after(100, self.process_log_queue)

    def load_config_into_state(self):
        """Load values from config manager into local state."""
        # Directories
        input_path = self.config_manager.get("input_dir")
        output_path = self.config_manager.get("output_dir")
        
        if input_path:
            self.input_dir = Path(input_path)
        if output_path:
            self.output_dir = Path(output_path)
            
    def save_current_config(self):
        """Save current UI values to config manager."""
        self.config_manager.set("server_url", self.url_entry.get().strip())
        self.config_manager.set("model_name", self.model_entry.get().strip())
        self.config_manager.set("max_workers", int(self.workers_slider.get()))
        # System prompt is saved when the prompt window closes, but we can ensure it here too if we had a reference
        # Directories
        self.config_manager.set("input_dir", str(self.input_dir))
        self.config_manager.set("output_dir", str(self.output_dir))
        self.config_manager.save_config()

    def setup_logging(self):
        # Attach our queue handler to the main logger
        queue_handler = QueueHandler(self.log_queue)
        queue_handler.setFormatter(logging.Formatter("%(asctime)s - %(message)s"))
        pipeline.logger.addHandler(queue_handler)

    def create_sidebar(self):
        self.sidebar_frame = ctk.CTkFrame(self, width=250, corner_radius=0)
        self.sidebar_frame.grid(row=0, column=0, sticky="nsew")
        self.sidebar_frame.grid_rowconfigure(8, weight=1)

        # Title
        self.logo_label = ctk.CTkLabel(self.sidebar_frame, text="OCR Pipeline", font=ctk.CTkFont(size=20, weight="bold"))
        self.logo_label.grid(row=0, column=0, padx=20, pady=(20, 10))

        # Input Directory
        self.input_label = ctk.CTkLabel(self.sidebar_frame, text="Input Directory:", anchor="w")
        self.input_label.grid(row=1, column=0, padx=20, pady=(10, 0), sticky="w")
        
        self.input_btn = ctk.CTkButton(self.sidebar_frame, text="Select Input", command=self.select_input_dir)
        self.input_btn.grid(row=2, column=0, padx=20, pady=5)
        
        self.input_path_label = ctk.CTkLabel(self.sidebar_frame, text=self.input_dir.name, text_color="gray")
        self.input_path_label.grid(row=3, column=0, padx=20, pady=0)

        # Output Directory
        self.output_label = ctk.CTkLabel(self.sidebar_frame, text="Output Directory:", anchor="w")
        self.output_label.grid(row=4, column=0, padx=20, pady=(10, 0), sticky="w")
        
        self.output_btn = ctk.CTkButton(self.sidebar_frame, text="Select Output", command=self.select_output_dir)
        self.output_btn.grid(row=5, column=0, padx=20, pady=5)
        
        self.output_path_label = ctk.CTkLabel(self.sidebar_frame, text=self.output_dir.name, text_color="gray")
        self.output_path_label.grid(row=6, column=0, padx=20, pady=0)

        # Options
        self.watch_mode_var = ctk.BooleanVar(value=False)
        self.watch_checkbox = ctk.CTkCheckBox(self.sidebar_frame, text="Watch Mode", variable=self.watch_mode_var)
        self.watch_checkbox.grid(row=7, column=0, padx=20, pady=20, sticky="w")

        # Configuration
        self.config_label = ctk.CTkLabel(self.sidebar_frame, text="Configuration:", anchor="w", font=ctk.CTkFont(weight="bold"))
        self.config_label.grid(row=8, column=0, padx=20, pady=(10, 5), sticky="w")

        # Server URL
        self.url_label = ctk.CTkLabel(self.sidebar_frame, text="Server URL:", anchor="w")
        self.url_label.grid(row=9, column=0, padx=20, pady=(0, 0), sticky="w")
        
        self.url_entry = ctk.CTkEntry(self.sidebar_frame, placeholder_text="http://localhost:1234/v1")
        self.url_entry.grid(row=10, column=0, padx=20, pady=(0, 5))
        self.url_entry.insert(0, self.config_manager.get("server_url"))
        
        # Test Connection Button
        self.test_conn_btn = ctk.CTkButton(self.sidebar_frame, text="Test Connection", command=self.test_connection_gui, height=24, font=ctk.CTkFont(size=11))
        self.test_conn_btn.grid(row=11, column=0, padx=20, pady=(0, 10))

        # Model Name
        self.model_label = ctk.CTkLabel(self.sidebar_frame, text="Model Name:", anchor="w")
        self.model_label.grid(row=12, column=0, padx=20, pady=(0, 0), sticky="w")
        
        self.model_entry = ctk.CTkEntry(self.sidebar_frame, placeholder_text="deepseek-ocr")
        self.model_entry.grid(row=13, column=0, padx=20, pady=(0, 10))
        self.model_entry.insert(0, self.config_manager.get("model_name"))
        
        # Max Workers
        self.workers_label = ctk.CTkLabel(self.sidebar_frame, text=f"Max Workers: {self.config_manager.get('max_workers')}", anchor="w")
        self.workers_label.grid(row=14, column=0, padx=20, pady=(0, 0), sticky="w")
        
        self.workers_slider = ctk.CTkSlider(self.sidebar_frame, from_=1, to=10, number_of_steps=9, command=self.update_workers_label)
        self.workers_slider.grid(row=15, column=0, padx=20, pady=(0, 10))
        self.workers_slider.set(self.config_manager.get("max_workers"))

        # Advanced Settings (Prompt)
        self.advanced_btn = ctk.CTkButton(self.sidebar_frame, text="Advanced Settings", command=self.open_advanced_settings, fg_color="gray", hover_color="gray30")
        self.advanced_btn.grid(row=16, column=0, padx=20, pady=(0, 10))

        # Start/Stop Buttons
        self.start_button = ctk.CTkButton(self.sidebar_frame, text="Start Processing", command=self.start_processing, fg_color="green", hover_color="darkgreen")
        self.start_button.grid(row=17, column=0, padx=20, pady=10)
        
        self.stop_button = ctk.CTkButton(self.sidebar_frame, text="Stop", command=self.stop_processing, fg_color="red", hover_color="darkred", state="disabled")
        self.stop_button.grid(row=18, column=0, padx=20, pady=(0, 20))

    def create_main_area(self):
        self.main_frame = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        self.main_frame.grid(row=0, column=1, sticky="nsew", padx=20, pady=20)
        self.main_frame.grid_rowconfigure(1, weight=1)
        self.main_frame.grid_columnconfigure(0, weight=1)

        # Header
        self.status_label = ctk.CTkLabel(self.main_frame, text="Ready", font=ctk.CTkFont(size=24))
        self.status_label.grid(row=0, column=0, sticky="w", pady=(0, 20))

        # Tabs
        self.tabview = ctk.CTkTabview(self.main_frame, width=600)
        self.tabview.grid(row=1, column=0, sticky="nsew")
        self.tabview.add("Log Console")
        self.tabview.add("Preview")
        self.tabview.columnconfigure(0, weight=1)
        self.tabview.rowconfigure(0, weight=1)

        # Log Console
        self.log_textbox = ctk.CTkTextbox(self.tabview.tab("Log Console"), width=600)
        self.log_textbox.grid(row=0, column=0, sticky="nsew")
        self.log_textbox.configure(state="disabled")

        # Configure tags for log coloring
        self.log_textbox.tag_config("timestamp", foreground="gray")
        self.log_textbox.tag_config("info", foreground="white") # Default
        self.log_textbox.tag_config("success", foreground="#00e676") # Bright Green
        self.log_textbox.tag_config("warning", foreground="orange")
        self.log_textbox.tag_config("error", foreground="#ff5252") # Red
        
        # Preview Area
        self.preview_textbox = ctk.CTkTextbox(self.tabview.tab("Preview"), width=600)
        self.preview_textbox.grid(row=0, column=0, sticky="nsew")
        self.preview_textbox.configure(state="disabled")

        # Progress Bar Frame
        self.progress_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.progress_frame.grid(row=2, column=0, sticky="ew", pady=(20, 0))
        self.progress_frame.grid_columnconfigure(0, weight=1)

        self.progress_label = ctk.CTkLabel(self.progress_frame, text="Processed: 0/0", anchor="w")
        self.progress_label.grid(row=0, column=0, sticky="w", padx=5)

        self.progress_bar = ctk.CTkProgressBar(self.progress_frame)
        self.progress_bar.grid(row=1, column=0, sticky="ew", padx=5, pady=(5, 0))
        self.progress_bar.set(0)

    def select_input_dir(self):
        path = filedialog.askdirectory(initialdir=self.input_dir)
        if path:
            self.input_dir = Path(path)
            self.input_path_label.configure(text=self.input_dir.name)
            self.log(f"Input directory set to: {self.input_dir}")

    def update_workers_label(self, value):
        self.workers_label.configure(text=f"Max Workers: {int(value)}")

    def test_connection_gui(self):
        url = self.url_entry.get().strip()
        if not url:
            messagebox.showerror("Error", "Please enter a Server URL")
            return
            
        self.test_conn_btn.configure(state="disabled", text="Testing...")
        
        def run_test():
            success, msg = pipeline.test_connection(url)
            self.after(0, lambda: self.show_connection_result(success, msg))
            
        threading.Thread(target=run_test, daemon=True).start()

    def show_connection_result(self, success, msg):
        self.test_conn_btn.configure(state="normal", text="Test Connection")
        if success:
            messagebox.showinfo("Success", msg)
        else:
            messagebox.showerror("Connection Failed", msg)

    def open_advanced_settings(self):
        if hasattr(self, 'advanced_window') and self.advanced_window is not None and self.advanced_window.winfo_exists():
            self.advanced_window.lift()
            return

        self.advanced_window = ctk.CTkToplevel(self)
        self.advanced_window.title("Advanced Settings")
        self.advanced_window.geometry("500x400")
        
        ctk.CTkLabel(self.advanced_window, text="System Prompt:", font=ctk.CTkFont(weight="bold")).pack(pady=(20, 5), padx=20, anchor="w")
        
        self.prompt_textbox = ctk.CTkTextbox(self.advanced_window, width=460, height=300)
        self.prompt_textbox.pack(pady=10, padx=20)
        
        current_prompt = self.config_manager.get("system_prompt")
        self.prompt_textbox.insert("0.0", current_prompt)
        
        save_btn = ctk.CTkButton(self.advanced_window, text="Save & Close", command=self.save_advanced_settings)
        save_btn.pack(pady=20)
        
    def save_advanced_settings(self):
        new_prompt = self.prompt_textbox.get("0.0", "end").strip()
        self.config_manager.set("system_prompt", new_prompt)
        self.advanced_window.destroy()
        self.advanced_window = None

    def select_output_dir(self):
        path = filedialog.askdirectory(initialdir=self.output_dir)
        if path:
            self.output_dir = Path(path)
            self.output_path_label.configure(text=self.output_dir.name)
            self.log(f"Output directory set to: {self.output_dir}")

    def log(self, message):
        self.log_queue.put(message)

    def process_log_queue(self):
        try:
            while True:
                msg = self.log_queue.get_nowait()
                self.log_textbox.configure(state="normal")
                
                # Default tags
                tags = ["info"]
                timestamp = ""
                content = msg
                
                # Simple parsing for timestamp "YYYY-MM-DD HH:MM:SS,mmm - LEVEL - Message"
                # But our formatter is just "%(asctime)s - %(message)s"
                # Ex: "2023-10-27 10:00:00,123 - Message" 
                # Wait, main.py uses: format="%(asctime)s - %(levelname)s - %(message)s"
                
                parts = msg.split(" - ", 2)
                if len(parts) >= 2:
                    timestamp = parts[0]
                    # Level might be in parts[1] if format includes it, or message starts there
                    # pipeline.logger format: "%(asctime)s - %(levelname)s - %(message)s"
                    if len(parts) >= 3:
                        level = parts[1].strip()
                        content = parts[2]
                        
                        if level == "INFO":
                            if "Successfully" in content or "Complete" in content:
                                tags = ["success"]
                            else:
                                tags = ["info"]
                        elif level == "WARNING":
                            tags = ["warning"]
                        elif level == "ERROR" or level == "CRITICAL":
                            tags = ["error"]
                    else:
                        # Fallback for simpler messages
                        content = parts[1]
                
                # Insert Timestamp
                if timestamp:
                    self.log_textbox.insert("end", timestamp + " - ", "timestamp")
                
                # Insert Message
                self.log_textbox.insert("end", content + "\n", tags)
                
                self.log_textbox.see("end")
                self.log_textbox.configure(state="disabled")
                
                # Check for preview
                if "Successfully saved: " in msg:
                    try:
                        path_str = msg.split("Successfully saved: ")[1].strip()
                        with open(path_str, "r", encoding="utf-8") as f:
                            content = f.read()
                        self.preview_textbox.configure(state="normal")
                        self.preview_textbox.delete("0.0", "end")
                        self.preview_textbox.insert("0.0", content)
                        self.preview_textbox.configure(state="disabled")
                        # Optional: self.tabview.set("Preview")
                    except Exception as e:
                        print(f"Failed to load preview: {e}")
                        
        except queue.Empty:
            pass
        finally:
            self.after(100, self.process_log_queue)

    def start_processing(self):
        if self.is_running:
            return
            
        # Save config first
        self.save_current_config()
        
        base_url = self.url_entry.get().strip()
        model_name = self.model_entry.get().strip()
        max_workers = int(self.workers_slider.get())
        system_prompt = self.config_manager.get("system_prompt")

        self.is_running = True
        self.stop_event.clear()
        
        self.start_button.configure(state="disabled")
        self.stop_button.configure(state="normal")
        self.input_btn.configure(state="disabled")
        self.output_btn.configure(state="disabled")
        self.watch_checkbox.configure(state="disabled")
        self.url_entry.configure(state="disabled")
        self.model_entry.configure(state="disabled")
        self.test_conn_btn.configure(state="disabled")
        self.workers_slider.configure(state="disabled")
        self.advanced_btn.configure(state="disabled")
        
        mode = "Watch Mode" if self.watch_mode_var.get() else "Batch Mode"
        self.status_label.configure(text=f"Running - {mode}", text_color="green")
        self.log(f"Starting {mode}...")

        if self.watch_mode_var.get():
            target = pipeline.watch_folder
            args = (self.input_dir, self.output_dir, self.stop_event, base_url, model_name, max_workers, system_prompt)
            self.progress_bar.configure(mode="indeterminate")
            self.progress_bar.start()
            self.progress_label.configure(text="Watch Mode Active")
        else:
            target = self.run_batch_wrapper
            args = (base_url, model_name, max_workers, system_prompt)
            self.progress_bar.configure(mode="determinate")
            self.progress_bar.set(0)
            self.progress_label.configure(text="Starting...")

        self.worker_thread = threading.Thread(target=target, args=args, daemon=True)
        self.worker_thread.start()

    def run_batch_wrapper(self, base_url, model_name, max_workers, system_prompt):
        """Wrapper to run batch processing and then reset UI."""
        try:
            pipeline.scan_and_process(
                self.input_dir, 
                self.output_dir, 
                progress_callback=self.update_progress_safe,
                base_url=base_url,
                model_name=model_name,
                max_workers=max_workers,
                system_prompt=system_prompt,
                stop_event=self.stop_event
            )
        except Exception as e:
            pipeline.logger.error(f"Error in batch processing: {e}")
        finally:
            # Schedule UI reset on main thread
            self.after(0, self.reset_ui_after_batch)

    def update_progress_safe(self, current, total):
        """Callback to update progress bar from worker thread."""
        self.after(0, lambda: self.update_progress(current, total))

    def update_progress(self, current, total):
        if total > 0:
            progress = current / total
            self.progress_bar.set(progress)
            self.progress_label.configure(text=f"Processed: {current}/{total}")
        else:
            self.progress_bar.set(1)
            self.progress_label.configure(text="No files to process")

    def reset_ui_after_batch(self):
        if self.is_running: # If not manually stopped
            self.log("Batch processing complete.")
            
            # Reset UI elements manually to show "Finished" instead of "Stopped"
            self.is_running = False
            self.stop_event.set()
            
            self.start_button.configure(state="normal")
            self.stop_button.configure(state="disabled", fg_color="red")
            self.input_btn.configure(state="normal")
            self.output_btn.configure(state="normal")
            self.watch_checkbox.configure(state="normal")
            self.url_entry.configure(state="normal")
            self.model_entry.configure(state="normal")
            self.test_conn_btn.configure(state="normal")
            self.workers_slider.configure(state="normal")
            self.advanced_btn.configure(state="normal")
            
            self.status_label.configure(text="Finished", text_color="green")
            self.log("Process finished successfully.")

    def stop_processing(self):
        if not self.is_running:
            return

        self.status_label.configure(text="Stopping...", text_color="orange")
        self.stop_event.set()
        
        # In watch mode, the thread loops, so we wait for it to see the event.
        # In batch mode, it might finish naturally.
        
        self.is_running = False
        self.start_button.configure(state="normal")
        self.stop_button.configure(state="disabled", fg_color="red")
        self.input_btn.configure(state="normal")
        self.output_btn.configure(state="normal")
        self.watch_checkbox.configure(state="normal")
        self.url_entry.configure(state="normal")
        self.model_entry.configure(state="normal")
        self.test_conn_btn.configure(state="normal")
        self.workers_slider.configure(state="normal")
        self.advanced_btn.configure(state="normal")
        
        if self.watch_mode_var.get():
            self.progress_bar.stop()
            self.progress_bar.configure(mode="determinate")
            self.progress_bar.set(0)

        self.status_label.configure(text="Stopped", text_color="gray")
        self.log("Process stopped.")

if __name__ == "__main__":
    app = OCRApp()
    app.mainloop()
