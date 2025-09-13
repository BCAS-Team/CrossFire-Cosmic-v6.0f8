"""
CrossFire Package Installation System
High-level package installation and removal logic with enhanced parallel processing
"""

import re
import sys
import time
import threading
import concurrent.futures
from typing import Tuple, List, Optional, Dict, Any
from dataclasses import dataclass
from pathlib import Path

from core.config import MANAGER_SETUP, _os_type
from core.logger import cprint, LOG
from core.execution import run_command, RunResult
from core.database import package_db
from core.progress import ProgressBar
from .detection import _detect_installed_managers, _manager_human, _ordered_install_manager_candidates
from .commands import INSTALL_HANDLERS, REMOVE_HANDLERS


@dataclass
class InstallResult:
    """Result of a package installation attempt"""
    package: str
    success: bool
    manager: Optional[str] = None
    version: Optional[str] = None
    duration: float = 0.0
    attempts: int = 0
    error: Optional[str] = None


class PackageInstallationError(Exception):
    """Custom exception for package installation errors"""
    def __init__(self, package: str, message: str, attempts: List[Tuple[str, RunResult]]):
        self.package = package
        self.message = message
        self.attempts = attempts
        super().__init__(f"Failed to install {package}: {message}")


def _extract_package_version(output: str, manager: str) -> str:
    """Extract version info from installation output with enhanced patterns."""
    try:
        if manager == "pip":
            # Look for "Successfully installed package-version"
            patterns = [
                r"Successfully installed .* (\S+)-(\d+\.\d+\.\d+[^\s]*)",
                r"Successfully installed (\S+)-(\d+\.\d+\.\d+[^\s]*)",
                r"Requirement already satisfied: (\S+)==(\d+\.\d+\.\d+[^\s]*)"
            ]
            for pattern in patterns:
                match = re.search(pattern, output)
                if match:
                    return match.group(2) if len(match.groups()) > 1 else match.group(1)
        elif manager == "npm":
            # Look for version in npm output
            patterns = [
                r"@(\d+\.\d+\.\d+[^\s]*)",
                r"(\d+\.\d+\.\d+[^\s]*)"
            ]
            for pattern in patterns:
                match = re.search(pattern, output)
                if match:
                    return match.group(1)
        elif manager in ["apt", "dnf", "yum", "zypper"]:
            # Look for version in package manager output
            match = re.search(r"(\d+\.\d+\.\d+[^\s]*)", output)
            if match:
                return match.group(1)
        elif manager == "brew":
            # Homebrew version extraction
            match = re.search(r"(\d+\.\d+\.\d+[^\s]*)", output)
            if match:
                return match.group(1)
    except Exception:
        pass
    return "installed"


def install_manager(manager: str) -> bool:
    """Attempt to install a package manager if supported on this OS."""
    manager = manager.lower()
    info = MANAGER_SETUP.get(manager)
    if not info:
        cprint(f"Manager '{manager}' not supported.", "ERROR")
        return False
    
    os_name = _os_type()
    if os_name not in info["os"]:
        cprint(f"{manager} is not supported on this OS ({os_name}).", "ERROR")
        return False
    
    # Check if already installed
    if _detect_installed_managers().get(manager, False):
        cprint(f"{_manager_human(manager)} is already installed.", "SUCCESS")
        return True
    
    cmd = info.get("install_cmd")
    install_msg = info.get("install")
    
    if cmd:
        cprint(f"Installing {_manager_human(manager)}...", "INFO")
        
        # Handle Python-based installations
        if manager == "pip":
            full_cmd = [sys.executable] + cmd
        else:
            full_cmd = cmd
            
        result = run_command(full_cmd, timeout=900, show_progress=True)
        if result.ok:
            cprint(f"Successfully installed {_manager_human(manager)}", "SUCCESS")
            return True
        else:
            cprint(f"Failed to install {_manager_human(manager)}: {result.err}", "ERROR")
            return False
    else:
        cprint(f"Manual installation required for {_manager_human(manager)}:", "WARNING")
        cprint(f"  {install_msg}", "INFO")
        return False


def install_package(pkg: str, preferred_manager: Optional[str] = None) -> Tuple[bool, List[Tuple[str, RunResult]]]:
    """Install a single package using available managers with enhanced progress tracking."""
    cprint(f"Preparing to install: {pkg}", "INFO")
    installed = _detect_installed_managers()
    
    if not any(installed.values()):
        cprint("No supported package managers are available on this system.", "ERROR")
        return (False, [])
    
    attempts: List[Tuple[str, RunResult]] = []
    candidates = _ordered_install_manager_candidates(pkg, installed)

    if preferred_manager:
        pm = preferred_manager.lower()
        if pm in INSTALL_HANDLERS and installed.get(pm):
            # Move preferred manager to front
            candidates = [pm] + [m for m in candidates if m != pm]
        else:
            available_managers = [m for m, avail in installed.items() if avail]
            cprint(f"Warning: --manager '{preferred_manager}' not available. Available: {', '.join(available_managers)}", "WARNING")

    if not candidates:
        cprint("No package managers available for installation.", "ERROR")
        return (False, [])

    if not LOG.quiet:
        cprint("Installation plan:", "CYAN")
        for i, m in enumerate(candidates, 1):
            cprint(f"  {i}. {_manager_human(m)}", "MUTED")

    for i, manager in enumerate(candidates, 1):
        cmd_builder = INSTALL_HANDLERS.get(manager)
        if not cmd_builder:
            continue
            
        try:
            cmd = cmd_builder(pkg)
            if not LOG.quiet:
                cprint(f"Attempt {i}/{len(candidates)}: Installing via {_manager_human(manager)}...", "INFO")
            
            # Use longer timeout for installations with progress tracking
            res = run_command(cmd, timeout=1800, retries=0, show_progress=True)
            attempts.append((manager, res))
            
            if res.ok:
                # Extract version and record installation
                version = _extract_package_version(res.out, manager)
                package_db.add_package(pkg, version, manager, ' '.join(cmd))
                
                cprint(f"Successfully installed '{pkg}' via {_manager_human(manager)}", "SUCCESS")
                return (True, attempts)
            else:
                # Show more helpful error messages
                err_msg = (res.err or res.out).strip()
                if err_msg and not LOG.quiet:
                    # Get the last few lines of error output
                    error_lines = err_msg.splitlines()
                    relevant_error = error_lines[-1] if error_lines else "Unknown error"
                    if len(relevant_error) > 180:
                        relevant_error = relevant_error[:177] + "..."
                    cprint(f"{_manager_human(manager)} failed: {relevant_error}", "WARNING")
                elif not LOG.quiet:
                    cprint(f"{_manager_human(manager)} failed with no error message", "WARNING")
                    
        except Exception as e:
            err_result = RunResult(False, -1, "", str(e))
            attempts.append((manager, err_result))
            if not LOG.quiet:
                cprint(f"{_manager_human(manager)} failed with exception: {str(e)}", "WARNING")

    cprint(f"Failed to install '{pkg}' with all available managers.", "ERROR")
    return (False, attempts)


def remove_package(pkg: str, preferred_manager: Optional[str] = None) -> Tuple[bool, List[Tuple[str, RunResult]]]:
    """Remove a single package using available managers."""
    cprint(f"Preparing to remove: {pkg}", "INFO")
    installed = _detect_installed_managers()
    
    if not any(installed.values()):
        cprint("No supported package managers are available on this system.", "ERROR")
        return (False, [])
    
    attempts: List[Tuple[str, RunResult]] = []
    
    # Check if package was installed via CrossFire
    crossfire_pkg = package_db.get_package_info(pkg)
    if crossfire_pkg:
        # Try to remove using the manager that was used to install it
        preferred_manager = crossfire_pkg.get('manager')
        cprint(f"Package was installed via {_manager_human(preferred_manager)}, trying that first", "INFO")
    
    # Build candidate list for removal
    candidates = []
    if preferred_manager and preferred_manager in REMOVE_HANDLERS and installed.get(preferred_manager):
        candidates.append(preferred_manager)
    
    # Add other available managers
    for manager in REMOVE_HANDLERS:
        if manager != preferred_manager and installed.get(manager):
            candidates.append(manager)

    if not candidates:
        cprint("No package managers available for removal.", "ERROR")
        return (False, [])

    if not LOG.quiet:
        cprint("Removal plan:", "CYAN")
        for i, m in enumerate(candidates, 1):
            cprint(f"  {i}. {_manager_human(m)}", "MUTED")

    for i, manager in enumerate(candidates, 1):
        cmd_builder = REMOVE_HANDLERS.get(manager)
        if not cmd_builder:
            continue
            
        try:
            cmd = cmd_builder(pkg)
            if not LOG.quiet:
                cprint(f"Attempt {i}/{len(candidates)}: Removing via {_manager_human(manager)}...", "INFO")
            
            res = run_command(cmd, timeout=600, retries=0)
            attempts.append((manager, res))
            
            if res.ok:
                # Remove from CrossFire database if it exists
                if crossfire_pkg:
                    package_db.remove_package(pkg)
                
                cprint(f"Successfully removed '{pkg}' via {_manager_human(manager)}", "SUCCESS")
                return (True, attempts)
            else:
                err_msg = (res.err or res.out).strip()
                if err_msg and not LOG.quiet:
                    error_lines = err_msg.splitlines()
                    relevant_error = error_lines[-1] if error_lines else "Unknown error"
                    if len(relevant_error) > 180:
                        relevant_error = relevant_error[:177] + "..."
                    cprint(f"{_manager_human(manager)} failed: {relevant_error}", "WARNING")
                elif not LOG.quiet:
                    cprint(f"{_manager_human(manager)} failed with no error message", "WARNING")
                    
        except Exception as e:
            err_result = RunResult(False, -1, "", str(e))
            attempts.append((manager, err_result))
            if not LOG.quiet:
                cprint(f"{_manager_human(manager)} failed with exception: {str(e)}", "WARNING")

    cprint(f"Failed to remove '{pkg}' with all available managers.", "ERROR")
    return (False, attempts)


def _install_single_with_timing(pkg: str, preferred_manager: Optional[str] = None) -> InstallResult:
    """Install a single package with timing information - helper for batch operations."""
    start_time = time.time()
    success, attempts = install_package(pkg, preferred_manager)
    duration = time.time() - start_time
    
    if success and attempts:
        manager, result = attempts[-1]  # Last successful attempt
        version = _extract_package_version(result.out, manager)
        return InstallResult(
            package=pkg,
            success=True,
            manager=manager,
            version=version,
            duration=duration,
            attempts=len(attempts)
        )
    else:
        error_msg = "Installation failed"
        if attempts:
            _, last_result = attempts[-1]
            error_msg = (last_result.err or last_result.out or error_msg).strip()
        
        return InstallResult(
            package=pkg,
            success=False,
            duration=duration,
            attempts=len(attempts),
            error=error_msg[:200]  # Limit error message length
        )


def install_packages_batch(packages: List[str], preferred_manager: Optional[str] = None, 
                          max_workers: int = 4, fail_fast: bool = False) -> Dict[str, Any]:
    """
    Install multiple packages in parallel with comprehensive error handling and progress tracking.
    
    Args:
        packages: List of package names to install
        preferred_manager: Preferred package manager to use
        max_workers: Maximum number of concurrent installations
        fail_fast: Stop all installations if one fails
    
    Returns:
        Dict containing success/failure information and timing data
    """
    if not packages:
        return {
            "success": [],
            "failed": [],
            "total_time": 0,
            "packages_processed": 0,
            "success_rate": 0.0
        }
    
    # Validate and clean package list
    clean_packages = [pkg.strip() for pkg in packages if pkg.strip()]
    if not clean_packages:
        return {
            "success": [],
            "failed": [{"package": "invalid", "error": "No valid packages provided"}],
            "total_time": 0,
            "packages_processed": 0,
            "success_rate": 0.0
        }
    
    start_time = time.time()
    results = {
        "success": [],
        "failed": [],
        "total_time": 0,
        "packages_processed": len(clean_packages),
        "success_rate": 0.0
    }
    
    if not LOG.quiet:
        cprint(f"Installing {len(clean_packages)} packages in parallel (max {max_workers} concurrent)...", "INFO")
    
    # Thread-safe progress tracking
    progress_lock = threading.Lock()
    completed_count = 0
    
    def update_progress():
        nonlocal completed_count
        with progress_lock:
            completed_count += 1
    
    # Use ThreadPoolExecutor for parallel installations
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers, 
                                             thread_name_prefix="CrossFire-Install") as executor:
        # Submit all installation tasks
        future_to_package = {}
        
        for pkg in clean_packages:
            future = executor.submit(_install_single_with_timing, pkg, preferred_manager)
            future_to_package[future] = pkg
        
        # Process results with progress bar
        if not LOG.quiet:
            progress = ProgressBar(len(clean_packages), "Installing packages", "packages")
        
        # Track completion order for better user feedback
        completion_times = []
        
        for future in concurrent.futures.as_completed(future_to_package, timeout=3600):
            package = future_to_package[future]
            
            try:
                install_result = future.result()
                completion_times.append(time.time() - start_time)
                
                if install_result.success:
                    results["success"].append({
                        "package": install_result.package,
                        "manager": install_result.manager,
                        "version": install_result.version,
                        "duration": install_result.duration,
                        "attempts": install_result.attempts
                    })
                    if not LOG.quiet:
                        cprint(f"✓ {package} ({install_result.manager})", "SUCCESS")
                else:
                    results["failed"].append({
                        "package": install_result.package,
                        "error": install_result.error or "Unknown error",
                        "attempts": install_result.attempts,
                        "duration": install_result.duration
                    })
                    if not LOG.quiet:
                        cprint(f"✗ {package}: {install_result.error}", "ERROR")
                    
                    # Fail fast if requested
                    if fail_fast:
                        cprint("Stopping remaining installations due to fail_fast=True", "WARNING")
                        # Cancel remaining futures
                        for remaining_future in future_to_package:
                            if not remaining_future.done():
                                remaining_future.cancel()
                        break
                        
            except concurrent.futures.TimeoutError:
                results["failed"].append({
                    "package": package,
                    "error": "Installation timed out",
                    "attempts": 0,
                    "duration": 3600.0
                })
                if not LOG.quiet:
                    cprint(f"✗ {package}: Timed out", "ERROR")
            except Exception as e:
                results["failed"].append({
                    "package": package,
                    "error": f"Unexpected error: {str(e)}",
                    "attempts": 0,
                    "duration": 0.0
                })
                if not LOG.quiet:
                    cprint(f"✗ {package}: Exception - {str(e)}", "ERROR")
            finally:
                update_progress()
                if not LOG.quiet:
                    progress.update()
        
        if not LOG.quiet:
            progress.finish()
    
    # Calculate final statistics
    results["total_time"] = time.time() - start_time
    success_count = len(results["success"])
    total_count = len(clean_packages)
    results["success_rate"] = (success_count / total_count) * 100 if total_count > 0 else 0.0
    
    # Summary output
    if not LOG.quiet:
        cprint(f"\nBatch installation complete:", "INFO")
        cprint(f"  Packages processed: {total_count}", "INFO")
        cprint(f"  Successful: {success_count}", "SUCCESS" if success_count > 0 else "MUTED")
        cprint(f"  Failed: {len(results['failed'])}", "ERROR" if results['failed'] else "MUTED")
        cprint(f"  Success rate: {results['success_rate']:.1f}%", 
               "SUCCESS" if results['success_rate'] >= 80 else "WARNING" if results['success_rate'] >= 50 else "ERROR")
        cprint(f"  Total time: {results['total_time']:.1f}s", "INFO")
    
    return results


def remove_packages_batch(packages: List[str], preferred_manager: Optional[str] = None, 
                         max_workers: int = 3) -> Dict[str, Any]:
    """
    Remove multiple packages in parallel.
    
    Args:
        packages: List of package names to remove
        preferred_manager: Preferred package manager to use
        max_workers: Maximum number of concurrent removals
    
    Returns:
        Dict containing success/failure information and timing data
    """
    if not packages:
        return {
            "success": [],
            "failed": [],
            "total_time": 0,
            "packages_processed": 0,
            "success_rate": 0.0
        }
    
    clean_packages = [pkg.strip() for pkg in packages if pkg.strip()]
    if not clean_packages:
        return {
            "success": [],
            "failed": [{"package": "invalid", "error": "No valid packages provided"}],
            "total_time": 0,
            "packages_processed": 0,
            "success_rate": 0.0
        }
    
    start_time = time.time()
    results = {
        "success": [],
        "failed": [],
        "total_time": 0,
        "packages_processed": len(clean_packages),
        "success_rate": 0.0
    }
    
    if not LOG.quiet:
        cprint(f"Removing {len(clean_packages)} packages in parallel (max {max_workers} concurrent)...", "INFO")
    
    # Use ThreadPoolExecutor for parallel removals
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers, 
                                             thread_name_prefix="CrossFire-Remove") as executor:
        future_to_package = {}
        
        for pkg in clean_packages:
            future = executor.submit(remove_package, pkg, preferred_manager)
            future_to_package[future] = pkg
        
        if not LOG.quiet:
            progress = ProgressBar(len(clean_packages), "Removing packages", "packages")
        
        for future in concurrent.futures.as_completed(future_to_package, timeout=1800):
            package = future_to_package[future]
            
            try:
                success, attempts = future.result()
                
                if success:
                    results["success"].append({
                        "package": package,
                        "attempts": len(attempts)
                    })
                    if not LOG.quiet:
                        cprint(f"✓ Removed {package}", "SUCCESS")
                else:
                    error_msg = "Removal failed"
                    if attempts:
                        _, last_result = attempts[-1]
                        error_msg = (last_result.err or last_result.out or error_msg).strip()[:200]
                    
                    results["failed"].append({
                        "package": package,
                        "error": error_msg,
                        "attempts": len(attempts)
                    })
                    if not LOG.quiet:
                        cprint(f"✗ {package}: {error_msg}", "ERROR")
                        
            except Exception as e:
                results["failed"].append({
                    "package": package,
                    "error": f"Exception: {str(e)}",
                    "attempts": 0
                })
                if not LOG.quiet:
                    cprint(f"✗ {package}: Exception - {str(e)}", "ERROR")
            finally:
                if not LOG.quiet:
                    progress.update()
        
        if not LOG.quiet:
            progress.finish()
    
    # Calculate final statistics
    results["total_time"] = time.time() - start_time
    success_count = len(results["success"])
    total_count = len(clean_packages)
    results["success_rate"] = (success_count / total_count) * 100 if total_count > 0 else 0.0
    
    if not LOG.quiet:
        cprint(f"\nBatch removal complete:", "INFO")
        cprint(f"  Packages processed: {total_count}", "INFO")
        cprint(f"  Successful: {success_count}", "SUCCESS" if success_count > 0 else "MUTED")
        cprint(f"  Failed: {len(results['failed'])}", "ERROR" if results['failed'] else "MUTED")
        cprint(f"  Success rate: {results['success_rate']:.1f}%", 
               "SUCCESS" if results['success_rate'] >= 80 else "WARNING")
        cprint(f"  Total time: {results['total_time']:.1f}s", "INFO")
    
    return results


def install_from_requirements_file(file_path: str, preferred_manager: Optional[str] = None, 
                                  max_workers: int = 4) -> Dict[str, Any]:
    """
    Install packages from a requirements file with parallel processing.
    
    Args:
        file_path: Path to requirements file
        preferred_manager: Preferred package manager
        max_workers: Maximum concurrent installations
        
    Returns:
        Dict containing installation results
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
    except FileNotFoundError:
        cprint(f"Requirements file not found: {file_path}", "ERROR")
        return {"success": False, "error": "File not found"}
    except Exception as e:
        cprint(f"Error reading requirements file: {e}", "ERROR")
        return {"success": False, "error": str(e)}
    
    # Parse package names from requirements file
    packages = []
    for line in lines:
        line = line.strip()
        if line and not line.startswith('#'):
            # Handle different requirement formats
            pkg_name = line.split('==')[0].split('>=')[0].split('<=')[0].split('~=')[0].split('!=')[0]
            pkg_name = pkg_name.strip()
            if pkg_name:
                packages.append(pkg_name)
    
    if not packages:
        cprint(f"No valid packages found in {file_path}", "WARNING")
        return {"success": False, "error": "No packages found"}
    
    cprint(f"Found {len(packages)} packages in requirements file", "INFO")
    
    # Use batch installation
    return install_packages_batch(packages, preferred_manager, max_workers)