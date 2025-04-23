# models/file_version.py

from dataclasses import dataclass
from typing import Dict, Any, Optional
from datetime import datetime

@dataclass
class FileVersion:
    """Data structure for file version information."""
    hash: str
    timestamp: str
    commit_message: str
    username: str
    file_path: str
    previous_hash: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

    def __post_init__(self):
        """Initialize metadata if not provided."""
        if self.metadata is None:
            self.metadata = {}