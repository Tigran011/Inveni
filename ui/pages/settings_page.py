# ui/pages/settings_page.py - Enhanced with responsive design and centralized time utilities

import os
import platform
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import json
import logging
from pathlib import Path
import glob
import shutil

# Import from utils package
from utils.time_utils import get_formatted_time, get_current_times, get_current_username
from utils.file_utils import format_size

class ToolTip:
    """Tooltip class for adding hover help text to widgets."""
    
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tooltip = None
        self.scheduled = None
        
        # Use bind tags to avoid conflicts with other bindings
        self.widget.bind("<Enter>", self.schedule_show, add="+")
        self.widget.bind("<Leave>", self.hide_tooltip, add="+")
        self.widget.bind("<ButtonPress>", self.hide_tooltip, add="+")
    
    def schedule_show(self, event=None):
        """Schedule tooltip to appear after a short delay."""
        self.cancel_schedule()
        self.scheduled = self.widget.after(600, self.show_tooltip)
    
    def cancel_schedule(self):
        """Cancel the scheduled tooltip appearance."""
        if self.scheduled:
            self.widget.after_cancel(self.scheduled)
            self.scheduled = None
    
    def show_tooltip(self, event=None):
        """Show tooltip window."""
        self.hide_tooltip()  # Ensure any existing tooltip is removed
        
        x = self.widget.winfo_rootx() + self.widget.winfo_width() // 2
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 5
        
        # Create tooltip window
        self.tooltip = tk.Toplevel(self.widget)
        self.tooltip.wm_overrideredirect(True)
        self.tooltip.wm_geometry(f"+{x-100}+{y}")
        
        # Create tooltip content
        frame = tk.Frame(self.tooltip, background="#ffffe0", borderwidth=1, relief="solid")
        frame.pack(fill="both", expand=True)
        
        label = tk.Label(
            frame, 
            text=self.text, 
            background="#ffffe0", 
            foreground="#333333",
            font=("Segoe UI", 9),
            padx=5,
            pady=2,
            justify="left"
        )
        label.pack()
        
    def hide_tooltip(self, event=None):
        """Hide tooltip window."""
        self.cancel_schedule()
        if self.tooltip:
            self.tooltip.destroy()
            self.tooltip = None

class SettingsPage:
    """UI for managing application settings with responsive design."""
    
    def __init__(self, parent, settings_manager, shared_state, colors=None, ui_scale=1.0, font_scale=1.0):
        """
        Initialize settings page with necessary services and responsive design.
        
        Args:
            parent: Parent tkinter container
            settings_manager: Service for settings management
            shared_state: Shared application state
            colors: Color palette (optional)
            ui_scale: UI scaling factor (optional)
            font_scale: Font scaling factor (optional)
        """
        self.parent = parent
        self.settings_manager = settings_manager
        self.settings = settings_manager.settings
        self.shared_state = shared_state
        self.ui_scale = ui_scale
        self.font_scale = font_scale
        self.tooltip_window = None
        self.resize_timer = None
        
        # Define standard padding scaled to screen size
        self.STANDARD_PADDING = int(10 * self.ui_scale)
        self.SMALL_PADDING = int(5 * self.ui_scale)
        self.LARGE_PADDING = int(20 * self.ui_scale)
        
        # Define current user and time for logs using centralized utilities
        self.username = get_current_username()
        self.current_time = get_formatted_time(use_utc=False)
        
        # Define color palette
        if colors:
            self.colors = colors
        else:
            # Default modernized color palette
            self.colors = {
                'primary': "#1976d2",       # Deeper blue for primary actions
                'primary_dark': "#004ba0",  # Darker variant for hover states
                'primary_light': "#63a4ff", # Lighter variant for backgrounds
                'secondary': "#546e7a",     # More muted secondary color
                'success': "#2e7d32",       # Deeper green for success
                'danger': "#c62828",        # Deeper red for errors/danger
                'warning': "#f57f17",       # Warmer orange for warnings
                'info': "#0277bd",          # Deep blue for information
                'light': "#f5f5f5",         # Light background
                'dark': "#263238",          # Deep dark for text
                'white': "#ffffff",         # Pure white
                'border': "#cfd8dc",        # Subtle border color
                'background': "#eceff1",    # Slightly blue-tinted background
                'card': "#ffffff",          # Card background
                'disabled': "#e0e0e0",      # Disabled elements
                'disabled_text': "#9e9e9e", # Disabled text
                'highlight': "#bbdefb"      # Highlight/selection color
            }
        
        # Create UI components
        self._create_ui()
        
        # Bind resize events
        self.frame.bind('<Configure>', self._on_frame_configure)

    def _create_ui(self):
        """Create the user interface with responsive grid layout."""
        # Create main frame with grid
        self.frame = ttk.Frame(self.parent)
        self.frame.grid(row=0, column=0, sticky='nsew')
        
        # Make frame responsive
        self.frame.grid_columnconfigure(0, weight=1)
        self.frame.grid_rowconfigure(0, weight=0)  # Header - fixed height
        self.frame.grid_rowconfigure(1, weight=0)  # Backup settings - fixed height
        self.frame.grid_rowconfigure(2, weight=0)  # Logging - fixed height
        self.frame.grid_rowconfigure(3, weight=0)  # System info - fixed height
        self.frame.grid_rowconfigure(4, weight=1)  # Empty space - flexible
        
        # Create content sections with card design
        self._create_header_section()
        self._create_backup_section()
        self._create_logging_section()
        self._create_system_info_section()
        
        # Initial UI update
        self._update_ui()

    def _create_header_section(self):
        """Create responsive header section with title."""
        self.header_frame = self._create_card_container(
            self.frame, 
            row=0, 
            column=0, 
            sticky='ew', 
            padx=self.STANDARD_PADDING, 
            pady=(self.STANDARD_PADDING, self.SMALL_PADDING)
        )
        
        # Header content with grid layout
        self.header_frame.grid_columnconfigure(0, weight=1)
        
        # Page title
        self.title_label = tk.Label(
            self.header_frame,
            text="Settings",
            font=("Segoe UI", int(18 * self.font_scale), "bold"),
            fg=self.colors['dark'],
            bg=self.colors['card']
        )
        self.title_label.grid(row=0, column=0, sticky='w', padx=self.STANDARD_PADDING, pady=self.STANDARD_PADDING)

    def _create_backup_section(self):
        """Create backup settings section with improved card design."""
        self.backup_card = self._create_card_container(
            self.frame, 
            row=1, 
            column=0, 
            sticky='ew', 
            padx=self.STANDARD_PADDING, 
            pady=self.SMALL_PADDING
        )
        
        # Section title
        self.backup_title = tk.Label(
            self.backup_card,
            text="Backup Settings",
            font=("Segoe UI", int(12 * self.font_scale), "bold"),
            fg=self.colors['dark'],
            bg=self.colors['card']
        )
        self.backup_title.pack(anchor='w', padx=self.STANDARD_PADDING, pady=(self.STANDARD_PADDING, self.SMALL_PADDING))
        
        # Separator
        separator = ttk.Separator(self.backup_card, orient='horizontal')
        separator.pack(fill='x', padx=self.STANDARD_PADDING, pady=(0, self.SMALL_PADDING))
        
        # Content container
        content = tk.Frame(self.backup_card, bg=self.colors['card'])
        content.pack(fill='x', expand=True, padx=self.STANDARD_PADDING, pady=(0, self.STANDARD_PADDING))
        content.grid_columnconfigure(0, weight=1)
        
        # Backup folder section
        folder_frame = tk.Frame(content, bg=self.colors['card'])
        folder_frame.grid(row=0, column=0, sticky='ew', pady=self.SMALL_PADDING)
        folder_frame.grid_columnconfigure(0, weight=1)
        
        folder_label = tk.Label(
            folder_frame,
            text="Backup Location:",
            font=("Segoe UI", int(11 * self.font_scale), "bold"),
            fg=self.colors['dark'],
            bg=self.colors['card']
        )
        folder_label.grid(row=0, column=0, sticky='w')
        
        # Get a readable version of the backup path
        backup_path = self.settings.get('backup_folder', '')
        readable_path = str(Path(backup_path).resolve()) if backup_path else "Not set"
        
        self.backup_folder_label = tk.Label(
            folder_frame,
            text=readable_path,
            font=("Segoe UI", int(10 * self.font_scale)),
            fg=self.colors['secondary'],
            bg=self.colors['card']
        )
        self.backup_folder_label.grid(row=1, column=0, sticky='w', pady=(0, self.SMALL_PADDING))
        
        # Button container with better alignment
        btn_frame = tk.Frame(folder_frame, bg=self.colors['card'])
        btn_frame.grid(row=2, column=0, sticky='w')
        
        self.select_folder_btn = self._create_button(
            btn_frame,
            "Select Backup Folder",
            self._select_backup_folder,
            is_primary=True,
            icon="📁"
        )
        self.select_folder_btn.pack(side='left')
        
        # Add tooltip
        ToolTip(self.select_folder_btn, "Choose where backup files will be stored")
        
        # Divider
        divider = ttk.Separator(content, orient='horizontal')
        divider.grid(row=1, column=0, sticky='ew', pady=self.STANDARD_PADDING)
        
        # Settings grid with 2 columns
        settings_frame = tk.Frame(content, bg=self.colors['card'])
        settings_frame.grid(row=2, column=0, sticky='ew')
        settings_frame.grid_columnconfigure(1, weight=1)
        
        # Max backups section
        max_label = tk.Label(
            settings_frame,
            text="Maximum Backups:",
            font=("Segoe UI", int(11 * self.font_scale)),
            fg=self.colors['dark'],
            bg=self.colors['card']
        )
        max_label.grid(row=0, column=0, sticky='w', pady=self.SMALL_PADDING)
        
        max_frame = tk.Frame(settings_frame, bg=self.colors['card'])
        max_frame.grid(row=0, column=1, sticky='w', padx=self.STANDARD_PADDING, pady=self.SMALL_PADDING)
        
        # Use a better styled Spinbox for max backups
        self.max_backups_var = tk.StringVar(value=str(self.settings.get("max_backups", 10)))
        
        self.max_backups_spinbox = ttk.Spinbox(
            max_frame, 
            from_=1, 
            to=100, 
            textvariable=self.max_backups_var,
            width=5,
            font=("Segoe UI", int(10 * self.font_scale))
        )
        self.max_backups_spinbox.pack(side='left', padx=(0, self.SMALL_PADDING))
        
        self.update_backups_btn = self._create_button(
            max_frame,
            "Apply",
            self._update_max_backups,
            is_primary=False,
            icon="✓",
            compact=True
        )
        self.update_backups_btn.pack(side='left')
        
        ToolTip(self.max_backups_spinbox, "Maximum number of backup versions to keep per file")
        
        # Compression option with better styling
        compress_label = tk.Label(
            settings_frame,
            text="Compress Backups:",
            font=("Segoe UI", int(11 * self.font_scale)),
            fg=self.colors['dark'],
            bg=self.colors['card']
        )
        compress_label.grid(row=1, column=0, sticky='w', pady=self.SMALL_PADDING)
        
        compress_frame = tk.Frame(settings_frame, bg=self.colors['card'])
        compress_frame.grid(row=1, column=1, sticky='w', padx=self.STANDARD_PADDING, pady=self.SMALL_PADDING)
        
        self.compress_var = tk.BooleanVar(value=self.settings.get("compress_backups", True))
        
        self.compress_check = ttk.Checkbutton(
            compress_frame,
            text="Enable",
            variable=self.compress_var,
            command=self._toggle_compression,
            style="Switch.TCheckbutton"
        )
        self.compress_check.pack(side='left')
        
        ToolTip(self.compress_check, "Compress backup files to save disk space")

    def _create_logging_section(self):
        """Create logging options section with improved card design."""
        self.logging_card = self._create_card_container(
            self.frame, 
            row=2, 
            column=0, 
            sticky='ew', 
            padx=self.STANDARD_PADDING, 
            pady=self.SMALL_PADDING
        )
        
        # Section title
        self.logging_title = tk.Label(
            self.logging_card,
            text="Logging Options",
            font=("Segoe UI", int(12 * self.font_scale), "bold"),
            fg=self.colors['dark'],
            bg=self.colors['card']
        )
        self.logging_title.pack(anchor='w', padx=self.STANDARD_PADDING, pady=(self.STANDARD_PADDING, self.SMALL_PADDING))
        
        # Separator
        separator = ttk.Separator(self.logging_card, orient='horizontal')
        separator.pack(fill='x', padx=self.STANDARD_PADDING, pady=(0, self.SMALL_PADDING))
        
        # Content container
        content = tk.Frame(self.logging_card, bg=self.colors['card'])
        content.pack(fill='x', expand=True, padx=self.STANDARD_PADDING, pady=(0, self.STANDARD_PADDING))
        content.grid_columnconfigure(0, weight=1)
        
        # Logging toggle section
        toggle_frame = tk.Frame(content, bg=self.colors['card'])
        toggle_frame.grid(row=0, column=0, sticky='ew', pady=self.SMALL_PADDING)
        toggle_frame.grid_columnconfigure(1, weight=1)
        
        logging_label = tk.Label(
            toggle_frame,
            text="Enable Logging:",
            font=("Segoe UI", int(11 * self.font_scale)),
            fg=self.colors['dark'],
            bg=self.colors['card']
        )
        logging_label.grid(row=0, column=0, sticky='w')
        
        self.logging_var = tk.BooleanVar(value=self.settings.get("logging_enabled", True))
        
        self.logging_check = ttk.Checkbutton(
            toggle_frame,
            text="",
            variable=self.logging_var,
            command=self._toggle_logging,
            style="Switch.TCheckbutton"
        )
        self.logging_check.grid(row=0, column=1, sticky='w', padx=self.STANDARD_PADDING)
        
        ToolTip(self.logging_check, "Enable application logging for troubleshooting")
        
        # Log file location with icon
        log_path = self._get_log_path()
        
        location_frame = tk.Frame(content, bg=self.colors['card'])
        location_frame.grid(row=1, column=0, sticky='ew', pady=self.SMALL_PADDING)
        
        log_icon = tk.Label(
            location_frame,
            text="📄",
            font=("Segoe UI", int(11 * self.font_scale)),
            fg=self.colors['info'],
            bg=self.colors['card']
        )
        log_icon.pack(side='left', padx=(0, self.SMALL_PADDING))
        
        log_location_label = tk.Label(
            location_frame,
            text=f"Log file: {log_path}",
            font=("Segoe UI", int(10 * self.font_scale)),
            fg=self.colors['secondary'],
            bg=self.colors['card']
        )
        log_location_label.pack(side='left')
        
        # Button container
        btn_frame = tk.Frame(content, bg=self.colors['card'])
        btn_frame.grid(row=2, column=0, sticky='w', pady=self.SMALL_PADDING)
        
        self.view_logs_btn = self._create_button(
            btn_frame,
            "View Logs",
            self._view_logs,
            is_primary=False,
            icon="🔍"
        )
        self.view_logs_btn.pack(side='left', padx=(0, self.STANDARD_PADDING))
        
        self.clear_logs_btn = self._create_button(
            btn_frame,
            "Clear Logs",
            self._clear_logs,
            is_primary=False,
            icon="🗑️"
        )
        self.clear_logs_btn.pack(side='left')
        
        # Add tooltips
        ToolTip(self.view_logs_btn, "View and search application logs")
        ToolTip(self.clear_logs_btn, "Delete all log files (cannot be undone)")

    def _create_system_info_section(self):
        """Create system information section with card design."""
        self.system_card = self._create_card_container(
            self.frame, 
            row=3, 
            column=0, 
            sticky='ew', 
            padx=self.STANDARD_PADDING, 
            pady=self.SMALL_PADDING
        )
        
        # Section title
        self.system_title = tk.Label(
            self.system_card,
            text="System Information",
            font=("Segoe UI", int(12 * self.font_scale), "bold"),
            fg=self.colors['dark'],
            bg=self.colors['card']
        )
        self.system_title.pack(anchor='w', padx=self.STANDARD_PADDING, pady=(self.STANDARD_PADDING, self.SMALL_PADDING))
        
        # Separator
        separator = ttk.Separator(self.system_card, orient='horizontal')
        separator.pack(fill='x', padx=self.STANDARD_PADDING, pady=(0, self.SMALL_PADDING))
        
        # Content container with grid for system info
        content = tk.Frame(self.system_card, bg=self.colors['card'])
        content.pack(fill='x', expand=True, padx=self.STANDARD_PADDING, pady=(0, self.STANDARD_PADDING))
        
        # Two-column grid for system info
        info_grid = tk.Frame(content, bg=self.colors['card'])
        info_grid.pack(fill='x')
        
        # Create system info with nicer styling
        system_info = {
            "Operating System": f"{platform.system()} {platform.release()}",
            "Python Version": platform.python_version(),
            "Username": self.username,
            "App Version": "1.0.0"  # You could pull this from a version file
        }
        
        # Display in two columns
        col1 = tk.Frame(info_grid, bg=self.colors['card'])
        col1.pack(side='left', fill='y', padx=(0, self.LARGE_PADDING))
        
        col2 = tk.Frame(info_grid, bg=self.colors['card'])
        col2.pack(side='left', fill='y')
        
        # Divide the items between columns
        items = list(system_info.items())
        half = len(items) // 2
        
        # First column
        for i, (key, value) in enumerate(items[:half]):
            item_frame = tk.Frame(col1, bg=self.colors['card'])
            item_frame.pack(anchor='w', pady=self.SMALL_PADDING)
            
            key_label = tk.Label(
                item_frame,
                text=f"{key}:",
                font=("Segoe UI", int(10 * self.font_scale), "bold"),
                fg=self.colors['dark'],
                bg=self.colors['card']
            )
            key_label.pack(side='left', padx=(0, self.SMALL_PADDING))
            
            value_label = tk.Label(
                item_frame,
                text=value,
                font=("Segoe UI", int(10 * self.font_scale)),
                fg=self.colors['secondary'],
                bg=self.colors['card']
            )
            value_label.pack(side='left')
        
        # Second column
        for i, (key, value) in enumerate(items[half:]):
            item_frame = tk.Frame(col2, bg=self.colors['card'])
            item_frame.pack(anchor='w', pady=self.SMALL_PADDING)
            
            key_label = tk.Label(
                item_frame,
                text=f"{key}:",
                font=("Segoe UI", int(10 * self.font_scale), "bold"),
                fg=self.colors['dark'],
                bg=self.colors['card']
            )
            key_label.pack(side='left', padx=(0, self.SMALL_PADDING))
            
            value_label = tk.Label(
                item_frame,
                text=value,
                font=("Segoe UI", int(10 * self.font_scale)),
                fg=self.colors['secondary'],
                bg=self.colors['card']
            )
            value_label.pack(side='left')

    def _create_card_container(self, parent, row, column, sticky, padx, pady):
        """Create a card-like container with subtle shadow for sections."""
        container = tk.Frame(
            parent,
            bg=self.colors['card'],
            bd=1,
            relief="solid",
            highlightbackground=self.colors['border'],
            highlightthickness=1
        )
        container.grid(row=row, column=column, sticky=sticky, padx=padx, pady=pady)
        
        # Add subtle shadow effect
        # Note: The shadow is simulated with border color for simplicity
        
        return container

    def _create_button(self, parent, text, command, is_primary=True, icon=None, compact=False):
        """Create a modern styled button with optional icon and proper hover behavior."""
        btn_text = f"{icon} {text}" if icon else text
        
        # Scale padding based on UI scale
        padx = int((10 if compact else 15) * self.ui_scale)
        pady = int((6 if compact else 8) * self.ui_scale)
        
        # Store original colors for state management
        primary_bg = self.colors['primary']
        primary_hover_bg = self.colors['primary_dark']
        secondary_bg = self.colors['light']
        secondary_hover_bg = '#e2e6ea'
        
        btn = tk.Button(
            parent,
            text=btn_text,
            command=command,
            font=("Segoe UI", int((9 if compact else 10) * self.font_scale), "bold" if is_primary else "normal"),
            bg=primary_bg if is_primary else secondary_bg,
            fg=self.colors['white'] if is_primary else self.colors['dark'],
            activebackground=primary_hover_bg if is_primary else secondary_hover_bg,
            activeforeground=self.colors['white'] if is_primary else self.colors['dark'],
            relief='flat',
            cursor='hand2',
            pady=pady,
            padx=padx,
            borderwidth=0
        )
        
        # Create more robust hover handlers with state checking
        def on_enter(event):
            if str(btn['state']) != 'disabled':
                btn.config(background=primary_hover_bg if is_primary else secondary_hover_bg)
        
        def on_leave(event):
            if str(btn['state']) != 'disabled':
                btn.config(background=primary_bg if is_primary else secondary_bg)
        
        # Add hover effect bindings
        btn.bind('<Enter>', on_enter)
        btn.bind('<Leave>', on_leave)
        
        # Store original colors as attributes for state recovery
        btn.primary_bg = primary_bg
        btn.primary_hover_bg = primary_hover_bg
        btn.secondary_bg = secondary_bg
        btn.secondary_hover_bg = secondary_hover_bg
        btn.is_primary = is_primary
        
        return btn

    def _set_button_state(self, button, enabled=True):
        """Safely set button state while preserving hover effects."""
        if not hasattr(button, 'is_primary'):
            button.config(state=tk.NORMAL if enabled else tk.DISABLED)
            return
            
        if enabled:
            button.config(state=tk.NORMAL)
            # Reset to normal background
            bg_color = button.primary_bg if button.is_primary else button.secondary_bg
            fg_color = self.colors['white'] if button.is_primary else self.colors['dark']
            button.config(background=bg_color, foreground=fg_color)
        else:
            button.config(state=tk.DISABLED)
            # Use a consistent disabled color
            button.config(background=self.colors['disabled'])
            button.config(foreground=self.colors['disabled_text'])

    def _get_log_path(self):
        """Get the path to the log file."""
        # First check in logs directory
        log_dir = "logs"
        log_path = os.path.join(log_dir, "app.log")
        if os.path.exists(log_path):
            return log_path
            
        # Fall back to app.log in current directory
        if os.path.exists("app.log"):
            return "app.log"
            
        # Return default path even if it doesn't exist yet
        return log_path

    def _select_backup_folder(self):
        """Open a folder selection dialog and validate."""
        folder_path = filedialog.askdirectory()
        if folder_path:
            if not os.path.exists(folder_path):
                try:
                    os.makedirs(folder_path)
                    logging.info(f"Backup folder created: {folder_path}")
                except Exception as e:
                    logging.error(f"Failed to create folder: {str(e)}")
                    self._show_error_message(f"Failed to create folder: {str(e)}")
                    return
                    
            if os.access(folder_path, os.W_OK):
                # Use the settings_manager's dedicated method
                if self.settings_manager.set_backup_folder(folder_path):
                    self.settings = self.settings_manager.settings  # Update our reference
                    readable_path = str(Path(folder_path).resolve())
                    self.backup_folder_label.config(text=readable_path)
                    self._show_success_message("Backup folder updated successfully!")
                else:
                    self._show_error_message("Failed to update backup folder.")
            else:
                logging.warning("Attempted to set non-writable folder")
                self._show_error_message("Selected folder is not writable.")

    def _update_max_backups(self):
        """Update the maximum number of backups."""
        try:
            max_backups_value = int(self.max_backups_var.get())
            if max_backups_value <= 0:
                raise ValueError("Max backups must be positive")
            
            # Use the settings_manager's dedicated method
            if self.settings_manager.set("max_backups", max_backups_value):
                self.settings = self.settings_manager.settings  # Update our reference
                logging.info(f"Max backups updated to {max_backups_value}")
                self._show_success_message("Max backups updated successfully!")
            else:
                self._show_error_message("Failed to update max backups.")
                
        except ValueError as e:
            logging.error(f"Invalid max backups value: {str(e)}")
            self._show_error_message("Please enter a positive number")

    def _toggle_logging(self):
        """Toggle logging setting on checkbox change."""
        log_enabled = self.logging_var.get()
        self.settings_manager.set("logging_enabled", log_enabled)
        self.settings = self.settings_manager.settings  # Update our reference
        
        status = "enabled" if log_enabled else "disabled" 
        logging.info(f"Logging {status}")
        
        # Enable/disable log buttons based on logging state
        self._set_button_state(self.view_logs_btn, log_enabled)
        self._set_button_state(self.clear_logs_btn, log_enabled)

    def _toggle_compression(self):
        """Toggle backup compression setting."""
        compression = self.compress_var.get()
        self.settings_manager.set("compress_backups", compression)
        self.settings = self.settings_manager.settings  # Update our reference
        
        status = "enabled" if compression else "disabled"
        logging.info(f"Backup compression {status}")
        
        # Optional: show a subtle notification
        self._show_success_message(f"Backup compression {status}", duration=1000)

    def _clear_logs(self):
        """Clear log files with confirmation."""
        # Create modern confirmation dialog
        confirm = self._create_confirm_dialog(
            "Clear Logs", 
            "Are you sure you want to clear all logs?",
            "This action cannot be undone. All log history will be deleted."
        )
        
        if not confirm:
            return
            
        log_path = self._get_log_path()
        log_dir = os.path.dirname(log_path) or "."
        
        try:
            # Clear main log file
            if os.path.exists(log_path):
                with open(log_path, 'w') as f:
                    # Use centralized time utility
                    timestamp = get_formatted_time(use_utc=False)
                    f.write(f"Logs cleared on {timestamp} by {self.username}\n")
            
            # Clear rotated logs
            for rotated_log in glob.glob(f"{log_path}.*"):
                try:
                    os.remove(rotated_log)
                except:
                    pass
                    
            logging.info("Log files cleared")
            self._show_success_message("Logs cleared successfully!")
            
        except Exception as e:
            logging.error(f"Failed to clear logs: {str(e)}")
            self._show_error_message(f"Failed to clear logs: {str(e)}")

    def _view_logs(self):
        """Display logs with improved styling and filtering."""
        log_path = self._get_log_path()
        
        # Create a modern log viewer dialog
        log_window = tk.Toplevel(self.parent)
        log_window.title("Log Viewer")
        log_window.geometry(f"{int(900 * self.ui_scale)}x{int(500 * self.ui_scale)}")
        log_window.minsize(int(600 * self.ui_scale), int(400 * self.ui_scale))
        
        # Add some styling to make it look modern
        log_window.configure(bg=self.colors['background'])
        
        # Title bar
        title_frame = tk.Frame(log_window, bg=self.colors['primary'])
        title_frame.pack(fill='x')
        
        title_label = tk.Label(
            title_frame,
            text="Application Logs",
            font=("Segoe UI", int(14 * self.font_scale), "bold"),
            fg=self.colors['white'],
            bg=self.colors['primary'],
            pady=self.STANDARD_PADDING
        )
        title_label.pack(side='left', padx=self.STANDARD_PADDING)
        
        # Main content container
        content_frame = tk.Frame(log_window, bg=self.colors['background'])
        content_frame.pack(fill='both', expand=True, padx=self.STANDARD_PADDING, pady=self.STANDARD_PADDING)
        content_frame.grid_columnconfigure(0, weight=1)
        content_frame.grid_rowconfigure(2, weight=1)  # Tree view row should expand
        
        # Status bar for log info
        status_frame = tk.Frame(content_frame, bg=self.colors['white'])
        status_frame.grid(row=0, column=0, sticky='ew', padx=0, pady=(0, self.SMALL_PADDING))
        status_frame.grid_columnconfigure(0, weight=1)
        
        log_size = "0 KB"
        entry_count = 0
        
        if os.path.exists(log_path):
            size_bytes = os.path.getsize(log_path)
            log_size = format_size(size_bytes)
            
            # Count log entries
            try:
                with open(log_path, 'r', encoding='utf-8') as f:
                    entry_count = sum(1 for line in f if " - " in line)
            except:
                pass
        
        status_text = f"Log file: {log_path} | Size: {log_size} | Entries: {entry_count}"
        status_label = tk.Label(
            status_frame, 
            text=status_text,
            font=("Segoe UI", int(9 * self.font_scale)),
            fg=self.colors['secondary'],
            bg=self.colors['white'],
            anchor='w',
            padx=self.STANDARD_PADDING,
            pady=self.SMALL_PADDING
        )
        status_label.grid(row=0, column=0, sticky='w')
        
        # Filter controls
        filter_frame = tk.Frame(content_frame, bg=self.colors['white'])
        filter_frame.grid(row=1, column=0, sticky='ew', padx=0, pady=(0, self.SMALL_PADDING))
        filter_frame.grid_columnconfigure(3, weight=1)  # Make search field expand
        
        # Level filter
        level_label = tk.Label(
            filter_frame, 
            text="Level:",
            font=("Segoe UI", int(10 * self.font_scale)),
            fg=self.colors['dark'],
            bg=self.colors['white'],
            padx=self.STANDARD_PADDING,
            pady=self.SMALL_PADDING
        )
        level_label.grid(row=0, column=0)
        
        level_var = tk.StringVar(value="All")
        level_combo = ttk.Combobox(
            filter_frame, 
            textvariable=level_var,
            values=["All", "INFO", "WARNING", "ERROR", "DEBUG"],
            width=10,
            font=("Segoe UI", int(9 * self.font_scale)),
            state="readonly"
        )
        level_combo.grid(row=0, column=1, padx=(0, self.STANDARD_PADDING))
        
        # Search filter
        search_label = tk.Label(
            filter_frame, 
            text="Search:",
            font=("Segoe UI", int(10 * self.font_scale)),
            fg=self.colors['dark'],
            bg=self.colors['white'],
            pady=self.SMALL_PADDING
        )
        search_label.grid(row=0, column=2)
        
        search_var = tk.StringVar()
        search_entry = ttk.Entry(
            filter_frame, 
            textvariable=search_var, 
            font=("Segoe UI", int(9 * self.font_scale)),
            width=25
        )
        search_entry.grid(row=0, column=3, sticky='ew', padx=(0, self.STANDARD_PADDING))
        
        # Apply button
        apply_btn = self._create_button(
            filter_frame, 
            "Apply Filter",
            lambda: self._refresh_logs(tree, log_path, level_var.get(), search_var.get()),
            is_primary=True,
            icon="🔍",
            compact=True
        )
        apply_btn.grid(row=0, column=4, padx=(0, self.SMALL_PADDING))
        
        # Reset button
        reset_btn = self._create_button(
            filter_frame, 
            "Reset",
            lambda: [level_var.set("All"), search_var.set(""), 
                     self._refresh_logs(tree, log_path, "All", "")],
            is_primary=False,
            icon="↺",
            compact=True
        )
        reset_btn.grid(row=0, column=5, padx=(0, self.STANDARD_PADDING))
        
        # Create card-like container for tree view
        tree_container = tk.Frame(
            content_frame,
            bg=self.colors['white'],
            bd=1,
            relief="solid",
            highlightbackground=self.colors['border'],
            highlightthickness=1
        )
        tree_container.grid(row=2, column=0, sticky='nsew')
        tree_container.grid_columnconfigure(0, weight=1)
        tree_container.grid_rowconfigure(0, weight=1)
        
        # Set up the treeview with style
        style = ttk.Style()
        style.configure(
            "LogView.Treeview",
            background=self.colors['white'],
            foreground=self.colors['dark'],
            rowheight=int(25 * self.ui_scale),
            fieldbackground=self.colors['white'],
            font=("Segoe UI", int(9 * self.font_scale))
        )
        style.configure(
            "LogView.Treeview.Heading",
            background=self.colors['light'],
            foreground=self.colors['secondary'],
            font=("Segoe UI", int(9 * self.font_scale), "bold"),
            relief='flat',
            padding=5
        )
        
        # Create tree view
        tree = ttk.Treeview(
            tree_container,
            columns=("Time", "Level", "Message"),
            show="headings",
            style="LogView.Treeview"
        )
        
        # Scrollbars
        y_scroll = ttk.Scrollbar(tree_container, orient="vertical", command=tree.yview)
        x_scroll = ttk.Scrollbar(tree_container, orient="horizontal", command=tree.xview)
        tree.configure(yscrollcommand=y_scroll.set, xscrollcommand=x_scroll.set)
        
        tree.grid(row=0, column=0, sticky='nsew')
        y_scroll.grid(row=0, column=1, sticky='ns')
        x_scroll.grid(row=1, column=0, sticky='ew')

        tree.heading("Time", text="Time")
        tree.heading("Level", text="Level")
        tree.heading("Message", text="Message")

        tree.column("Time", width=int(150 * self.ui_scale), minwidth=int(120 * self.ui_scale))
        tree.column("Level", width=int(80 * self.ui_scale), minwidth=int(60 * self.ui_scale))
        tree.column("Message", width=int(600 * self.ui_scale), minwidth=int(200 * self.ui_scale))
        
        # Configure tag colors
        tree.tag_configure('ERROR', foreground=self.colors['danger'])
        tree.tag_configure('WARNING', foreground=self.colors['warning'])
        tree.tag_configure('INFO', foreground=self.colors['success'])
        tree.tag_configure('DEBUG', foreground=self.colors['info'])
        tree.tag_configure('even_row', background='#f8f9fa')
        tree.tag_configure('odd_row', background=self.colors['white'])
        
        # Button bar at bottom
        button_frame = tk.Frame(content_frame, bg=self.colors['background'])
        button_frame.grid(row=3, column=0, sticky='e', pady=(self.SMALL_PADDING, 0))
        
        # Refresh button
        refresh_btn = self._create_button(
            button_frame,
            "Refresh",
            lambda: self._refresh_logs(tree, log_path, level_var.get(), search_var.get()),
            is_primary=False,
            icon="🔄"
        )
        refresh_btn.pack(side='left', padx=(0, self.SMALL_PADDING))
        
        # Export button
        export_btn = self._create_button(
            button_frame,
            "Export Logs",
            lambda: self._export_logs(log_path),
            is_primary=False,
            icon="📤"
        )
        export_btn.pack(side='left', padx=(0, self.SMALL_PADDING))
        
        # Close button
        close_btn = self._create_button(
            button_frame,
            "Close",
            log_window.destroy,
            is_primary=True,
            icon="✖"
        )
        close_btn.pack(side='left')
        
        # Initial load of logs
        self._refresh_logs(tree, log_path, "All", "")
        
        # Bind key events
        search_entry.bind("<Return>", lambda event: self._refresh_logs(tree, log_path, level_var.get(), search_var.get()))
        log_window.bind("<Escape>", lambda event: log_window.destroy())
        
        # Make window modal
        log_window.transient(self.parent)
        log_window.grab_set()
        log_window.focus_set()

    def _refresh_logs(self, tree, log_path, level_filter="All", search_text=""):
        """Refresh the logs in the treeview with filtering."""
        # Clear existing items
        for item in tree.get_children():
            tree.delete(item)
            
        if not os.path.exists(log_path):
            tree.insert("", "end", values=("", "", "No log file found"), tags=("INFO",))
            return
            
        entry_count = 0
        filtered_count = 0
            
        try:
            with open(log_path, "r", encoding='utf-8') as log_file:
                for i, line in enumerate(log_file):
                    entry_count += 1
                    try:
                        parts = line.strip().split(" - ", 2)
                        if len(parts) == 3:
                            timestamp_str, level, message = parts
                            
                            # Apply level filter
                            if level_filter != "All" and level != level_filter:
                                continue
                                
                            # Apply search filter (case insensitive)
                            if search_text and search_text.lower() not in line.lower():
                                continue
                                
                            # Format timestamp for display - use the timestamp as is, 
                            # since it's already formatted from the log
                            local_time = timestamp_str
                            
                            # Row styling (alternating)
                            row_tag = 'even_row' if i % 2 == 0 else 'odd_row'
                            
                            tree.insert("", 0, values=(
                                local_time,
                                level,
                                message
                            ), tags=(level, row_tag))
                            
                            filtered_count += 1
                    except Exception:
                        # If line doesn't parse properly, show it raw
                        if not search_text or search_text.lower() in line.lower():
                            tree.insert("", 0, values=(
                                "",
                                "",
                                line.strip()
                            ))
                            filtered_count += 1
                            
            # If no entries after filtering, show a message
            if filtered_count == 0:
                filter_msg = f"No log entries match filter: Level={level_filter}"
                if search_text:
                    filter_msg += f", Search='{search_text}'"
                tree.insert("", "end", values=("", "", filter_msg), tags=("INFO",))
                
        except Exception as e:
            tree.insert("", "end", values=("", "ERROR", f"Failed to read log file: {str(e)}"), tags=("ERROR",))

    def _export_logs(self, log_path):
        """Export logs to a file."""
        if not os.path.exists(log_path):
            self._show_error_message("No log file to export")
            return
            
        # Get timestamp for filename using centralized time utility
        timestamp = get_formatted_time(use_utc=False, format_str="%Y%m%d_%H%M%S")
        default_filename = f"logs_export_{timestamp}.txt"
        
        # Ask for save location
        export_path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
            initialfile=default_filename
        )
        
        if not export_path:
            return  # User cancelled
            
        try:
            # Simple file copy
            shutil.copy2(log_path, export_path)
            self._show_success_message(f"Logs exported to {export_path}")
        except Exception as e:
            self._show_error_message(f"Failed to export logs: {str(e)}")

    def _update_ui(self):
        """Update UI elements with current settings."""
        # Backup settings
        backup_path = self.settings.get('backup_folder', '')
        readable_path = str(Path(backup_path).resolve()) if backup_path else "Not set"
        self.backup_folder_label.config(text=readable_path)
        
        self.max_backups_var.set(str(self.settings.get("max_backups", 10)))
        self.compress_var.set(self.settings.get("compress_backups", True))
        
        # Logging settings
        log_enabled = self.settings.get("logging_enabled", True)
        self.logging_var.set(log_enabled)
        
        # Update button states based on logging
        self._set_button_state(self.view_logs_btn, log_enabled)
        self._set_button_state(self.clear_logs_btn, log_enabled)

    def _create_confirm_dialog(self, title, message, detail=None):
        """Create a modern confirmation dialog."""
        # Create dialog
        dialog = tk.Toplevel(self.parent)
        dialog.transient(self.parent)
        dialog.title(title)
        
        # Dialog size and position
        dialog_width = int(400 * self.ui_scale)
        dialog_height = int(200 * self.ui_scale)
        
        # Ensure it's visible on screen
        screen_width = dialog.winfo_screenwidth()
        screen_height = dialog.winfo_screenheight()
        
        # Center on screen
        x = (screen_width - dialog_width) // 2
        y = (screen_height - dialog_height) // 2
        dialog.geometry(f"{dialog_width}x{dialog_height}+{x}+{y}")
        
        # Make dialog non-resizable
        dialog.resizable(False, False)
        
        # Modern styling
        dialog.configure(bg=self.colors['white'])
        
        # Content container with padding
        content = tk.Frame(dialog, bg=self.colors['white'], padx=int(20 * self.ui_scale), pady=int(15 * self.ui_scale))
        content.pack(fill='both', expand=True)
        
        # Warning icon
        icon_label = tk.Label(
            content,
            text="⚠️",
            font=("Segoe UI", int(36 * self.font_scale)),
            fg=self.colors['warning'],
            bg=self.colors['white']
        )
        icon_label.grid(row=0, column=0, padx=(0, int(15 * self.ui_scale)))
        
        # Frame for message and details
        text_frame = tk.Frame(content, bg=self.colors['white'])
        text_frame.grid(row=0, column=1, sticky='nsew')
        
        # Message
        message_label = tk.Label(
            text_frame,
            text=message,
            font=("Segoe UI", int(12 * self.font_scale), "bold"),
            fg=self.colors['dark'],
            bg=self.colors['white'],
            justify=tk.LEFT,
            wraplength=int(270 * self.ui_scale)
        )
        message_label.pack(anchor='w')
        
        # Details
        if detail:
            detail_label = tk.Label(
                text_frame,
                text=detail,
                font=("Segoe UI", int(10 * self.font_scale)),
                fg=self.colors['secondary'],
                bg=self.colors['white'],
                justify=tk.LEFT,
                wraplength=int(270 * self.ui_scale)
            )
            detail_label.pack(anchor='w', pady=(int(5 * self.ui_scale), 0))
        
        # Button container
        button_frame = tk.Frame(dialog, bg=self.colors['white'], pady=int(15 * self.ui_scale))
        button_frame.pack(fill='x')
        
        # Store result
        result = []
        
        # Cancel button
        cancel_btn = self._create_button(
            button_frame,
            "Cancel",
            lambda: (dialog.destroy(), result.append(False)),
            is_primary=False
        )
        cancel_btn.pack(side='right', padx=(0, int(10 * self.ui_scale)))
        
        # Confirm button
        confirm_btn = self._create_button(
            button_frame,
            "Confirm",
            lambda: (dialog.destroy(), result.append(True)),
            is_primary=True
        )
        confirm_btn.pack(side='right', padx=(0, int(5 * self.ui_scale)))
        
        # Make modal and wait for result
        dialog.protocol("WM_DELETE_WINDOW", lambda: (dialog.destroy(), result.append(False)))
        dialog.grab_set()
        dialog.focus_force()
        dialog.wait_window()
        
        # Return result
        return result and result[0]

    def _show_success_message(self, message, duration=2000):
        """Show a modern success toast notification."""
        self._show_toast_message(message, self.colors['success'], duration)

    def _show_error_message(self, message, duration=2000):
        """Show a modern error toast notification."""
        self._show_toast_message(message, self.colors['danger'], duration)

    def _show_toast_message(self, message, bg_color, duration=2000):
        """Show a modern toast notification."""
        # Close any existing toast
        if hasattr(self, 'toast_window') and self.toast_window:
            self.toast_window.destroy()
            
        # Create toast window
        self.toast_window = tk.Toplevel(self.parent)
        self.toast_window.wm_overrideredirect(True)
        
        # Position at bottom center of parent
        parent_x = self.parent.winfo_rootx()
        parent_y = self.parent.winfo_rooty()
        parent_width = self.parent.winfo_width()
        parent_height = self.parent.winfo_height()
        
        # Calculate position
        toast_width = int(300 * self.ui_scale)
        toast_height = int(50 * self.ui_scale)
        toast_x = parent_x + (parent_width - toast_width) // 2
        toast_y = parent_y + parent_height - toast_height - int(30 * self.ui_scale)
        
        self.toast_window.geometry(f"{toast_width}x{toast_height}+{toast_x}+{toast_y}")
        
        # Toast content
        toast_frame = tk.Frame(self.toast_window, bg=bg_color)
        toast_frame.pack(fill='both', expand=True)
        
        # Message
        message_label = tk.Label(
            toast_frame,
            text=message,
            font=("Segoe UI", int(11 * self.font_scale), "bold"),
            fg=self.colors['white'],
            bg=bg_color,
            padx=int(15 * self.ui_scale),
            pady=int(10 * self.ui_scale)
        )
        message_label.pack(fill='both', expand=True)
        
        # Auto-close
        self.parent.after(duration, self._close_toast)
        
    def _close_toast(self):
        """Close the toast notification."""
        if hasattr(self, 'toast_window') and self.toast_window:
            self.toast_window.destroy()
            self.toast_window = None

    def _on_frame_configure(self, event=None):
        """Handle frame resize with debounce."""
        # Debounce resize events
        if self.resize_timer:
            self.parent.after_cancel(self.resize_timer)
        
        # Schedule layout refresh after resize stops
        self.resize_timer = self.parent.after(100, self.refresh_layout)
    
    def refresh_layout(self):
        """Refresh layout on window resize or other events."""
        # Future implementation for responsive adjustments
        pass