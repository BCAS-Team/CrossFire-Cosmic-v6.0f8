import hashlib
import os
import shutil
import stat
import sys
import time
import urllib.request
import subprocess
from pathlib import Path
from typing import Dict, Tuple, Optional

from core.config import CROSSFIRE_CACHE, OS_NAME, _os_type
from core.execution import run_command
from core.logger import cprint, LOG
from core.progress import ProgressBar
from managers.detection import _detect_installed_managers, _manager_human


def get_crossfire_executable_path() -> Optional[Path]:
    """Find the actual CrossFire executable path using multiple detection methods."""
    try:
        # Method 1: Check if we're running as a script
        if hasattr(sys.modules.get('__main__'), '__file__'):
            current_file = Path(sys.modules['__main__'].__file__).resolve()
            if current_file.name in ['main.py', 'crossfire', 'crossfire.exe', 'crossfire.py']:
                return current_file
            
            # Look for main.py in parent directories
            for parent in current_file.parents:
                main_py = parent / 'main.py'
                if main_py.exists():
                    return main_py
    except (AttributeError, NameError):
        pass
    
    # Method 2: Check sys.argv[0]
    if sys.argv and sys.argv[0]:
        argv_path = Path(sys.argv[0]).resolve()
        if argv_path.exists() and argv_path.is_file():
            return argv_path
    
    # Method 3: Check common installation locations
    common_locations = []
    
    if OS_NAME == "Windows":
        common_locations.extend([
            Path.home() / "AppData" / "Local" / "CrossFire" / "crossfire.exe",
            Path.home() / "AppData" / "Local" / "CrossFire" / "main.py",
            Path.home() / "AppData" / "Local" / "CrossFire" / "crossfire.py"
        ])
    else:
        common_locations.extend([
            Path.home() / ".local" / "bin" / "crossfire",
            Path.home() / ".local" / "bin" / "main.py",
            Path("/usr/local/bin/crossfire"),
            Path("/usr/bin/crossfire")
        ])
    
    for location in common_locations:
        if location.exists() and location.is_file():
            return location
    
    # Method 4: Look in current directory
    current_dir = Path.cwd()
    for name in ['main.py', 'crossfire.py', 'crossfire']:
        potential_path = current_dir / name
        if potential_path.exists() and potential_path.is_file():
            return potential_path
    
    if not LOG.quiet:
        cprint("Warning: Could not determine CrossFire executable path", "WARNING")
    return None


def download_with_resume(url: str, dest_path: Path, expected_hash: str = None) -> bool:
    """Download a file with resume capability and progress tracking."""
    try:
        if not LOG.quiet:
            cprint(f"Downloading from: {url}", "INFO")
        
        # Check if partial download exists
        resume_pos = 0
        if dest_path.exists():
            resume_pos = dest_path.stat().st_size
            if resume_pos > 0 and not LOG.quiet:
                cprint(f"Resuming download from byte {resume_pos}", "INFO")
        
        # Create request with resume header
        request = urllib.request.Request(url)
        request.add_header('User-Agent', 'CrossFire/5.0 (Enhanced Update System)')
        if resume_pos > 0:
            request.add_header('Range', f'bytes={resume_pos}-')
        
        with urllib.request.urlopen(request, timeout=30) as response:
            # Get total size
            if resume_pos > 0:
                # For resumed downloads, get original size from Content-Range header
                content_range = response.info().get('Content-Range', '')
                if content_range:
                    total_size = int(content_range.split('/')[-1])
                else:
                    total_size = int(response.info().get('Content-Length', 0)) + resume_pos
            else:
                total_size = int(response.info().get('Content-Length', 0))
            
            if total_size == 0:
                if not LOG.quiet:
                    cprint("Warning: Cannot determine file size", "WARNING")
                total_size = 10 * 1024 * 1024  # Assume 10MB
            
            # Setup progress tracking
            progress = ProgressBar(total_size, "Download", "B")
            progress.current = resume_pos
            hash_sha256 = hashlib.sha256()
            
            # If resuming, read existing file to update hash
            if resume_pos > 0:
                with open(dest_path, 'rb') as f:
                    while True:
                        chunk = f.read(32768)
                        if not chunk:
                            break
                        hash_sha256.update(chunk)
            
            # Create destination directory
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Download with resume
            mode = 'ab' if resume_pos > 0 else 'wb'
            with open(dest_path, mode) as f:
                while True:
                    chunk = response.read(32768)  # 32KB chunks
                    if not chunk:
                        break
                    
                    f.write(chunk)
                    hash_sha256.update(chunk)
                    progress.update(len(chunk))
            
            progress.finish()
            
            # Verify hash if provided
            if expected_hash:
                actual_hash = hash_sha256.hexdigest()
                if actual_hash.lower() != expected_hash.lower():
                    cprint(f"Hash verification failed!", "ERROR")
                    cprint(f"Expected: {expected_hash}", "ERROR")
                    cprint(f"Actual:   {actual_hash}", "ERROR")
                    dest_path.unlink()
                    return False
                else:
                    if not LOG.quiet:
                        cprint("Hash verification successful", "SUCCESS")
            
            file_size_mb = dest_path.stat().st_size / 1024 / 1024
            if not LOG.quiet:
                cprint(f"Downloaded {file_size_mb:.1f} MB successfully", "SUCCESS")
            return True
            
    except Exception as e:
        cprint(f"Download failed: {e}", "ERROR")
        if dest_path.exists() and resume_pos == 0:  # Don't delete partial downloads
            dest_path.unlink()
        return False


def backup_current_executable(executable_path: Path) -> Optional[Path]:
    """Create a backup of the current executable with cleanup."""
    try:
        timestamp = int(time.time())
        backup_path = executable_path.with_suffix(f'.backup.{timestamp}')
        
        shutil.copy2(executable_path, backup_path)
        if not LOG.quiet:
            cprint(f"Backup created: {backup_path.name}", "INFO")
        
        # Keep only the 3 most recent backups
        backup_pattern = f"{executable_path.stem}.backup.*"
        backups = list(executable_path.parent.glob(backup_pattern))
        backups.sort(key=lambda x: x.stat().st_mtime, reverse=True)
        
        for old_backup in backups[3:]:  # Keep only 3 most recent
            try:
                old_backup.unlink()
                if not LOG.quiet:
                    cprint(f"Removed old backup: {old_backup.name}", "INFO")
            except OSError:
                pass
        
        return backup_path
        
    except Exception as e:
        if not LOG.quiet:
            cprint(f"Failed to create backup: {e}", "WARNING")
        return None


def cross_update(url: str, verify_sha256: str = None) -> bool:
    """Enhanced cross-platform self-update with proper error handling."""
    if not LOG.quiet:
        cprint("Starting CrossFire self-update...", "INFO")
    
    try:
        # Find current executable
        current_executable = get_crossfire_executable_path()
        if not current_executable:
            cprint("Could not locate CrossFire executable for update", "ERROR")
            return False
        
        if not LOG.quiet:
            cprint(f"Updating executable: {current_executable}", "INFO")
        
        # Download to temporary file
        temp_file = CROSSFIRE_CACHE / f"crossfire_update_{int(time.time())}.tmp"
        
        if not download_with_resume(url, temp_file, verify_sha256):
            return False
        
        # Create backup
        backup_path = backup_current_executable(current_executable)
        
        # Platform-specific update process
        if OS_NAME == "Windows":
            success = _windows_update(current_executable, temp_file, backup_path)
        else:
            success = _unix_update(current_executable, temp_file, backup_path)
        
        # Clean up temporary file
        if temp_file.exists():
            temp_file.unlink()
        
        if success:
            if not LOG.quiet:
                cprint("CrossFire updated successfully!", "SUCCESS")
                cprint("Restart CrossFire to use the new version", "INFO")
            
            # Verify the update worked
            try:
                result = run_command([str(current_executable), '--version'], timeout=10)
                if result.ok and not LOG.quiet:
                    version_output = result.out.strip()
                    cprint(f"Update verified: {version_output}", "SUCCESS")
            except:
                pass
            
            return True
        else:
            cprint("Update failed - restoring from backup", "ERROR")
            if backup_path and backup_path.exists():
                try:
                    shutil.copy2(backup_path, current_executable)
                    if not LOG.quiet:
                        cprint("Backup restored successfully", "SUCCESS")
                except Exception as e:
                    cprint(f"Failed to restore backup: {e}", "ERROR")
            return False
            
    except Exception as e:
        cprint(f"Update failed with exception: {e}", "ERROR")
        return False


def _windows_update(current_exe: Path, new_file: Path, backup_path: Optional[Path]) -> bool:
    """Handle Windows-specific update process using batch script."""
    try:
        # On Windows, we can't overwrite a running executable directly
        # Create a batch script to handle the update
        update_script = current_exe.parent / "crossfire_update.bat"
        
        backup_restore = ""
        if backup_path:
            backup_restore = f'''if %errorlevel% neq 0 (
    echo Update failed! Restoring backup...
    copy /y "{backup_path}" "{current_exe}"
    if %errorlevel% equ 0 echo Backup restored successfully
)'''
        
        script_content = f'''@echo off
echo Waiting for CrossFire to close...
timeout /t 3 /nobreak >nul 2>&1

echo Updating CrossFire executable...
copy /y "{new_file}" "{current_exe}"

if %errorlevel% equ 0 (
    echo CrossFire updated successfully!
) else (
    echo Update failed!
    {backup_restore}
)

echo Cleaning up...
del /f /q "{new_file}" 2>nul
del /f /q "{update_script}" 2>nul

pause
'''
        
        with open(update_script, 'w', encoding='utf-8') as f:
            f.write(script_content)
        
        # Start the update script in a new window
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        
        subprocess.Popen(
            ['cmd', '/c', str(update_script)],
            startupinfo=startupinfo
        )
        
        if not LOG.quiet:
            cprint("Update script started. CrossFire will be updated automatically.", "INFO")
        
        return True
        
    except Exception as e:
        cprint(f"Windows update process failed: {e}", "ERROR")
        return False


def _unix_update(current_exe: Path, new_file: Path, backup_path: Optional[Path]) -> bool:
    """Handle Unix/Linux/macOS update process."""
    try:
        # Copy new file over current executable
        shutil.copy2(new_file, current_exe)
        
        # Make executable
        current_exe.chmod(current_exe.stat().st_mode | stat.S_IEXEC)
        
        return True
        
    except Exception as e:
        cprint(f"Unix update process failed: {e}", "ERROR")
        return False


def _update_manager(manager: str) -> Tuple[str, bool, str]:
    """Update a specific package manager with enhanced error handling."""
    manager = manager.lower()
    
    update_commands = {
        "pip": [sys.executable, "-m", "pip", "install", "--upgrade", "pip"],
        "npm": ["npm", "update", "-g", "npm"],
        "brew": ["brew", "update", "&&", "brew", "upgrade"],
        "apt": "sudo apt update && sudo apt upgrade -y",
        "dnf": ["sudo", "dnf", "update", "-y"],
        "yum": ["sudo", "yum", "update", "-y"],  
        "pacman": ["sudo", "pacman", "-Syu", "--noconfirm"],
        "zypper": ["sudo", "zypper", "update", "-y"],
        "apk": ["sudo", "apk", "update", "&&", "sudo", "apk", "upgrade"],
        "snap": ["sudo", "snap", "refresh"],
        "flatpak": ["flatpak", "update", "-y"],
        "choco": ["choco", "upgrade", "all", "-y"],
        "winget": ["winget", "upgrade", "--all", "--silent", "--accept-package-agreements", "--accept-source-agreements"]
    }
    
    cmd = update_commands.get(manager)
    if not cmd:
        return (manager, False, f"Update not supported for {manager}")
    
    # Check if manager is actually installed
    installed = _detect_installed_managers()
    if not installed.get(manager):
        return (manager, False, f"{_manager_human(manager)} is not installed")
    
    try:
        if not LOG.quiet:
            cprint(f"Updating {_manager_human(manager)}...", "INFO")
        
        use_shell = isinstance(cmd, str)
        result = run_command(cmd, timeout=1200, show_progress=True, shell=use_shell)
        
        if result.ok:
            return (manager, True, "Update successful")
        else:
            # Extract meaningful error message
            error_msg = result.err or result.out or "Update failed"
            if error_msg:
                lines = error_msg.strip().split('\n')
                # Get the most relevant error line
                relevant_lines = [line for line in lines if any(word in line.lower() 
                                for word in ['error', 'failed', 'denied', 'not found', 'permission'])]
                if relevant_lines:
                    relevant_error = relevant_lines[-1]
                else:
                    relevant_error = lines[-1] if lines else "Update failed"
                
                if len(relevant_error) > 100:
                    relevant_error = relevant_error[:97] + "..."
                return (manager, False, relevant_error)
            return (manager, False, "Update failed with no error message")
            
    except Exception as e:
        return (manager, False, f"Exception: {str(e)[:100]}")


def _update_all_managers() -> Dict[str, Dict[str, str]]:
    """Update all available package managers with progress tracking."""
    installed = _detect_installed_managers()
    available_managers = [mgr for mgr, avail in installed.items() if avail]
    
    if not available_managers:
        if not LOG.quiet:
            cprint("No package managers found to update", "WARNING")
        return {}
    
    if not LOG.quiet:
        cprint(f"Updating {len(available_managers)} package managers...", "INFO")
    
    results = {}
    progress = ProgressBar(len(available_managers), "Updating managers", "managers")
    
    for manager in available_managers:
        name, ok, msg = _update_manager(manager)
        results[name] = {"ok": str(ok).lower(), "msg": msg}
        
        if not LOG.quiet:
            color = "SUCCESS" if ok else "WARNING"
            cprint(f"{_manager_human(name)}: {msg}", color)
        
        progress.update()
    
    progress.finish()
    
    # Summary
    if not LOG.quiet:
        successful = sum(1 for r in results.values() if r.get("ok") == "true")
        total = len(results)
        cprint(f"Manager updates complete: {successful}/{total} successful", 
               "SUCCESS" if successful > 0 else "WARNING")
    
    return results