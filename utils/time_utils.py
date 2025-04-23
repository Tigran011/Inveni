"""
Centralized time utilities module for consistent time handling across the application.
Provides functions for UTC and local time formatting, string conversions,
and related system information like username.
"""

from datetime import datetime, timedelta
import pytz
import os
import platform
from typing import Dict, Tuple, Optional, Union

# Standard time format used throughout the application
TIME_FORMAT = "%Y-%m-%d %H:%M:%S"
TIME_FORMAT_WITH_TZ = "%Y-%m-%d %H:%M:%S %Z"

def get_current_times() -> Dict[str, Union[str, datetime, float]]:
    """
    Get both UTC and local time in a dictionary with multiple formats.
    
    Returns:
        Dict with 'utc', 'local', 'utc_iso', and 'timestamp' values.
    """
    now_utc = datetime.now(pytz.UTC)
    now_local = now_utc.astimezone()
    
    return {
        "utc": now_utc.strftime(TIME_FORMAT),
        "local": now_local.strftime(TIME_FORMAT_WITH_TZ),
        "utc_iso": now_utc.strftime(TIME_FORMAT),  # Add this for UI compatibility
        "timestamp": now_utc.timestamp(),  # Add numeric timestamp for sorting
        "datetime_utc": now_utc,  # The actual datetime object for advanced usage
        "datetime_local": now_local  # The actual datetime object for advanced usage
    }

def get_formatted_time(use_utc=True) -> str:
    """
    Get a consistently formatted timestamp string.
    
    Args:
        use_utc: If True, return UTC time; otherwise return local time
        
    Returns:
        str: Formatted timestamp YYYY-MM-DD HH:MM:SS
    """
    if use_utc:
        # Using datetime.now(pytz.UTC) for proper timezone awareness
        current_time = datetime.now(pytz.UTC)
    else:
        # Local time
        current_time = datetime.now()
        
    return current_time.strftime(TIME_FORMAT)

def format_timestamp_dual(timestamp_str: str) -> Tuple[str, str]:
    """
    Convert UTC timestamp to both UTC and local time strings.
    
    Args:
        timestamp_str: A timestamp string in YYYY-MM-DD HH:MM:SS format.
        
    Returns:
        Tuple of (utc_string, local_string)
    """
    try:
        dt_utc = datetime.strptime(timestamp_str, TIME_FORMAT)
        dt_utc = pytz.UTC.localize(dt_utc)
        dt_local = dt_utc.astimezone()
        
        return (
            dt_utc.strftime(TIME_FORMAT),
            dt_local.strftime(TIME_FORMAT_WITH_TZ)
        )
    except Exception:
        return ("Unknown", "Unknown")

def format_timestamp(timestamp_str: str, include_timezone=False) -> str:
    """
    Format a timestamp string consistently.
    
    Args:
        timestamp_str: A timestamp string in YYYY-MM-DD HH:MM:SS format.
        include_timezone: Whether to include timezone information.
        
    Returns:
        Formatted timestamp string.
    """
    try:
        dt_utc = datetime.strptime(timestamp_str, TIME_FORMAT)
        dt_utc = pytz.UTC.localize(dt_utc)
        
        if include_timezone:
            return dt_utc.strftime(TIME_FORMAT_WITH_TZ)
        return dt_utc.strftime(TIME_FORMAT)
    except Exception:
        return "Unknown"

def get_current_username() -> str:
    """
    Get current system username consistently and safely.
    
    Returns:
        str: Current username or fallback value if unavailable.
    """
    try:
        return os.getlogin()
    except Exception:
        # Fallback methods based on OS
        try:
            if platform.system() == 'Windows':
                return os.environ.get('USERNAME', 'unknown_user')
            else:  # Unix-like systems
                import pwd
                return pwd.getpwuid(os.getuid()).pw_name
        except Exception:
            return 'unknown_user'

def parse_timestamp(timestamp_str: str) -> Optional[datetime]:
    """
    Parse a timestamp string into a datetime object with UTC timezone.
    
    Args:
        timestamp_str: A timestamp string in YYYY-MM-DD HH:MM:SS format.
        
    Returns:
        datetime object with UTC timezone or None if parsing fails
    """
    try:
        dt = datetime.strptime(timestamp_str, TIME_FORMAT)
        return pytz.UTC.localize(dt)
    except Exception:
        # Try additional formats
        formats_to_try = [
            TIME_FORMAT_WITH_TZ,
            "%Y-%m-%d",
            "%d-%m-%Y %H:%M:%S",
            "%m/%d/%Y %H:%M:%S"
        ]
        
        for fmt in formats_to_try:
            try:
                dt = datetime.strptime(timestamp_str, fmt)
                return pytz.UTC.localize(dt)
            except ValueError:
                continue
                
        return None

def timestamp_to_age_string(timestamp_str: str) -> str:
    """
    Convert a timestamp to a human-readable age string (e.g., "2 days ago").
    
    Args:
        timestamp_str: A timestamp string in YYYY-MM-DD HH:MM:SS format.
        
    Returns:
        Human-readable age string.
    """
    try:
        dt_utc = datetime.strptime(timestamp_str, TIME_FORMAT)
        dt_utc = pytz.UTC.localize(dt_utc)
        now_utc = datetime.now(pytz.UTC)
        delta = now_utc - dt_utc
        
        # Convert to appropriate unit
        if delta.days > 365:
            years = delta.days // 365
            return f"{years} year{'s' if years != 1 else ''} ago"
        elif delta.days > 30:
            months = delta.days // 30
            return f"{months} month{'s' if months != 1 else ''} ago"
        elif delta.days > 0:
            return f"{delta.days} day{'s' if delta.days != 1 else ''} ago"
        elif delta.seconds >= 3600:
            hours = delta.seconds // 3600
            return f"{hours} hour{'s' if hours != 1 else ''} ago"
        elif delta.seconds >= 60:
            minutes = delta.seconds // 60
            return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
        else:
            return "just now"
    except Exception:
        return "unknown time ago"

def is_timestamp_older_than(timestamp_str: str, days: int = 0, hours: int = 0, 
                           minutes: int = 0, seconds: int = 0) -> bool:
    """
    Check if a timestamp is older than the specified time duration.
    
    Args:
        timestamp_str: A timestamp string in YYYY-MM-DD HH:MM:SS format.
        days, hours, minutes, seconds: Time components for comparison.
        
    Returns:
        bool: True if timestamp is older than the specified duration.
    """
    try:
        dt_utc = datetime.strptime(timestamp_str, TIME_FORMAT)
        dt_utc = pytz.UTC.localize(dt_utc)
        now_utc = datetime.now(pytz.UTC)
        
        # Calculate the threshold datetime
        threshold = now_utc - timedelta(days=days, hours=hours, 
                                        minutes=minutes, seconds=seconds)
        
        # Return true if the timestamp is older than the threshold
        return dt_utc < threshold
    except Exception:
        # Default to True for safety in case of invalid timestamps
        return True

def format_date_for_display(dt: Union[str, datetime, dict, None], include_time: bool = True) -> str:
    """
    Format a date(time) for user-friendly display with improved format handling.
    
    Args:
        dt: A datetime object, timestamp string, or dict with time info.
        include_time: Whether to include the time component.
        
    Returns:
        Formatted date string for display.
    """
    try:
        # Handle None case
        if dt is None:
            return "Unknown date"
            
        # Handle dictionary case (for metadata.modification_time)
        if isinstance(dt, dict):
            # Try to get local time first, then UTC
            if "local" in dt:
                return format_date_for_display(dt["local"], include_time)
            elif "utc" in dt:
                return format_date_for_display(dt["utc"], include_time)
            else:
                return "Unknown date format"
        
        # Handle string case with multiple format attempts
        if isinstance(dt, str):
            # If it's an empty string or "Unknown"
            if not dt or dt.lower() == "unknown":
                return "Unknown date"
                
            # Try multiple common date formats
            formats_to_try = [
                TIME_FORMAT,                # Standard format: 2025-04-22 20:03:52
                TIME_FORMAT_WITH_TZ,        # With timezone: 2025-04-22 20:03:52 UTC
                "%Y-%m-%d",                 # Date only: 2025-04-22
                "%d-%m-%Y %H:%M:%S",        # European format
                "%m/%d/%Y %H:%M:%S",        # US format
                "%b %d, %Y at %I:%M %p"     # Already formatted
            ]
            
            # Try each format until one works
            for fmt in formats_to_try:
                try:
                    parsed_dt = datetime.strptime(dt, fmt)
                    # Localize if needed
                    if parsed_dt.tzinfo is None:
                        parsed_dt = pytz.UTC.localize(parsed_dt)
                    
                    # Convert to local time for display
                    local_dt = parsed_dt.astimezone()
                    
                    # Format based on preference
                    if include_time:
                        return local_dt.strftime("%b %d, %Y at %I:%M %p")
                    else:
                        return local_dt.strftime("%b %d, %Y")
                except ValueError:
                    continue
            
            # If we got here, none of the formats worked
            # Just return the original string rather than "Unknown"
            return dt
        
        # Handle datetime object case
        if isinstance(dt, datetime):
            # Ensure timezone awareness
            if dt.tzinfo is None:
                dt = pytz.UTC.localize(dt)
            
            # Convert to local time
            local_dt = dt.astimezone()
            
            # Format based on preference
            if include_time:
                return local_dt.strftime("%b %d, %Y at %I:%M %p")
            else:
                return local_dt.strftime("%b %d, %Y")
                
        # For numeric timestamp (seconds since epoch)
        if isinstance(dt, (int, float)):
            dt = datetime.fromtimestamp(dt, pytz.UTC)
            local_dt = dt.astimezone()
            
            if include_time:
                return local_dt.strftime("%b %d, %Y at %I:%M %p")
            else:
                return local_dt.strftime("%b %d, %Y")
        
        # For other types, convert to string
        return str(dt)
        
    except Exception as e:
        # More informative error handling
        try:
            return f"Cannot format date: {str(dt)[:30]}"
        except:
            return "Unknown date"