# core/version_manager.py

import os
import json
import hashlib
from datetime import datetime
import pytz
from typing import Dict, Any, Optional, List, Tuple

class VersionManager:
    """Manages file versioning and history."""
    
    def __init__(self, backup_folder="backups"):
        self.backup_folder = backup_folder
        os.makedirs(backup_folder, exist_ok=True)
        self.tracked_files_path = "tracked_files.json"
        
    def calculate_file_hash(self, file_path: str) -> str:
        """Calculate SHA-256 hash of file contents."""
        try:
            with open(file_path, 'rb') as f:
                return hashlib.sha256(f.read()).hexdigest()
        except Exception as e:
            self._log_error(f"Failed to calculate file hash: {str(e)}")
            raise
    
    def has_file_changed(self, file_path: str, tracked_files: Dict[str, Any]) -> Tuple[bool, str, str]:
        """
        Check if file has changed from its last tracked version.
        Returns (has_changed, current_hash, last_hash)
        """
        try:
            current_hash = self.calculate_file_hash(file_path)
            normalized_path = os.path.normpath(file_path)
            
            if normalized_path not in tracked_files:
                return True, current_hash, ""
                
            versions = tracked_files[normalized_path].get("versions", {})
            if not versions:
                return True, current_hash, ""
                
            # Get most recent version hash
            latest_version = sorted(
                versions.items(),
                key=lambda x: datetime.strptime(x[1]["timestamp"], "%Y-%m-%d %H:%M:%S"),
                reverse=True
            )[0]
            
            last_hash = latest_version[0]
            return current_hash != last_hash, current_hash, last_hash
            
        except Exception as e:
            self._log_error(f"Failed to check file changes: {str(e)}")
            raise
    
    def load_tracked_files(self) -> Dict[str, Any]:
        """Load tracked files from JSON."""
        try:
            with open(self.tracked_files_path, "r", encoding='utf-8') as file:
                return json.load(file)
        except FileNotFoundError:
            return {}
        except json.JSONDecodeError:
            self._log_error("Error: tracked_files.json is corrupted.")
            return {}
    
    def save_tracked_files(self, tracked_files: Dict[str, Any]) -> None:
        """Save tracked files to JSON with proper formatting."""
        try:
            with open(self.tracked_files_path, "w", encoding='utf-8') as file:
                json.dump(tracked_files, file, indent=4, ensure_ascii=False)
        except Exception as e:
            self._log_error(f"Failed to save tracked files: {str(e)}")
            raise
    
    def get_backup_path(self, file_path: str, file_hash: str) -> str:
        """Construct the backup file path."""
        base_name = os.path.basename(file_path)
        version_dir = os.path.join(self.backup_folder, "versions", base_name)
        os.makedirs(version_dir, exist_ok=True)
        return os.path.join(version_dir, f"{file_hash}.gz")
    
    def get_backup_count(self, file_path: str) -> int:
        """Get the current number of backups for a file."""
        try:
            normalized_path = os.path.normpath(file_path)
            base_name = os.path.basename(normalized_path)
            version_dir = os.path.join(self.backup_folder, "versions", base_name)
            
            if not os.path.exists(version_dir):
                return 0
                
            return len([f for f in os.listdir(version_dir) if f.endswith('.gz')])
        except Exception:
            return 0
    
    def _log_error(self, error_message: str) -> None:
        """Log error messages with UTC timestamp."""
        log_file_path = os.path.join(os.getcwd(), "error_log.txt")
        current_time = datetime.now(pytz.UTC).strftime("%Y-%m-%d %H:%M:%S")
        username = os.getlogin()
        
        with open(log_file_path, "a", encoding='utf-8') as log_file:
            log_file.write(f"[{current_time}] [{username}] {error_message}\n")