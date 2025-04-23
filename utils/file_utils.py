# utils/file_utils.py

import os
import shutil
import hashlib
from typing import Dict, Any

def calculate_file_hash(file_path: str) -> str:
    """Calculate SHA-256 hash of file contents."""
    try:
        with open(file_path, 'rb') as f:
            return hashlib.sha256(f.read()).hexdigest()
    except Exception as e:
        print(f"Failed to calculate file hash: {str(e)}")
        raise

def format_size(size: int) -> str:
    """Format file size in human-readable format."""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size < 1024:
            return f"{size:.2f} {unit}"
        size /= 1024
    return f"{size:.2f} PB"

def get_file_extension(file_path: str) -> str:
    """Get the file extension in lowercase."""
    return os.path.splitext(file_path.lower())[1]

def get_temp_backup_path(file_path: str, backup_folder: str) -> str:
    """Get path for temporary .bak file in backup folder."""
    from datetime import datetime
    base_name = os.path.basename(file_path)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = os.path.join(backup_folder, "temp_backups")
    os.makedirs(backup_dir, exist_ok=True)
    return os.path.join(backup_dir, f"{base_name}.{timestamp}.bak")

def ensure_dir_exists(directory: str) -> bool:
    """Ensure directory exists, create if necessary."""
    if not os.path.exists(directory):
        try:
            os.makedirs(directory)
            return True
        except Exception:
            return False
    return True