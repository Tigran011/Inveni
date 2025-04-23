import os
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from datetime import datetime
import threading

# Import from utils package
from utils.time_utils import get_current_times, get_current_username, format_date_for_display
from utils.file_utils import format_size
from utils.type_handler import FileTypeHandler

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

class CommitPage:
    """UI page for committing file changes with responsive design."""
    
    def __init__(self, parent, version_manager, backup_manager, settings_manager, shared_state, colors=None, ui_scale=1.0, font_scale=1.0):
        """Initialize commit page with necessary services and responsive design."""
        self.parent = parent
        self.version_manager = version_manager
        self.backup_manager = backup_manager
        self.settings_manager = settings_manager
        self.settings = settings_manager.settings
        self.shared_state = shared_state
        self.ui_scale = ui_scale
        self.font_scale = font_scale
        
        # Define standard padding scaled to screen size
        self.STANDARD_PADDING = int(10 * self.ui_scale)
        self.SMALL_PADDING = int(5 * self.ui_scale)
        self.LARGE_PADDING = int(20 * self.ui_scale)
        
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
        
        # Initialize state
        self.selected_file = shared_state.get_selected_file()
        self.has_changes = False
        self.type_handler = FileTypeHandler()
        self.username = get_current_username()  # Use time_utils to get username
        self._hide_feedback_timer = None
        self.current_layout = "wide"
        
        # Get settings
        self.backup_folder = self.settings.get("backup_folder", "backups")
        os.makedirs(self.backup_folder, exist_ok=True)
        
        # Set up UI components
        self._create_ui()
        
        # Register callbacks for file changes
        self.shared_state.add_file_callback(self._on_file_updated)
        self.shared_state.add_monitoring_callback(self._on_file_changed)

    def _create_ui(self):
        """Create the user interface with responsive grid layout."""
        # Create main frame with grid
        self.frame = ttk.Frame(self.parent)
        self.frame.grid(row=0, column=0, sticky='nsew')
        
        # Make frame responsive
        self.frame.grid_columnconfigure(0, weight=1)
        self.frame.grid_rowconfigure(0, weight=0)  # Header - fixed height
        self.frame.grid_rowconfigure(1, weight=0)  # File section - fixed height
        self.frame.grid_rowconfigure(2, weight=1)  # Info section - flexible height
        self.frame.grid_rowconfigure(3, weight=0)  # Commit section - fixed height
        
        # Create content sections
        self._create_header_section()
        self._create_file_section()
        self._create_file_info_section()
        self._create_commit_section()
        
        # Register for resize events with debounce
        self.resize_timer = None
        self.frame.bind('<Configure>', self._on_frame_configure)
        
        # Add cleanup on frame destruction
        self.frame.bind('<Destroy>', lambda e: self._cleanup())

    def _create_header_section(self):
        """Create responsive header section with title and status."""
        self.header_frame = self._create_card_container(
            self.frame, 
            row=0, 
            column=0, 
            sticky='ew', 
            padx=self.STANDARD_PADDING, 
            pady=(self.STANDARD_PADDING, self.SMALL_PADDING)
        )
        
        # Title area
        self.title_label = tk.Label(
            self.header_frame,
            text="Commit Changes",
            font=("Segoe UI", int(18 * self.font_scale), "bold"),
            fg=self.colors['dark'],
            bg=self.colors['card']
        )
        self.title_label.pack(side='left', padx=self.STANDARD_PADDING, pady=self.STANDARD_PADDING)
        
        # Status indicator on right side
        self.status_indicator = tk.Label(
            self.header_frame,
            text="No file selected",
            font=("Segoe UI", int(10 * self.font_scale)),
            fg=self.colors['secondary'],
            bg=self.colors['card'],
            padx=self.STANDARD_PADDING
        )
        self.status_indicator.pack(side='right', padx=self.STANDARD_PADDING, pady=self.STANDARD_PADDING)

    def _create_file_section(self):
        """Create unified file section (selection or display) with card design."""
        # Create card container
        self.file_section = self._create_card_container(
            self.frame, 
            row=1, 
            column=0, 
            sticky='ew', 
            padx=self.STANDARD_PADDING, 
            pady=self.SMALL_PADDING
        )
        
        # Section title
        self.file_title = tk.Label(
            self.file_section,
            text="File Selection",
            font=("Segoe UI", int(12 * self.font_scale), "bold"),
            fg=self.colors['dark'],
            bg=self.colors['card']
        )
        self.file_title.pack(anchor='w', padx=self.STANDARD_PADDING, pady=(self.STANDARD_PADDING, self.SMALL_PADDING))
        
        # Separator
        separator = ttk.Separator(self.file_section, orient='horizontal')
        separator.pack(fill='x', padx=self.STANDARD_PADDING, pady=(0, self.SMALL_PADDING))
        
        # Content area - will be filled by either file selector or file info
        self.file_content = tk.Frame(self.file_section, bg=self.colors['card'])
        self.file_content.pack(fill='x', expand=True, padx=self.STANDARD_PADDING, pady=(0, self.STANDARD_PADDING))
        
        # Either show file info or file selector
        if self.selected_file and os.path.exists(self.selected_file):
            self._show_file_info()
        else:
            self._show_file_selector()

    def _create_file_info_section(self):
        """Create responsive file information section with card design."""
        # Create card container
        self.info_section = self._create_card_container(
            self.frame, 
            row=2, 
            column=0, 
            sticky='nsew', 
            padx=self.STANDARD_PADDING, 
            pady=self.SMALL_PADDING
        )
        
        # Section title
        self.info_title = tk.Label(
            self.info_section,
            text="File Information",
            font=("Segoe UI", int(12 * self.font_scale), "bold"),
            fg=self.colors['dark'],
            bg=self.colors['card']
        )
        self.info_title.pack(anchor='w', padx=self.STANDARD_PADDING, pady=(self.STANDARD_PADDING, self.SMALL_PADDING))
        
        # Separator
        separator = ttk.Separator(self.info_section, orient='horizontal')
        separator.pack(fill='x', padx=self.STANDARD_PADDING, pady=(0, self.SMALL_PADDING))
        
        # Status bar for change indicator
        self.status_bar = tk.Frame(
            self.info_section,
            height=int(4 * self.ui_scale),
            bg=self.colors['secondary']
        )
        self.status_bar.pack(fill='x', padx=self.STANDARD_PADDING)
        
        # Metadata area
        self.metadata_frame = tk.Frame(self.info_section, bg=self.colors['card'])
        self.metadata_frame.pack(fill='both', expand=True, padx=self.STANDARD_PADDING, pady=self.SMALL_PADDING)
        
        # Style for metadata display
        self.metadata_text = tk.Text(
            self.metadata_frame,
            height=int(10 * self.ui_scale),
            font=("Segoe UI", int(10 * self.font_scale)),
            wrap=tk.WORD,
            relief="flat",
            bd=0,
            bg=self.colors['card'],
            fg=self.colors['dark'],
            padx=self.SMALL_PADDING,
            pady=self.SMALL_PADDING
        )
        self.metadata_text.pack(side='left', fill='both', expand=True)
        
        # Add scrollbar with modern styling
        scrollbar = ttk.Scrollbar(
            self.metadata_frame,
            orient="vertical",
            command=self.metadata_text.yview
        )
        scrollbar.pack(side='right', fill='y')
        self.metadata_text.configure(yscrollcommand=scrollbar.set)
        
        # Update the metadata display
        self._update_metadata_display()

    def _create_commit_section(self):
        """Create responsive commit section with card design."""
        # Create card container
        self.commit_section = self._create_card_container(
            self.frame, 
            row=3, 
            column=0, 
            sticky='ew', 
            padx=self.STANDARD_PADDING, 
            pady=(self.SMALL_PADDING, self.STANDARD_PADDING)
        )
        
        # Section title
        self.commit_title = tk.Label(
            self.commit_section,
            text="Commit Changes",
            font=("Segoe UI", int(12 * self.font_scale), "bold"),
            fg=self.colors['dark'],
            bg=self.colors['card']
        )
        self.commit_title.pack(anchor='w', padx=self.STANDARD_PADDING, pady=(self.STANDARD_PADDING, self.SMALL_PADDING))
        
        # Separator
        separator = ttk.Separator(self.commit_section, orient='horizontal')
        separator.pack(fill='x', padx=self.STANDARD_PADDING, pady=(0, self.SMALL_PADDING))
        
        # Last commit section (if available)
        self.last_commit_frame = None
        self.last_commit = self._get_last_commit()
        
        if self.last_commit:
            self.last_commit_frame = tk.Frame(
                self.commit_section, 
                bg=self.colors['white'],
                bd=1, 
                relief="solid",
                highlightbackground=self.colors['border'],
                highlightthickness=1,
                cursor="hand2"  # Hand cursor to indicate clickability
            )
            self.last_commit_frame.pack(fill="x", padx=self.STANDARD_PADDING, pady=self.SMALL_PADDING)
            
            # Bind click event to the frame
            self.last_commit_frame.bind("<Button-1>", lambda e: self._use_last_commit())
            
            last_commit_label = tk.Label(
                self.last_commit_frame,
                text="Last commit (click to use):",
                font=("Segoe UI", int(9 * self.font_scale)),
                bg=self.colors['white'],
                fg=self.colors['secondary'],
                anchor="w",
                cursor="hand2"  # Hand cursor to indicate clickability
            )
            last_commit_label.pack(fill="x", padx=self.STANDARD_PADDING, pady=(self.SMALL_PADDING, 0))
            # Bind click event to the label too
            last_commit_label.bind("<Button-1>", lambda e: self._use_last_commit())
            
            last_commit_text = tk.Label(
                self.last_commit_frame,
                text=self.last_commit,
                font=("Segoe UI", int(10 * self.font_scale)),
                bg=self.colors['white'],
                fg=self.colors['dark'],
                anchor="w",
                wraplength=350,
                justify=tk.LEFT,
                cursor="hand2"  # Hand cursor to indicate clickability
            )
            last_commit_text.pack(fill="x", padx=self.STANDARD_PADDING, pady=(0, self.SMALL_PADDING))
            # Bind click event to the text too
            last_commit_text.bind("<Button-1>", lambda e: self._use_last_commit())
        
        # Commit message label
        self.commit_label = tk.Label(
            self.commit_section,
            text="Describe your changes:",
            font=("Segoe UI", int(10 * self.font_scale), "bold"),
            fg=self.colors['dark'],
            bg=self.colors['card']
        )
        self.commit_label.pack(anchor='w', padx=self.STANDARD_PADDING, pady=(self.SMALL_PADDING, self.SMALL_PADDING))
        
        # Modern styled commit message entry
        self.entry_frame = tk.Frame(
            self.commit_section,
            bg=self.colors['white'],
            highlightbackground=self.colors['border'],
            highlightthickness=1,
            bd=0
        )
        self.entry_frame.pack(fill='x', padx=self.STANDARD_PADDING, pady=(0, self.STANDARD_PADDING))
        
        self.commit_message_entry = tk.Entry(
            self.entry_frame,
            font=("Segoe UI", int(11 * self.font_scale)),
            bd=0,
            relief='flat',
            bg=self.colors['white'],
            fg=self.colors['dark'],
            insertbackground=self.colors['dark']
        )
        self.commit_message_entry.pack(fill='x', expand=True, padx=self.STANDARD_PADDING, pady=self.STANDARD_PADDING)
        self.commit_message_entry.bind("<Return>", self._commit_file_action)
        
        # Action buttons (commit and reset)
        self.action_frame = tk.Frame(
            self.commit_section,
            bg=self.colors['card']
        )
        self.action_frame.pack(fill='x', padx=self.STANDARD_PADDING, pady=(self.SMALL_PADDING, self.STANDARD_PADDING))
        
        # Reset button
        self.reset_btn = self._create_button(
            self.action_frame,
            "Reset",
            self._reset_form,
            is_primary=False,
            icon="🔄"
        )
        self.reset_btn.pack(side='left', padx=(0, self.SMALL_PADDING))
        
        # Commit button
        self.commit_btn = self._create_button(
            self.action_frame,
            "Commit Changes",
            self._commit_file_action,
            is_primary=True,
            icon="💾"
        )
        self.commit_btn.pack(side='right')
        
        # Add tooltip to commit button
        ToolTip(self.commit_btn, "Save the current state of your file\nwith a descriptive message")
        
        # Initially disable commit components if no file is selected
        if not self.selected_file:
            self.commit_message_entry.config(state=tk.DISABLED)
            self._set_button_state(self.commit_btn, False)
            self._set_button_state(self.reset_btn, False)

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
        return container

    def _show_file_selector(self):
        """Show file selection interface."""
        # Clear any existing content
        for widget in self.file_content.winfo_children():
            widget.destroy()
        
        # Create selector frame
        selector_frame = tk.Frame(
            self.file_content,
            bg=self.colors['card'],
            padx=self.STANDARD_PADDING,
            pady=self.STANDARD_PADDING
        )
        selector_frame.pack(fill='both', expand=True)
        
        # Icon
        icon_label = tk.Label(
            selector_frame,
            text="📄",
            font=("Segoe UI", int(36 * self.font_scale)),
            fg=self.colors['secondary'],
            bg=self.colors['card']
        )
        icon_label.pack(pady=(self.SMALL_PADDING, self.SMALL_PADDING))
        
        # Text
        text_label = tk.Label(
            selector_frame,
            text="Select a file to track",
            font=("Segoe UI", int(12 * self.font_scale)),
            fg=self.colors['secondary'],
            bg=self.colors['card']
        )
        text_label.pack(pady=(0, self.STANDARD_PADDING))
        
        # Select button
        self.select_btn = self._create_button(
            selector_frame,
            "Select File",
            self._select_file,
            is_primary=True
        )
        self.select_btn.pack(pady=self.SMALL_PADDING)

    def _show_file_info(self):
        """Show selected file information."""
        # Clear any existing content
        for widget in self.file_content.winfo_children():
            widget.destroy()
        
        # File info container
        file_info = tk.Frame(self.file_content, bg=self.colors['card'])
        file_info.pack(fill='x', expand=True)
        
        # Get file info
        category = self.type_handler.get_file_category(self.selected_file)
        icon = self.type_handler.get_category_icon(category)
        filename = os.path.basename(self.selected_file)
        filepath = os.path.dirname(self.selected_file)
        
        # File header with icon and name
        file_header = tk.Frame(file_info, bg=self.colors['card'])
        file_header.pack(fill='x', expand=True, pady=self.SMALL_PADDING)
        
        icon_label = tk.Label(
            file_header,
            text=icon,
            font=("Segoe UI", int(24 * self.font_scale)),
            bg=self.colors['card']
        )
        icon_label.pack(side='left', padx=(0, self.SMALL_PADDING))
        
        name_label = tk.Label(
            file_header,
            text=filename,
            font=("Segoe UI", int(12 * self.font_scale), "bold"),
            fg=self.colors['dark'],
            bg=self.colors['card']
        )
        name_label.pack(side='left', fill='x', expand=True, anchor='w')
        
        # Change file button
        change_btn = self._create_button(
            file_header,
            "Change",
            self._select_file,
            is_primary=False,
            icon="🔄"
        )
        change_btn.pack(side='right')
        
        # File path
        path_label = tk.Label(
            file_info,
            text=filepath,
            font=("Segoe UI", int(9 * self.font_scale)),
            fg=self.colors['secondary'],
            bg=self.colors['card'],
            anchor='w'
        )
        path_label.pack(fill='x', expand=True, pady=(self.SMALL_PADDING, self.STANDARD_PADDING))

    def _create_button(self, parent, text, command, is_primary=True, icon=None):
        """Create a modern styled button with optional icon and proper hover behavior."""
        btn_text = f"{icon} {text}" if icon else text
        
        # Store original colors for state management
        primary_bg = self.colors['primary']
        primary_hover_bg = self.colors['primary_dark']
        secondary_bg = self.colors['light']
        secondary_hover_bg = '#e2e6ea'
        
        # Scale padding based on UI scale
        padx = int(15 * self.ui_scale)
        pady = int(8 * self.ui_scale)
        
        btn = tk.Button(
            parent,
            text=btn_text,
            command=command,
            font=("Segoe UI", int(10 * self.font_scale), "bold" if is_primary else "normal"),
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

    def _get_last_commit(self):
        """Get the last commit message for this file."""
        try:
            if not self.selected_file:
                return None
                
            # Get tracked files
            tracked_files = self.version_manager.load_tracked_files()
            normalized_path = os.path.normpath(self.selected_file)
            
            if normalized_path in tracked_files:
                versions = tracked_files[normalized_path].get("versions", {})
                if versions:
                    # Find the latest version
                    latest_version = None
                    latest_timestamp = None
                    
                    for version_hash, info in versions.items():
                        timestamp = info.get("timestamp", "")
                        if not latest_timestamp or timestamp > latest_timestamp:
                            latest_timestamp = timestamp
                            latest_version = info
                    
                    if latest_version:
                        return latest_version.get("commit_message", "")
            
            return None
        except Exception:
            return None
    
    def _use_last_commit(self):
        """Use the last commit message when clicked."""
        if self.last_commit:
            self.commit_message_entry.delete(0, tk.END)
            self.commit_message_entry.insert(0, self.last_commit)
            self.commit_message_entry.focus_set()

    def _get_backup_count(self, file_path):
        """Get actual backup count for a file."""
        try:
            normalized_path = os.path.normpath(file_path)
            tracked_files = self.version_manager.load_tracked_files()
            
            if normalized_path in tracked_files:
                # Count the versions in the tracked file data
                versions = tracked_files[normalized_path].get("versions", {})
                return len(versions)
            return 0
        except Exception:
            return 0

    def _reset_form(self):
        """Reset the commit form."""
        self.commit_message_entry.delete(0, tk.END)

    def _select_file(self):
        """Open file dialog to select a file."""
        file_path = filedialog.askopenfilename(
            title="Select File to Track",
            filetypes=[
                ("All files", "*.*"),
                ("Text files", "*.txt"),
                ("Python files", "*.py"),
                ("Documents", "*.doc;*.docx;*.pdf"),
                ("Images", "*.jpg;*.jpeg;*.png;*.gif")
            ]
        )
        if file_path:
            # Disable UI elements during loading
            if hasattr(self, 'select_btn') and self.select_btn.winfo_exists():
                self._set_button_state(self.select_btn, False)
            self.commit_message_entry.config(state=tk.DISABLED)
            self._set_button_state(self.commit_btn, False)
            
            self.shared_state.set_selected_file(file_path)
            normalized_path = os.path.normpath(file_path)
            
            # Use version manager to get tracked files
            tracked_files = self.version_manager.load_tracked_files()
            
            def enable_ui():
                if os.path.exists(file_path):
                    self.commit_message_entry.config(state=tk.NORMAL)
                    self._set_button_state(self.commit_btn, True)
                    self._set_button_state(self.reset_btn, True)
                self._update_metadata_display()
                # Update last commit
                self.last_commit = self._get_last_commit()
                self._update_last_commit_display()
            
            # Set up monitoring
            file_monitor = self.shared_state.file_monitor
            if file_monitor:
                if normalized_path in tracked_files and hasattr(file_monitor, 'add_new_file'):
                    file_monitor.add_new_file(normalized_path)
                else:
                    file_monitor.set_file(file_path)
            
            # Schedule UI update
            self.parent.after(100, enable_ui)
        else:
            self.shared_state.set_selected_file(None)
            if self.shared_state.file_monitor:
                self.shared_state.file_monitor.set_file(None)

    def _update_last_commit_display(self):
        """Update the last commit display section."""
        # Remove existing last commit frame if it exists
        if self.last_commit_frame and self.last_commit_frame.winfo_exists():
            self.last_commit_frame.destroy()
            self.last_commit_frame = None
        
        if self.last_commit:
            self.last_commit_frame = tk.Frame(
                self.commit_section, 
                bg=self.colors['white'],
                bd=1, 
                relief="solid",
                highlightbackground=self.colors['border'],
                highlightthickness=1,
                cursor="hand2"  # Hand cursor to indicate clickability
            )
            self.last_commit_frame.pack(fill="x", padx=self.STANDARD_PADDING, pady=self.SMALL_PADDING)
            
            # Bind click event to the frame
            self.last_commit_frame.bind("<Button-1>", lambda e: self._use_last_commit())
            
            last_commit_label = tk.Label(
                self.last_commit_frame,
                text="Last commit (click to use):",
                font=("Segoe UI", int(9 * self.font_scale)),
                bg=self.colors['white'],
                fg=self.colors['secondary'],
                anchor="w",
                cursor="hand2"  # Hand cursor to indicate clickability
            )
            last_commit_label.pack(fill="x", padx=self.STANDARD_PADDING, pady=(self.SMALL_PADDING, 0))
            # Bind click event to the label too
            last_commit_label.bind("<Button-1>", lambda e: self._use_last_commit())
            
            last_commit_text = tk.Label(
                self.last_commit_frame,
                text=self.last_commit,
                font=("Segoe UI", int(10 * self.font_scale)),
                bg=self.colors['white'],
                fg=self.colors['dark'],
                anchor="w",
                wraplength=350,
                justify=tk.LEFT,
                cursor="hand2"  # Hand cursor to indicate clickability
            )
            last_commit_text.pack(fill="x", padx=self.STANDARD_PADDING, pady=(0, self.SMALL_PADDING))
            # Bind click event to the text too
            last_commit_text.bind("<Button-1>", lambda e: self._use_last_commit())

    def _on_file_changed(self, file_path: str, has_changes: bool) -> None:
        """Handle file change detection."""
        if file_path == self.selected_file:
            self.has_changes = has_changes
            # Schedule UI update on main thread
            self.parent.after(0, self._update_metadata_display)
            
            # Change status bar color based on changes
            if has_changes and hasattr(self, 'status_bar'):
                self.status_bar.config(bg=self.colors['danger'])
            elif hasattr(self, 'status_bar'):
                self.status_bar.config(bg=self.colors['success'])
                
            # Update status indicator in header
            status_text = "Modified" if has_changes else "No changes"
            status_color = self.colors['danger'] if has_changes else self.colors['success']
            self.status_indicator.config(text=status_text, fg=status_color)

    def _update_metadata_display(self):
        """Update the metadata display with file information."""
        if not self.selected_file or not os.path.exists(self.selected_file):
            self._show_empty_metadata()
            return

        try:
            # Get metadata through the version manager
            file_path = self.selected_file
            metadata = self._get_file_metadata(file_path)
            
            # Get the actual backup count from the version manager
            current_backups = self._get_backup_count(file_path)
            # Get max backups from settings as requested
            max_backups = self.settings.get('max_backups', 5)
            
            category = self.type_handler.get_file_category(file_path)
            category_icon = self.type_handler.get_category_icon(category)
            
            change_status = "Modified" if self.has_changes else "No changes"
            status_color = self.colors['danger'] if self.has_changes else self.colors['success']
            
            # Get current time using time_utils
            times = get_current_times()
            
            # Update file section
            self._show_file_info()
            
            # Create a well-formatted metadata display
            info_text = ""
            
            # Header with file name and icon
            info_text += f"{category_icon} {os.path.basename(file_path)}\n\n"
            
            # Status section
            info_text += f"Status: {change_status}\n"
            info_text += f"Type: {category.value}\n"
            info_text += f"Size: {format_size(metadata['size'])}\n\n"
            
            # Times section
            info_text += "Time Information\n"
            info_text += f"├─ Modified (UTC): {metadata['modification_time']['utc']}\n"
            info_text += f"├─ Modified (Local): {metadata['modification_time']['local']}\n"
            info_text += f"└─ Current Time: {format_date_for_display(times['local'])}\n\n"
            
            # Version control section
            info_text += "Version Control\n"
            info_text += f"├─ Backups: {current_backups}/{max_backups}\n"
            info_text += f"└─ Tracked by: {self.username}\n"
            
            self.metadata_text.config(state=tk.NORMAL)
            self.metadata_text.delete(1.0, tk.END)
            self.metadata_text.insert(tk.END, info_text)
            
            # Style sections
            self._apply_text_styles()
            
            self.metadata_text.config(state=tk.DISABLED)
            
            # Update status bar
            if hasattr(self, 'status_bar'):
                self.status_bar.config(bg=status_color)
            
        except Exception as e:
            self._show_error_metadata(str(e))

    def _show_empty_metadata(self):
        """Show empty state for metadata display."""
        empty_text = (
            "No file selected\n\n"
            "Please select a file to view its information and commit changes."
        )
        
        self.metadata_text.config(state=tk.NORMAL)
        self.metadata_text.delete(1.0, tk.END)
        self.metadata_text.insert(tk.END, empty_text)
        self.metadata_text.config(state=tk.DISABLED)
        
        # Gray status bar for empty state
        if hasattr(self, 'status_bar'):
            self.status_bar.config(bg=self.colors['secondary'])
            
        # Update status indicator
        self.status_indicator.config(text="No file selected", fg=self.colors['secondary'])

    def _show_error_metadata(self, error_message):
        """Show error state for metadata display."""
        error_text = (
            "Error retrieving file information\n\n"
            f"Details: {error_message}"
        )
        
        self.metadata_text.config(state=tk.NORMAL)
        self.metadata_text.delete(1.0, tk.END)
        self.metadata_text.insert(tk.END, error_text)
        self.metadata_text.config(state=tk.DISABLED)
        
        # Red status bar for error state
        if hasattr(self, 'status_bar'):
            self.status_bar.config(bg=self.colors['danger'])
            
        # Update status indicator
        self.status_indicator.config(text="Error", fg=self.colors['danger'])

    def _apply_text_styles(self):
        """Apply text styles to metadata display."""
        # Find and style sections
        self.metadata_text.tag_configure(
            "header", 
            font=("Segoe UI", int(12 * self.font_scale), "bold"),
            foreground=self.colors['dark']
        )
        
        self.metadata_text.tag_configure(
            "section_title", 
            font=("Segoe UI", int(11 * self.font_scale), "bold"),
            foreground=self.colors['secondary']
        )
        
        self.metadata_text.tag_configure(
            "status_modified", 
            foreground=self.colors['danger'],
            font=("Segoe UI", int(10 * self.font_scale), "bold")
        )
        
        self.metadata_text.tag_configure(
            "status_ok", 
            foreground=self.colors['success'],
            font=("Segoe UI", int(10 * self.font_scale), "bold")
        )
        
        # Apply header style to first line
        self.metadata_text.tag_add("header", "1.0", "1.end")
        
        # Apply section titles
        text = self.metadata_text.get("1.0", "end")
        lines = text.split("\n")
        line_num = 1
        
        for i, line in enumerate(lines):
            # Section titles (lines without indentation and without a colon)
            if line and ":" not in line and not line.startswith("├─") and not line.startswith("└─"):
                if i > 0:  # Skip the header which already has a style
                    self.metadata_text.tag_add("section_title", f"{line_num}.0", f"{line_num}.end")
            
            # Status line
            if line.startswith("Status:"):
                if "Modified" in line:
                    self.metadata_text.tag_add("status_modified", f"{line_num}.8", f"{line_num}.end")
                else:
                    self.metadata_text.tag_add("status_ok", f"{line_num}.8", f"{line_num}.end")
            
            line_num += 1

    def _get_file_metadata(self, file_path):
        """Get file metadata using either version manager or direct file access."""
        if hasattr(self.version_manager, 'get_file_metadata'):
            return self.version_manager.get_file_metadata(file_path)
        
        # Fallback to direct file access using os module
        stat = os.stat(file_path)
        return {
            "size": stat.st_size,
            "modification_time": {
                "utc": datetime.utcfromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
                "local": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S %Z")
            },
            "username": self.username
        }

    def _commit_file_action(self, event=None):
        """Handle the commit action with feedback."""
        if not self.selected_file or not os.path.exists(self.selected_file):
            self._show_feedback("No valid file selected!", success=False)
            return

        commit_message = self.commit_message_entry.get().strip()
        if not commit_message:
            self._show_feedback("Please enter a commit message!", success=False)
            return

        # Show progress UI
        self._show_progress_indicator("Committing changes...")
        
        # Use threading to prevent UI freeze for larger files
        threading.Thread(target=self._perform_commit, args=(commit_message,), daemon=True).start()

    def _perform_commit(self, commit_message):
        """Perform the actual commit operation in background thread."""
        try:
            # Use version manager to check for changes
            tracked_files = self.version_manager.load_tracked_files()
            has_changed, current_hash, last_hash = self.version_manager.has_file_changed(
                self.selected_file, 
                tracked_files
            )
            
            if not has_changed:
                # Ask for confirmation on main thread
                def ask_confirmation():
                    response = messagebox.askyesno(
                        "No Changes", 
                        "No changes detected. Create backup anyway?"
                    )
                    if response:
                        self._continue_commit(commit_message, current_hash, last_hash, tracked_files)
                    else:
                        self._hide_progress_indicator()
                
                self.parent.after(0, ask_confirmation)
            else:
                # Continue with commit
                self._continue_commit(commit_message, current_hash, last_hash, tracked_files)
                
        except Exception as e:
            # Show error on main thread
            error_msg = str(e)
            self.parent.after(0, lambda error=error_msg: self._show_feedback(
                f"Failed to commit: {error}", success=False
            ))

    def _continue_commit(self, commit_message, current_hash, last_hash, tracked_files):
        """Continue with commit operation after checks."""
        try:
            # Create backup using backup manager
            backup_path = self.backup_manager.create_backup(
                self.selected_file, 
                current_hash, 
                self.settings
            )
            
            # Get metadata
            metadata = self._get_file_metadata(self.selected_file)
            times = get_current_times()
            normalized_path = os.path.normpath(self.selected_file)
            
            # Update tracked files
            is_first_commit = normalized_path not in tracked_files
            
            if is_first_commit:
                tracked_files[normalized_path] = {"versions": {}}

            tracked_files[normalized_path]["versions"][current_hash] = {
                "timestamp": times['utc'],
                "commit_message": commit_message,
                "username": self.username,
                "metadata": metadata,
                "previous_hash": last_hash
            }
            
            # Save tracked files
            self.version_manager.save_tracked_files(tracked_files)
            
            # Start monitoring if first commit
            if is_first_commit and self.shared_state.file_monitor and hasattr(self.shared_state.file_monitor, 'add_new_file'):
                self.shared_state.file_monitor.add_new_file(normalized_path)
            
            # Clear entry and update
            self.commit_message_entry.delete(0, tk.END)
            
            # CHANGED: Use notify_version_commit instead of notify_version_change to refresh system tray
            self.shared_state.notify_version_commit()
            
            if self.shared_state.file_monitor:
                self.shared_state.file_monitor.refresh_tracked_files()
            
            # Hide progress and show success
            self._hide_progress_indicator()
            self._show_feedback("Changes committed successfully!", success=True)
            
            # Update UI
            self.last_commit = commit_message
            self._update_last_commit_display()
            self._update_metadata_display()
            
        except Exception as e:
            error_msg = str(e)
            self._hide_progress_indicator()
            self.parent.after(0, lambda error=error_msg: self._show_feedback(
                f"Failed to commit: {error}", success=False
            ))

    def _show_progress_indicator(self, message):
        """Show progress indicator with message."""
        if not hasattr(self, 'progress_overlay'):
            # Create progress overlay
            self.progress_overlay = tk.Frame(
                self.frame,
                bg=self.colors['white'],
                bd=1,
                relief='solid'
            )
            
            # Position it centered
            self.progress_overlay.place(
                relx=0.5, rely=0.5,
                anchor='center',
                width=int(300 * self.ui_scale), height=int(100 * self.ui_scale)
            )
            
            # Add spinner (animated gif or text-based)
            self.progress_label = tk.Label(
                self.progress_overlay,
                text="⟳",
                font=("Segoe UI", int(24 * self.font_scale)),
                fg=self.colors['primary'],
                bg=self.colors['white']
            )
            self.progress_label.pack(pady=(int(10 * self.ui_scale), int(5 * self.ui_scale)))
            
            # Add message
            self.progress_message = tk.Label(
                self.progress_overlay,
                text=message,
                font=("Segoe UI", int(11 * self.font_scale)),
                fg=self.colors['dark'],
                bg=self.colors['white']
            )
            self.progress_message.pack()
            
            # Start animation
            self._animate_spinner()
        else:
            self.progress_message.config(text=message)
            self.progress_overlay.lift()

    def _animate_spinner(self):
        """Animate the spinner in the progress indicator."""
        if hasattr(self, 'progress_label') and self.progress_label.winfo_exists():
            # Rotate the spinner character
            spinner_chars = "⟳⟲"
            current = self.progress_label.cget("text")
            next_char = spinner_chars[1] if current == spinner_chars[0] else spinner_chars[0]
            self.progress_label.config(text=next_char)
            
            # Continue animation if progress overlay exists
            if hasattr(self, 'progress_overlay') and self.progress_overlay.winfo_exists():
                self.parent.after(250, self._animate_spinner)

    def _hide_progress_indicator(self):
        """Hide the progress indicator."""
        if hasattr(self, 'progress_overlay') and self.progress_overlay.winfo_exists():
            self.progress_overlay.destroy()
            if hasattr(self, 'progress_overlay'):
                delattr(self, 'progress_overlay')

    def _show_feedback(self, message, success=True):
        """Show feedback message to user."""
        # Hide progress if showing
        self._hide_progress_indicator()
        
        # Configure look based on success/failure
        bg_color = self.colors['success'] if success else self.colors['danger']
        
        # Create feedback UI if doesn't exist
        if not hasattr(self, 'feedback_frame'):
            self.feedback_frame = tk.Frame(
                self.header_frame,
                bg=bg_color,
                padx=int(15 * self.ui_scale),
                pady=int(8 * self.ui_scale)
            )
            self.feedback_frame.pack(side='right', padx=(int(10 * self.ui_scale), 0))
            
            self.feedback_label = tk.Label(
                self.feedback_frame,
                text=message,
                font=("Segoe UI", int(10 * self.font_scale), "bold"),
                fg=self.colors['white'],
                bg=bg_color
            )
            self.feedback_label.pack()
            
            # Auto-hide after 3 seconds
            self._hide_feedback_timer = self.parent.after(3000, self._hide_feedback)
        else:
            # Update existing feedback
            self.feedback_frame.config(bg=bg_color)
            self.feedback_label.config(text=message, bg=bg_color)
            self.feedback_frame.pack()
            
            # Reset auto-hide timer
            if self._hide_feedback_timer:
                self.parent.after_cancel(self._hide_feedback_timer)
            self._hide_feedback_timer = self.parent.after(3000, self._hide_feedback)

    def _hide_feedback(self):
        """Hide the feedback message."""
        if hasattr(self, 'feedback_frame') and self.feedback_frame.winfo_exists():
            self.feedback_frame.pack_forget()

    def _on_file_updated(self, file_path):
        """Update UI when file selection changes."""
        self.selected_file = file_path
        
        # Always try to add the file to monitoring if it exists
        if file_path and os.path.exists(file_path):
            normalized_path = os.path.normpath(file_path)
            tracked_files = self.version_manager.load_tracked_files()
            
            if self.shared_state.file_monitor:
                # If the file is already tracked, make sure it's being monitored
                if normalized_path in tracked_files and hasattr(self.shared_state.file_monitor, 'add_new_file'):
                    self.shared_state.file_monitor.add_new_file(normalized_path)
                else:
                    self.shared_state.file_monitor.set_file(file_path)
            
            # Enable UI elements
            self.commit_message_entry.config(state=tk.NORMAL)
            self._set_button_state(self.commit_btn, True)
            self._set_button_state(self.reset_btn, True)
            
            # Update file display
            self._show_file_info()
            
            # Update last commit
            self.last_commit = self._get_last_commit()
            self._update_last_commit_display()
        else:
            if self.shared_state.file_monitor:
                self.shared_state.file_monitor.set_file(None)
            
            # Disable UI elements
            self.commit_message_entry.config(state=tk.DISABLED)
            self._set_button_state(self.commit_btn, False)
            self._set_button_state(self.reset_btn, False)
            
            # Show file selector instead of file display
            self._show_file_selector()
        
        # Update metadata display
        self._update_metadata_display()

    def refresh_layout(self):
        """Refresh layout on window resize or other events."""
        # Update any size-dependent elements
        if hasattr(self, 'frame') and self.frame.winfo_exists():
            self.frame.update_idletasks()
            
            # Get current width
            width = self.frame.winfo_width()
            
            # Check if we need to change layout
            new_layout = "wide"
            if width < 600:
                new_layout = "narrow"
            elif width < 900:
                new_layout = "medium"
            
            # Only update if layout changed
            if new_layout != self.current_layout:
                self.current_layout = new_layout
                self._apply_responsive_layout(new_layout)

    def _apply_responsive_layout(self, layout_type):
        """Apply responsive layout based on width."""
        # Update text wrapping
        if layout_type == "narrow":
            # Narrow layout adjustments
            self.metadata_text.config(width=40)
        elif layout_type == "medium":
            # Medium layout adjustments
            self.metadata_text.config(width=60)
        else:
            # Wide layout adjustments
            self.metadata_text.config(width=80)

    def _on_frame_configure(self, event=None):
        """Handle frame resize with debounce."""
        # Debounce resize events
        if self.resize_timer:
            self.parent.after_cancel(self.resize_timer)
        
        # Schedule layout refresh after resize stops
        self.resize_timer = self.parent.after(100, self.refresh_layout)

    def _cleanup(self):
        """Clean up resources when frame is destroyed."""
        # Remove callbacks
        try:
            if hasattr(self.shared_state, 'remove_callback'):
                self.shared_state.remove_callback(self._on_file_updated)
                self.shared_state.remove_callback(self._on_file_changed)
        except Exception as e:
            print(f"Error during callback cleanup: {e}")
        
        # Cancel any pending timers
        if hasattr(self, '_hide_feedback_timer') and self._hide_feedback_timer:
            try:
                self.parent.after_cancel(self._hide_feedback_timer)
            except:
                pass
        
        if hasattr(self, 'resize_timer') and self.resize_timer:
            try:
                self.parent.after_cancel(self.resize_timer)
            except:
                pass