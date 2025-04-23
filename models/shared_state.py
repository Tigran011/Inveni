import os
from typing import Optional, List, Callable, Dict, Set, Any

# Updated imports to use all centralized time utilities
from utils.time_utils import get_current_times, get_formatted_time, get_current_username

class SharedState:
    """Shared state to synchronize file selection, version updates, and system tray across the app."""
    def __init__(self):
        self.selected_file: Optional[str] = None
        self.file_callbacks: List[Callable[[Optional[str]], None]] = []
        self.version_callbacks: List[Callable[[], None]] = []
        self.last_update: Optional[str] = None  # Now using string format from time utils
        self.current_user: str = get_current_username()  # Using centralized username function
        self._active = True
        self._file_history: List[str] = []  # Track file selection history
        self._max_history = 10  # Maximum number of files to remember
        
        # File monitoring related attributes
        self.file_monitor = None
        self.tracked_files: Set[str] = set()
        self.monitoring_callbacks: List[Callable[[str, bool], None]] = []
        
        # System tray integration
        self.system_tray_callbacks: List[Callable[[Dict[str, Any]], None]] = []
        self.pending_changes: Dict[str, Dict] = {}  # Track files with pending changes
        self.main_app = None  # Will hold reference to main application
        
        # Initialize with current time
        times = get_current_times()
        self.initialization_time = times['utc']
        
        # Flag for app shutdown state
        self.is_exiting = False

    def get_selected_file(self) -> Optional[str]:
        """Get the currently selected file path."""
        if self.selected_file and os.path.exists(self.selected_file):
            return self.selected_file
        return None

    def set_selected_file(self, file_path: Optional[str]) -> None:
        """
        Set the selected file and notify all file selection listeners.
        
        Args:
            file_path: The path to the selected file or None if no file is selected
        """
        if file_path is None:
            self.selected_file = None
        else:
            try:
                normalized_path = os.path.normpath(file_path)
                if os.path.exists(normalized_path):
                    self.selected_file = normalized_path
                    # Add to history if it's a new file
                    if normalized_path not in self._file_history:
                        self._file_history.append(normalized_path)
                        if len(self._file_history) > self._max_history:
                            self._file_history.pop(0)
                else:
                    print(f"Warning: File does not exist: {normalized_path}")
                    self.selected_file = None
            except Exception as e:
                print(f"Error normalizing path: {str(e)}")
                self.selected_file = None

        if self._active:
            self._notify_file_callbacks()

    def get_file_history(self) -> List[str]:
        """Get list of recently selected files that still exist."""
        return [f for f in self._file_history if os.path.exists(f)]

    def track_file(self, file_path: str) -> None:
        """Add a file to tracking system."""
        if file_path and os.path.exists(file_path):
            normalized_path = os.path.normpath(file_path)
            self.tracked_files.add(normalized_path)
            if self.file_monitor:
                self.file_monitor.set_file(normalized_path)
                self.file_monitor.refresh_tracked_files()

    def untrack_file(self, file_path: str) -> None:
        """Remove a file from tracking system."""
        if file_path:
            normalized_path = os.path.normpath(file_path)
            self.tracked_files.discard(normalized_path)
            if self.file_monitor:
                self.file_monitor._cleanup_file(normalized_path)
                
            # Also remove from pending changes if present
            if normalized_path in self.pending_changes:
                del self.pending_changes[normalized_path]
                self._notify_system_tray_update()

    def is_file_tracked(self, file_path: str) -> bool:
        """Check if a file is being tracked."""
        if file_path:
            normalized_path = os.path.normpath(file_path)
            return normalized_path in self.tracked_files
        return False

    def add_monitoring_callback(self, callback: Callable[[str, bool], None]) -> None:
        """Add a callback for file monitoring events."""
        if callback not in self.monitoring_callbacks:
            self.monitoring_callbacks.append(callback)

    def notify_file_changed(self, file_path: str, has_changed: bool) -> None:
        """Notify when a tracked file changes."""
        if self._active:
            # Track pending changes for system tray
            if has_changed and file_path:
                self._add_pending_change(file_path)
                
            # Notify all monitoring callbacks
            for callback in self.monitoring_callbacks[:]:
                try:
                    callback(file_path, has_changed)
                except Exception as e:
                    print(f"Error in monitoring callback: {str(e)}")

    def _add_pending_change(self, file_path: str) -> None:
        """Add a file to pending changes for system tray tracking."""
        if not file_path:
            return
            
        normalized_path = os.path.normpath(file_path)
        
        # Check if this file is being tracked before adding to pending changes
        if normalized_path in self.tracked_files:
            times = get_current_times()
            
            if normalized_path not in self.pending_changes:
                self.pending_changes[normalized_path] = {
                    'first_detected': times['utc'],
                    'last_updated': times['utc']
                }
            else:
                self.pending_changes[normalized_path]['last_updated'] = times['utc']
                
            # Notify system tray of change
            self._notify_system_tray_update()

    def clear_pending_change(self, file_path: str) -> None:
        """Clear a specific file from pending changes (e.g., after commit)."""
        if not file_path:
            return
            
        normalized_path = os.path.normpath(file_path)
        if normalized_path in self.pending_changes:
            del self.pending_changes[normalized_path]
            self._notify_system_tray_update()

    def get_pending_changes_count(self) -> int:
        """Get count of files with pending changes for system tray."""
        return len(self.pending_changes)

    def get_pending_changes(self) -> Dict[str, Dict]:
        """Get dictionary of files with pending changes."""
        return self.pending_changes.copy()

    def add_system_tray_callback(self, callback: Callable[[Dict[str, Any]], None]) -> None:
        """Add a callback for system tray status updates."""
        if callback not in self.system_tray_callbacks:
            self.system_tray_callbacks.append(callback)
            
            # Immediately trigger with current state
            if self._active:
                self._notify_system_tray_update()

    def notify_system_tray_update(self, status: Optional[Dict[str, Any]] = None) -> None:
        """Notify system tray about status changes."""
        self._notify_system_tray_update(status)
        
    def notify_version_commit(self) -> None:
        """
        Notify that a file has been committed to update the system tray recent files.
        This method should be called after a successful commit to ensure
        the system tray's Recent Files menu is refreshed immediately.
        """
        # First update version tracking (timestamps, etc)
        self.notify_version_change()
        
        # Then update the system tray menu with fresh recent files
        if self._active and not self.is_exiting:
            # Call to main app to refresh tray menu
            if self.main_app and hasattr(self.main_app, 'refresh_tray_menu'):
                try:
                    self.main_app.refresh_tray_menu()
                except Exception as e:
                    print(f"Error refreshing tray menu after commit: {str(e)}")

    def _notify_system_tray_update(self, status: Optional[Dict[str, Any]] = None) -> None:
        """Internal method to notify system tray callbacks with current status."""
        if not self._active or self.is_exiting:
            return
            
        # If no status is provided, build current status
        if status is None:
            is_monitoring = True
            if self.file_monitor and hasattr(self.file_monitor, 'is_monitoring'):
                is_monitoring = self.file_monitor.is_monitoring
                
            status = {
                'is_monitoring': is_monitoring,
                'pending_changes': len(self.pending_changes),
                'files_with_changes': list(self.pending_changes.keys())
            }
        
        # Notify all system tray callbacks
        for callback in self.system_tray_callbacks[:]:
            try:
                callback(status)
            except Exception as e:
                print(f"Error in system tray callback: {str(e)}")
                
        # Also notify main app directly if available
        if self.main_app and hasattr(self.main_app, 'update_tray_status'):
            try:
                self.main_app.update_tray_status(status)
            except Exception as e:
                print(f"Error updating main app tray: {str(e)}")

    def notify_version_change(self) -> None:
        """
        Notify all version change listeners that a new version has been committed.
        Updates the last_update timestamp using centralized time utility.
        """
        # Use centralized time function instead of direct datetime usage
        self.last_update = get_formatted_time(use_utc=True)
        
        if self._active:
            self._notify_version_callbacks()

    def add_file_callback(self, callback: Callable[[Optional[str]], None]) -> None:
        """
        Add a callback to be triggered when the selected file changes.
        
        Args:
            callback: Function to be called when file selection changes
        """
        if callback not in self.file_callbacks:
            self.file_callbacks.append(callback)
            # Trigger callback immediately with current state if active
            if self._active:
                try:
                    callback(self.get_selected_file())
                except Exception as e:
                    print(f"Error in initial file callback: {str(e)}")

    def add_version_callback(self, callback: Callable[[], None]) -> None:
        """
        Add a callback to be triggered when a new version is committed.
        
        Args:
            callback: Function to be called when a new version is committed
        """
        if callback not in self.version_callbacks:
            self.version_callbacks.append(callback)

    def _notify_file_callbacks(self) -> None:
        """Notify all registered file selection callbacks."""
        current_file = self.get_selected_file()
        for callback in self.file_callbacks[:]:  # Create a copy to allow modification during iteration
            try:
                callback(current_file)
            except Exception as e:
                print(f"Error in file callback: {str(e)}")

    def _notify_version_callbacks(self) -> None:
        """Notify all registered version change callbacks."""
        for callback in self.version_callbacks[:]:  # Create a copy to allow modification during iteration
            try:
                callback()
            except Exception as e:
                print(f"Error in version callback: {str(e)}")

    def remove_callback(self, callback: Callable) -> None:
        """
        Remove a callback from all callback lists.
        
        Args:
            callback: The callback function to remove
        """
        if callback in self.file_callbacks:
            self.file_callbacks.remove(callback)
        if callback in self.version_callbacks:
            self.version_callbacks.remove(callback)
        if callback in self.monitoring_callbacks:
            self.monitoring_callbacks.remove(callback)
        if callback in self.system_tray_callbacks:
            self.system_tray_callbacks.remove(callback)

    def pause_callbacks(self) -> None:
        """Temporarily pause callback notifications."""
        self._active = False

    def resume_callbacks(self) -> None:
        """Resume callback notifications and trigger updates."""
        self._active = True
        self._notify_file_callbacks()
        if self.last_update:
            self._notify_version_callbacks()
        self._notify_system_tray_update()

    def is_file_selected(self) -> bool:
        """Check if a valid file is currently selected."""
        return bool(self.get_selected_file())

    def update_after_commit(self, file_path: str) -> None:
        """Update state after a successful commit."""
        if file_path:
            normalized_path = os.path.normpath(file_path)
            # Clear from pending changes
            self.clear_pending_change(normalized_path)
            # Notify version callbacks and system tray
            self.notify_version_commit()  # Use the new method that also updates the tray menu

    def get_state_info(self) -> Dict:
        """Get current state information for debugging."""
        is_monitoring = True
        if self.file_monitor and hasattr(self.file_monitor, 'is_monitoring'):
            is_monitoring = self.file_monitor.is_monitoring
            
        return {
            "current_file": self.get_selected_file(),
            "last_update": self.last_update,  # Now already a formatted string
            "current_user": self.current_user,
            "callbacks_active": self._active,
            "file_callbacks_count": len(self.file_callbacks),
            "version_callbacks_count": len(self.version_callbacks),
            "monitoring_callbacks_count": len(self.monitoring_callbacks),
            "system_tray_callbacks_count": len(self.system_tray_callbacks),
            "recent_files": self.get_file_history(),
            "tracked_files": list(self.tracked_files),
            "pending_changes": len(self.pending_changes),
            "pending_files": list(self.pending_changes.keys()),
            "monitoring_active": is_monitoring,
            "initialization_time": self.initialization_time,
            "file_monitor_active": bool(self.file_monitor),
            "main_app_connected": bool(self.main_app)
        }

    def clear_history(self) -> None:
        """Clear file selection history."""
        self._file_history.clear()