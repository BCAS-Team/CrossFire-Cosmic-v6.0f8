import sys
import shutil
from typing import List
from .detection import _get_python_commands


# Install command handlers
def _pip_install(pkg: str) -> List[str]:
    python_cmds = _get_python_commands()
    for cmd in python_cmds:
        if shutil.which(cmd[0]):
            return cmd + ["-m", "pip", "install", "--user", pkg]
    return [sys.executable, "-m", "pip", "install", "--user", pkg]

def _npm_install(pkg: str) -> List[str]:
    return ["npm", "install", "-g", pkg]

def _apt_install(pkg: str) -> List[str]:
    return ["sudo", "apt", "install", "-y", pkg]

def _dnf_install(pkg: str) -> List[str]:
    return ["sudo", "dnf", "install", "-y", pkg]

def _yum_install(pkg: str) -> List[str]:
    return ["sudo", "yum", "install", "-y", pkg]

def _pacman_install(pkg: str) -> List[str]:
    return ["sudo", "pacman", "-S", "--noconfirm", pkg]

def _zypper_install(pkg: str) -> List[str]:
    return ["sudo", "zypper", "--non-interactive", "install", pkg]

def _apk_install(pkg: str) -> List[str]:
    return ["sudo", "apk", "add", pkg]

def _brew_install(pkg: str) -> List[str]:
    return ["brew", "install", pkg]

def _choco_install(pkg: str) -> List[str]:
    return ["choco", "install", "-y", pkg]

def _winget_install(pkg: str) -> List[str]:
    return ["winget", "install", "--silent", "--accept-package-agreements", "--accept-source-agreements", pkg]

def _snap_install(pkg: str) -> List[str]:
    return ["sudo", "snap", "install", pkg]

def _flatpak_install(pkg: str) -> List[str]:
    return ["flatpak", "install", "-y", pkg]

# Removal command handlers
def _pip_remove(pkg: str) -> List[str]:
    python_cmds = _get_python_commands()
    for cmd in python_cmds:
        if shutil.which(cmd[0]):
            return cmd + ["-m", "pip", "uninstall", "-y", pkg]
    return [sys.executable, "-m", "pip", "uninstall", "-y", pkg]

def _npm_remove(pkg: str) -> List[str]:
    return ["npm", "uninstall", "-g", pkg]

def _brew_remove(pkg: str) -> List[str]:
    return ["brew", "uninstall", pkg]

def _apt_remove(pkg: str) -> List[str]:
    return ["sudo", "apt", "remove", "-y", pkg]

def _dnf_remove(pkg: str) -> List[str]:
    return ["sudo", "dnf", "remove", "-y", pkg]

def _yum_remove(pkg: str) -> List[str]:
    return ["sudo", "yum", "remove", "-y", pkg]

def _pacman_remove(pkg: str) -> List[str]:
    return ["sudo", "pacman", "-R", "--noconfirm", pkg]

def _snap_remove(pkg: str) -> List[str]:
    return ["sudo", "snap", "remove", pkg]

def _flatpak_remove(pkg: str) -> List[str]:
    return ["flatpak", "uninstall", "-y", pkg]

# Command handler mappings
INSTALL_HANDLERS = {
    "pip": _pip_install, "npm": _npm_install, "apt": _apt_install, 
    "dnf": _dnf_install, "yum": _yum_install, "pacman": _pacman_install, 
    "zypper": _zypper_install, "apk": _apk_install, "brew": _brew_install,
    "choco": _choco_install, "winget": _winget_install, "snap": _snap_install, 
    "flatpak": _flatpak_install,
}

REMOVE_HANDLERS = {
    "pip": _pip_remove, "npm": _npm_remove, "brew": _brew_remove,
    "apt": _apt_remove, "dnf": _dnf_remove, "yum": _yum_remove,
    "pacman": _pacman_remove, "snap": _snap_remove, "flatpak": _flatpak_remove,
}