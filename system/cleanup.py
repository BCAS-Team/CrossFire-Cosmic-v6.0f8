import os
import sys
import shutil
from pathlib import Path
from typing import Dict, List

from core.execution import run_command
from core.logger import cprint, LOG
from core.progress import ProgressBar
from managers.detection import _detect_installed_managers, _manager_human


def find_pycache_dirs(start_path: Path) -> List[Path]:
    """Recursively find all __pycache__ directories and .pyc files."""
    cache_items = []
    try:
        for root, dirs, files in os.walk(start_path):
            # Add __pycache__ directories
            if '__pycache__' in dirs:
                cache_items.append(Path(root) / '__pycache__')
            
            # Add individual .pyc files
            for file in files:
                if file.endswith('.pyc'):
                    cache_items.append(Path(root) / file)
    except (PermissionError, OSError):
        pass  # Skip directories we can't access
    return cache_items


def clear_python_cache() -> Dict[str, str]:
    """Clear Python cache files and directories."""
    if not LOG.quiet:
        cprint("Clearing Python cache files...", "INFO")
    
    try:
        # Common Python cache locations
        cache_locations = [
            Path.cwd(),  # Current directory
            Path.home(),  # User home directory
        ]
        
        # Add Python installation directory
        if hasattr(sys, 'prefix'):
            cache_locations.append(Path(sys.prefix))
        
        # Add site-packages directories
        try:
            import site
            for site_dir in site.getsitepackages():
                cache_locations.append(Path(site_dir))
        except:
            pass
        
        # Add PYTHONPATH directories
        if 'PYTHONPATH' in os.environ:
            for path in os.environ['PYTHONPATH'].split(os.pathsep):
                if path and Path(path).exists():
                    cache_locations.append(Path(path))
        
        total_removed = 0
        total_size = 0
        
        # Remove duplicates and filter valid paths
        unique_locations = []
        for loc in cache_locations:
            if loc.exists() and loc not in unique_locations:
                unique_locations.append(loc)
        
        for location in unique_locations:
            cache_items = find_pycache_dirs(location)
            
            for cache_item in cache_items:
                try:
                    if cache_item.is_file():
                        size = cache_item.stat().st_size
                        cache_item.unlink()
                        total_removed += 1
                        total_size += size
                    elif cache_item.is_dir():
                        # Calculate directory size before removal
                        for file_path in cache_item.rglob('*'):
                            if file_path.is_file():
                                try:
                                    total_size += file_path.stat().st_size
                                    total_removed += 1
                                except (OSError, PermissionError):
                                    pass
                        shutil.rmtree(cache_item, ignore_errors=True)
                except (OSError, PermissionError):
                    pass  # Skip files we can't remove
        
        size_mb = total_size / (1024 * 1024)
        message = f"Removed {total_removed} cache files ({size_mb:.1f} MB freed)"
        return {"ok": "true", "msg": message}
        
    except Exception as e:
        return {"ok": "false", "msg": f"Error clearing Python cache: {e}"}


def clear_node_cache() -> Dict[str, str]:
    """Clear Node.js npm cache."""
    try:
        # Check if npm is available
        if not shutil.which("npm"):
            return {"ok": "false", "msg": "NPM not available"}
        
        result = run_command(["npm", "cache", "clean", "--force"], timeout=120)
        if result.ok:
            return {"ok": "true", "msg": "NPM cache cleared successfully"}
        else:
            error_msg = result.err or result.out or "Failed to clear NPM cache"
            return {"ok": "false", "msg": error_msg.strip()[:100]}
    except Exception as e:
        return {"ok": "false", "msg": f"Error clearing NPM cache: {e}"}


def clear_system_temp() -> Dict[str, str]:
    """Clear system temporary files safely."""
    if not LOG.quiet:
        cprint("Clearing system temporary files...", "INFO")
    
    try:
        import tempfile
        import time
        
        temp_dir = Path(tempfile.gettempdir())
        if not temp_dir.exists():
            return {"ok": "false", "msg": "Temp directory not found"}
        
        total_removed = 0
        total_size = 0
        current_time = time.time()
        
        # Patterns for temporary files (only remove CrossFire and common temp patterns)
        patterns = [
            "crossfire_*",
            "pip-*",
            "npm-*",
            "tmp_*",
            "temp_*"
        ]
        
        for pattern in patterns:
            for temp_item in temp_dir.glob(pattern):
                try:
                    # Only remove files/dirs older than 1 hour to be safe
                    if temp_item.stat().st_mtime + 3600 < current_time:
                        if temp_item.is_file():
                            size = temp_item.stat().st_size
                            temp_item.unlink()
                            total_removed += 1
                            total_size += size
                        elif temp_item.is_dir():
                            # Calculate directory size
                            for file_path in temp_item.rglob('*'):
                                if file_path.is_file():
                                    try:
                                        total_size += file_path.stat().st_size
                                        total_removed += 1
                                    except (OSError, PermissionError):
                                        pass
                            shutil.rmtree(temp_item, ignore_errors=True)
                except (OSError, PermissionError):
                    pass  # Skip files we can't remove
        
        size_mb = total_size / (1024 * 1024)
        message = f"Removed {total_removed} temporary files ({size_mb:.1f} MB freed)"
        return {"ok": "true", "msg": message}
        
    except Exception as e:
        return {"ok": "false", "msg": f"Error clearing temporary files: {e}"}


def cleanup_system() -> Dict[str, Dict[str, str]]:
    """Enhanced cleanup with cache clearing and progress tracking."""
    if not LOG.quiet:
        cprint("Starting comprehensive system cleanup...", "INFO")
    
    results = {}
    installed = _detect_installed_managers()
    
    # Package manager cleanup commands
    cleanup_commands = {
        "pip": [sys.executable, "-m", "pip", "cache", "purge"],
        "npm": ["npm", "cache", "clean", "--force"],
        "brew": ["brew", "cleanup", "--prune=all"],
        "apt": "sudo apt autoremove -y && sudo apt autoclean",
        "dnf": ["sudo", "dnf", "clean", "all"],
        "yum": ["sudo", "yum", "clean", "all"],
        "pacman": ["sudo", "pacman", "-Sc", "--noconfirm"],
        "zypper": ["sudo", "zypper", "clean", "--all"],
        "apk": ["sudo", "apk", "cache", "clean"],
        "snap": ["sudo", "snap", "refresh"],
        "flatpak": ["flatpak", "uninstall", "--unused", "-y"],
        "choco": ["choco", "cleanup", "-y"],
        "winget": ["winget", "upgrade", "--all", "--silent"]
    }
    
    # Filter to only available package managers
    available_cleanups = []
    for mgr, cmd in cleanup_commands.items():
        if installed.get(mgr):
            available_cleanups.append((mgr, cmd))
    
    # Add custom cleanup operations
    custom_cleanups = [
        ("python_cache", clear_python_cache),
        ("node_cache", clear_node_cache),
        ("system_temp", clear_system_temp),
    ]
    
    total_operations = len(available_cleanups) + len(custom_cleanups)
    
    if total_operations == 0:
        if not LOG.quiet:
            cprint("No cleanup operations available.", "WARNING")
        return results
    
    progress = ProgressBar(total_operations, "Cleanup progress", "operations")
    
    # Run package manager cleanups
    for manager, cmd in available_cleanups:
        try:
            if not LOG.quiet:
                cprint(f"Cleaning {_manager_human(manager)}...", "INFO")
            
            use_shell = isinstance(cmd, str)
            result = run_command(cmd, timeout=300, shell=use_shell)
            
            if result.ok:
                results[manager] = {"ok": "true", "msg": "Cleanup successful"}
                if not LOG.quiet:
                    cprint(f"{_manager_human(manager)}: Cleanup successful", "SUCCESS")
            else:
                error_msg = result.err or result.out or "Cleanup failed"
                results[manager] = {"ok": "false", "msg": error_msg.strip()[:100]}
                if not LOG.quiet:
                    cprint(f"{_manager_human(manager)}: Cleanup failed", "WARNING")
                
        except Exception as e:
            results[manager] = {"ok": "false", "msg": f"Exception: {e}"}
            if not LOG.quiet:
                cprint(f"{_manager_human(manager)}: Exception during cleanup: {e}", "WARNING")
        finally:
            progress.update(1)
    
    # Run custom cleanups
    for cleanup_name, cleanup_func in custom_cleanups:
        try:
            if not LOG.quiet:
                display_name = cleanup_name.replace('_', ' ').title()
                cprint(f"Running {display_name} cleanup...", "INFO")
            
            result = cleanup_func()
            results[cleanup_name] = result
            
            if not LOG.quiet:
                color = "SUCCESS" if result.get("ok") == "true" else "WARNING"
                display_name = cleanup_name.replace('_', ' ').title()
                cprint(f"{display_name}: {result['msg']}", color)
            
        except Exception as e:
            results[cleanup_name] = {"ok": "false", "msg": f"Exception: {e}"}
            if not LOG.quiet:
                display_name = cleanup_name.replace('_', ' ').title()
                cprint(f"{display_name}: Exception during cleanup: {e}", "WARNING")
        finally:
            progress.update(1)
    
    progress.finish()
    
    # Summary
    if not LOG.quiet:
        successful = sum(1 for r in results.values() if r.get("ok") == "true")
        total = len(results)
        cprint(f"Cleanup complete: {successful}/{total} operations completed successfully", 
               "SUCCESS" if successful > 0 else "WARNING")
    
    return results