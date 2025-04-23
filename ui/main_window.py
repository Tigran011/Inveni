import os
import tkinter as tk
from tkinter import ttk, messagebox
import sys

# Import centralized time utilities
from utils.time_utils import get_formatted_time, get_current_username, get_current_times

# Import pages
from ui.pages.commit_page import CommitPage
from ui.pages.restore_page import RestorePage
from ui.pages.settings_page import SettingsPage

# Import dialogs
from ui.dialogs.commit_dialog import QuickCommitDialog

class ToolTip:
    """Tooltip class with improved behavior to prevent flickering."""
    
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tooltip = None
        self.scheduled = None
        
        # Use delay to prevent flickering
        self.widget.bind("<Enter>", self.schedule_tooltip, add="+")
        self.widget.bind("<Leave>", self.hide_tooltip, add="+")
    
    def schedule_tooltip(self, event=None):
        """Schedule tooltip to appear after a short delay."""
        self.cancel_schedule()
        self.scheduled = self.widget.after(500, self.show_tooltip)
    
    def cancel_schedule(self):
        """Cancel the scheduled tooltip."""
        if self.scheduled:
            self.widget.after_cancel(self.scheduled)
            self.scheduled = None
    
    def show_tooltip(self, event=None):
        """Show tooltip window at a fixed position relative to the widget."""
        # Cancel any existing tooltip
        self.hide_tooltip()
        
        # Get widget position
        x = self.widget.winfo_rootx() + (self.widget.winfo_width() // 2)
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 5
        
        # Create tooltip window
        self.tooltip = tk.Toplevel(self.widget)
        self.tooltip.wm_overrideredirect(True)
        self.tooltip.wm_geometry(f"+{x-50}+{y}")
        
        # Create tooltip content
        label = tk.Label(
            self.tooltip, 
            text=self.text, 
            background="#ffffe0", 
            foreground="#333333",
            relief="solid", 
            borderwidth=1,
            font=("Segoe UI", 9),
            padx=5,
            pady=2
        )
        label.pack()
    
    def hide_tooltip(self, event=None):
        """Hide tooltip window."""
        self.cancel_schedule()
        if self.tooltip:
            self.tooltip.destroy()
            self.tooltip = None

class MainWindow:
    """Main application window with responsive UI."""
    
    # UI constants
    STANDARD_PADDING = 10
    MIN_WIDTH = 900
    MIN_HEIGHT = 650

    def __init__(self, root, settings_manager, shared_state, version_manager, backup_manager, file_monitor):
        """Initialize main window and UI components."""
        self.root = root
        self.settings_manager = settings_manager
        self.settings = settings_manager.settings
        self.shared_state = shared_state
        self.version_manager = version_manager
        self.backup_manager = backup_manager
        self.file_monitor = file_monitor
        
        # Set mutual references
        self.shared_state.main_app = self
        
        # Set minimum size
        self.root.minsize(self.MIN_WIDTH, self.MIN_HEIGHT)
        
        # Detect screen size and set scaling
        self._detect_screen_size()
        
        # Create styles
        self._create_styles()
        
        # Create UI
        self._create_ui()
        
        # Set up window events
        self._setup_events()

    def _detect_screen_size(self):
        """Detect screen size and set appropriate scaling values."""
        width = self.root.winfo_screenwidth()
        height = self.root.winfo_screenheight()
        
        # Set UI scale based on screen resolution
        if width <= 1366:  # Small screens
            self.ui_scale = 0.9
            self.font_scale = 0.9
        elif width <= 1920:  # Medium screens (Full HD)
            self.ui_scale = 1.0
            self.font_scale = 1.0
        else:  # Large/high-res screens
            self.ui_scale = 1.2
            self.font_scale = 1.1
        
        # Update padding based on scale
        self.SCALED_PADDING = int(self.STANDARD_PADDING * self.ui_scale)

    def _create_styles(self):
        """Create custom styles for the application."""
        self._button_styles_configured = False
        
        style = ttk.Style()
        
        # Define colors - modernized palette
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
            'highlight': "#bbdefb",     # Highlight/selection color
            'tab_selected_text': "#1e2f47"  # Light blue text for selected tabs (easy to read)
        }
        
        # Base font sizes adjusted by scale
        base_font_size = int(10 * self.font_scale)
        header_font_size = int(16 * self.font_scale)
        large_font_size = int(12 * self.font_scale)
        small_font_size = int(9 * self.font_scale)
        
        # Apply base styles
        style.configure('TFrame', background=self.colors['background'])
        style.configure('TLabel', background=self.colors['background'], font=('Segoe UI', base_font_size))
        style.configure('TButton', font=('Segoe UI', base_font_size))
        
        # Header style
        style.configure('Header.TLabel', 
                       font=('Segoe UI', header_font_size, 'bold'), 
                       foreground=self.colors['dark'])
        
        # Subheader style
        style.configure('Subheader.TLabel', 
                       font=('Segoe UI', large_font_size, 'bold'), 
                       foreground=self.colors['secondary'])
        
        # Card styles
        style.configure('Card.TFrame', 
                       background=self.colors['white'], 
                       relief='flat')
        
        # Modern notebook style with clear active indicators
        style.configure(
            'Custom.TNotebook',
            background=self.colors['background'],
            borderwidth=0,
            tabmargins=[2, 5, 2, 0],
            tabposition='n',
            padding=[10, 10]
        )

        style.configure(
            'Custom.TNotebook.Tab',
            background=self.colors['light'],
            foreground=self.colors['secondary'],
            padding=[int(20 * self.ui_scale), int(10 * self.ui_scale)],  # Scale padding
            borderwidth=1,
            font=('Segoe UI', base_font_size)
        )

        # Modified selected tab with improved text contrast
        style.map('Custom.TNotebook.Tab',
            background=[
                ('selected', self.colors['primary']),
                ('active', '#e1e9ff')  # Lighter hover state
            ],
            foreground=[
                # Changed from white to a light blue that offers better contrast
                ('selected', self.colors['tab_selected_text']),
                ('active', self.colors['primary_dark'])
            ],
            font=[
                ('selected', ('Segoe UI', base_font_size, 'bold'))
            ]
        )
        
        # Tree view style
        style.configure(
            "Treeview",
            background=self.colors['white'],
            foreground=self.colors['dark'],
            rowheight=int(25 * self.ui_scale),  # Scale row height
            fieldbackground=self.colors['white'],
            borderwidth=1,
            font=("Segoe UI", small_font_size)
        )
        
        style.configure(
            "Treeview.Heading",
            background=self.colors['light'],
            foreground=self.colors['secondary'],
            font=("Segoe UI", small_font_size, "bold"),
            relief='flat',
            padding=5
        )
        
        # Selection colors
        style.map('Treeview',
            background=[('selected', self.colors['primary'])],
            foreground=[('selected', self.colors['white'])]
        )
        
        # Custom button styles
        style.configure(
            'Primary.TButton',
            font=("Segoe UI", base_font_size, "bold"),
            background=self.colors['primary'],
            foreground=self.colors['white'],
            padding=(int(15 * self.ui_scale), int(8 * self.ui_scale))
        )
        
        # Primary button hover style
        style.map(
            'Primary.TButton',
            background=[('active', self.colors['primary_dark']), ('!active', self.colors['primary'])],
            foreground=[('active', self.colors['white']), ('!active', self.colors['white'])]
        )
        
        # Secondary button style
        style.configure(
            'Secondary.TButton',
            font=("Segoe UI", base_font_size),
            background=self.colors['light'],
            foreground=self.colors['dark'],
            padding=(int(15 * self.ui_scale), int(8 * self.ui_scale))
        )
        
        # Secondary button hover style
        style.map(
            'Secondary.TButton',
            background=[('active', '#e2e6ea'), ('!active', self.colors['light'])],
            foreground=[('active', self.colors['dark']), ('!active', self.colors['dark'])]
        )
        
        self._button_styles_configured = True

    def _create_ui(self):
        """Create the main user interface with responsive grid layout."""
        # Configure root with responsive grid
        self.root.configure(background=self.colors['background'])
        self.root.grid_columnconfigure(0, weight=1)
        self.root.grid_rowconfigure(0, weight=1)
        
        # Create main container with grid
        self.main_frame = ttk.Frame(self.root)
        self.main_frame.grid(row=0, column=0, sticky='nsew', padx=self.SCALED_PADDING, pady=self.SCALED_PADDING)
        
        # Make main_frame responsive
        self.main_frame.grid_columnconfigure(0, weight=1)
        self.main_frame.grid_rowconfigure(1, weight=1)  # Notebook gets all extra space
        self.main_frame.grid_rowconfigure(0, weight=0)  # Fixed height for top bar
        self.main_frame.grid_rowconfigure(2, weight=0)  # Fixed height for status bar
        
        # Create top bar
        self._create_top_bar()
        
        # Create content area with notebook
        self._create_notebook()
        
        # Create status bar
        self._create_status_bar()

    def _create_top_bar(self):
        """Create responsive top bar with app title and file selection."""
        self.top_bar = ttk.Frame(self.main_frame)
        self.top_bar.grid(row=0, column=0, sticky='ew', pady=(0, self.SCALED_PADDING))
        
        # Make top bar responsive
        self.top_bar.grid_columnconfigure(0, weight=1)  # Title gets extra space
        self.top_bar.grid_columnconfigure(1, weight=0)  # File controls stay fixed width
        
        # App title
        title = ttk.Label(
            self.top_bar, 
            text="Inveni File Version Manager",
            style="Header.TLabel"
        )
        title.grid(row=0, column=0, sticky='w', padx=self.SCALED_PADDING)
        
        # File selection section
        file_frame = ttk.Frame(self.top_bar)
        file_frame.grid(row=0, column=1, sticky='e', padx=self.SCALED_PADDING)
        
        current_file_label = ttk.Label(
            file_frame, 
            text="Current File:",
            font=("Segoe UI", int(10 * self.font_scale))
        )
        current_file_label.pack(side=tk.LEFT, padx=(0, 5))
        
        self.selected_file_label = ttk.Label(
            file_frame,
            text="None",
            font=("Segoe UI", int(10 * self.font_scale), "italic"),
            foreground=self.colors['secondary']
        )
        self.selected_file_label.pack(side=tk.LEFT, padx=(0, 10))
        
        # Select file button with improved handling
        self.select_file_button = ttk.Button(
            file_frame,
            text="Select File",
            command=self._select_file,
            style='Secondary.TButton'
        )
        self.select_file_button.pack(side=tk.LEFT)
        
        # Add tooltip
        ToolTip(self.select_file_button, "Choose a file to track and manage versions")

    def _create_notebook(self):
        """Create responsive notebook with tabs for different pages."""
        self.notebook = ttk.Notebook(
            self.main_frame, 
            style='Custom.TNotebook'
        )
        self.notebook.grid(row=1, column=0, sticky='nsew')
        
        # Create pages
        self.commit_page = CommitPage(
            self.notebook,
            self.version_manager, 
            self.backup_manager, 
            self.settings_manager, 
            self.shared_state,
            self.colors,
            ui_scale=self.ui_scale,
            font_scale=self.font_scale
        )
        
        self.restore_page = RestorePage(
            self.notebook,
            self.version_manager, 
            self.backup_manager, 
            self.settings_manager, 
            self.shared_state,
            self.colors,
            ui_scale=self.ui_scale,
            font_scale=self.font_scale
        )
        
        self.settings_page = SettingsPage(
            self.notebook,
            self.settings_manager, 
            self.shared_state,
            self.colors,
            ui_scale=self.ui_scale,
            font_scale=self.font_scale
        )
        
        # Add pages to notebook with icons
        self.notebook.add(self.commit_page.frame, text=" 📝 Commit")
        self.notebook.add(self.restore_page.frame, text=" 🔄 Restore")
        self.notebook.add(self.settings_page.frame, text=" ⚙️ Settings")
        
        # Bind tab change event
        self.notebook.bind("<<NotebookTabChanged>>", self._on_tab_changed)

    def _create_status_bar(self):
        """Create responsive status bar at the bottom of the window."""
        self.status_frame = ttk.Frame(
            self.main_frame,
            relief="sunken",
            borderwidth=1
        )
        self.status_frame.grid(row=2, column=0, sticky='ew', pady=(self.SCALED_PADDING, 0))
        
        # Status bar should be responsive
        self.status_frame.grid_columnconfigure(1, weight=1)  # Middle section expands
        
        # Version info
        self.version_label = ttk.Label(
            self.status_frame,
            text="Inveni v1.0",
            font=("Segoe UI", int(9 * self.font_scale)),
            foreground=self.colors['secondary'],
            padding=(self.SCALED_PADDING, self.SCALED_PADDING//2)
        )
        self.version_label.grid(row=0, column=0, sticky='w')
        
        # Status message (will be shown dynamically)
        self.status_message = ttk.Label(
            self.status_frame,
            text="Ready",
            font=("Segoe UI", int(9 * self.font_scale)),
            padding=(self.SCALED_PADDING, self.SCALED_PADDING//2)
        )
        self.status_message.grid(row=0, column=1, sticky='w', padx=(20, 0))
        
        # User info on the right - using centralized time and username utilities
        username = get_current_username()
        current_time = get_formatted_time(use_utc=False)  # Use local time for display
        
        self.user_label = ttk.Label(
            self.status_frame,
            text=f"User: {username} | {current_time}",
            font=("Segoe UI", int(9 * self.font_scale)),
            foreground=self.colors['secondary'],
            padding=(self.SCALED_PADDING, self.SCALED_PADDING//2)
        )
        self.user_label.grid(row=0, column=2, sticky='e')
        
        # Add progress bar (initially hidden)
        self.progress_bar = ttk.Progressbar(
            self.status_frame,
            mode='indeterminate',
            length=100
        )
        # Will be shown when needed

    def _setup_events(self):
        """Set up window events and callbacks."""
        # Register shared state callbacks
        self.shared_state.add_file_callback(self._update_selected_file)
        
        # Window resize event with debounce
        self.resize_timer = None
        self.root.bind("<Configure>", self._on_window_resize)
        
        # Update time in status bar periodically
        self._update_status_time()

    def _on_window_resize(self, event):
        """Handle window resize events with debouncing."""
        if event.widget == self.root:
            # Debounce resize events
            if self.resize_timer:
                self.root.after_cancel(self.resize_timer)
            
            # Schedule layout refresh after resize stops
            self.resize_timer = self.root.after(100, self._refresh_layout)

    def _refresh_layout(self):
        """Refresh layout after resize events."""
        # Update any pages that have refresh methods
        if hasattr(self.commit_page, 'refresh_layout'):
            self.commit_page.refresh_layout()
            
        if hasattr(self.restore_page, 'refresh_layout'):
            self.restore_page.refresh_layout()
            
        if hasattr(self.settings_page, 'refresh_layout'):
            self.settings_page.refresh_layout()

    def _on_tab_changed(self, event):
        """Handle notebook tab change events."""
        # Check if application is exiting
        if hasattr(self.shared_state, 'is_exiting') and self.shared_state.is_exiting:
            return
            
        try:
            current_tab = self.notebook.index(self.notebook.select())
            
            # Refresh specific tabs when selected
            if current_tab == 1:  # Restore tab
                if hasattr(self.restore_page, '_refresh_version_list'):
                    self.restore_page._refresh_version_list()
            
            # Update status message
            tab_names = ["Commit", "Restore", "Settings"]
            self.show_status(f"Switched to {tab_names[current_tab]} view")
        except Exception as e:
            # Silently handle errors during tab switch
            pass

    def _select_file(self):
        """Open file dialog to select a file."""
        from tkinter import filedialog
        
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
            self.show_status(f"Selected: {os.path.basename(file_path)}")
            self.shared_state.set_selected_file(file_path)

    def _update_selected_file(self, file_path):
        """Update UI when selected file changes."""
        if file_path and os.path.exists(file_path):
            filename = os.path.basename(file_path)
            self.selected_file_label.config(
                text=filename,
                foreground=self.colors['dark'],
                font=("Segoe UI", int(10 * self.font_scale), "bold")
            )
        else:
            self.selected_file_label.config(
                text="None",
                foreground=self.colors['secondary'],
                font=("Segoe UI", int(10 * self.font_scale), "italic")
            )

    def _update_status_time(self):
        """Update the time in the status bar."""
        # Skip update if app is exiting
        if hasattr(self.shared_state, 'is_exiting') and self.shared_state.is_exiting:
            return
            
        try:
            # Use centralized time and username utilities
            current_time = get_formatted_time(use_utc=False)  # Use local time for display
            username = get_current_username()
            self.user_label.config(text=f"User: {username} | {current_time}")
            
            # Schedule next update in 1 second
            self.root.after(1000, self._update_status_time)
        except Exception:
            # Silently handle errors during shutdown
            pass

    def show_commit_dialog(self, file_path):
        """Show commit dialog for quick changes."""
        try:
            QuickCommitDialog(
                file_path,
                self.settings,
                self.shared_state,
                self.version_manager,
                self.backup_manager,
                colors=self.colors,
                ui_scale=self.ui_scale,
                font_scale=self.font_scale
            )
            return True
        except Exception as e:
            print(f"Error showing commit dialog: {str(e)}")
            return False

    def show_status(self, message, is_progress=False, duration=3000):
        """Show status message with optional progress indicator."""
        # Update message
        self.status_message.config(text=message)
        
        # Show progress indicator if requested
        if is_progress:
            self.progress_bar.grid(row=0, column=3, padx=(0, 10))
            self.progress_bar.start(10)
            
            # Schedule to stop and hide after duration
            self.root.after(duration, lambda: (
                self.progress_bar.stop(),
                self.progress_bar.grid_remove()
            ))
        
        # Auto-clear after duration if not progress
        if not is_progress:
            self.root.after(duration, lambda: self.status_message.config(text="Ready"))

    def provide_visual_feedback(self, message, success=True, duration=3000):
        """Show a temporary visual feedback message in the current tab."""
        # Create popup
        feedback = tk.Toplevel(self.root)
        feedback.overrideredirect(True)
        
        # Position near the mouse
        x = self.root.winfo_pointerx()
        y = self.root.winfo_pointery()
        feedback.geometry(f"+{x+10}+{y+10}")
        
        # Create message with color based on success
        label = tk.Label(
            feedback,
            text=message,
            fg=self.colors['white'],
            bg=self.colors['success'] if success else self.colors['danger'],
            font=("Segoe UI", int(10 * self.font_scale), "bold"),
            padx=int(15 * self.ui_scale),
            pady=int(10 * self.ui_scale)
        )
        label.pack()
        
        # Auto-close after duration
        self.root.after(duration, feedback.destroy)
        
        # Also update status
        self.show_status(message, duration=duration)