import tkinter as tk
import os
from datetime import datetime
from utils.time_utils import get_current_times, get_current_username

class QuickCommitDialog:
    def __init__(self, file_path, settings, shared_state, version_manager, backup_manager, colors=None, ui_scale=1.0, font_scale=1.0):
        """Streamlined commit dialog with clickable last commit display."""
        self.file_path = file_path
        self.settings = settings
        self.shared_state = shared_state
        self.version_manager = version_manager
        self.backup_manager = backup_manager
        self.result = False
        self.ui_scale = ui_scale
        self.font_scale = font_scale
        
        # Use time_utils instead of hardcoded values
        self.username = get_current_username()
        self.times = get_current_times()
        self.current_time = self.times["utc"]
        
        # Modern color scheme - use passed colors if provided
        if colors:
            self.colors = colors
        else:
            # Default colors that match main app
            self.colors = {
                'primary': "#1976d2",
                'primary_dark': "#004ba0",
                'secondary': "#546e7a",
                'light': "#f5f5f5",
                'dark': "#263238",
                'white': "#ffffff",
                'border': "#cfd8dc",
                'background': "#eceff1",
                'card': "#ffffff",
                'danger': "#c62828"
            }
        
        # Calculate paddings based on scale
        self.std_padding = int(10 * self.ui_scale)
        self.small_padding = int(5 * self.ui_scale)
        
        # Get last commit message
        self.last_commit = self._get_last_commit()
        
        # Create window with dynamic sizing
        self.root = tk.Toplevel()
        self.root.title("Commit Changes")
        self.root.minsize(350, 200)
        self.root.resizable(True, True)
        self.root.configure(bg=self.colors['background'])
        
        # Card container
        self.card_frame = tk.Frame(
            self.root,
            bg=self.colors['card'],
            bd=1,
            relief="solid",
            highlightbackground=self.colors['border'],
            highlightthickness=1
        )
        self.card_frame.pack(fill="both", expand=True, padx=15, pady=15)
        
        # Main frame with padding
        self.main_frame = tk.Frame(self.card_frame, bg=self.colors['card'])
        self.main_frame.pack(fill="both", expand=True, padx=self.std_padding, pady=self.std_padding)
        
        # File name with icon
        filename = os.path.basename(file_path)
        file_frame = tk.Frame(self.main_frame, bg=self.colors['card'])
        file_frame.pack(fill="x", pady=self.small_padding)
        
        # Simple file icon based on extension
        ext = os.path.splitext(filename)[1].lower()
        icon = "📄"  # Default
        if ext in ['.jpg', '.jpeg', '.png', '.gif', '.bmp']:
            icon = "🖼️"
        elif ext in ['.py', '.js', '.html', '.css', '.java']:
            icon = "💻"
        elif ext in ['.txt', '.md']:
            icon = "📝"
        elif ext in ['.doc', '.docx']:
            icon = "📄"
        
        file_icon = tk.Label(
            file_frame, 
            text=icon, 
            font=("Segoe UI", int(16 * self.font_scale)), 
            bg=self.colors['card']
        )
        file_icon.pack(side="left")
        
        file_label = tk.Label(
            file_frame, 
            text=filename,
            font=("Segoe UI", int(12 * self.font_scale), "bold"),
            bg=self.colors['card'],
            fg=self.colors['dark']
        )
        file_label.pack(side="left", padx=self.small_padding)
        
        # Last commit section (if available) - now clickable
        if self.last_commit:
            last_commit_frame = tk.Frame(
                self.main_frame, 
                bg=self.colors['white'],
                bd=1, 
                relief="solid",
                highlightbackground=self.colors['border'],
                highlightthickness=1,
                cursor="hand2"  # Hand cursor to indicate clickability
            )
            last_commit_frame.pack(fill="x", pady=self.std_padding)
            
            # Bind click event to the frame
            last_commit_frame.bind("<Button-1>", lambda e: self._use_last_commit())
            
            last_commit_label = tk.Label(
                last_commit_frame,
                text="Last commit (click to use):",
                font=("Segoe UI", int(9 * self.font_scale)),
                bg=self.colors['white'],
                fg=self.colors['secondary'],
                anchor="w",
                cursor="hand2"  # Hand cursor to indicate clickability
            )
            last_commit_label.pack(fill="x", padx=self.std_padding, pady=(self.small_padding, 0))
            # Bind click event to the label too
            last_commit_label.bind("<Button-1>", lambda e: self._use_last_commit())
            
            last_commit_text = tk.Label(
                last_commit_frame,
                text=self.last_commit,
                font=("Segoe UI", int(10 * self.font_scale)),
                bg=self.colors['white'],
                fg=self.colors['dark'],
                anchor="w",
                wraplength=350,
                justify=tk.LEFT,
                cursor="hand2"  # Hand cursor to indicate clickability
            )
            last_commit_text.pack(fill="x", padx=self.std_padding, pady=(0, self.small_padding))
            # Bind click event to the text too
            last_commit_text.bind("<Button-1>", lambda e: self._use_last_commit())
        
        # Message label
        msg_label = tk.Label(
            self.main_frame, 
            text="Describe your changes:",
            font=("Segoe UI", int(10 * self.font_scale), "bold"),
            bg=self.colors['card'],
            fg=self.colors['dark'],
            anchor="w"
        )
        msg_label.pack(fill="x", pady=(self.std_padding, self.small_padding))
        
        # Message entry with border
        entry_frame = tk.Frame(
            self.main_frame, 
            bg=self.colors['white'],
            highlightbackground=self.colors['border'],
            highlightthickness=1
        )
        entry_frame.pack(fill="x", pady=self.small_padding)
        
        self.message_entry = tk.Entry(
            entry_frame, 
            font=("Segoe UI", int(11 * self.font_scale)),
            bd=0,
            bg=self.colors['white'],
            fg=self.colors['dark']
        )
        self.message_entry.pack(fill="x", padx=self.std_padding, pady=self.std_padding)
        self.message_entry.focus_set()
        
        # Error message area (initially empty)
        self.error_label = tk.Label(
            self.main_frame,
            text="",
            font=("Segoe UI", int(9 * self.font_scale)),
            fg=self.colors['danger'],
            bg=self.colors['card'],
            anchor="w"
        )
        self.error_label.pack(fill="x", pady=self.small_padding)
        
        # Separator
        separator = tk.Frame(self.main_frame, height=1, bg=self.colors['border'])
        separator.pack(fill="x", pady=self.std_padding)
        
        # Button frame
        btn_frame = tk.Frame(self.main_frame, bg=self.colors['card'])
        btn_frame.pack(fill="x", pady=(self.small_padding, 0))
        
        # Buttons with better styling
        self.skip_btn = self._create_button(
            btn_frame, 
            "Skip",
            self.cancel,
            is_primary=False
        )
        self.skip_btn.pack(side="right", padx=self.small_padding)
        
        self.commit_btn = self._create_button(
            btn_frame, 
            "Commit",
            self.save,
            is_primary=True
        )
        self.commit_btn.pack(side="right")
        
        # Status line with username and timestamp - using local time for display
        status_frame = tk.Frame(self.main_frame, bg=self.colors['card'])
        status_frame.pack(fill="x", pady=(self.std_padding, 0))
        
        status_label = tk.Label(
            status_frame,
            text=f"User: {self.username} | Time: {self.times['local'].strftime('%Y-%m-%d %H:%M:%S')}",
            font=("Segoe UI", int(8 * self.font_scale)),
            fg=self.colors['secondary'],
            bg=self.colors['card'],
            anchor="w"
        )
        status_label.pack(side="left")
        
        # Update UI layout
        self.root.update_idletasks()
        
        # Get natural size after packing widgets
        width = self.main_frame.winfo_reqwidth() + 60
        height = self.main_frame.winfo_reqheight() + 60
        
        # Center window after knowing its size
        self.center_window(width, height)
        
        # Make modal
        self.root.transient()
        self.root.grab_set()
        self.root.focus_force()
        
        # Bind keys
        self.root.bind("<Return>", lambda e: self.save())
        self.root.bind("<Escape>", lambda e: self.cancel())
        
        # Keep window on top
        self.root.attributes("-topmost", True)
    
    def _create_button(self, parent, text, command, is_primary=True):
        """Create a stylish button that matches the main application."""
        # Store original colors for hover effects
        primary_bg = self.colors['primary']
        primary_hover_bg = self.colors['primary_dark']
        secondary_bg = self.colors['light']
        secondary_hover_bg = '#e2e6ea'
        
        btn = tk.Button(
            parent,
            text=text,
            command=command,
            font=("Segoe UI", int(10 * self.font_scale), "bold" if is_primary else "normal"),
            bg=primary_bg if is_primary else secondary_bg,
            fg=self.colors['white'] if is_primary else self.colors['dark'],
            activebackground=primary_hover_bg if is_primary else secondary_hover_bg,
            activeforeground=self.colors['white'] if is_primary else self.colors['dark'],
            relief='flat',
            cursor='hand2',
            pady=int(8 * self.ui_scale),
            padx=int(15 * self.ui_scale),
            borderwidth=0
        )
        
        # Create hover effect handlers
        def on_enter(event):
            btn.config(background=primary_hover_bg if is_primary else secondary_hover_bg)
        
        def on_leave(event):
            btn.config(background=primary_bg if is_primary else secondary_bg)
        
        # Add hover effect bindings
        btn.bind('<Enter>', on_enter)
        btn.bind('<Leave>', on_leave)
        
        return btn
    
    def _get_last_commit(self):
        """Get the last commit message for this file."""
        try:
            # Get tracked files
            tracked_files = self.version_manager.load_tracked_files()
            normalized_path = os.path.normpath(self.file_path)
            
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
            self.message_entry.delete(0, tk.END)
            self.message_entry.insert(0, self.last_commit)
            self.message_entry.focus_set()
    
    def center_window(self, width, height):
        """Center the window on screen with dynamic size."""
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        
        # Ensure window fits on screen
        width = min(width, screen_width - 100)
        height = min(height, screen_height - 100)
        
        x = (screen_width - width) // 2
        y = (screen_height - height) // 2
        
        self.root.geometry(f"{width}x{height}+{x}+{y}")
    
    def cancel(self):
        """Cancel and close the dialog."""
        self.result = False
        self.root.destroy()
    
    def save(self):
        """Save changes."""
        message = self.message_entry.get().strip()
        if not message:
            self.error_label.config(text="Please enter a message")
            self.message_entry.focus_set()
            return
        else:
            self.error_label.config(text="")
            
        try:
            # Get tracked files
            tracked_files = self.version_manager.load_tracked_files()
            
            # Check for changes
            has_changed, current_hash, last_hash = self.version_manager.has_file_changed(
                self.file_path, tracked_files
            )
            
            if not has_changed:
                self.result = False
                self.root.destroy()
                return
                
            # Create backup
            self.backup_manager.create_backup(
                self.file_path,
                current_hash,
                self.settings
            )
            
            # Get file info - use the times we already have
            normalized_path = os.path.normpath(self.file_path)
            
            # Get metadata
            if hasattr(self.version_manager, 'get_file_metadata'):
                metadata = self.version_manager.get_file_metadata(self.file_path)
            else:
                # Basic metadata
                stat = os.stat(self.file_path)
                metadata = {
                    "size": stat.st_size,
                    "modification_time": {
                        "utc": datetime.utcfromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
                        "local": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S %Z")
                    }
                }
            
            # Update tracked files
            if normalized_path not in tracked_files:
                tracked_files[normalized_path] = {"versions": {}}
                
            tracked_files[normalized_path]["versions"][current_hash] = {
                "timestamp": self.current_time,
                "commit_message": message,
                "username": self.username,
                "metadata": metadata,
                "previous_hash": last_hash
            }
            
            # Save changes
            self.version_manager.save_tracked_files(tracked_files)
            
            # Update file monitor state
            if hasattr(self.shared_state, 'file_monitor') and self.shared_state.file_monitor:
                if hasattr(self.shared_state.file_monitor, 'update_after_commit'):
                    self.shared_state.file_monitor.update_after_commit(self.file_path, current_hash)
            
            # Notify about version change - CHANGED to update system tray menu
            self.shared_state.notify_version_commit()
            
            # Success
            self.result = True
            self.root.destroy()
            
        except Exception as e:
            # Show error
            self.error_label.config(text=f"Error: {str(e)}")
    
    def show(self):
        """Show dialog and return result."""
        self.root.wait_window()
        return self.result