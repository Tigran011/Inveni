import os
import time
import threading
import queue
from typing import Callable, Optional, Dict, Set
from threading import Lock

# Updated imports to match new project structure
from utils.file_utils import calculate_file_hash
from utils.time_utils import get_formatted_time, get_current_username

class FileMonitor:
    """Monitors files for changes and triggers appropriate actions."""
    
    def __init__(self, callback: Callable[[str, bool], None], settings=None, shared_state=None, version_manager=None):
        self.watched_files: Dict[str, Dict] = {}
        self.callback = callback
        self.settings = settings
        self.shared_state = shared_state
        self.version_manager = version_manager
        self.tracked_files = self.version_manager.load_tracked_files() if version_manager else {}
        self.lock = Lock()
        self.active_files: Set[str] = set()
        self.last_dialog_time: Dict[str, float] = {}
        self.dialog_cooldown = 2.0  # Seconds to wait before showing dialog again
        
        # Track files being restored to prevent commit dialog
        self.restoring_files: Set[str] = set()
        
        # Debug information
        self.username = get_current_username()  # Using centralized username function
        self.debug_mode = True
        
        # Store reference to main application
        self.main_app = None
        if shared_state and hasattr(shared_state, 'main_app'):
            self.main_app = shared_state.main_app

        # Background processing
        self.background_queue = queue.Queue()
        self.background_thread = None
        self.running = True
        self.is_monitoring = True  # Added for pause/resume functionality
        self._stop_event = threading.Event()
        self._start_background_thread()
        
        # Status tracking for system tray
        self.pending_changes_count = 0
        self.files_with_changes = set()

    def _start_background_thread(self):
        """Start the background monitoring thread."""
        if self.background_thread is None or not self.background_thread.is_alive():
            self.background_thread = threading.Thread(
                target=self._background_monitor,
                daemon=True
            )
            self.background_thread.start()

    def _background_monitor(self):
        """Background thread for file monitoring."""
        while self.running and not self._stop_event.is_set():
            try:
                # Process any queued tasks
                try:
                    task, args = self.background_queue.get(timeout=0.5)
                    task(*args)
                    self.background_queue.task_done()
                except queue.Empty:
                    pass

                # Regular file monitoring - only if monitoring is enabled
                if self.running and not self._stop_event.is_set() and self.is_monitoring:
                    self.check_for_changes()
                
                time.sleep(0.5)  # Reduced sleep time for better responsiveness
            except Exception as e:
                self._log_debug(f"Error in background monitor: {str(e)}")
                time.sleep(5)

    def _log_debug(self, message: str) -> None:
        """Log debug information with timestamp."""
        if self.debug_mode:
            # Using centralized time utility for consistent formatting
            current_time = get_formatted_time(use_utc=True)
            print(f"[{current_time}] [{self.username}] {message}")

    def add_background_task(self, task, *args):
        """Add a task to be executed in background."""
        self.background_queue.put((task, args))

    def set_file(self, file_path: Optional[str]) -> None:
        """Set or update a file to be monitored."""
        def _set_file_task(path):
            with self.lock:
                if path and os.path.exists(path):
                    normalized_path = os.path.normpath(path)
                    try:
                        current_hash = calculate_file_hash(path)
                        current_mtime = os.path.getmtime(path)
                        
                        self.watched_files[normalized_path] = {
                            'hash': current_hash,
                            'mtime': current_mtime,
                            'last_check': time.time(),
                            'is_open': True,
                            'size': os.path.getsize(path)
                        }
                        
                        self.active_files.add(normalized_path)
                        self._log_debug(f"Now monitoring: {normalized_path}")
                        
                    except Exception as e:
                        self._log_debug(f"Error setting file {normalized_path}: {str(e)}")
                else:
                    self._cleanup_file(path)

        self.add_background_task(_set_file_task, file_path)

    def _cleanup_file(self, file_path: Optional[str]) -> None:
        """Clean up monitoring for a file."""
        if file_path:
            normalized_path = os.path.normpath(file_path)
            self.watched_files.pop(normalized_path, None)
            self.active_files.discard(normalized_path)
            
            # Also remove from files with changes for system tray
            if normalized_path in self.files_with_changes:
                self.files_with_changes.remove(normalized_path)
                self.pending_changes_count = max(0, self.pending_changes_count - 1)
                self._notify_system_tray_status()
                
            self._log_debug(f"Stopped monitoring: {normalized_path}")

    def mark_file_as_restoring(self, file_path: str) -> None:
        """Mark a file as currently being restored to prevent commit dialog."""
        normalized_path = os.path.normpath(file_path)
        with self.lock:
            self.restoring_files.add(normalized_path)
            self._log_debug(f"Marked file as restoring: {normalized_path}")

    def unmark_file_as_restoring(self, file_path: str) -> None:
        """Remove a file from the restoring list once restoration is complete."""
        normalized_path = os.path.normpath(file_path)
        with self.lock:
            if normalized_path in self.restoring_files:
                self.restoring_files.remove(normalized_path)
                self._log_debug(f"Removed file from restoring list: {normalized_path}")

    def is_file_restoring(self, file_path: str) -> bool:
        """Check if a file is currently being restored."""
        normalized_path = os.path.normpath(file_path)
        with self.lock:
            return normalized_path in self.restoring_files

    def check_for_changes(self) -> None:
        """Check all monitored files for changes."""
        if not self.is_monitoring:
            return  # Skip if monitoring is paused
            
        with self.lock:
            current_time = time.time()
            
            for file_path in list(self.watched_files.keys()):
                if not os.path.exists(file_path):
                    self._cleanup_file(file_path)
                    continue

                try:
                    file_info = self.watched_files[file_path]
                    current_mtime = os.path.getmtime(file_path)
                    current_size = os.path.getsize(file_path)
                    
                    # Check if file is being written to
                    if current_size != file_info['size']:
                        file_info['size'] = current_size
                        file_info['is_open'] = True
                        continue

                    # Check for modifications
                    if current_mtime != file_info['mtime']:
                        current_hash = calculate_file_hash(file_path)
                        has_changed = current_hash != file_info['hash']
                        
                        # Check if file is closed
                        was_open = file_info['is_open']
                        is_closed = self._is_file_closed(file_path)
                        
                        if was_open and is_closed and has_changed:
                            self._handle_file_closed(file_path, current_hash)
                        
                        file_info.update({
                            'hash': current_hash,
                            'mtime': current_mtime,
                            'is_open': not is_closed
                        })
                        
                        if has_changed:
                            # Track changes for system tray
                            if file_path not in self.files_with_changes:
                                self.files_with_changes.add(file_path)
                                self.pending_changes_count += 1
                                self._notify_system_tray_status()
                                
                            self.callback(file_path, True)
                    
                    # Update last check time
                    file_info['last_check'] = current_time
                    
                except Exception as e:
                    self._log_debug(f"Error checking {file_path}: {str(e)}")

    def _is_file_closed(self, file_path: str) -> bool:
        """Check if a file is closed using multiple methods."""
        try:
            # Try exclusive access
            with open(file_path, 'rb+') as f:
                return True
        except (IOError, PermissionError):
            try:
                # Alternative check: compare consecutive reads
                size1 = os.path.getsize(file_path)
                time.sleep(0.1)
                size2 = os.path.getsize(file_path)
                return size1 == size2
            except Exception:
                return False

    def _handle_file_closed(self, file_path: str, current_hash: str) -> None:
        """Handle file closed event with changes."""
        normalized_path = os.path.normpath(file_path)
        current_time = time.time()

        # Refresh tracked files from version manager if available        
        if self.version_manager:
            self.tracked_files = self.version_manager.load_tracked_files()
        
        # ALWAYS update the file's hash and metadata, even for restores
        # This ensures future changes will be detected correctly
        file_info = self.watched_files.get(normalized_path, {})
        file_info.update({
            'hash': current_hash,
            'mtime': os.path.getmtime(file_path) if os.path.exists(file_path) else 0,
            'size': os.path.getsize(file_path) if os.path.exists(file_path) else 0,
            'is_open': False,
            'last_check': current_time
        })
        self.watched_files[normalized_path] = file_info
        self._log_debug(f"Updated file tracking hash to: {current_hash[:8]}... for {normalized_path}")
        
        # Check if file is being restored - skip commit dialog if so
        if normalized_path in self.restoring_files:
            self._log_debug(f"File closed after restore - skipping commit dialog: {normalized_path}")
            self.unmark_file_as_restoring(normalized_path)
            return
        
        # Check if file is tracked and dialog cooldown has passed
        if (normalized_path in self.tracked_files and 
            current_time - self.last_dialog_time.get(normalized_path, 0) > self.dialog_cooldown):
            
            self._log_debug(f"File closed with changes: {normalized_path}")
            self._show_commit_dialog(normalized_path)
            self.last_dialog_time[normalized_path] = current_time

    def _show_commit_dialog(self, file_path: str) -> None:
        """Show the quick commit dialog through the main application."""
        if self.main_app:
            try:
                self.main_app.show_commit_dialog(file_path)
                self._log_debug(f"Requested commit dialog for: {file_path}")
            except Exception as e:
                self._log_debug(f"Error showing commit dialog: {str(e)}")
        else:
            self._log_debug("Cannot show dialog - no main application reference")
            
    def update_after_commit(self, file_path: str, new_hash: str) -> None:
        """
        Update the file monitoring state after a successful commit.
        
        Args:
            file_path: Path to the file that was committed
            new_hash: Hash of the committed version
        """
        normalized_path = os.path.normpath(file_path)
        with self.lock:
            self._log_debug(f"Updating file monitoring state after commit: {normalized_path}")
            
            # Update the tracked files list
            self.refresh_tracked_files()
            
            # Update the file's watched state with the new hash
            if normalized_path in self.watched_files:
                self.watched_files[normalized_path].update({
                    'hash': new_hash,  # Update to the committed hash
                    'mtime': os.path.getmtime(normalized_path) if os.path.exists(normalized_path) else 0,
                    'size': os.path.getsize(normalized_path) if os.path.exists(normalized_path) else 0,
                    'last_check': time.time(),
                })
                
                self._log_debug(f"Updated monitoring hash to committed version: {new_hash[:8]}... for {normalized_path}")
            else:
                # If not being watched, add it to watches
                self.set_file(normalized_path)
                
            # Reset any "is_restoring" flags just to be safe
            if normalized_path in self.restoring_files:
                self.restoring_files.remove(normalized_path)
                
            # Remove from pending changes for system tray
            if normalized_path in self.files_with_changes:
                self.files_with_changes.remove(normalized_path)
                self.pending_changes_count = max(0, self.pending_changes_count - 1)
                self._notify_system_tray_status()
                
    def force_reset_monitoring(self, file_path: str) -> None:
        """
        Force reset of file monitoring state - useful after restores or other operations
        that change the file outside the normal edit-save workflow.
        
        Args:
            file_path: Path to the file to reset
        """
        normalized_path = os.path.normpath(file_path)
        with self.lock:
            # Remove from watched files to force a clean re-add
            if normalized_path in self.watched_files:
                self.watched_files.pop(normalized_path)
                
            # Remove any restoring flags
            if normalized_path in self.restoring_files:
                self.restoring_files.remove(normalized_path)
            
            # Remove from pending changes
            if normalized_path in self.files_with_changes:
                self.files_with_changes.remove(normalized_path)
                self.pending_changes_count = max(0, self.pending_changes_count - 1)
                self._notify_system_tray_status()
                
            self._log_debug(f"*** FORCED RESET of file monitoring: {normalized_path} ***")
            
            # Re-add to monitoring with fresh state
            self.set_file(normalized_path)

    def refresh_tracked_files(self) -> None:
        """Refresh the list of tracked files."""
        try:
            if self.version_manager:
                self.tracked_files = self.version_manager.load_tracked_files()
            else:
                self._log_debug("No version manager available to refresh tracked files")
            self._log_debug("Tracked files list refreshed")
        except Exception as e:
            self._log_debug(f"Error refreshing tracked files: {str(e)}")

    def get_file_status(self, file_path: str) -> Dict:
        """Get detailed status of a monitored file."""
        normalized_path = os.path.normpath(file_path)
        with self.lock:
            if normalized_path in self.watched_files:
                status = self.watched_files[normalized_path].copy()
                status['is_tracked'] = normalized_path in self.tracked_files
                status['is_restoring'] = normalized_path in self.restoring_files
                status['has_pending_changes'] = normalized_path in self.files_with_changes
                return status
            return {}

    def get_change_size(self, file_path: str) -> int:
        """Get approximate size of file changes since last hash."""
        normalized_path = os.path.normpath(file_path)
        with self.lock:
            if normalized_path in self.watched_files:
                current_size = os.path.getsize(normalized_path) if os.path.exists(normalized_path) else 0
                original_size = self.watched_files[normalized_path].get('size', 0)
                return abs(current_size - original_size)
            return 0

    def get_change_type(self, file_path: str) -> str:
        """Get type of change (addition, deletion, modification)."""
        normalized_path = os.path.normpath(file_path)
        with self.lock:
            if normalized_path in self.watched_files:
                current_size = os.path.getsize(normalized_path) if os.path.exists(normalized_path) else 0
                original_size = self.watched_files[normalized_path].get('size', 0)
                
                if current_size > original_size:
                    return "addition"
                elif current_size < original_size:
                    return "deletion"
                else:
                    return "modification"
            return "unknown"

    def add_new_file(self, file_path: str) -> None:
        """Add a new file to monitoring after first commit"""
        def _add_new_file_task(path):
            with self.lock:
                normalized_path = os.path.normpath(path)
                self._log_debug(f"Adding new file to monitor: {normalized_path}")
                
                # Refresh tracked files from version manager if available
                if self.version_manager:
                    self.tracked_files = self.version_manager.load_tracked_files()
                
                if normalized_path not in self.tracked_files:
                    self.tracked_files[normalized_path] = {"versions": {}}
                
                if normalized_path not in self.watched_files:
                    self.set_file(normalized_path)
                    self._log_debug(f"Started monitoring new file: {normalized_path}")

        self.add_background_task(_add_new_file_task, file_path)

    # System tray integration methods
    def pause(self):
        """Pause file monitoring temporarily."""
        self.is_monitoring = False
        self._log_debug("File monitoring paused")
        self._notify_system_tray_status()
        
    def resume(self):
        """Resume file monitoring."""
        self.is_monitoring = True
        self._log_debug("File monitoring resumed")
        self._notify_system_tray_status()
    
    def is_paused(self):
        """Check if monitoring is paused."""
        return not self.is_monitoring
        
    def get_pending_changes_count(self) -> int:
        """Get number of files with pending changes for system tray."""
        with self.lock:
            return self.pending_changes_count
            
    def get_files_with_changes(self) -> Set[str]:
        """Get set of files with pending changes."""
        with self.lock:
            return set(self.files_with_changes)
    
    def clear_pending_changes(self):
        """Clear all pending changes (after commit all)."""
        with self.lock:
            self.files_with_changes.clear()
            self.pending_changes_count = 0
            self._notify_system_tray_status()
    
    def _notify_system_tray_status(self):
        """Notify the main app about changes in status for system tray updates."""
        try:
            if self.shared_state and hasattr(self.shared_state, 'notify_system_tray_update'):
                status = {
                    'is_monitoring': self.is_monitoring,
                    'pending_changes': self.pending_changes_count,
                    'files_with_changes': list(self.files_with_changes)
                }
                self.shared_state.notify_system_tray_update(status)
        except Exception as e:
            self._log_debug(f"Error notifying system tray: {str(e)}")

    def stop(self):
        """Stop the background monitoring cleanly."""
        self._stop_event.set()
        self.running = False
        
        # Wait for queue to finish processing
        try:
            self.background_queue.join(timeout=2.0)
        except:
            pass
            
        if self.background_thread and self.background_thread.is_alive():
            self.background_thread.join(timeout=2.0)
            self._log_debug("File monitor stopped")