from enum import Enum
from typing import Dict, List
import os

class FileCategory(Enum):
    CODE = "code"
    DOCUMENT = "document"
    IMAGE = "image"
    SPREADSHEET = "spreadsheet"
    DATABASE = "database"
    CONFIG = "config"
    TEXT = "text"
    UNKNOWN = "unknown"

class FileTypeHandler:
    def __init__(self):
        self.extensions = {
            # Code files
            '.py': FileCategory.CODE,
            '.js': FileCategory.CODE,
            '.java': FileCategory.CODE,
            '.cpp': FileCategory.CODE,
            '.h': FileCategory.CODE,
            '.cs': FileCategory.CODE,
            '.php': FileCategory.CODE,
            
            # Documents
            '.doc': FileCategory.DOCUMENT,
            '.docx': FileCategory.DOCUMENT,
            '.pdf': FileCategory.DOCUMENT,
            '.md': FileCategory.DOCUMENT,
            '.txt': FileCategory.TEXT,
            
            # Config files
            '.json': FileCategory.CONFIG,
            '.yaml': FileCategory.CONFIG,
            '.xml': FileCategory.CONFIG,
            '.ini': FileCategory.CONFIG,
            
            # Images
            '.jpg': FileCategory.IMAGE,
            '.png': FileCategory.IMAGE,
            '.gif': FileCategory.IMAGE,
            
            # Spreadsheets
            '.xlsx': FileCategory.SPREADSHEET,
            '.csv': FileCategory.SPREADSHEET,
        }
        
        # Default commit messages per category
        self.category_commits = {
            FileCategory.CODE: [
                "Added new feature",
                "Fixed bug",
                "Code cleanup",
                "Updated dependencies",
                "Performance improvement"
            ],
            FileCategory.DOCUMENT: [
                "Updated content",
                "Fixed formatting",
                "Added section",
                "Revised document",
                "Fixed typos"
            ],
            FileCategory.IMAGE: [
                "Updated image",
                "Compressed image",
                "Cropped image",
                "Color adjustment",
                "New image version"
            ],
            FileCategory.SPREADSHEET: [
                "Updated data",
                "Fixed formulas",
                "Added new sheet",
                "Updated calculations",
                "Format improvements"
            ],
            FileCategory.CONFIG: [
                "Updated settings",
                "Changed configuration",
                "Added new options",
                "Security update",
                "Environment changes"
            ],
            FileCategory.TEXT: [
                "Updated content",
                "Added notes",
                "Fixed formatting",
                "Content revision",
                "Minor changes"
            ],
            FileCategory.UNKNOWN: [
                "Updated file",
                "Made changes",
                "New version",
                "Minor update",
                "Fixed issues"
            ]
        }

    def get_file_category(self, file_path: str) -> FileCategory:
        """Determine file category based on extension."""
        ext = os.path.splitext(file_path.lower())[1]
        return self.extensions.get(ext, FileCategory.UNKNOWN)

    def get_commit_suggestions(self, file_path: str) -> List[str]:
        """Get relevant commit message suggestions for the file type."""
        category = self.get_file_category(file_path)
        return self.category_commits.get(category, self.category_commits[FileCategory.UNKNOWN])

    def get_category_icon(self, category: FileCategory) -> str:
        """Get emoji icon for file category."""
        icons = {
            FileCategory.CODE: "👨‍💻",
            FileCategory.DOCUMENT: "📄",
            FileCategory.IMAGE: "🖼️",
            FileCategory.SPREADSHEET: "📊",
            FileCategory.DATABASE: "🗄️",
            FileCategory.CONFIG: "⚙️",
            FileCategory.TEXT: "📝",
            FileCategory.UNKNOWN: "📎"
        }
        return icons.get(category, "📎")