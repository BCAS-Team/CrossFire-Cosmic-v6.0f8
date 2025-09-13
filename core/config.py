import platform
from pathlib import Path

# Version info
__version__ = "CrossFire v6.0f8 - Cosmic (Pre-Release)"

# Configuration & Constants
DEFAULT_UPDATE_URL = ""
CROSSFIRE_DIR = Path.home() / ".crossfire"
CROSSFIRE_DB = CROSSFIRE_DIR / "packages.db"
CROSSFIRE_CACHE = CROSSFIRE_DIR / "cache"

# Ensure CrossFire directory exists
CROSSFIRE_DIR.mkdir(exist_ok=True)
CROSSFIRE_CACHE.mkdir(exist_ok=True)

# OS & Architecture Detection
OS_NAME = platform.system()
ARCH = platform.architecture()[0]

try:
    import distro  # type: ignore
    DISTRO_NAME = distro.id() or "linux"
    DISTRO_VERSION = distro.version() or ""
except Exception:
    if OS_NAME == "Darwin":
        DISTRO_NAME = "macOS"
        DISTRO_VERSION = platform.mac_ver()[0]
    elif OS_NAME == "Windows":
        DISTRO_NAME = "Windows"
        DISTRO_VERSION = platform.version()
    else:
        DISTRO_NAME = OS_NAME.lower()
        DISTRO_VERSION = ""

# Package manager install command handlers mapping
MANAGER_INSTALL_HANDLERS = {
    "pip": "pip_install",
    "npm": "npm_install", 
    "apt": "apt_install",
    "dnf": "dnf_install",
    "yum": "yum_install",
    "pacman": "pacman_install",
    "zypper": "zypper_install",
    "apk": "apk_install",
    "brew": "brew_install",
    "choco": "choco_install",
    "winget": "winget_install",
    "snap": "snap_install",
    "flatpak": "flatpak_install",
}

# Package manager removal command handlers mapping
MANAGER_REMOVE_HANDLERS = {
    "pip": "pip_remove",
    "npm": "npm_remove",
    "brew": "brew_remove",
    "apt": "apt_remove",
    "dnf": "dnf_remove",
    "yum": "yum_remove",
    "pacman": "pacman_remove",
    "snap": "snap_remove",
    "flatpak": "flatpak_remove",
}

# Manager setup information
MANAGER_SETUP = {
    "pip": {
        "os": ["windows", "linux", "macos"],
        "install": "Pip is bundled with Python 3.4+. Run: python -m ensurepip --upgrade",
        "install_cmd": ["-m", "ensurepip", "--upgrade"]
    },
    "npm": {
        "os": ["windows", "linux", "macos"],
        "install": "https://nodejs.org/ (download Node.js which includes npm)",
        "install_cmd": None
    },
    "apt": {
        "os": ["linux"],
        "install": "APT is preinstalled on Debian/Ubuntu systems",
        "install_cmd": None
    },
    "dnf": {
        "os": ["linux"],
        "install": "DNF is preinstalled on Fedora systems",
        "install_cmd": None
    },
    "yum": {
        "os": ["linux"],
        "install": "YUM is preinstalled on RHEL/CentOS systems",
        "install_cmd": None
    },
    "pacman": {
        "os": ["linux"],
        "install": "pacman is preinstalled on Arch Linux",
        "install_cmd": None
    },
    "zypper": {
        "os": ["linux"],
        "install": "zypper is preinstalled on openSUSE",
        "install_cmd": None
    },
    "apk": {
        "os": ["linux"],
        "install": "apk is bundled with Alpine Linux",
        "install_cmd": None
    },
    "brew": {
        "os": ["macos", "linux"],
        "install": '/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"',
        "install_cmd": None  # Requires shell execution
    },
    "choco": {
        "os": ["windows"],
        "install": 'Set-ExecutionPolicy Bypass -Scope Process -Force; [System.Net.ServicePointManager]::SecurityProtocol = [System.Net.ServicePointManager]::SecurityProtocol -bor 3072; iex ((New-Object System.Net.WebClient).DownloadString("https://chocolatey.org/install.ps1"))',
        "install_cmd": None  # Requires PowerShell
    },
    "winget": {
        "os": ["windows"],
        "install": "winget is preinstalled on Windows 11. Install via Microsoft Store on Windows 10.",
        "install_cmd": None
    },
    "snap": {
        "os": ["linux"],
        "install": "Install snapd package",
        "install_cmd": ["sudo", "apt", "install", "-y", "snapd"]
    },
    "flatpak": {
        "os": ["linux"],
        "install": "Install flatpak package",
        "install_cmd": ["sudo", "apt", "install", "-y", "flatpak"]
    },
}

# Global logger instance placeholder (will be imported from logger module)
LOG = None

def _os_type() -> str:
    """Returns a simplified OS name for heuristics."""
    s = platform.system().lower()
    if s.startswith("win"): return "windows"
    if s == "darwin": return "macos"
    if s == "linux": return "linux"
    return "unknown"