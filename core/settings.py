import os
import platform
import json
import logging
import shutil
from pathlib import Path
from typing import Dict, Any, List, Optional, Callable
from logging.handlers import RotatingFileHandler

# Import the centralized time utilities
from utils.time_utils import get_formatted_time, get_current_username

class SettingsManager:
    """
    Comprehensive application settings manager with robust error handling,
    validation, and UI integration capabilities.
    """
    
    # Settings version for migration support
    SETTINGS_VERSION = 3  # Incremented for removing deprecated settings
    
    # Settings validation schema - REMOVED auto_backup_interval
    SETTINGS_SCHEMA = {
        "backup_folder": {"type": str, "required": True},
        "max_backups": {"type": int, "min": 1, "max": 100, "required": True},
        "logging_enabled": {"type": bool, "required": True},
        "username": {"type": str, "required": True},
        "compress_backups": {"type": bool, "required": False},
        "check_for_updates": {"type": bool, "required": False},
        "notification_level": {"type": str, "options": ["none", "minimal", "full"], "required": False},
        "settings_version": {"type": int, "required": False}
    }
    
    # List of deprecated settings to remove
    DEPRECATED_SETTINGS = [
        "auto_backup_interval"
    ]
    
    def __init__(self, settings_file: str = "settings.json", app_name: str = "Inveni"):
        """
        Initialize the settings manager.
        
        Args:
            settings_file: Path to the settings JSON file
            app_name: Application name used for folder paths
        """
        self.settings_file = settings_file
        self.app_name = app_name
        self.callbacks = []
        
        # Configure logging with rotation
        self._configure_logging()
        
        # Load settings
        self.settings = self._load_settings()
        
        # Ensure data directories exist
        self._ensure_directories()
    
    def _configure_logging(self) -> None:
        """Configure application logging with rotation."""
        log_dir = "logs"
        os.makedirs(log_dir, exist_ok=True)
        
        log_file = os.path.join(log_dir, "app.log")
        
        handler = RotatingFileHandler(
            log_file,
            maxBytes=5*1024*1024,  # 5 MB
            backupCount=3
        )
        
        # Use centralized time format for log timestamps
        formatter = logging.Formatter(
            "%(asctime)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        handler.setFormatter(formatter)
        
        logger = logging.getLogger()
        logger.setLevel(logging.INFO)
        
        # Remove any existing handlers to prevent duplicates
        for hdlr in logger.handlers[:]:
            logger.removeHandler(hdlr)
            
        logger.addHandler(handler)
        
    def _ensure_directories(self) -> None:
        """Ensure all required directories exist."""
        # Ensure backup folder exists
        backup_folder = self.get("backup_folder")
        if backup_folder:
            os.makedirs(backup_folder, exist_ok=True)
            
            # Create subdirectories
            versions_dir = os.path.join(backup_folder, "versions")
            temp_dir = os.path.join(backup_folder, "temp")
            
            os.makedirs(versions_dir, exist_ok=True)
            os.makedirs(temp_dir, exist_ok=True)
        
    def _get_default_backup_folder(self) -> str:
        """Determine the default backup folder based on platform."""
        system = platform.system().lower()
        
        # Use platform-specific standard locations
        if system == "windows":
            # Windows: Use LocalAppData
            base_path = os.path.join(os.getenv('LOCALAPPDATA', os.getcwd()), self.app_name)
        elif system == "darwin":  # macOS
            # macOS: Use Application Support directory
            base_path = os.path.expanduser(f"~/Library/Application Support/{self.app_name}")
        else:  # Linux and others
            # Linux: Use .local/share
            base_path = os.path.expanduser(f"~/.local/share/{self.app_name}")
        
        # Use a consistent "backups" subfolder
        folder_path = os.path.join(base_path, "backups")
        
        # Try to create the directory
        try:
            os.makedirs(folder_path, exist_ok=True)
            logging.info(f"Default backup folder set to: {folder_path}")
            return folder_path
        except (OSError, PermissionError) as e:
            logging.warning(f"Could not create default backup folder: {e}")
            # Fall back to app directory
            fallback_path = os.path.join(os.getcwd(), "backups")
            os.makedirs(fallback_path, exist_ok=True)
            logging.info(f"Using fallback backup folder: {fallback_path}")
            return fallback_path
        
    def _get_default_settings(self) -> Dict[str, Any]:
        """Get default settings with platform-specific adjustments."""
        # Use centralized username function for better error handling
        username = get_current_username()
        
        return {
            "backup_folder": self._get_default_backup_folder(),
            "max_backups": 10,
            "logging_enabled": True,
            "username": username,
            "compress_backups": True,
            "check_for_updates": True,
            "notification_level": "minimal",
            "settings_version": self.SETTINGS_VERSION
        }
        
    def _load_settings(self) -> Dict[str, Any]:
        """Load settings with defaults and validation."""
        default_settings = self._get_default_settings()

        if os.path.exists(self.settings_file):
            try:
                with open(self.settings_file, "r", encoding='utf-8') as f:
                    settings = json.load(f)
                    
                    # Always update username to current user
                    # Use centralized username function
                    current_username = get_current_username()
                    old_username = settings.get("username", "User")
                    settings["username"] = current_username
                    
                    # Check for path with old username pattern
                    current_backup_folder = settings.get("backup_folder", "")
                    needs_migration = False
                    old_backup_folder = None

                    # Fix paths with hardcoded "User" or paths with old usernames
                    if "backups_User" in current_backup_folder:
                        old_backup_folder = current_backup_folder
                        # Get a proper default path instead 
                        new_backup_folder = self._get_default_backup_folder()
                        settings["backup_folder"] = new_backup_folder
                        needs_migration = True
                        logging.info(f"Fixing hardcoded backup folder: {old_backup_folder} -> {new_backup_folder}")
                    elif f"backups_{old_username}" in current_backup_folder and old_username != current_username:
                        old_backup_folder = current_backup_folder
                        new_backup_folder = self._get_default_backup_folder()
                        settings["backup_folder"] = new_backup_folder
                        needs_migration = True
                        logging.info(f"Updating username in backup folder: {old_backup_folder} -> {new_backup_folder}")
                    
                    # Schedule migration after settings are loaded
                    # We'll migrate files if we changed paths and if old path exists
                    if needs_migration and old_backup_folder and os.path.exists(old_backup_folder):
                        self._migrate_backup_path(old_backup_folder, settings["backup_folder"])
                    
                    # Update with any missing defaults
                    for key, value in default_settings.items():
                        if key not in settings:
                            settings[key] = value
                    
                    # Check for settings migration (version changes)
                    if settings.get("settings_version", 0) < self.SETTINGS_VERSION:
                        settings = self._migrate_settings(settings)
                    
                    # Remove deprecated settings
                    settings = self._remove_deprecated_settings(settings)
                    
                    # Validate settings
                    settings = self._validate_settings(settings)
                    
                    # Save updated settings
                    self.save_settings(settings)
                    return settings
                    
            except (json.JSONDecodeError, IOError) as e:
                logging.error(f"Settings file error: {str(e)}. Resetting to defaults.")
                return self._reset_settings()

        return self._reset_settings()
    
    def _remove_deprecated_settings(self, settings: Dict[str, Any]) -> Dict[str, Any]:
        """Remove deprecated settings from the settings dictionary."""
        for key in self.DEPRECATED_SETTINGS:
            if key in settings:
                logging.info(f"Removing deprecated setting: {key}")
                settings.pop(key, None)
        return settings
    
    def _migrate_backup_path(self, old_path: str, new_path: str) -> None:
        """
        Migrate backup files from old path to new path.
        This is called during settings load if paths change.
        """
        if old_path == new_path:
            return
            
        logging.info(f"Starting backup migration: {old_path} -> {new_path}")
        
        try:
            # Make sure target exists
            os.makedirs(new_path, exist_ok=True)
            
            old_versions_dir = os.path.join(old_path, "versions")
            new_versions_dir = os.path.join(new_path, "versions")
            
            if os.path.exists(old_versions_dir):
                # Create the versions directory at the new location
                os.makedirs(new_versions_dir, exist_ok=True)
                
                # Copy all files and directories
                for item in os.listdir(old_versions_dir):
                    src_item = os.path.join(old_versions_dir, item)
                    dst_item = os.path.join(new_versions_dir, item)
                    
                    if os.path.isdir(src_item):
                        # Copy directory and all contents
                        if not os.path.exists(dst_item):
                            shutil.copytree(src_item, dst_item)
                    else:
                        # Copy file
                        shutil.copy2(src_item, dst_item)
                        
                logging.info(f"Successfully migrated backup files from {old_path} to {new_path}")
                
                # Optionally clean up old directory after migration
                # Uncomment if you want to automatically clean up:
                # shutil.rmtree(old_path, ignore_errors=True)
                # logging.info(f"Removed old backup folder: {old_path}")
            else:
                logging.info(f"No versions directory found at old path: {old_versions_dir}")
                
        except Exception as e:
            logging.error(f"Backup migration failed: {str(e)}")
        
    def _validate_settings(self, settings: Dict[str, Any]) -> Dict[str, Any]:
        """Validate settings against schema and fix any issues."""
        validated = {}
        default_settings = self._get_default_settings()
        
        for key, schema in self.SETTINGS_SCHEMA.items():
            # Check if required key is missing
            if schema.get("required", False) and key not in settings:
                validated[key] = default_settings.get(key)
                logging.warning(f"Missing required setting '{key}'. Using default: {default_settings.get(key)}")
                continue
                
            # If key is not in settings, skip validation
            if key not in settings:
                continue
                
            value = settings[key]
            
            # Type validation
            expected_type = schema.get("type")
            if expected_type and not isinstance(value, expected_type):
                try:
                    # Try to convert
                    if expected_type == bool and isinstance(value, (int, str)):
                        if isinstance(value, str):
                            value = value.lower() in ('yes', 'true', 'y', '1')
                        else:
                            value = bool(value)
                    elif expected_type == int and isinstance(value, str):
                        value = int(value)
                    elif expected_type == str:
                        value = str(value)
                    else:
                        value = default_settings.get(key)
                        logging.warning(f"Invalid type for '{key}'. Using default: {value}")
                except (ValueError, TypeError):
                    value = default_settings.get(key)
                    logging.warning(f"Could not convert '{key}'. Using default: {value}")
            
            # Range validation for numeric values
            if expected_type == int:
                min_val = schema.get("min")
                max_val = schema.get("max")
                if min_val is not None and value < min_val:
                    value = min_val
                    logging.warning(f"Value for '{key}' below minimum ({min_val}). Adjusted.")
                if max_val is not None and value > max_val:
                    value = max_val
                    logging.warning(f"Value for '{key}' above maximum ({max_val}). Adjusted.")
            
            # Options validation
            if "options" in schema and value not in schema["options"]:
                value = default_settings.get(key)
                logging.warning(f"Invalid option for '{key}'. Using default: {value}")
            
            validated[key] = value
        
        # Keep non-schema values except for deprecated settings
        for key, value in settings.items():
            if key not in validated and key not in self.DEPRECATED_SETTINGS:
                validated[key] = value
            
        return validated
        
    def _migrate_settings(self, settings: Dict[str, Any]) -> Dict[str, Any]:
        """Migrate settings from older versions."""
        current_version = settings.get("settings_version", 0)
        
        # Example migration from version 0 to 1
        if current_version == 0:
            # Add new settings introduced in version 1
            settings["notification_level"] = "minimal"
            settings["auto_backup_interval"] = 5
            settings["compress_backups"] = True
            
            logging.info("Migrated settings from version 0 to 1")
        
        # Migration from version 1 to 2
        if current_version <= 1:
            # In version 2 we improved the backup folder path structure
            # The path migration is handled in _load_settings, we just need to update version
            logging.info("Migrated settings from version 1 to 2")
            
        # Migration from version 2 to 3
        if current_version <= 2:
            # In version 3 we removed deprecated settings
            if "auto_backup_interval" in settings:
                settings.pop("auto_backup_interval")
                logging.info("Removed deprecated auto_backup_interval setting")
            logging.info("Migrated settings from version 2 to 3")
            
        # Update version
        settings["settings_version"] = self.SETTINGS_VERSION
        return settings
    
    def _reset_settings(self) -> Dict[str, Any]:
        """Reset settings to default values."""
        default_settings = self._get_default_settings()
        self.save_settings(default_settings)
        logging.info("Settings reset to default values")
        return default_settings
        
    def save_settings(self, settings: Optional[Dict[str, Any]] = None) -> bool:
        """
        Save settings with proper encoding and notify listeners.
        
        Returns:
            bool: True if save was successful, False otherwise
        """
        if settings is None:
            settings = self.settings
            
        # Remove deprecated settings before saving
        settings = self._remove_deprecated_settings(settings.copy())
            
        try:
            with open(self.settings_file, "w", encoding='utf-8') as f:
                json.dump(settings, f, indent=4, ensure_ascii=False)
            logging.info("Settings saved successfully")
            
            # Update internal settings
            self.settings = settings
            
            # Notify listeners
            self._notify_listeners()
            return True
            
        except (IOError, OSError) as e:
            logging.error(f"Failed to save settings: {str(e)}")
            return False
            
    def get(self, key: str, default: Any = None) -> Any:
        """Get a setting value with default fallback."""
        return self.settings.get(key, default)
        
    def set(self, key: str, value: Any) -> bool:
        """
        Set a setting and save changes.
        
        Args:
            key: Setting key to change
            value: New value
            
        Returns:
            bool: True if the setting was changed, False otherwise
        """
        # Check if key is deprecated
        if key in self.DEPRECATED_SETTINGS:
            logging.warning(f"Attempted to set deprecated setting: {key}")
            return False
            
        # Check if key is in schema
        if key not in self.SETTINGS_SCHEMA:
            logging.warning(f"Attempted to set unknown setting: {key}")
            return False
            
        # Special handling for the backup folder
        if key == "backup_folder":
            return self.set_backup_folder(value)
        
        # Validate value against schema
        schema = self.SETTINGS_SCHEMA[key]
        expected_type = schema.get("type")
        
        # Type check
        if expected_type and not isinstance(value, expected_type):
            logging.warning(f"Invalid type for setting '{key}'. Expected {expected_type}, got {type(value)}")
            return False
            
        # Range check for numeric values
        if expected_type == int:
            min_val = schema.get("min")
            max_val = schema.get("max")
            if min_val is not None and value < min_val:
                logging.warning(f"Value for '{key}' below minimum ({min_val})")
                return False
            if max_val is not None and value > max_val:
                logging.warning(f"Value for '{key}' above maximum ({max_val})")
                return False
                
        # Options check
        if "options" in schema and value not in schema["options"]:
            logging.warning(f"Invalid option for '{key}': {value}")
            return False
            
        # Set and save
        changed = self.settings.get(key) != value
        self.settings[key] = value
        
        if changed:
            self.save_settings()
            return True
        return False
        
    def set_backup_folder(self, folder_path: str) -> bool:
        """
        Change the backup folder with proper migration of existing data.
        
        Args:
            folder_path: New backup folder path
            
        Returns:
            bool: True if changed successfully, False otherwise
        """
        if not folder_path:
            logging.error("Backup folder cannot be empty")
            return False
            
        # Normalize path
        folder_path = os.path.normpath(folder_path)
        
        # If path is the same, do nothing
        if folder_path == self.settings.get("backup_folder"):
            return False
            
        # Try to create the directory
        try:
            os.makedirs(folder_path, exist_ok=True)
            
            # Create subdirectories
            versions_dir = os.path.join(folder_path, "versions")
            temp_dir = os.path.join(folder_path, "temp")
            
            os.makedirs(versions_dir, exist_ok=True)
            os.makedirs(temp_dir, exist_ok=True)
            
            # If we have existing data, migrate it
            old_folder = self.settings.get("backup_folder")
            if old_folder and os.path.exists(old_folder) and old_folder != folder_path:
                self.migrate_backup_data(old_folder, folder_path)
            
            # Update setting
            self.settings["backup_folder"] = folder_path
            self.save_settings()
            
            logging.info(f"Backup folder changed to: {folder_path}")
            return True
            
        except (OSError, PermissionError) as e:
            logging.error(f"Failed to set backup folder: {str(e)}")
            return False
            
    def migrate_backup_data(self, source_folder: str, target_folder: str) -> bool:
        """
        Migrate backup data from source to target folder.
        
        Args:
            source_folder: Source backup folder
            target_folder: Target backup folder
            
        Returns:
            bool: True if migration was successful, False otherwise
        """
        try:
            # Ensure target exists
            os.makedirs(target_folder, exist_ok=True)
            
            # Get source subfolders
            source_versions = os.path.join(source_folder, "versions")
            
            if os.path.exists(source_versions) and os.listdir(source_versions):
                # Ensure target subfolder exists
                target_versions = os.path.join(target_folder, "versions")
                os.makedirs(target_versions, exist_ok=True)
                
                # Copy all files
                for item in os.listdir(source_versions):
                    item_path = os.path.join(source_versions, item)
                    if os.path.isdir(item_path):
                        shutil.copytree(
                            item_path,
                            os.path.join(target_versions, item),
                            dirs_exist_ok=True
                        )
                    else:
                        shutil.copy2(item_path, os.path.join(target_versions, item))
                        
            logging.info(f"Successfully migrated backup data from {source_folder} to {target_folder}")
            return True
            
        except (OSError, PermissionError, shutil.Error) as e:
            logging.error(f"Failed to migrate backup data: {str(e)}")
            return False
            
    def add_listener(self, callback: Callable[[], None]) -> None:
        """
        Add a listener to be notified when settings change.
        
        Args:
            callback: Function to call when settings change
        """
        if callback not in self.callbacks:
            self.callbacks.append(callback)
            
    def remove_listener(self, callback: Callable[[], None]) -> None:
        """
        Remove a settings change listener.
        
        Args:
            callback: Function to remove from notifications
        """
        if callback in self.callbacks:
            self.callbacks.remove(callback)
            
    def _notify_listeners(self) -> None:
        """Notify all listeners about settings changes."""
        for callback in self.callbacks:
            try:
                callback()
            except Exception as e:
                logging.error(f"Error in settings listener: {str(e)}")
                
    def reset_to_defaults(self) -> bool:
        """
        Reset settings to default values.
        
        Returns:
            bool: True if reset was successful
        """
        self.settings = self._get_default_settings()
        return self.save_settings()
        
    def export_settings(self, export_path: str) -> bool:
        """
        Export settings to a file.
        
        Args:
            export_path: Path to export settings to
            
        Returns:
            bool: True if export was successful
        """
        try:
            # Create a copy without deprecated settings
            export_data = self._remove_deprecated_settings(self.settings.copy())
            
            with open(export_path, "w", encoding='utf-8') as f:
                json.dump(export_data, f, indent=4, ensure_ascii=False)
                
            logging.info(f"Settings exported to {export_path}")
            return True
            
        except (IOError, OSError) as e:
            logging.error(f"Failed to export settings: {str(e)}")
            return False
            
    def import_settings(self, import_path: str) -> bool:
        """
        Import settings from a file.
        
        Args:
            import_path: Path to import settings from
            
        Returns:
            bool: True if import was successful
        """
        try:
            with open(import_path, "r", encoding='utf-8') as f:
                imported_settings = json.load(f)
                
            # Validate imported settings
            username = self.settings.get("username")  # Preserve current username
            imported_settings["username"] = username
            
            # Remove deprecated settings
            imported_settings = self._remove_deprecated_settings(imported_settings)
            
            validated_settings = self._validate_settings(imported_settings)
            self.settings = validated_settings
            self.save_settings()
            
            logging.info(f"Settings imported from {import_path}")
            return True
            
        except (json.JSONDecodeError, IOError, OSError) as e:
            logging.error(f"Failed to import settings: {str(e)}")
            return False
            
    def get_ui_friendly_value(self, key: str) -> str:
        """
        Get a user-friendly representation of a setting value.
        
        Args:
            key: Setting key
            
        Returns:
            str: Human-readable value
        """
        value = self.get(key)
        
        if key == "backup_folder":
            return str(Path(value).resolve())
            
        elif key == "max_backups":
            return f"{value} versions"
            
        elif key == "notification_level":
            levels = {
                "none": "None",
                "minimal": "Minimal",
                "full": "Full"
            }
            return levels.get(value, value.capitalize())
            
        elif isinstance(value, bool):
            return "Enabled" if value else "Disabled"
            
        return str(value)
        
    def get_all_settings(self) -> Dict[str, Dict[str, Any]]:
        """
        Get all settings with metadata for UI display.
        
        Returns:
            Dict containing all settings with their metadata
        """
        result = {}
        
        for key in self.SETTINGS_SCHEMA.keys():
            if key in self.settings:
                result[key] = {
                    "value": self.settings[key],
                    "display_value": self.get_ui_friendly_value(key),
                    "schema": self.SETTINGS_SCHEMA.get(key, {})
                }
                
        return result