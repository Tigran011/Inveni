import os
import gzip
import shutil
import hashlib
import platform
import appdirs
from typing import Dict, Any, Optional, List, Set
from tkinter import messagebox

# Import the centralized time utilities
from utils.time_utils import get_formatted_time, get_current_username

class BackupManager:
    """Manages file backups and restoration."""
    
    def __init__(self, backup_folder=None, version_manager=None, debug=False):
        """
        Initialize backup manager with specified or default backup location.
        
        Args:
            backup_folder: Optional custom backup folder path. If None, uses app data directory.
            version_manager: Version manager instance for tracking versions.
            debug: Enable verbose debug logging.
        """
        if backup_folder is None:
            # Use standard application data directory
            app_name = "Inveni"
            app_author = "Inveni"
            data_dir = appdirs.user_data_dir(app_name, app_author)
            self.backup_folder = os.path.join(data_dir, "backups")
        else:
            # Use specified folder, resolving to absolute path if relative
            self.backup_folder = os.path.abspath(backup_folder)
        
        self.version_manager = version_manager
        self.debug = debug
        
        # Cache to avoid repeated lookups for non-existent backups
        self._known_missing_backups = set()
        
        # Create backup directory if it doesn't exist
        os.makedirs(self.backup_folder, exist_ok=True)
        print(f"Using backup folder: {self.backup_folder}")
        
    def create_backup(self, file_path: str, file_hash: str, settings: dict) -> str:
        """Create a compressed backup and manage backup count."""
        try:
            normalized_path = os.path.normpath(file_path)
            backup_path = self._get_backup_path(normalized_path, file_hash)
            
            # Clear known missing backups for this file as we're making changes
            self._clear_missing_cache_for_file(normalized_path)
            
            print(f"Creating backup at: {backup_path}")
            
            # Create compressed backup
            with open(normalized_path, 'rb') as src, gzip.open(backup_path, 'wb') as dst:
                shutil.copyfileobj(src, dst)

            tracked_files = self.version_manager.load_tracked_files() if self.version_manager else {}
            max_backups = settings.get('max_backups', 5)
            
            # Call improved clean_old_backups that properly enforces limits
            self._clean_old_backups(normalized_path, max_backups, tracked_files)

            return backup_path

        except Exception as e:
            self._log_error(f"Failed to create backup: {str(e)}")
            raise
            
    def restore_file_version(self, file_path: str, file_hash: str) -> None:
        """Restore a specific version of a file."""
        try:
            normalized_path = os.path.normpath(file_path)
            backup_path = self._get_backup_path(normalized_path, file_hash)
            
            if self.debug:
                print(f"Restoring from backup: {backup_path}")

            if not self.check_backup_exists(normalized_path, file_hash):
                raise FileNotFoundError(f"Backup not found: {backup_path}")

            # Create backup of current file in temp backup folder
            temp_backup_path = self._get_temp_backup_path(normalized_path)
            if os.path.exists(normalized_path):
                shutil.copy2(normalized_path, temp_backup_path)

            # Check if this is an Office document (doc, docx, xls, xlsx, ppt, pptx)
            _, ext = os.path.splitext(normalized_path)
            if ext.lower() in ['.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx']:
                # Use special handling for Office documents
                self._restore_office_document(normalized_path, backup_path)
            else:
                # Regular restore for other file types
                with gzip.open(backup_path, 'rb') as src, open(normalized_path, 'wb') as dst:
                    shutil.copyfileobj(src, dst)

        except PermissionError as e:
            self._log_error(f"Permission denied restoring file: {str(e)}")
            # Display user-friendly error message
            messagebox.showerror(
                "Permission Denied",
                f"Could not restore file due to permission restrictions.\n\n"
                "Please close any applications that may be using this file and try again."
            )
            raise
        except Exception as e:
            self._log_error(f"Restore failed: {str(e)}")
            raise
    
    def _restore_office_document(self, target_file: str, backup_path: str) -> None:
        """Special method to handle restoring Office documents which may be locked or protected."""
        # Create a temporary file in the same directory as the target
        temp_dir = os.path.dirname(target_file)
        temp_file = os.path.join(temp_dir, f"temp_{os.path.basename(target_file)}")
        
        try:
            # First check if the file is accessible for writing
            if os.path.exists(target_file) and not self._can_write_to_file(target_file):
                # Use centralized time and username utilities
                current_time = get_formatted_time(use_utc=True)
                username = get_current_username()
                self._log_error(f"[{current_time}] [{username}] Cannot restore document because it's currently open in Microsoft Office")
                raise PermissionError(
                f"The file appears to be open in Microsoft Office.\n"
                f"Please close the document in Word/Excel/PowerPoint first, then try again."
                )
                
            # Extract the compressed backup to a temporary file
            with gzip.open(backup_path, 'rb') as src, open(temp_file, 'wb') as dst:
                shutil.copyfileobj(src, dst)
                
            # Replace the target file with our temporary file
            if os.path.exists(target_file):
                # For Windows, use a special method to handle potentially locked files
                if platform.system() == 'Windows':
                    try:
                        # First try to remove the target 
                        os.unlink(target_file)
                    except:
                        # If that fails, try using os.replace which can sometimes work with locked files
                        pass
                    os.rename(temp_file, target_file)
                else:
                    # For other platforms
                    os.replace(temp_file, target_file)
            else:
                # If target doesn't exist, simply rename the temp file
                os.rename(temp_file, target_file)
                
        except Exception as e:
            # Clean up the temporary file if it exists
            if os.path.exists(temp_file):
                try:
                    os.remove(temp_file)
                except:
                    pass
            raise
    
    def _can_write_to_file(self, file_path: str) -> bool:
        """Check if we can write to a file."""
        if not os.path.exists(file_path):
            # File doesn't exist, check if directory is writable
            return os.access(os.path.dirname(file_path), os.W_OK)
            
        # Try to open the file for writing to check if it's locked
        try:
            with open(file_path, 'a'):
                pass
            return True
        except:
            return False
    
    def get_version_content(self, file_path: str, file_hash: str) -> bytes:
        """Get the content of a specific version."""
        try:
            normalized_path = os.path.normpath(file_path)
            backup_path = self._get_backup_path(normalized_path, file_hash)
            
            # Check if backup exists using our optimized method
            if not self.check_backup_exists(normalized_path, file_hash):
                raise FileNotFoundError(f"Backup not found: {backup_path}")
                
            # Read compressed content
            with gzip.open(backup_path, 'rb') as f:
                return f.read()
                
        except Exception as e:
            self._log_error(f"Failed to read version content: {str(e)}")
            raise
    
    def _get_cache_key(self, file_path: str, file_hash: str) -> str:
        """Generate a cache key for the missing backups cache."""
        normalized_path = os.path.normpath(file_path)
        return f"{normalized_path}|{file_hash}"
    
    def _clear_missing_cache_for_file(self, file_path: str) -> None:
        """Clear all missing cache entries for a specific file."""
        normalized_path = os.path.normpath(file_path)
        prefix = f"{normalized_path}|"
        
        # Use a list to avoid modifying the set during iteration
        to_remove = [key for key in self._known_missing_backups if key.startswith(prefix)]
        for key in to_remove:
            self._known_missing_backups.discard(key)
    
    def check_backup_exists(self, file_path: str, file_hash: str) -> bool:
        """Check if a backup exists for the given file and hash."""
        # Check the cache first to avoid repeated filesystem checks
        cache_key = self._get_cache_key(file_path, file_hash)
        if cache_key in self._known_missing_backups:
            return False
            
        normalized_path = os.path.normpath(file_path)
        backup_path = self._get_backup_path(normalized_path, file_hash)
        exists = os.path.exists(backup_path)
        
        if not exists:
            # Try the old backup path approach if not found (compatibility)
            base_name = os.path.basename(normalized_path)
            old_version_dir = os.path.join(self.backup_folder, "versions", base_name)
            old_backup_path = os.path.join(old_version_dir, f"{file_hash}.gz")
            exists = os.path.exists(old_backup_path)
            
            if exists and self.debug:
                print(f"Found backup using old path structure: {old_backup_path}")
                # Optional: migrate to new path structure
                # shutil.copy2(old_backup_path, backup_path)
        
        if not exists:
            # Add to cache of known missing backups to avoid future filesystem checks
            self._known_missing_backups.add(cache_key)
            
            # Only log if debug mode is enabled
            if self.debug:
                print(f"Backup not found at: {backup_path}")
            
        return exists
            
    def _get_backup_path(self, file_path: str, file_hash: str) -> str:
        """
        Construct the backup file path consistently across app runs.
        
        Uses a deterministic folder path based on filename and a stable hash of the directory.
        """
        normalized_path = os.path.normpath(file_path)
        base_name = os.path.basename(normalized_path)
        file_dir = os.path.dirname(normalized_path)
        
        # Use a deterministic hash based on the directory path
        # MD5 is used here because we just need a consistent folder name, not security
        dir_hash = hashlib.md5(file_dir.encode('utf-8')).hexdigest()[:8]
        
        version_dir = os.path.join(self.backup_folder, "versions", f"{dir_hash}_{base_name}")
        os.makedirs(version_dir, exist_ok=True)
        return os.path.join(version_dir, f"{file_hash}.gz")
        
    def _get_temp_backup_path(self, file_path: str) -> str:
        """Get path for temporary .bak file in backup folder."""
        normalized_path = os.path.normpath(file_path)
        base_name = os.path.basename(normalized_path)
        
        # Use consistent time format from utilities with UTC time
        timestamp = get_formatted_time(use_utc=True).replace(":", "").replace(" ", "_").replace("-", "")[:15]
        
        backup_dir = os.path.join(self.backup_folder, "temp_backups")
        os.makedirs(backup_dir, exist_ok=True)
        return os.path.join(backup_dir, f"{base_name}.{timestamp}.bak")
    
    def _get_all_backup_files(self, file_path: str) -> List[Dict]:
        """Get all backup files for a given file path, sorted by creation time."""
        normalized_path = os.path.normpath(file_path)
        version_dir = os.path.dirname(self._get_backup_path(normalized_path, "dummy"))
        
        if not os.path.exists(version_dir):
            return []
            
        backup_files = []
        for filename in os.listdir(version_dir):
            if filename.endswith('.gz'):
                file_path = os.path.join(version_dir, filename)
                backup_files.append({
                    'path': file_path,
                    'hash': os.path.splitext(filename)[0],
                    'mtime': os.path.getmtime(file_path)
                })
                
        # Sort by modification time (newest first)
        backup_files.sort(key=lambda x: x['mtime'], reverse=True)
        return backup_files
        
    def _clean_old_backups(self, file_path: str, max_backups: int, tracked_files: Dict) -> None:
        """
        Clean up old backups keeping only the most recent ones.
        This method properly enforces the max_backups limit and updates caches.
        """
        try:
            normalized_path = os.path.normpath(file_path)
            if self.debug:
                print(f"Cleaning old backups for {normalized_path}, max allowed: {max_backups}")
            
            # Get all backup files from the filesystem
            all_backups = self._get_all_backup_files(normalized_path)
            
            if not all_backups:
                if self.debug:
                    print("No backup files found to clean")
                return
                
            # If we have more backups than allowed, delete the oldest ones
            if len(all_backups) > max_backups:
                # Keep the newest max_backups, delete the rest
                backups_to_delete = all_backups[max_backups:]
                backups_to_keep = all_backups[:max_backups]
                
                print(f"Found {len(all_backups)} backups, keeping {len(backups_to_keep)}, deleting {len(backups_to_delete)}")
                
                # Delete excess backup files
                for backup in backups_to_delete:
                    try:
                        os.remove(backup['path'])
                        print(f"Deleted old backup: {backup['path']}")
                        
                        # Add to missing backups cache
                        cache_key = self._get_cache_key(normalized_path, backup['hash'])
                        self._known_missing_backups.add(cache_key)
                        
                        # Also remove from tracked files if present
                        if normalized_path in tracked_files and "versions" in tracked_files[normalized_path]:
                            if backup['hash'] in tracked_files[normalized_path]["versions"]:
                                del tracked_files[normalized_path]["versions"][backup['hash']]
                                print(f"Removed version entry for hash: {backup['hash']}")
                    except Exception as e:
                        self._log_error(f"Failed to delete backup {backup['path']}: {str(e)}")
                
                # Save the updated tracked files if we modified them
                if self.version_manager and normalized_path in tracked_files:
                    self.version_manager.save_tracked_files(tracked_files)
            else:
                if self.debug:
                    print(f"Only {len(all_backups)} backups found, no cleaning needed (max is {max_backups})")

            # Always clean up old temporary .bak files
            self._cleanup_old_bak_files()

        except Exception as e:
            self._log_error(f"Failed to clean old backups: {str(e)}")
            raise
            
    def _cleanup_old_bak_files(self) -> None:
        """Clean up .bak files older than 24 hours."""
        try:
            from datetime import datetime, timedelta  # For time comparison only
            
            temp_backup_dir = os.path.join(self.backup_folder, "temp_backups")
            if not os.path.exists(temp_backup_dir):
                return

            # For this specific function, we need direct datetime objects for comparison
            current_time = datetime.now()
            one_day_ago = current_time - timedelta(days=1)
            
            for filename in os.listdir(temp_backup_dir):
                if filename.endswith('.bak'):
                    file_path = os.path.join(temp_backup_dir, filename)
                    file_time = datetime.fromtimestamp(os.path.getctime(file_path))
                    if file_time < one_day_ago:
                        os.remove(file_path)
        except Exception as e:
            self._log_error(f"Failed to cleanup old .bak files: {str(e)}")
            
    def _log_error(self, error_message: str) -> None:
        """Log error messages with timestamp."""
        log_dir = os.path.join(self.backup_folder, "logs")
        os.makedirs(log_dir, exist_ok=True)
        log_file_path = os.path.join(log_dir, "error_log.txt")
        
        # Use centralized time and username utilities
        current_time = get_formatted_time(use_utc=True)
        username = get_current_username()
        
        with open(log_file_path, "a", encoding='utf-8') as log_file:
            log_file.write(f"[{current_time}] [{username}] {error_message}\n")
            
    def debug_check_paths(self, file_path, file_hash):
        """Debug method to check path construction."""
        normalized_path = os.path.normpath(file_path)
        backup_path = self._get_backup_path(normalized_path, file_hash)
        
        # Check if file exists
        exists = os.path.exists(backup_path)
        
        print(f"Debug Path Info for file: {file_path}")
        print(f"Normalized path: {normalized_path}")
        print(f"Backup path: {backup_path}")
        print(f"Backup exists: {exists}")
        
        # Try old path structure
        base_name = os.path.basename(normalized_path)
        old_version_dir = os.path.join(self.backup_folder, "versions", base_name)
        old_backup_path = os.path.join(old_version_dir, f"{file_hash}.gz")
        old_exists = os.path.exists(old_backup_path)
        
        print(f"Old-style backup path: {old_backup_path}")
        print(f"Old-style backup exists: {old_exists}")
        
        # Check current backup count
        all_backups = self._get_all_backup_files(normalized_path)
        print(f"Current backup count: {len(all_backups)}")
        
        # Check missing backups cache
        cache_key = self._get_cache_key(normalized_path, file_hash)
        is_cached = cache_key in self._known_missing_backups
        print(f"In missing backups cache: {is_cached}")
        print(f"Missing backups cache size: {len(self._known_missing_backups)}")
        
        # Also check direct file format (added for debugging)
        file_dir = os.path.dirname(normalized_path)
        dir_hash = hashlib.md5(file_dir.encode('utf-8')).hexdigest()[:8]
        direct_backup = os.path.join(self.backup_folder, "versions", f"{dir_hash}_{base_name}")
        direct_exists = os.path.exists(direct_backup)
        
        print(f"Direct file path: {direct_backup}")
        print(f"Direct file exists: {direct_exists}")
        
        return exists or old_exists or direct_exists

    def clear_missing_cache(self):
        """
        Clear the missing backups cache.
        Useful when debugging or if the filesystem state might have changed externally.
        """
        cache_size = len(self._known_missing_backups)
        self._known_missing_backups.clear()
        print(f"Cleared missing backups cache ({cache_size} entries)")