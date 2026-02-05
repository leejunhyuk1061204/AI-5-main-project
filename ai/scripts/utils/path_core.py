import os
from pathlib import Path

class PathCore:
    """
    Project-wide path management utility.
    Ensures that script execution is robust regardless of the current working directory.
    """
    
    # Resolve the project root: this should be the 'AI-5-main-project' directory
    # Depending on where this file is located: ai/scripts/utils/path_core.py (3 levels deep from root)
    PROJECT_ROOT = Path(__file__).resolve().parents[3]
    AI_DIR = PROJECT_ROOT / "ai"
    
    @classmethod
    def get_abs_path(cls, relative_path: str) -> str:
        """
        Converts a project-relative path (e.g., 'ai/data/...') to an absolute path.
        """
        # If it's already absolute or has a drive letter (Windows), return as is
        if os.path.isabs(relative_path) or (len(relative_path) > 1 and relative_path[1] == ":"):
            return relative_path
            
        return str((cls.PROJECT_ROOT / relative_path).resolve())

    @classmethod
    def ensure_dir(cls, path: str):
        """Ensures that the directory for the given path exists."""
        abs_path = cls.get_abs_path(path)
        os.makedirs(os.path.dirname(abs_path), exist_ok=True)
        return abs_path

# Export a singleton-like instance if needed, but classmethods are fine.
if __name__ == "__main__":
    print(f"Project Root: {PathCore.PROJECT_ROOT}")
    print(f"AI Directory: {PathCore.AI_DIR}")
    print(f"Test Path: {PathCore.get_abs_path('ai/data/yolo/engine/data.yaml')}")
