import tkinter as tk
from tkinter import messagebox
import os
import sys
import threading
import time
from PIL import Image, ImageDraw
import pystray
import argparse
from datetime import datetime
import tempfile
import atexit

sys.path.append(os.path.abspath(os.path.dirname(__file__)))

# Single instance implementation with file lock for better reliability
class SingleInstanceChecker:
    """Ensures only one instance of the application runs at a time using file locking."""
    
    def __init__(self, unique_id="inveni_file_manager_lock"):
        """Initialize with a unique ID for this application."""
        self.unique_id = unique_id
        self.lockfile = os.path.join(tempfile.gettempdir(), f"{self.unique_id}.lock")
        self.lockfd = None
        
    def is_another_instance_running(self):
        """Check if another instance is already running using file locking."""
        try:
            # If lock file exists but is stale (contains a PID that no longer exists)
            if os.path.exists(self.lockfile):
                with open(self.lockfile, 'r') as f:
                    old_pid = f.read().strip()
                    try:
                        # Check if process with this PID exists
                        old_pid = int(old_pid)
                        # Windows-specific process check
                        if sys.platform == 'win32':
                            import ctypes
                            kernel32 = ctypes.windll.kernel32
                            handle = kernel32.OpenProcess(1, 0, old_pid)
                            if handle == 0:
                                # Process doesn't exist, remove stale lock
                                os.remove(self.lockfile)
                            else:
                                kernel32.CloseHandle(handle)
                                # Try to signal the other instance
                                self._signal_existing_instance()
                                return True
                        # Unix process check
                        else:
                            import signal
                            os.kill(old_pid, 0)  # This raises OSError if process doesn't exist
                            # Process exists, try to signal it
                            self._signal_existing_instance()
                            return True
                    except (ValueError, OSError):
                        # Invalid PID or process doesn't exist, remove stale lock
                        os.remove(self.lockfile)
            
            # Create lock file with current PID
            with open(self.lockfile, 'w') as f:
                f.write(str(os.getpid()))
            
            # Register cleanup on exit
            atexit.register(self._cleanup)
            
            # Successfully created lock, no other instance is running
            return False
            
        except Exception as e:
            print(f"Error in single instance check: {e}")
            # In case of error, assume no other instance is running
            return False
    
    def _signal_existing_instance(self):
        """Signal the existing instance to show its window."""
        try:
            # Create signal file
            signal_file = os.path.join(tempfile.gettempdir(), f"{self.unique_id}.signal")
            with open(signal_file, 'w') as f:
                f.write(f"SHOW_WINDOW|{os.getpid()}|{time.time()}")
            print(f"Signal file created at: {signal_file}")
            return True
        except Exception as e:
            print(f"Error signaling existing instance: {e}")
            return False
    
    def _cleanup(self):
        """Clean up the lock file on exit."""
        try:
            if os.path.exists(self.lockfile):
                os.remove(self.lockfile)
        except:
            pass
    
    def check_for_signals(self, show_callback):
        """Check for signals from other instances periodically."""
        signal_file = os.path.join(tempfile.gettempdir(), f"{self.unique_id}.signal")
        
        def check_signal_thread():
            last_modified = 0
            while True:
                try:
                    if os.path.exists(signal_file):
                        # Get file modification time
                        mod_time = os.path.getmtime(signal_file)
                        if mod_time > last_modified:
                            # Signal file was recently modified
                            last_modified = mod_time
                            
                            # Check signal content
                            with open(signal_file, 'r') as f:
                                signal_data = f.read().strip()
                            
                            # Process signal
                            parts = signal_data.split('|')
                            if len(parts) >= 1 and parts[0] == "SHOW_WINDOW":
                                print("Received show window signal")
                                if show_callback:
                                    # Call in main thread
                                    if hasattr(show_callback, '__self__') and hasattr(show_callback.__self__, 'after'):
                                        show_callback.__self__.after(0, show_callback)
                                    else:
                                        show_callback()
                except Exception as e:
                    print(f"Error checking for signals: {e}")
                finally:
                    # Check every second
                    time.sleep(1)
        
        # Start signal checking in background thread
        signal_thread = threading.Thread(target=check_signal_thread, daemon=True)
        signal_thread.start()

# Add resource path function for PyInstaller compatibility
def resource_path(relative_path):
    """Get absolute path to resource, works for dev and for PyInstaller"""
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = getattr(sys, '_MEIPASS', os.path.abspath(os.path.dirname(__file__)))
    except Exception:
        base_path = os.path.abspath(os.path.dirname(__file__))
    
    return os.path.join(base_path, relative_path)

# Import core components
from core.settings import SettingsManager
from core.version_manager import VersionManager
from core.backup_manager import BackupManager
from core.file_monitor import FileMonitor

# Import shared state
from models.shared_state import SharedState

# Import UI
from ui.main_window import MainWindow

# Import utils
from utils.time_utils import get_current_times, get_formatted_time, get_current_username
from utils.type_handler import FileTypeHandler

# Define icon paths properly with resource_path for PyInstaller compatibility
ICON_MAIN = resource_path(os.path.join("resources", "icons", "inveni_icon.ico"))
ICON_TASKBAR = resource_path(os.path.join("resources", "icons", "inveni_icon.ico"))
ICON_TRAY = resource_path(os.path.join("resources", "icons", "inveni_icon.ico"))
ICON_DIALOG = resource_path(os.path.join("resources", "icons", "inveni_icon.ico")) 

# Helper for timestamp formatting
def get_timestamp_str():
    """Get a formatted timestamp string for logging."""
    try:
        # Try to use utc_iso if available in get_current_times()
        times = get_current_times()
        if 'utc_iso' in times:
            return times['utc_iso']
        elif 'utc' in times:
            # If only utc is available, format it
            return times['utc'].strftime("%Y-%m-%d %H:%M:%S")
        else:
            # Fallback to simple datetime formatting
            return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        # Last resort fallback
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

class InveniApp:
    """Main application class with system tray integration."""
    
    def __init__(self):
        """Initialize the application and core components."""
        # Set DPI awareness for Windows
        try:
            from ctypes import windll
            windll.shcore.SetProcessDpiAwareness(1)
        except:
            pass
            
        # Track tray state
        self.tray_icon = None
        self.tray_thread = None
        self.tray_active = False  # Track if tray is already created
        self.pending_changes = 0
        self.files_with_changes = set()
            
        # Initialize window
        self.root = tk.Tk()
        self.root.title("Inveni - File Version Manager")
        
        # Override close button to minimize to tray
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        
        # Set window icon - Try taskbar icon first, then main icon
        try:
            if os.path.exists(ICON_TASKBAR):
                self.root.iconbitmap(ICON_TASKBAR)
                self.icon_path = ICON_TASKBAR
                print(f"Using taskbar icon: {ICON_TASKBAR}")
            elif os.path.exists(ICON_MAIN):
                self.root.iconbitmap(ICON_MAIN)
                self.icon_path = ICON_MAIN
                print(f"Using main icon: {ICON_MAIN}")
            elif os.path.exists("assets/icon.ico"):
                self.root.iconbitmap("assets/icon.ico")
                self.icon_path = "assets/icon.ico"
                print("Using assets/icon.ico fallback")
            else:
                self.icon_path = None
                print("Could not find any application icons")
        except Exception as e:
            print(f"Could not load icon: {e}")
            self.icon_path = None
        
        # Initialize core components
        self.settings_manager = SettingsManager()
        self.shared_state = SharedState()

        self.shared_state.app_icon_path = ICON_DIALOG
        
        # Add methods to SharedState for system tray updates
        def notify_system_tray_update(status):
            self.update_tray_status(status)
            
        def notify_version_commit():
            # Call this after a file is committed to update the recent files menu
            self.refresh_tray_menu()
        
        self.shared_state.notify_system_tray_update = notify_system_tray_update
        self.shared_state.notify_version_commit = notify_version_commit  # NEW: Connect version commits to tray refresh
        
        # Initialize version and backup managers
        self.version_manager = VersionManager(
            self.settings_manager.settings.get("backup_folder", "backups")
        )
        
        self.backup_manager = BackupManager(
            self.settings_manager.settings.get("backup_folder", "backups"), 
            self.version_manager
        )
        
        # Initialize main window first
        self.app = MainWindow(
            self.root,
            self.settings_manager,
            self.shared_state,
            self.version_manager,
            self.backup_manager,
            None  # Pass None for file_monitor initially
        )
        
        # Set the main_app reference in shared state
        self.shared_state.main_app = self.app
        
        # Now initialize file monitor with proper references
        self.file_monitor = FileMonitor(
            callback=self.on_file_changed,
            settings=self.settings_manager.settings,
            shared_state=self.shared_state,
            version_manager=self.version_manager
        )
        
        # Connect file monitor to main window and shared state
        self.app.file_monitor = self.file_monitor
        self.shared_state.file_monitor = self.file_monitor
        
        # Initialize utilities
        self.file_type_handler = FileTypeHandler()
        
        # Flag to indicate app is being destroyed
        self.is_exiting = False
        
        # Set up system tray
        self.setup_system_tray()
        
        # Load existing tracked files
        try:
            tracked_files = self.version_manager.load_tracked_files()
            for file_path in tracked_files:
                if os.path.exists(file_path):
                    self.file_monitor.set_file(file_path)
        except Exception as e:
            print(f"Error loading tracked files: {e}")
            
        # Log startup with dynamic username from time_utils
        current_username = get_current_username()
        print(f"[{get_timestamp_str()}] [{current_username}] Inveni started with system tray support")

    def on_file_changed(self, file_path, has_changed):
        """Handle file change notifications with tray update."""
        # Skip if we're exiting
        if self.is_exiting:
            return
            
        # Call the original notification function
        self.shared_state.notify_file_changed(file_path, has_changed)
            
    def setup_system_tray(self):
        """Set up system tray icon and menu."""
        try:
            # If we're already setting up the tray or exiting, don't do it again
            if self.tray_active or self.is_exiting:
                return
                
            # Set flag to prevent multiple concurrent setups
            self.tray_active = True
            
            # If previous tray exists, stop it 
            if self.tray_icon is not None:
                try:
                    # Don't try to join the thread if we're on it
                    current_thread = threading.current_thread()
                    if self.tray_thread and current_thread is not self.tray_thread:
                        self.tray_icon.stop()
                        if self.tray_thread.is_alive():
                            self.tray_thread.join(timeout=1.0)
                    else:
                        # Just stop it without joining
                        self.tray_icon.stop()
                except Exception as e:
                    print(f"Error stopping previous tray icon: {e}")
            
            # Function to create tray icon with status indicators
            def create_icon():
                # Try to load the specific tray icon first, then fallback in order
                if os.path.exists(ICON_TRAY):
                    icon_path = ICON_TRAY
                    print(f"Using tray icon: {ICON_TRAY}")
                elif self.icon_path and os.path.exists(self.icon_path):
                    icon_path = self.icon_path
                    print(f"Using fallback icon for tray: {self.icon_path}")
                else:
                    icon_path = None
                    print("No icons found, using generated icon for tray")
                
                if icon_path:
                    try:
                        # For .ico files we need special handling
                        if icon_path.endswith('.ico'):
                            # Convert to PNG first if it's an ICO file
                            image = Image.open(icon_path)
                            image = image.convert('RGBA')
                        else:
                            image = Image.open(icon_path)
                    except Exception as e:
                        print(f"Error loading icon - using default: {e}")
                        image = self._create_default_icon()
                else:
                    image = self._create_default_icon()
                
                # Add change indicator if needed
                if self.pending_changes > 0:
                    try:
                        draw = ImageDraw.Draw(image)
                        
                        # Calculate position (bottom right corner)
                        width, height = image.size
                        circle_size = min(width, height) // 3
                        x = width - circle_size - 2
                        y = height - circle_size - 2
                        
                        # Draw red circle
                        draw.ellipse(
                            (x, y, x + circle_size, y + circle_size),
                            fill='red'
                        )
                        
                        # Add number if more than one change
                        if self.pending_changes > 1:
                            x_text = x + circle_size // 2 - 4
                            y_text = y + circle_size // 2 - 4
                            draw.text(
                                (x_text, y_text),
                                str(min(self.pending_changes, 9)),
                                fill='white'
                            )
                    except Exception as e:
                        print(f"Error drawing notification indicator: {e}")
                
                return image
                
            # Get recent files for menu
            recent_files = self.get_recent_files()
            
            # Create menu items based on current state - SIMPLIFIED as requested
            menu_items = [
                pystray.MenuItem('Open Inveni', self.show_window),
            ]
            
            # Add recent files submenu if available
            if recent_files:
                recent_menu_items = []
                for file_path in recent_files[:5]:  # Limit to 5 recent files
                    try:
                        file_name = os.path.basename(file_path)
                        # Create a proper callback function for each file
                        def create_callback(path):
                            return lambda _: self.select_file_from_tray(path)
                        
                        recent_menu_items.append(
                            pystray.MenuItem(file_name, create_callback(file_path))
                        )
                    except Exception as e:
                        print(f"Error adding recent file to menu: {e}")
                
                if recent_menu_items:
                    menu_items.append(
                        pystray.MenuItem('Recent Files', pystray.Menu(*recent_menu_items))
                    )
            
            # Add exit item (all other options removed as requested)
            menu_items.append(pystray.MenuItem('Exit', self.exit_app))
            
            # Create the tray icon
            self.tray_icon = pystray.Icon(
                "Inveni",
                create_icon(),
                "Inveni File Versioning",
                menu=pystray.Menu(*menu_items)
            )
            
            # Run the tray icon in a separate thread
            self.tray_thread = threading.Thread(
                target=self.tray_icon.run,
                daemon=True
            )
            self.tray_thread.start()
            
            # Use dynamic username from time_utils
            current_username = get_current_username()
            print(f"[{get_timestamp_str()}] [{current_username}] System tray integration activated")
            
        except Exception as e:
            print(f"Failed to set up system tray: {e}")
        finally:
            # Reset flag after setup is complete or failed
            self.tray_active = False
    
    def refresh_tray_menu(self):
        """Refresh the system tray menu to show updated recent files."""
        try:
            # If we're exiting, don't update
            if self.is_exiting:
                return
                
            # Delay slightly to ensure version data is saved
            time.sleep(0.2)
                
            # Only update if tray exists and we're not already updating
            if hasattr(self, 'tray_icon') and self.tray_icon is not None and not self.tray_active:
                # Check if icon is alive before updating
                if self.tray_thread and self.tray_thread.is_alive():
                    # Reset and recreate the tray icon with fresh menu
                    self.setup_system_tray()
                    
                    # Use dynamic username from time_utils
                    current_username = get_current_username()
                    print(f"[{get_timestamp_str()}] [{current_username}] Refreshed tray menu with latest files")
        except Exception as e:
            print(f"Error refreshing tray menu: {e}")
    
    def select_file_from_tray(self, file_path):
        """Select a file from the system tray menu."""
        try:
            # Don't process if we're shutting down
            if self.is_exiting:
                return
            
            # Use dynamic username from time_utils
            current_username = get_current_username()
            print(f"[{get_timestamp_str()}] [{current_username}] Selecting file from tray: {file_path}")
            
            # First make the window visible
            self.show_window()
            
            # Use the built-in method to set the selected file via shared state
            # This triggers the UI update through registered callbacks
            self.root.after(300, lambda: self.shared_state.set_selected_file(file_path))
            
            # Show status in the app
            if hasattr(self.app, 'show_status'):
                self.root.after(350, lambda: self.app.show_status(
                    f"Selected: {os.path.basename(file_path)}"
                ))
                
        except Exception as e:
            print(f"Error selecting file from tray: {e}")
    
    def get_recent_files(self):
        """Get list of recently accessed files."""
        try:
            tracked_files = self.version_manager.load_tracked_files()
            
            # Sort files by last accessed time if available
            recent_files = []
            for file_path, data in tracked_files.items():
                if os.path.exists(file_path):
                    try:
                        last_time = data.get('last_accessed', 0)
                        if not last_time and 'versions' in data:
                            # Use latest version timestamp if available
                            versions = data.get('versions', {})
                            if versions:
                                last_time = max(v.get('timestamp', 0) for v in versions.values())
                        
                        recent_files.append((file_path, last_time))
                    except Exception:
                        recent_files.append((file_path, 0))
            
            # Sort by time (newest first) and return just the paths
            recent_files.sort(key=lambda x: x[1], reverse=True)
            return [path for path, _ in recent_files]
        except Exception as e:
            print(f"Error getting recent files: {e}")
            return []
            
    def _create_default_icon(self):
        """Create a default icon if the icon file isn't available."""
        image = Image.new('RGBA', (64, 64), color=(0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        
        # Draw a more polished "I" icon with better colors
        # Blue background similar to Inveni branding
        draw.rectangle((5, 5, 59, 59), fill=(0, 120, 212))
        # White "I" symbol
        draw.rectangle((25, 15, 39, 49), fill=(255, 255, 255))
        
        return image
    
    def update_tray_status(self, status=None):
        """Update the tray icon to reflect current status."""
        try:
            # If we're exiting, don't update
            if self.is_exiting:
                return
                
            # If specific status is provided from FileMonitor, use it
            if status:
                self.pending_changes = status.get('pending_changes', self.pending_changes)
                self.files_with_changes = set(status.get('files_with_changes', []))
            
            # Only update if tray exists and we're not already updating
            if hasattr(self, 'tray_icon') and self.tray_icon is not None and not self.tray_active:
                # Check if icon is alive before updating
                if self.tray_thread and self.tray_thread.is_alive():
                    # Reset and recreate the tray icon
                    self.setup_system_tray()
        except Exception as e:
            print(f"Error updating tray status: {e}")
    
    def on_close(self):
        """Handle window close event - minimize to tray."""
        # Don't process if we're already exiting
        if self.is_exiting:
            return
            
        should_minimize = self.settings_manager.settings.get("minimize_to_tray", True)
        
        if should_minimize:
            self.root.withdraw()  # Hide the window instead of destroying
            # Show balloon notification
            if hasattr(self, 'tray_icon') and self.tray_icon is not None:
                try:
                    self.tray_icon.notify(
                        "Inveni is still running",
                        "File monitoring continues in background."  # Shortened message
                    )
                except Exception as e:
                    print(f"Could not show notification: {e}")
        else:
            self.exit_app()
    
    def show_window(self, *args):
        """Show the main application window."""
        # Don't process if we're exiting
        if self.is_exiting:
            return
            
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()
    
    def exit_app(self, *args):
        """Properly exit the application."""
        try:
            # Set exiting flag to prevent further updates
            if self.is_exiting:  # Already exiting, don't duplicate
                return
                
            self.is_exiting = True
            
            # Use dynamic username from time_utils
            current_username = get_current_username()
            print(f"[{get_timestamp_str()}] [{current_username}] Inveni exiting")
            
            # Disable all event handlers that might trigger UI updates
            try:
                # 1. Unbind window resize events
                self.root.unbind("<Configure>")
                
                # 2. Unbind notebook tab change events
                if hasattr(self.app, 'notebook'):
                    try:
                        self.app.notebook.unbind("<<NotebookTabChanged>>")
                    except:
                        pass
                
                # 3. Disable timer-based updates
                for after_id in self.root.tk.call('after', 'info'):
                    try:
                        self.root.after_cancel(after_id)
                    except:
                        pass
                        
                # 4. Set a flag in shared state to stop updates
                if hasattr(self.shared_state, 'is_exiting'):
                    self.shared_state.is_exiting = True
                    
                # 5. Withdraw the window to stop any resize/redraw events
                self.root.withdraw()
            except Exception as e:
                print(f"Error disabling event handlers: {e}")
            
            # Stop file monitoring first
            if self.file_monitor:
                self.file_monitor.stop()
            
            # Stop tray icon if it exists
            if hasattr(self, 'tray_icon') and self.tray_icon is not None:
                # Check if we're on the tray thread
                current_thread = threading.current_thread()
                is_tray_thread = (self.tray_thread and current_thread is self.tray_thread)
                
                # Stop the icon
                self.tray_icon.stop()
                
                # Only try to join if we're not on the tray thread
                if not is_tray_thread and self.tray_thread and self.tray_thread.is_alive():
                    try:
                        self.tray_thread.join(timeout=1.0)
                    except Exception as e:
                        print(f"Warning during thread join: {e}")
            
            # Handle exit differently based on which thread we're on
            if threading.current_thread() is self.tray_thread:
                # We're on the tray thread - need to exit via a different thread
                threading.Thread(
                    target=self._force_exit_from_thread,
                    daemon=True
                ).start()
                
                # Also set a fallback force exit
                threading.Timer(2.0, lambda: sys.exit(0)).start()
            else:
                # We're on the main thread or another thread
                self._force_exit_from_thread()
                
        except Exception as e:
            print(f"Error during exit: {e}")
            # Force exit if needed
            sys.exit(0)
    
    def _force_exit_from_thread(self):
        """Force exit from a separate thread."""
        try:
            time.sleep(0.1)  # Brief delay to let any ongoing operations complete
            
            # Force destroy the root window
            try:
                # Destroy all child widgets first to prevent callbacks
                for widget in self.root.winfo_children():
                    try:
                        widget.destroy()
                    except:
                        pass
                self.root.destroy()
            except Exception as e:
                print(f"Error destroying root: {e}")
                
            # Force kill the process if destroy failed
            time.sleep(0.5)
            sys.exit(0)
        except Exception as e:
            print(f"Force exit error: {e}")
            sys.exit(0)
    
    def run(self):
        """Run the application."""
        # Parse command line arguments
        parser = argparse.ArgumentParser(description="Inveni - File Version Manager")
        parser.add_argument('--minimized', action='store_true', help='Start minimized to system tray')
        parser.add_argument('--file', help='Open with specific file selected')
        args, unknown = parser.parse_known_args()
        
        # Check if we should start minimized
        if args.minimized:
            self.root.withdraw()
        
        # Handle file argument
        if args.file and os.path.exists(args.file):
            # Schedule file selection after the UI is fully loaded
            self.root.after(500, lambda: self.shared_state.set_selected_file(args.file))
        
        # Start the main loop
        self.root.mainloop()


def main():
    """Application entry point."""
    try:
        # Display current time and username information
        current_time = get_formatted_time(use_utc=True)
        current_username = get_current_username()
        print(f"Current Date and Time (UTC - YYYY-MM-DD HH:MM:SS formatted): {current_time}")
        print(f"Current User's Login: {current_username}")
        
        # Check if another instance is already running
        instance_checker = SingleInstanceChecker()
        if instance_checker.is_another_instance_running():
            print("Inveni is already running. Focusing the existing window...")
            # Exit this instance immediately
            return
        
        # Create and run app normally if no other instance is running
        app = InveniApp()
        
        # Set up signal checking for window focus
        instance_checker.check_for_signals(app.show_window)
        
        # Run the application
        app.run()
    except Exception as e:
        error_msg = f"Application error: {str(e)}"
        print(error_msg)
        
        with open("error.log", "a", encoding='utf-8') as f:
            # Use dynamic username from time_utils
            current_username = get_current_username()
            timestamp = get_timestamp_str()
            f.write(f"[{timestamp}] [{current_username}] {error_msg}\n")
            
        messagebox.showerror("Error", error_msg)
        raise

if __name__ == "__main__":
    main()
