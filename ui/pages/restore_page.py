import os
import tkinter as tk
from tkinter import messagebox, ttk
from datetime import datetime 
import threading
import time

# Updated imports for new project structure
from utils.file_utils import format_size, calculate_file_hash
from utils.time_utils import get_current_times, get_current_username, format_timestamp_dual, format_date_for_display

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

class RestorePage:
    """UI for restoring previous file versions with responsive design."""

    def __init__(self, parent, version_manager, backup_manager, settings_manager, shared_state, colors=None, ui_scale=1.0, font_scale=1.0):
        """
        Initialize restore page with necessary services and responsive design.

        Args:
            parent: Parent tkinter container
            version_manager: Service for version management
            backup_manager: Service for backup operations
            settings_manager: Service for settings management
            shared_state: Shared application state
            colors: Color palette (optional)
            ui_scale: UI scaling factor (optional)
            font_scale: Font scaling factor (optional)
        """
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
        self.backup_folder = self.settings.get("backup_folder", "backups")
        self.username = get_current_username()  # Use time_utils instead of os.getlogin()
        self.tooltip_window = None
        self.loading = False
        self.versions_data = []
        self.resize_timer = None
        self.MAX_UNAVAILABLE_VERSIONS = 10  # Limit unavailable versions to 10

        # Create UI components
        self._create_ui()

        # Register callbacks
        self.shared_state.add_file_callback(self._on_file_updated)
        self.shared_state.add_version_callback(self._refresh_version_list)

        # Initial refresh
        self._refresh_version_list()

    def _create_ui(self):
        """Create the user interface with responsive grid layout."""
        # Create main frame with grid
        self.frame = ttk.Frame(self.parent)
        self.frame.grid(row=0, column=0, sticky='nsew')

        # Make frame responsive
        self.frame.grid_columnconfigure(0, weight=1)
        self.frame.grid_rowconfigure(0, weight=0)  # Header - fixed height
        self.frame.grid_rowconfigure(1, weight=0)  # Metadata - fixed height
        self.frame.grid_rowconfigure(2, weight=1)  # Version history - flexible
        self.frame.grid_rowconfigure(3, weight=0)  # Actions - fixed height

        # Create content sections with card design
        self._create_header_section()
        self._create_metadata_section()
        self._create_version_history_section()
        self._create_action_section()

        # Register for resize events with debounce
        self.frame.bind('<Configure>', self._on_frame_configure)

        # Bind cleanup
        self.frame.bind('<Destroy>', lambda e: self._cleanup())

    def _create_header_section(self):
        """Create responsive header section with title and controls."""
        self.header_frame = self._create_card_container(
            self.frame,
            row=0,
            column=0,
            sticky='ew',
            padx=self.STANDARD_PADDING,
            pady=(self.STANDARD_PADDING, self.SMALL_PADDING)
        )

        # Header content with grid layout
        self.header_frame.grid_columnconfigure(1, weight=1)

        # Page title
        self.title_label = tk.Label(
            self.header_frame,
            text="Restore Version",
            font=("Segoe UI", int(18 * self.font_scale), "bold"),
            fg=self.colors['dark'],
            bg=self.colors['card']
        )
        self.title_label.grid(row=0, column=0, sticky='w', padx=self.STANDARD_PADDING, pady=self.STANDARD_PADDING)

        # Search and filter controls
        self.filter_frame = tk.Frame(self.header_frame, bg=self.colors['card'])
        self.filter_frame.grid(row=0, column=1, sticky='e', padx=self.STANDARD_PADDING, pady=self.STANDARD_PADDING)

        # Search entry
        self.search_var = tk.StringVar()
        self.search_frame = tk.Frame(
            self.filter_frame,
            bg=self.colors['white'],
            highlightbackground=self.colors['border'],
            highlightthickness=1,
            bd=0
        )
        self.search_frame.pack(side='left', padx=(0, self.STANDARD_PADDING))

        self.search_entry = tk.Entry(
            self.search_frame,
            textvariable=self.search_var,
            font=("Segoe UI", int(10 * self.font_scale)),
            width=20,
            bd=0,
            relief='flat',
            bg=self.colors['white']
        )
        self.search_entry.pack(side='left', padx=self.STANDARD_PADDING, pady=6)
        self.search_entry.bind("<KeyRelease>", self._filter_versions)

        # Search icon/button
        search_btn = tk.Button(
            self.search_frame,
            text="🔍",
            font=("Segoe UI", int(10 * self.font_scale)),
            bg=self.colors['white'],
            fg=self.colors['secondary'],
            bd=0,
            relief='flat',
            command=self._filter_versions
        )
        search_btn.pack(side='right', padx=(0, 5))

        # Add placeholder text
        self.search_entry.insert(0, "Search versions...")
        self.search_entry.config(fg=self.colors['secondary'])

        def on_focus_in(e):
            if self.search_entry.get() == "Search versions...":
                self.search_entry.delete(0, 'end')
                self.search_entry.config(fg=self.colors['dark'])

        def on_focus_out(e):
            if self.search_entry.get() == '':
                self.search_entry.insert(0, "Search versions...")
                self.search_entry.config(fg=self.colors['secondary'])

        self.search_entry.bind('<FocusIn>', on_focus_in)
        self.search_entry.bind('<FocusOut>', on_focus_out)

        # Filter dropdown
        self.filter_var = tk.StringVar(value="All Versions")
        self.filter_menu = ttk.Combobox(
            self.filter_frame,
            textvariable=self.filter_var,
            font=("Segoe UI", int(10 * self.font_scale)),
            state="readonly",
            width=15,
            values=["All Versions", "Available Only", "Last 7 Days", "My Versions"]
        )
        self.filter_menu.pack(side='left')
        self.filter_menu.bind("<<ComboboxSelected>>", self._filter_versions)

        # Add tooltip
        ToolTip(self.filter_menu, "Filter version history by availability or time")

    def _create_metadata_section(self):
        """Create responsive file metadata section with card design."""
        self.metadata_card = self._create_card_container(
            self.frame,
            row=1,
            column=0,
            sticky='ew',
            padx=self.STANDARD_PADDING,
            pady=self.SMALL_PADDING
        )

        # Section title
        self.metadata_title = tk.Label(
            self.metadata_card,
            text="Current File",
            font=("Segoe UI", int(12 * self.font_scale), "bold"),
            fg=self.colors['dark'],
            bg=self.colors['card']
        )
        self.metadata_title.pack(anchor='w', padx=self.STANDARD_PADDING, pady=(self.STANDARD_PADDING, self.SMALL_PADDING))

        # Separator
        separator = ttk.Separator(self.metadata_card, orient='horizontal')
        separator.pack(fill='x', padx=self.STANDARD_PADDING, pady=(0, self.SMALL_PADDING))

        # File info container
        self.file_info = tk.Frame(self.metadata_card, bg=self.colors['card'])
        self.file_info.pack(fill='x', expand=True, padx=self.STANDARD_PADDING, pady=(0, self.STANDARD_PADDING))

        # File info content with grid layout for responsive alignment
        self.file_info.grid_columnconfigure(1, weight=1)

        # File icon
        self.file_icon_label = tk.Label(
            self.file_info,
            text="📄",
            font=("Segoe UI", int(32 * self.font_scale)),
            bg=self.colors['card'],
            fg=self.colors['secondary']
        )
        self.file_icon_label.grid(row=0, column=0, rowspan=2, padx=self.STANDARD_PADDING, pady=self.STANDARD_PADDING)

        # File name with larger font
        self.file_name_label = tk.Label(
            self.file_info,
            text="No file selected",
            font=("Segoe UI", int(14 * self.font_scale), "bold"),
            fg=self.colors['dark'],
            bg=self.colors['card'],
            anchor='w'
        )
        self.file_name_label.grid(row=0, column=1, sticky='w')

        # File details with better formatting
        self.file_details_label = tk.Label(
            self.file_info,
            text="Select a file to see its details",
            font=("Segoe UI", int(9 * self.font_scale)),
            fg=self.colors['secondary'],
            bg=self.colors['card'],
            justify=tk.LEFT,
            anchor='w'
        )
        self.file_details_label.grid(row=1, column=1, sticky='w', pady=(self.SMALL_PADDING, 0))

        # Status indicator
        self.status_indicator = tk.Frame(
            self.file_info,
            bg=self.colors['secondary'],  # Default neutral color
            width=int(80 * self.ui_scale),
            height=int(5 * self.ui_scale)
        )
        self.status_indicator.grid(row=2, column=1, sticky='w', pady=(self.SMALL_PADDING, 0))

    def _create_version_history_section(self):
        """Create responsive version history section with card design."""
        self.version_card = self._create_card_container(
            self.frame,
            row=2,
            column=0,
            sticky='nsew',
            padx=self.STANDARD_PADDING,
            pady=self.SMALL_PADDING
        )

        # Section title
        self.version_title = tk.Label(
            self.version_card,
            text="Version History",
            font=("Segoe UI", int(12 * self.font_scale), "bold"),
            fg=self.colors['dark'],
            bg=self.colors['card']
        )
        self.version_title.pack(anchor='w', padx=self.STANDARD_PADDING, pady=(self.STANDARD_PADDING, self.SMALL_PADDING))

        # Separator
        separator = ttk.Separator(self.version_card, orient='horizontal')
        separator.pack(fill='x', padx=self.STANDARD_PADDING, pady=(0, self.SMALL_PADDING))

        # Status bar at top
        self.status_bar = tk.Frame(
            self.version_card,
            bg=self.colors['card'],
            bd=0
        )
        self.status_bar.pack(fill='x', padx=self.STANDARD_PADDING, pady=(0, self.SMALL_PADDING))

        # Left side: version count
        self.version_count_label = tk.Label(
            self.status_bar,
            text="No versions available",
            font=("Segoe UI", int(10 * self.font_scale)),
            fg=self.colors['secondary'],
            bg=self.colors['card']
        )
        self.version_count_label.pack(side='left')

        # Right side: refresh button
        self.refresh_btn = self._create_button(
            self.status_bar,
            "Refresh",
            self._refresh_version_list,
            is_primary=False,
            icon="🔄",
            compact=True
        )
        self.refresh_btn.pack(side='right')

        # Tree view container
        self.tree_container = tk.Frame(
            self.version_card,
            bg=self.colors['white'],
            bd=1,
            relief='solid',
            highlightbackground=self.colors['border'],
            highlightthickness=1
        )
        self.tree_container.pack(fill='both', expand=True, padx=self.STANDARD_PADDING, pady=(0, self.STANDARD_PADDING))

        # Make tree container responsive
        self.tree_container.grid_columnconfigure(0, weight=1)
        self.tree_container.grid_rowconfigure(0, weight=1)

        # Columns for our tree
        self.columns = (
            "Local Time",
            "Message",
            "User",
            "Size",
            "Modified",
            "Status"
        )

        # Create scrollbars
        y_scrollbar = ttk.Scrollbar(self.tree_container)
        y_scrollbar.grid(row=0, column=1, sticky='ns')

        x_scrollbar = ttk.Scrollbar(self.tree_container, orient='horizontal')
        x_scrollbar.grid(row=1, column=0, sticky='ew')

        # Create tree view with improved styling
        style = ttk.Style()
        style.configure(
            "ModernTree.Treeview",
            background=self.colors['white'],
            foreground=self.colors['dark'],
            rowheight=int(30 * self.ui_scale),
            fieldbackground=self.colors['white'],
            borderwidth=0,
            font=("Segoe UI", int(10 * self.font_scale))
        )

        style.configure(
            "ModernTree.Treeview.Heading",
            background=self.colors['light'],
            foreground=self.colors['secondary'],
            font=("Segoe UI", int(9 * self.font_scale), "bold"),
            relief='flat',
            padding=5
        )

        # Selection colors
        style.map('ModernTree.Treeview',
            background=[('selected', self.colors['primary'])],
            foreground=[('selected', self.colors['white'])]
        )

        # Create tree view
        self.version_tree = ttk.Treeview(
            self.tree_container,
            columns=self.columns,
            show='headings',
            style='ModernTree.Treeview',
            selectmode='browse',
            yscrollcommand=y_scrollbar.set,
            xscrollcommand=x_scrollbar.set
        )
        self.version_tree.grid(row=0, column=0, sticky='nsew')

        # Configure scrollbars
        y_scrollbar.config(command=self.version_tree.yview)
        x_scrollbar.config(command=self.version_tree.xview)

        # Configure columns
        column_widths = {
            "Local Time": int(150 * self.ui_scale),
            "Message": int(200 * self.ui_scale),
            "User": int(100 * self.ui_scale),
            "Size": int(80 * self.ui_scale),
            "Modified": int(150 * self.ui_scale),
            "Status": int(100 * self.ui_scale)
        }

        for col, width in column_widths.items():
            self.version_tree.heading(col, text=col, anchor='w')
            self.version_tree.column(col, width=width, minwidth=width, anchor='w')

        # Configure tags for available/unavailable versions
        self.version_tree.tag_configure('available', foreground=self.colors['success'])
        self.version_tree.tag_configure('unavailable', foreground=self.colors['danger'])
        self.version_tree.tag_configure('even_row', background='#f8f9fa')
        self.version_tree.tag_configure('odd_row', background=self.colors['white'])

        # Bind events
        self.version_tree.bind('<<TreeviewSelect>>', self._on_version_selected)
        self.version_tree.bind('<Double-1>', self._on_version_double_click)

        # Empty state message
        self.empty_message = tk.Label(
            self.tree_container,
            text="No versions available for this file",
            font=("Segoe UI", int(11 * self.font_scale)),
            fg=self.colors['secondary'],
            bg=self.colors['white']
        )
        # Will be shown when needed

        # Loading indicator
        self.loading_frame = tk.Frame(self.tree_container, bg=self.colors['white'])
        self.loading_label = tk.Label(
            self.loading_frame,
            text="⟳",
            font=("Segoe UI", int(24 * self.font_scale)),
            fg=self.colors['primary'],
            bg=self.colors['white']
        )
        self.loading_label.pack(pady=(int(20 * self.ui_scale), int(10 * self.ui_scale)))

        self.loading_text = tk.Label(
            self.loading_frame,
            text="Loading versions...",
            font=("Segoe UI", int(11 * self.font_scale)),
            fg=self.colors['secondary'],
            bg=self.colors['white']
        )
        self.loading_text.pack()
        # Will be shown when needed

    def _create_action_section(self):
        """Create action buttons section with responsive design."""
        self.action_card = self._create_card_container(
            self.frame,
            row=3,
            column=0,
            sticky='ew',
            padx=self.STANDARD_PADDING,
            pady=(self.SMALL_PADDING, self.STANDARD_PADDING)
        )

        # Button container with right alignment
        self.button_frame = tk.Frame(self.action_card, bg=self.colors['card'])
        self.button_frame.pack(fill='x', padx=self.STANDARD_PADDING, pady=self.STANDARD_PADDING)

        # Main restore button (right-aligned)
        self.restore_button = self._create_button(
            self.button_frame,
            "Restore Selected Version",
            self._restore_selected_version,
            is_primary=True,
            icon="♻️"
        )
        self.restore_button.pack(side='right')
        self.restore_button.config(state=tk.DISABLED)

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

    def _check_backup_exists(self, file_path: str, version_hash: str) -> bool:
        """Check if backup file exists for given version."""
        try:
            # Use backup_manager if it has the method
            if hasattr(self.backup_manager, 'check_backup_exists'):
                return self.backup_manager.check_backup_exists(file_path, version_hash)

            # Fallback to direct check
            backup_path = os.path.join(
                self.backup_folder,
                "versions",
                os.path.basename(file_path),
                f"{version_hash}.gz"
            )
            return os.path.exists(backup_path)
        except Exception:
            return False

    def _hide_tooltip(self, event=None):
        """Hide tooltip."""
        if self.tooltip_window:
            self.tooltip_window.destroy()
            self.tooltip_window = None

    def _show_loading(self):
        """Show loading indicator."""
        self.loading = True
        self.version_tree.grid_remove()
        self.empty_message.place_forget()
        self.loading_frame.place(relx=0.5, rely=0.5, anchor='center')
        self._animate_loading()

    def _hide_loading(self):
        """Hide loading indicator."""
        self.loading = False
        self.loading_frame.place_forget()

        # Show the tree if we have data
        if self.version_tree.get_children():
            self.version_tree.grid()
        else:
            self.empty_message.place(relx=0.5, rely=0.5, anchor='center')

    def _animate_loading(self):
        """Animate the loading indicator."""
        if not self.loading:
            return

        # Rotate the spinner character
        current_text = self.loading_label.cget("text")
        self.loading_label.config(text="⟲" if current_text == "⟳" else "⟳")

        # Schedule next animation frame
        self.parent.after(250, self._animate_loading)

    def _filter_versions(self, event=None):
        """Filter version list based on search and filter criteria."""
        search_text = self.search_entry.get().lower()
        filter_option = self.filter_var.get()

        # Skip the placeholder text
        if search_text == "search versions...":
            search_text = ""

        # Clear the tree
        self.version_tree.delete(*self.version_tree.get_children())

        # Get all versions from data
        if not self.versions_data:
            return

        filtered_versions = []
        current_time = get_current_times()["utc"]

        for version_hash, info in self.versions_data:
            # Apply filters
            if filter_option == "Available Only" and not self._check_backup_exists(self.selected_file, version_hash):
                continue

            if filter_option == "Last 7 Days":
                # Check if version is within last 7 days (use time_utils)
                try:
                    time_diff_days = (datetime.strptime(current_time, "%Y-%m-%d %H:%M:%S") - 
                                     datetime.strptime(info["timestamp"], "%Y-%m-%d %H:%M:%S")).days
                    if time_diff_days > 7:
                        continue
                except:
                    pass

            if filter_option == "My Versions" and info.get("username", "") != self.username:
                continue

            # Apply search
            if search_text:
                # Search in message, username, and timestamp
                message = info.get("commit_message", "").lower()
                username = info.get("username", "").lower()
                timestamp = info.get("timestamp", "").lower()

                if (search_text not in message and
                    search_text not in username and
                    search_text not in timestamp):
                    continue

            # Add to filtered list
            filtered_versions.append((version_hash, info))

        # Display filtered versions
        self._populate_version_tree(filtered_versions)

    def _populate_version_tree(self, versions_data):
        """Populate tree with version data, limiting unavailable versions to 10."""
        # Clear tree
        self.version_tree.delete(*self.version_tree.get_children())

        if not versions_data:
            self.version_tree.grid_remove()
            self.empty_message.place(relx=0.5, rely=0.5, anchor='center')
            return

        # Show tree
        self.empty_message.place_forget()
        self.version_tree.grid()

        # Sort versions by timestamp (newest first)
        sorted_versions = sorted(
            versions_data,
            key=lambda x: datetime.strptime(x[1]["timestamp"], "%Y-%m-%d %H:%M:%S") 
                if "timestamp" in x[1] else datetime.min,
            reverse=True
        )

        # Split into available and unavailable versions
        available_versions = []
        unavailable_versions = []

        for version_hash, info in sorted_versions:
            if self._check_backup_exists(self.selected_file, version_hash):
                available_versions.append((version_hash, info))
            else:
                unavailable_versions.append((version_hash, info))

        # Limit unavailable versions to MAX_UNAVAILABLE_VERSIONS
        unavailable_versions = unavailable_versions[:self.MAX_UNAVAILABLE_VERSIONS]
        
        # Combine lists with available versions first, then limited unavailable versions
        display_versions = available_versions + unavailable_versions

        # Insert versions into tree (keeping sort by timestamp)
        display_versions.sort(
            key=lambda x: datetime.strptime(x[1]["timestamp"], "%Y-%m-%d %H:%M:%S") 
                if "timestamp" in x[1] else datetime.min,
            reverse=True
        )

        # Insert versions into tree
        for i, (version_hash, info) in enumerate(display_versions):
            metadata = info.get("metadata", {})
            utc_time, local_time = format_timestamp_dual(info["timestamp"])

            # Check if backup exists
            backup_available = self._check_backup_exists(self.selected_file, version_hash)
            status_text = "Available" if backup_available else "Unavailable"

            values = (
                local_time,
                info.get("commit_message", "No message"),
                info.get("username", self.username),
                format_size(metadata.get("size", 0)),
                format_date_for_display(metadata.get("modification_time", {}).get("local", "Unknown")),
                status_text
            )

            # Row tags for styling
            tags = [version_hash]
            tags.append('available' if backup_available else 'unavailable')
            tags.append('even_row' if i % 2 == 0 else 'odd_row')

            self.version_tree.insert(
                "",
                "end",
                values=values,
                tags=tags
            )

        # Update version count
        total_available = len(available_versions)
        total_unavailable = len(unavailable_versions)
        total_hidden = len(sorted_versions) - len(display_versions)
        
        if total_hidden > 0:
            count_text = f"Showing {len(display_versions)} versions ({total_available} available, {total_hidden} older unavailable hidden)"
        else:
            count_text = f"Showing {len(display_versions)} versions ({total_available} available)"
        
        self.version_count_label.config(text=count_text)

    def _refresh_version_list(self, event=None):
        """Refresh the version list with availability indicators."""
        # Don't refresh if no file is selected
        if not self.selected_file or not os.path.exists(self.selected_file):
            self._update_file_metadata(None)
            self.version_count_label.config(text="No file selected")
            self.version_tree.delete(*self.version_tree.get_children())
            self.empty_message.place(relx=0.5, rely=0.5, anchor='center')
            self.version_tree.grid_remove()
            return

        # Show loading indicator
        self._show_loading()

        # Use threading to prevent UI freeze
        threading.Thread(target=self._load_version_data, daemon=True).start()

    def _load_version_data(self):
        """Load version data in a background thread."""
        try:
            # Use version_manager to get tracked files
            tracked_files = self.version_manager.load_tracked_files()
            normalized_path = os.path.normpath(self.selected_file)

            if normalized_path not in tracked_files:
                self.versions_data = []
                self.parent.after(0, self._update_ui_after_loading)
                return

            versions = tracked_files[normalized_path].get("versions", {})
            if not versions:
                self.versions_data = []
                self.parent.after(0, self._update_ui_after_loading)
                return

            # Convert to list of (version_hash, info) tuples
            self.versions_data = list(versions.items())

            # Update UI on main thread
            self.parent.after(0, self._update_ui_after_loading)

        except Exception as e:
            print(f"Error loading version data: {str(e)}")
            self.versions_data = []
            self.parent.after(0, lambda: self._show_error(f"Failed to load versions: {str(e)}"))

    def _update_ui_after_loading(self):
        """Update UI after version data is loaded."""
        # Hide loading
        self._hide_loading()

        # Update file metadata
        self._update_file_metadata(self.selected_file)

        # Populate the tree with all versions
        self._populate_version_tree(self.versions_data)

        # Apply filter if needed
        if self.filter_var.get() != "All Versions" or (
            self.search_entry.get() and self.search_entry.get() != "Search versions..."):
            self._filter_versions()

    def _show_error(self, message):
        """Show error message and update UI."""
        self._hide_loading()
        self.version_count_label.config(text=f"Error: {message}")
        self.empty_message.config(text=f"Error: {message}")
        self.empty_message.place(relx=0.5, rely=0.5, anchor='center')
        self.version_tree.grid_remove()

    def _update_file_metadata(self, file_path):
        """Update the file metadata display."""
        if not file_path or not os.path.exists(file_path):
            # Reset to empty state
            self.file_name_label.config(text="No file selected")
            self.file_details_label.config(text="Select a file to see its details")
            self.file_icon_label.config(text="📄", fg=self.colors['secondary'])
            self.status_indicator.config(bg=self.colors['secondary'])
            return

        try:
            # Get file metadata
            filename = os.path.basename(file_path)
            file_ext = os.path.splitext(filename)[1].lower()

            # Use version_manager to get metadata if available
            if hasattr(self.version_manager, 'get_file_metadata'):
                metadata = self.version_manager.get_file_metadata(file_path)
            else:
                # Fallback to direct stat
                stat = os.stat(file_path)
                times = get_current_times()
                metadata = {
                    "size": stat.st_size,
                    "modification_time": {
                        "local": times["local"],
                        "utc": times["utc"]
                    },
                    "file_type": file_ext
                }

            # Set file icon based on extension
            icon = "📄"  # Default
            icon_color = self.colors['primary']

            if file_ext in ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.svg']:
                icon = "🖼️"
                icon_color = self.colors['info']
            elif file_ext in ['.doc', '.docx', '.pdf', '.txt', '.md']:
                icon = "📝"
                icon_color = self.colors['primary']
            elif file_ext in ['.py', '.js', '.html', '.css', '.java']:
                icon = "💻"
                icon_color = self.colors['success']
            elif file_ext in ['.mp3', '.wav', '.ogg', '.flac']:
                icon = "🎵"
                icon_color = self.colors['warning']
            elif file_ext in ['.mp4', '.avi', '.mov', '.wmv']:
                icon = "🎬"
                icon_color = self.colors['danger']

            # Update UI elements
            self.file_name_label.config(text=filename)

            # Format details
            size_str = format_size(metadata['size'])
            mod_time = metadata['modification_time']['local']
            versions_count = len(self.versions_data) if hasattr(self, 'versions_data') else 0

            details = f"Size: {size_str}  •  Modified: {mod_time}  •  Versions: {versions_count}"
            self.file_details_label.config(text=details)

            # Update icon
            self.file_icon_label.config(text=icon, fg=icon_color)

            # Update status indicator
            has_changes = False
            if hasattr(self.shared_state, 'file_monitor'):
                file_monitor = self.shared_state.file_monitor
                if hasattr(file_monitor, 'has_changes'):
                    has_changes = file_monitor.has_changes(file_path)

            self.status_indicator.config(
                bg=self.colors['danger'] if has_changes else self.colors['success']
            )

        except Exception as e:
            self.file_name_label.config(text=os.path.basename(file_path))
            self.file_details_label.config(text=f"Error: {str(e)}")
            self.file_icon_label.config(text="⚠️", fg=self.colors['warning'])
            self.status_indicator.config(bg=self.colors['warning'])

    def _on_version_selected(self, event):
        """Handle version selection in tree view."""
        selection = self.version_tree.selection()
        if not selection:
            self._set_button_state(self.restore_button, False)
            return

        item_data = self.version_tree.item(selection[0])
        tags = item_data["tags"]

        if 'available' in tags:
            self._set_button_state(self.restore_button, True)
        else:
            self._set_button_state(self.restore_button, False)

            # Show warning tooltip
            self._show_warning_tooltip(
                "This version's backup file is not available.\n"
                "The backup may have been deleted or moved."
            )

    def _on_version_double_click(self, event):
        """Handle double click on version."""
        selection = self.version_tree.selection()
        if not selection:
            return

        item_data = self.version_tree.item(selection[0])
        tags = item_data["tags"]

        if 'available' in tags:
            # Double-clicking on a version with a backup simply shows restore confirmation
            self._restore_selected_version()

    def _show_warning_tooltip(self, message):
        """Show warning tooltip near the restore button."""
        # Position tooltip near the restore button
        x = self.restore_button.winfo_rootx() + self.restore_button.winfo_width() // 2
        y = self.restore_button.winfo_rooty() - 30

        # Close any existing tooltip
        self._hide_tooltip()

        # Create new tooltip
        self.tooltip_window = tk.Toplevel(self.parent)
        self.tooltip_window.wm_overrideredirect(True)
        self.tooltip_window.wm_geometry(f"+{x}+{y}")

        # Style the tooltip
        tooltip_frame = tk.Frame(
            self.tooltip_window,
            bg=self.colors['warning'],
            bd=0
        )
        tooltip_frame.pack(fill='both', expand=True)

        tooltip_label = tk.Label(
            tooltip_frame,
            text=message,
            font=("Segoe UI", int(9 * self.font_scale), "bold"),
            bg=self.colors['warning'],
            fg=self.colors['dark'],
            justify=tk.LEFT,
            padx=10,
            pady=8
        )
        tooltip_label.pack(fill='both')

        # Auto-hide after 3 seconds
        self.parent.after(3000, self._hide_tooltip)

    def _animate_restore_success(self):
        """Show animation for successful restore."""
        # Create success overlay
        overlay = tk.Toplevel(self.parent)
        overlay.transient(self.parent)
        overlay.overrideredirect(True)

        # Position at center of parent
        x = self.parent.winfo_rootx() + (self.parent.winfo_width() // 2)
        y = self.parent.winfo_rooty() + (self.parent.winfo_height() // 2)
        overlay.geometry(f"+{x-150}+{y-100}")

        # Create content
        success_frame = tk.Frame(overlay, bg=self.colors['success'], padx=int(40 * self.ui_scale), pady=int(30 * self.ui_scale))
        success_frame.pack(fill='both', expand=True)

        check_label = tk.Label(
            success_frame,
            text="✓",
            font=("Segoe UI", int(64 * self.font_scale)),
            fg=self.colors['white'],
            bg=self.colors['success']
        )
        check_label.pack(pady=(int(10 * self.ui_scale), 0))

        message = tk.Label(
            success_frame,
            text="Version Restored Successfully!",
            font=("Segoe UI", int(14 * self.font_scale), "bold"),
            fg=self.colors['white'],
            bg=self.colors['success']
        )
        message.pack(pady=(0, int(10 * self.ui_scale)))

        # Auto-close after 1.5 seconds
        self.parent.after(1500, overlay.destroy)

    def _restore_selected_version(self):
        """Restore a selected version with backup availability check."""
        if not self.selected_file or not self.version_tree.selection():
            return

        selected_item = self.version_tree.selection()[0]
        item_data = self.version_tree.item(selected_item)
        tags = item_data["tags"]
        values = item_data["values"]

        if not tags:
            return

        version_hash = tags[0]

        # Check if backup exists
        if not self._check_backup_exists(self.selected_file, version_hash):
            self._show_warning_tooltip(
                "This version's backup file is not available.\n"
                "The backup may have been deleted or moved."
            )
            return

        local_time, message, user, size, modified, status = values

        # Show confirmation dialog with modern styling
        confirm_dialog = self._create_improved_confirm_dialog(
            "Restore Version",
            f"Are you sure you want to restore this version?\nThis will replace the current file content.",
            {
                "Time": local_time,
                "Message": message,
                "Size": size,
                "User": user
            }
        )

        if confirm_dialog:
            try:
                # Show progress animation
                progress = self._show_progress_dialog("Restoring version...")

                # Restore in a separate thread
                def do_restore():
                    try:
                        # Mark file as being restored to prevent commit dialog
                        if hasattr(self.shared_state, 'file_monitor'):
                            self.shared_state.file_monitor.mark_file_as_restoring(self.selected_file)

                        # Use backup manager to restore version
                        self.backup_manager.restore_file_version(self.selected_file, version_hash)

                        # Wait for file operations to complete
                        time.sleep(0.2)

                        # Force reset file monitoring to ensure future changes will be detected
                        if hasattr(self.shared_state, 'file_monitor'):
                            file_monitor = self.shared_state.file_monitor

                            # Completely remove and re-add the file to monitoring
                            normalized_path = os.path.normpath(self.selected_file)
                            with file_monitor.lock:
                                # First remove from all tracking collections
                                if normalized_path in file_monitor.restoring_files:
                                    file_monitor.restoring_files.remove(normalized_path)
                                if normalized_path in file_monitor.watched_files:
                                    file_monitor.watched_files.pop(normalized_path)

                                # Add as a completely new file with fresh state
                                if os.path.exists(normalized_path):
                                    try:
                                        current_hash = calculate_file_hash(normalized_path)
                                        current_mtime = os.path.getmtime(normalized_path)
                                        current_size = os.path.getsize(normalized_path)

                                        file_monitor.watched_files[normalized_path] = {
                                            'hash': current_hash,
                                            'mtime': current_mtime,
                                            'last_check': time.time(),
                                            'is_open': False,  # File is closed after restore
                                            'size': current_size
                                        }

                                        file_monitor.active_files.add(normalized_path)

                                        # Log with current time and username
                                        times = get_current_times()
                                        print(f"[{times['utc']}] [{self.username}] *** FORCED RESET of file monitoring after restore: {normalized_path} ***")
                                    except Exception as e:
                                        times = get_current_times()
                                        print(f"[{times['utc']}] [{self.username}] Error during forced reset: {str(e)}")

                        # Hide progress and show success on main thread
                        self.parent.after(0, lambda: (
                            progress.destroy(),
                            self._animate_restore_success(),
                            self._refresh_version_list(),
                            self._update_file_metadata(self.selected_file)
                        ))
                    except Exception as e:
                        # Show error on main thread
                        error_msg = str(e)  # Capture the exception message first
                        self.parent.after(0, lambda error=error_msg: (
                            progress.destroy(),
                            messagebox.showerror("Error", f"Failed to restore version: {error}")
                        ))

                # Start restore thread
                threading.Thread(target=do_restore, daemon=True).start()

            except Exception as e:
                messagebox.showerror("Error", f"Failed to restore: {str(e)}")

    def _show_progress_dialog(self, message):
        """Show a progress dialog for long operations."""
        # Create dialog
        progress = tk.Toplevel(self.parent)
        progress.transient(self.parent)
        progress.title("Working...")
        progress.geometry(f"{int(300 * self.ui_scale)}x{int(120 * self.ui_scale)}")
        progress.resizable(False, False)

        # Position in center of parent
        x = self.parent.winfo_rootx() + (self.parent.winfo_width() // 2) - int(150 * self.ui_scale)
        y = self.parent.winfo_rooty() + (self.parent.winfo_height() // 2) - int(60 * self.ui_scale)
        progress.geometry(f"+{x}+{y}")

        # Dialog content
        content = tk.Frame(progress, padx=int(20 * self.ui_scale), pady=int(20 * self.ui_scale))
        content.pack(fill='both', expand=True)

        # Spinner
        spinner_label = tk.Label(
            content,
            text="⟳",
            font=("Segoe UI", int(24 * self.font_scale)),
            fg=self.colors['primary']
        )
        spinner_label.pack()

        # Message
        msg_label = tk.Label(
            content,
            text=message,
            font=("Segoe UI", int(11 * self.font_scale))
        )
        msg_label.pack(pady=(int(10 * self.ui_scale), 0))

        # Animate spinner
        def spin():
            current = spinner_label.cget("text")
            spinner_label.config(text="⟲" if current == "⟳" else "⟳")
            progress.after(250, spin)

        spin()

        # Prevent closing
        progress.protocol("WM_DELETE_WINDOW", lambda: None)
        progress.grab_set()

        return progress

    def _create_improved_confirm_dialog(self, title, message, details=None):
        """
        Create a larger confirmation dialog that shows all content and buttons.
        Fixes the issue where only part of the dialog was visible.
        """
        # Create dialog
        dialog = tk.Toplevel(self.parent)
        dialog.transient(self.parent)
        dialog.title(title)

        # Make dialog much larger
        dialog_width = int(500 * self.ui_scale)
        dialog_height = int(350 * self.ui_scale)

        # Ensure it's visible on screen
        screen_width = dialog.winfo_screenwidth()
        screen_height = dialog.winfo_screenheight()

        # Keep dialog within screen bounds
        dialog_width = min(dialog_width, screen_width - 100)
        dialog_height = min(dialog_height, screen_height - 100)

        # Set size and position
        x = (screen_width - dialog_width) // 2
        y = (screen_height - dialog_height) // 2
        dialog.geometry(f"{dialog_width}x{dialog_height}+{x}+{y}")

        # Make dialog resizable
        dialog.resizable(True, True)

        # Use the entire dialog for content
        main_container = tk.Frame(dialog, padx=int(30 * self.ui_scale), pady=int(30 * self.ui_scale))
        main_container.pack(fill='both', expand=True)
        main_container.grid_columnconfigure(0, weight=1)
        main_container.grid_rowconfigure(1, weight=1)  # Details area can expand

        # Top section with icon and message
        top_frame = tk.Frame(main_container)
        top_frame.grid(row=0, column=0, sticky='ew', pady=(0, int(20 * self.ui_scale)))
        top_frame.grid_columnconfigure(1, weight=1)

        # Warning icon
        icon_label = tk.Label(
            top_frame,
            text="⚠️",
            font=("Segoe UI", int(36 * self.font_scale)),
            fg=self.colors['warning']
        )
        icon_label.grid(row=0, column=0, padx=(0, int(20 * self.ui_scale)))

        # Message with plenty of space
        msg_label = tk.Label(
            top_frame,
            text=message,
            font=("Segoe UI", int(12 * self.font_scale)),
            justify=tk.LEFT,
            wraplength=int(400 * self.ui_scale),
            anchor='w'
        )
        msg_label.grid(row=0, column=1, sticky='w')

        # Details section
        if details:
            # Create a frame for details with scrolling if needed
            details_frame = tk.Frame(
                main_container,
                bd=1,
                relief='solid',
                highlightbackground=self.colors['border'],
                highlightthickness=1
            )
            details_frame.grid(row=1, column=0, sticky='nsew', pady=(0, int(20 * self.ui_scale)))
            details_frame.grid_columnconfigure(0, weight=1)
            details_frame.grid_rowconfigure(0, weight=1)

            # Inner container with padding
            inner_frame = tk.Frame(details_frame, padx=int(20 * self.ui_scale), pady=int(15 * self.ui_scale))
            inner_frame.pack(fill='both', expand=True)
            inner_frame.grid_columnconfigure(1, weight=1)

            # Add details as grid of labels
            row = 0
            for key, value in details.items():
                # Column for key
                key_label = tk.Label(
                    inner_frame,
                    text=f"{key}:",
                    font=("Segoe UI", int(11 * self.font_scale), "bold"),
                    anchor='w'
                )
                key_label.grid(row=row, column=0, sticky='nw', pady=5)

                # Column for value
                value_label = tk.Label(
                    inner_frame,
                    text=str(value),
                    font=("Segoe UI", int(11 * self.font_scale)),
                    anchor='w',
                    wraplength=int(300 * self.ui_scale)
                )
                value_label.grid(row=row, column=1, sticky='nw', padx=(15, 0), pady=5)

                row += 1

        # Button frame at very bottom, fixed height
        button_frame = tk.Frame(main_container)
        button_frame.grid(row=2, column=0, sticky='ew', pady=(10, 0))
        button_frame.grid_columnconfigure(1, weight=1)  # Push buttons to right

        # Store result
        result = []

        # Cancel button
        cancel_btn = tk.Button(
            button_frame,
            text="Cancel",
            font=("Segoe UI", int(11 * self.font_scale)),
            command=lambda: (dialog.destroy(), result.append(False)),
            bg=self.colors['light'],
            fg=self.colors['dark'],
            padx=25,
            pady=12,  # Taller buttons
            relief='flat'
        )
        cancel_btn.grid(row=0, column=1, sticky='e', padx=(0, 10))

        # Confirm button
        confirm_btn = tk.Button(
            button_frame,
            text="Restore Version",
            font=("Segoe UI", int(11 * self.font_scale), "bold"),
            command=lambda: (dialog.destroy(), result.append(True)),
            bg=self.colors['primary'],
            fg=self.colors['white'],
            padx=25,
            pady=12,  # Taller buttons
            relief='flat'
        )
        confirm_btn.grid(row=0, column=2, sticky='e')

        # Make modal and wait for result
        dialog.protocol("WM_DELETE_WINDOW", lambda: (dialog.destroy(), result.append(False)))
        dialog.grab_set()
        dialog.focus_force()
        dialog.wait_window()

        # Return result
        return result and result[0]

    def _on_file_updated(self, file_path):
        """Callback when file selection changes."""
        self.selected_file = file_path

        # Update UI based on selection
        if self.selected_file and os.path.exists(self.selected_file):
            self._update_file_metadata(file_path)
            self._refresh_version_list()
            self._set_button_state(self.restore_button, False)  # Will be enabled when version selected
        else:
            self._update_file_metadata(None)
            self.version_tree.delete(*self.version_tree.get_children())
            self.empty_message.place(relx=0.5, rely=0.5, anchor='center')
            self.version_tree.grid_remove()
            self._set_button_state(self.restore_button, False)

    def _on_frame_configure(self, event=None):
        """Handle frame resize with debounce."""
        # Debounce resize events
        if self.resize_timer:
            self.parent.after_cancel(self.resize_timer)

        # Schedule layout refresh after resize stops
        self.resize_timer = self.parent.after(100, self.refresh_layout)

    def refresh_layout(self):
        """Refresh layout on window resize or other events."""
        # Update tree column widths
        if hasattr(self, 'version_tree') and self.version_tree.winfo_exists():
            width = self.version_tree.winfo_width()
            if width > 50:  # Only adjust if tree has been rendered
                # Adjust column widths - these might need tweaking without the timeline taking space
                total_weight = 1.1 # Sum of weights below
                self.version_tree.column("Local Time", width=int(width * 0.20 / total_weight))
                self.version_tree.column("Message", width=int(width * 0.35 / total_weight))
                self.version_tree.column("User", width=int(width * 0.15 / total_weight))
                self.version_tree.column("Size", width=int(width * 0.10 / total_weight))
                self.version_tree.column("Modified", width=int(width * 0.15 / total_weight))
                self.version_tree.column("Status", width=int(width * 0.15 / total_weight))


    def _cleanup(self):
        """Clean up resources when frame is destroyed."""
        try:
            # Remove callbacks from shared state
            # Check if remove_callback exists and is callable
            if hasattr(self.shared_state, 'remove_callback') and callable(self.shared_state.remove_callback):
                # Use try-except for each removal in case one fails
                try:
                    self.shared_state.remove_callback(self._on_file_updated)
                except ValueError: # Callback might have already been removed
                    pass
                try:
                    self.shared_state.remove_callback(self._refresh_version_list)
                except ValueError:
                    pass

            # Close any open tooltip
            self._hide_tooltip()
        except Exception as e:
            # Consider logging this error instead of printing
            print(f"Error during cleanup: {e}")