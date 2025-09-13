import sys
import shutil
import platform
from typing import Dict

from core.config import MANAGER_INSTALL_HANDLERS, _os_type


def _get_python_commands():
    """Get available Python executable commands."""
    commands = []
    
    # Try current Python first
    if sys.executable:
        commands.append([sys.executable])
    
    # Try common Python commands
    for cmd in ["python3", "python", "py"]:
        if shutil.which(cmd):
            commands.append([cmd])
    
    return commands


def _detect_installed_managers() -> Dict[str, bool]:
    """Detect available package managers."""
    available = {}
    
    for name in MANAGER_INSTALL_HANDLERS.keys():
        if name == "pip":
            # Check if any Python/pip combination works
            python_cmds = _get_python_commands()
            available[name] = any(shutil.which(cmd[0]) for cmd in python_cmds if cmd)
        else:
            # Check if the manager binary exists
            available[name] = shutil.which(name) is not None
    
    return available


def _manager_human(name: str) -> str:
    """Returns a human-readable name for a manager."""
    names = {
        "pip": "Python (pip)", "npm": "Node.js (npm)", "apt": "APT", "dnf": "DNF", 
        "yum": "YUM", "pacman": "Pacman", "zypper": "Zypper", "apk": "APK", 
        "brew": "Homebrew", "choco": "Chocolatey", "winget": "Winget", 
        "snap": "Snap", "flatpak": "Flatpak",
    }
    return names.get(name, name.title())


def _system_manager_priority():
    """Returns a prioritized list of system package managers for the current OS."""
    ot = _os_type()
    
    if ot == "macos": 
        return ["brew", "snap", "flatpak"]
    elif ot == "windows": 
        return ["winget", "choco"]
    elif ot == "linux":
        # Detect Linux distribution and prioritize accordingly
        linux_managers = [
            ("apt", ["apt", "apt-get"]),
            ("dnf", ["dnf"]),
            ("yum", ["yum"]),
            ("pacman", ["pacman"]),
            ("zypper", ["zypper"]),
            ("apk", ["apk"])
        ]
        
        for manager, commands in linux_managers:
            if any(shutil.which(cmd) for cmd in commands):
                return [manager, "snap", "flatpak"]
        
        # Fallback to universal package managers
        return ["snap", "flatpak"]
    
    return ["snap", "flatpak"]


def _looks_like_python_pkg(pkg: str) -> bool:
    """Heuristics for Python packages."""
    python_indicators = ["==", ">=", "<=", "~=", "!=", "[", "]"]
    python_common = ["py", "django", "flask", "numpy", "pandas", "requests", "boto3", "tensorflow", "torch"]
    
    # Check for version specifiers
    if any(indicator in pkg for indicator in python_indicators):
        return True
    
    # Check for common Python package prefixes/names
    pkg_lower = pkg.lower()
    if any(pkg_lower.startswith(prefix) for prefix in python_common):
        return True
    
    return False


def _looks_like_npm_pkg(pkg: str) -> bool:
    """Heuristics for NPM packages."""
    npm_indicators = pkg.startswith("@")
    npm_common = ["express", "react", "vue", "angular", "typescript", "eslint", "webpack", "lodash", "axios"]
    
    if npm_indicators:
        return True
    
    pkg_lower = pkg.lower()
    if pkg_lower in npm_common:
        return True
    
    return False


def _ordered_install_manager_candidates(pkg: str, installed: Dict[str, bool]):
    """Generates a prioritized list of managers to try for a given package."""
    prefs = []
    
    # Prioritize based on package type heuristics
    if _looks_like_python_pkg(pkg) and installed.get("pip"):
        prefs.append("pip")
    if _looks_like_npm_pkg(pkg) and installed.get("npm"):
        prefs.append("npm")
    
    # Add system package managers in priority order
    for manager in _system_manager_priority():
        if installed.get(manager) and manager not in prefs:
            prefs.append(manager)
    
    # Add any remaining installed managers
    for manager, is_installed in installed.items():
        if is_installed and manager not in prefs:
            prefs.append(manager)
    
    return prefs


def list_managers_status() -> Dict[str, str]:
    """Get status of all package managers."""
    installed = _detect_installed_managers()
    status = {}
    for manager in MANAGER_INSTALL_HANDLERS.keys():
        if manager in installed and installed[manager]:
            status[manager] = "Installed"
        else:
            status[manager] = "Not Installed"
    return status