import sys
import os

# Add vendor directory to sys.path
VENDOR_DIR = os.path.join(os.path.dirname(__file__), "vendor")
if VENDOR_DIR not in sys.path:
    sys.path.insert(0, VENDOR_DIR)

# Force vendored libraries to replace globally installed versions
import vendor.requests as vendored_requests
import vendor.distro as vendored_distro
sys.modules['requests'] = vendored_requests
sys.modules['distro'] = vendored_distro

# ===== STANDARD LIBRARY IMPORTS =====
import argparse
import json
import shlex
import importlib.util
from typing import List, Optional, Dict, Any

# ===== CORE MODULES =====
from core.config import __version__, LOG, OS_NAME, DEFAULT_UPDATE_URL, MANAGER_INSTALL_HANDLERS
from core.logger import cprint
from core.database import package_db
from core.execution import run_command
from core.progress import ProgressBar

# ===== MANAGERS =====
from managers.detection import (
    _detect_installed_managers,
    _manager_human,
    list_managers_status
)
from managers.installer import (
    install_package, remove_package, install_manager,
    install_packages_batch, remove_packages_batch, install_from_requirements_file
)

# ===== SEARCH =====
from search.engine import search_engine

# ===== SYSTEM FUNCTIONS =====
from system.health import health_check
from system.cleanup import cleanup_system, clear_python_cache
from system.stats import show_statistics, show_installed_packages
from system.setup import install_launcher, add_to_path_safely
from system.update import cross_update, _update_all_managers, _update_manager
from system.bulk import bulk_install_from_file, export_packages

# ===== NETWORK =====
from network.testing import SpeedTest

# ===== MODULE SYSTEM =====
class ModuleManager:
    """Manages dynamic loading and execution of CrossFire modules."""
    
    def __init__(self, modules_dir: str = None):
        self.modules_dir = modules_dir or os.path.join(os.path.dirname(__file__), "modules")
        self.loaded_modules = {}
        self._discover_modules()
    
    def _discover_modules(self):
        """Discover available modules in the modules directory."""
        if not os.path.exists(self.modules_dir):
            return
        
        for item in os.listdir(self.modules_dir):
            module_path = os.path.join(self.modules_dir, item)
            if os.path.isdir(module_path):
                main_py = os.path.join(module_path, "main.py")
                if os.path.exists(main_py):
                    self.loaded_modules[item.lower()] = {
                        'name': item,
                        'path': module_path,
                        'main_file': main_py,
                        'loaded': False,
                        'module_obj': None
                    }
    
    def list_modules(self) -> Dict[str, Dict]:
        """List all discovered modules."""
        return self.loaded_modules.copy()
    
    def load_module(self, module_name: str):
        """Dynamically load a module."""
        module_name = module_name.lower()
        if module_name not in self.loaded_modules:
            return None
        
        module_info = self.loaded_modules[module_name]
        if module_info['loaded']:
            return module_info['module_obj']
        
        try:
            spec = importlib.util.spec_from_file_location(
                f"crossfire_module_{module_name}", 
                module_info['main_file']
            )
            module_obj = importlib.util.module_from_spec(spec)
            
            # Add the module's directory to sys.path temporarily
            original_path = sys.path[:]
            sys.path.insert(0, module_info['path'])
            
            try:
                spec.loader.exec_module(module_obj)
                module_info['module_obj'] = module_obj
                module_info['loaded'] = True
                return module_obj
            finally:
                sys.path[:] = original_path
                
        except Exception as e:
            if not LOG.quiet:
                cprint(f"Error loading module '{module_name}': {e}", "ERROR")
            return None
    
    def execute_module(self, module_name: str, args: List[str]) -> int:
        """Execute a module's main function with arguments."""
        module_obj = self.load_module(module_name)
        if not module_obj:
            cprint(f"Module '{module_name}' not found or failed to load", "ERROR")
            return 1
        
        # Check for required functions
        if not hasattr(module_obj, 'main'):
            cprint(f"Module '{module_name}' missing required 'main' function", "ERROR")
            return 1
        
        try:
            # Call the module's main function
            result = module_obj.main(args)
            return result if isinstance(result, int) else 0
        except Exception as e:
            if not LOG.quiet:
                cprint(f"Error executing module '{module_name}': {e}", "ERROR")
            if LOG.verbose:
                import traceback
                traceback.print_exc()
            return 1
    
    def get_module_info(self, module_name: str) -> Optional[Dict]:
        """Get information about a module."""
        module_obj = self.load_module(module_name.lower())
        if not module_obj:
            return None
        
        info = {
            'name': module_name,
            'description': getattr(module_obj, '__description__', 'No description available'),
            'version': getattr(module_obj, '__version__', '1.0.0'),
            'author': getattr(module_obj, '__author__', 'Unknown'),
            'commands': getattr(module_obj, '__commands__', []),
            'help_text': getattr(module_obj, '__help__', 'No help available')
        }
        return info


# Initialize module manager
module_manager = ModuleManager()


def create_parser() -> argparse.ArgumentParser:
    """Creates the enhanced command-line argument parser with module support."""
    parser = argparse.ArgumentParser(
        prog="crossfire",
        description="CrossFire — Production Universal Package Manager CLI with Enhanced Performance & Module Support",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Commands:
  General:
    --version                   Show CrossFire version
    -q, --quiet                 Quiet mode (errors only)
    -v, --verbose               Verbose output
    --json                      Output results in JSON format
    --interactive               Launch interactive shell (REPL)

  Module System:
    --list-modules              List all available modules
    --module-info <NAME>        Show detailed information about a module
    --module <NAME> [ARGS...]   Execute a specific module with arguments

  Package Management:
    --list-managers             List all supported package managers with status
    --install-manager <NAME>    Install a specific package manager (pip, npm, brew, etc.)
    --list-installed            Show packages installed via CrossFire
    -s, --search <QUERY>        Search across PyPI, NPM, and Homebrew
    -i, --install <PKG>         Install a package by name
    -r, --remove <PKG>          Remove/uninstall a package
    --manager <NAME>            Preferred manager to use (pip, npm, apt, brew, etc.)
    --install-from <FILE>       Install packages from a requirements file
    --export <MANAGER>          Export installed packages list
    -o, --output <FILE>         Output file for export command

  Enhanced Batch Operations:
    --install-batch <PKG1,PKG2> Install multiple packages (comma-separated)
    --remove-batch <PKG1,PKG2>  Remove multiple packages (comma-separated)
    --max-workers <N>           Max concurrent operations (default: 4)
    --fail-fast                 Stop batch operation on first failure
    --batch-timeout <SECONDS>   Timeout for entire batch operation (default: 3600)

  System Management:
    -um, --update-manager <NAME> Update specific manager or 'ALL'
    -cu, --crossupdate [URL]     Self-update from URL (default: GitHub)
    --sha256 <HASH>             Expected SHA256 hash for update verification
    --cleanup                   Clean package manager caches only
    --cleanup-deep              Deep cleanup (includes Python cache, temp files)
    --cleanup-pycache           Clear Python __pycache__ directories only
    --health-check              Run comprehensive system health check
    --stats                     Show detailed package statistics
    --setup [DIR]               Install CrossFire launcher (optionally at a specific directory)

  Network Testing:
    --speed-test                Test internet download speed
    --ping-test                 Test network latency to various hosts
    --test-url <URL>            Custom URL for speed testing
    --test-duration <SECONDS>   Duration for speed test (default: 10s)

  Search Options:
    --search-limit <N>          Limit search results (default: 20)
    --search-timeout <SECONDS>  Search timeout (default: 45s)

Examples:
  crossfire --module example-module arg1 arg2    # Execute a module
  crossfire --list-modules                       # List available modules
  crossfire --module-info MyModule               # Get module information
        """
    )

    parser.add_argument("--version", action="version", version=f"CrossFire {__version__}")

    # General / logging
    parser.add_argument("--json", action="store_true", help="Output results in JSON format")
    parser.add_argument("-q", "--quiet", action="store_true", help="Quiet mode (errors only)")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output")
    parser.add_argument("--interactive", action="store_true", help="Launch interactive shell (REPL)")

    # Module system
    parser.add_argument("--list-modules", action="store_true", help="List all available modules")
    parser.add_argument("--module-info", metavar="NAME", help="Show detailed information about a module")
    parser.add_argument("--module", metavar="NAME", help="Execute a specific module")
    parser.add_argument("module_args", nargs="*", help="Arguments to pass to the module")

    # Package management
    parser.add_argument("--list-managers", action="store_true", help="List all supported managers and their status")
    parser.add_argument("--install-manager", metavar="NAME", help="Install a specific package manager (pip, npm, brew, etc.)")
    parser.add_argument("--list-installed", action="store_true", help="Show packages installed via CrossFire")
    parser.add_argument("-s", "--search", metavar="QUERY", help="Search across real package repositories (PyPI, NPM, Homebrew)")
    parser.add_argument("-i", "--install", metavar="PKG", help="Install a package by name")
    parser.add_argument("-r", "--remove", metavar="PKG", help="Remove/uninstall a package")
    parser.add_argument("--manager", metavar="NAME", help="Preferred manager to use (pip, npm, apt, brew, etc.)")
    parser.add_argument("--install-from", metavar="FILE", help="Install packages from requirements file")
    parser.add_argument("--export", metavar="MANAGER", help="Export installed packages list")
    parser.add_argument("-o", "--output", metavar="FILE", help="Output file for export command")
    
    # Enhanced batch operations
    parser.add_argument("--install-batch", metavar="PKG1,PKG2,PKG3", 
                       help="Install multiple packages (comma-separated)")
    parser.add_argument("--remove-batch", metavar="PKG1,PKG2,PKG3", 
                       help="Remove multiple packages (comma-separated)")
    parser.add_argument("--max-workers", type=int, default=4, metavar="N",
                       help="Maximum concurrent operations (default: 4)")
    parser.add_argument("--fail-fast", action="store_true",
                       help="Stop batch operation on first failure")
    parser.add_argument("--batch-timeout", type=int, default=3600, metavar="SECONDS",
                       help="Timeout for entire batch operation (default: 3600s)")
    
    # System management
    parser.add_argument("-um", "--update-manager", metavar="NAME", help="Update specific manager or 'ALL'")
    parser.add_argument("-cu", "--crossupdate", nargs="?", const=DEFAULT_UPDATE_URL, metavar="URL",
                         help="Self-update from URL (default: GitHub)")
    parser.add_argument("--sha256", metavar="HASH", help="Expected SHA256 hash for update verification")
    parser.add_argument("--cleanup", action="store_true", help="Clean package manager caches only")
    parser.add_argument("--cleanup-deep", action="store_true", help="Deep cleanup including Python cache and temp files")
    parser.add_argument("--cleanup-pycache", action="store_true", help="Clear Python __pycache__ directories only")
    parser.add_argument("--health-check", action="store_true", help="Run comprehensive system health check")
    parser.add_argument("--stats", action="store_true", help="Show detailed package manager statistics")
    parser.add_argument(
        "--setup", nargs="?", const="", metavar="DIR",
        help="Install CrossFire launcher (optionally at a specific directory)"
    )

    # Network testing
    parser.add_argument("--speed-test", action="store_true", help="Test internet download speed")
    parser.add_argument("--ping-test", action="store_true", help="Test network latency to various hosts")
    parser.add_argument("--test-url", metavar="URL", help="Custom URL for speed testing")
    parser.add_argument("--test-duration", type=int, default=10, metavar="SECONDS",
                         help="Duration for speed test (default: 10s)")

    # Enhanced search options
    parser.add_argument("--search-limit", type=int, default=20, metavar="N",
                         help="Limit search results (default: 20)")
    parser.add_argument("--search-timeout", type=int, default=45, metavar="SECONDS",
                         help="Search timeout in seconds (default: 45s)")

    return parser


def run_standard_cleanup() -> Dict[str, Dict[str, str]]:
    """Run standard package manager cleanup only."""
    results = {}
    installed = _detect_installed_managers()
    
    # Package manager cleanup commands only
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
    }
    
    available_cleanups = [(mgr, cmd) for mgr, cmd in cleanup_commands.items() if installed.get(mgr)]
    
    if not available_cleanups:
        if not LOG.quiet:
            cprint("No package managers found to clean up.", "WARNING")
        return results
    
    progress = ProgressBar(len(available_cleanups), "Cleanup progress", "managers")
    
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
    
    progress.finish()
    return results


def show_enhanced_status() -> int:
    """Shows the enhanced tool status with module support."""
    if not LOG.json_mode:
        # Welcome header
        cprint("=" * 60, "CYAN")
        cprint(f"{__version__}", "SUCCESS")
        cprint("=" * 60, "CYAN")
    
    status_info = list_managers_status()
    modules_info = module_manager.list_modules()

    if LOG.json_mode:
        output = {
            "version": __version__,
            "managers": status_info,
            "crossfire_packages": len(package_db.get_installed_packages()),
            "modules": {name: info for name, info in modules_info.items()},
            "enhanced_features": [
                "parallel_search", "batch_installation", "concurrent_processing",
                "intelligent_caching", "optimized_networking", "module_system"
            ]
        }
        print(json.dumps(output, indent=2, ensure_ascii=False))
    else:
        installed_managers = sorted([m for m, s in status_info.items() if s == "Installed"])
        
        cprint(f"\nAvailable Package Managers ({len(installed_managers)}):", "SUCCESS")
        if installed_managers:
            for i, manager in enumerate(installed_managers, 1):
                cprint(f"  {i:2d}. {_manager_human(manager)}", "SUCCESS")
        else:
            cprint("      None found - consider installing pip, npm, brew, or apt", "WARNING")
        
        # Show modules
        if modules_info:
            cprint(f"\nAvailable Modules ({len(modules_info)}):", "CYAN")
            for i, (name, info) in enumerate(modules_info.items(), 1):
                cprint(f"  {i:2d}. {info['name']}", "CYAN")
            cprint("      Use --list-modules for details, --module <name> to execute", "INFO")
        else:
            cprint(f"\nNo Modules Found:", "MUTED")
            cprint("      Create modules in ./modules/{ModuleName}/main.py", "INFO")
        
        # Show CrossFire-managed packages
        crossfire_packages = package_db.get_installed_packages()
        cprint(f"\nCrossFire-Managed Packages: {len(crossfire_packages)}", "INFO")
        if crossfire_packages:
            recent = crossfire_packages[:3]  # Show 3 most recent
            for pkg in recent:
                cprint(f"  • {pkg['name']} via {_manager_human(pkg['manager'])}", "SUCCESS")
            if len(crossfire_packages) > 3:
                cprint(f"  ... and {len(crossfire_packages) - 3} more", "MUTED")
        
        cprint("\nEnhanced Features:", "CYAN")
        cprint("    • Parallel search across repositories (3-5x faster)", "SUCCESS")
        cprint("    • Batch installation with concurrent processing", "SUCCESS")
        cprint("    • Intelligent caching and retry logic", "SUCCESS")
        cprint("    • Optimized network connections", "SUCCESS")
        cprint("    • Dynamic module system for extensibility", "SUCCESS")
        
        cprint("\nQuick Start:", "CYAN")
        cprint("    crossfire --setup                    # Install CrossFire globally", "INFO")
        cprint("    crossfire -s 'python library'        # Enhanced parallel search", "INFO") 
        cprint("    crossfire -i numpy                   # Install with tracking", "INFO")
        cprint("    crossfire --install-batch 'numpy,requests,flask'  # Batch install", "INFO")
        cprint("    crossfire --module MyModule arg1     # Execute custom module", "INFO")
        cprint("    crossfire --list-modules             # Show available modules", "INFO")
        cprint("    crossfire --install-manager brew     # Install package managers", "INFO")
        cprint("    crossfire --cleanup-deep             # Deep system cleanup", "INFO")
        cprint("    crossfire --health-check             # System diagnostics", "INFO")
        cprint("    crossfire --help                     # Show all commands", "INFO")
    
    return 0


# ==========================
# Enhanced Interactive Shell (REPL) with Module Support
# ==========================
HELP_TEXT = """
Interactive commands (type 'help' to show this, 'exit' to quit):
  search <query> [--manager <name>] [--limit <N>]
  install <pkg> [--manager <name>]
  install-batch <pkg1,pkg2,pkg3> [--manager <name>] [--max-workers <N>]
  remove <pkg> [--manager <name>]
  remove-batch <pkg1,pkg2,pkg3> [--max-workers <N>]
  list-managers | list-installed
  install-manager <name>
  update-manager <NAME|ALL>
  crossupdate [URL] [--sha256 <HASH>]
  cleanup | cleanup-deep | cleanup-pycache
  stats | health-check
  speed-test [--url <URL>] [--duration <s>] | ping-test
  export <MANAGER> [to <FILE>]
  install-from <FILE> [--manager <name>] [--max-workers <N>]
  setup [DIR]
  
  Module Commands:
  list-modules                    # List all available modules
  module-info <name>             # Show module information
  module <name> [args...]        # Execute a module
  
  clear
  version
  help
  exit | quit

Enhanced Features:
  • All searches use parallel processing for faster results
  • Batch operations support concurrent processing
  • Smart caching reduces repeated network requests
  • Optimized error handling and retry logic
  • Dynamic module system for custom functionality
"""


def _print_banner():
    os.system('cls' if os.name == 'nt' else 'clear')
    cprint("=" * 60, "CYAN")
    cprint(f"{__version__} — Enhanced Interactive Mode", "SUCCESS")
    cprint("Featuring parallel processing, batch operations & modules", "INFO")
    cprint("Type 'help' for commands, 'exit' to quit.", "INFO")
    cprint("=" * 60, "CYAN")

def _parse_kv(args: List[str]) -> Dict[str, str]:
    """Parse simple --key value pairs from token list."""
    out: Dict[str, str] = {}
    i = 0
    while i < len(args):
        tok = args[i]
        if tok.startswith("--") and i + 1 < len(args):
            out[tok[2:]] = args[i + 1]
            i += 2
        else:
            i += 1
    return out


def interactive_shell() -> int:
    _print_banner()

    # Show quick status on start
    try:
        list_managers_status()
    except Exception:
        pass

    while True:
        try:
            line = input("crossfire> ").strip()
        except (EOFError, KeyboardInterrupt):
            cprint("", "MUTED")
            break
        if not line:
            continue

        try:
            parts = shlex.split(line)
        except ValueError as e:
            cprint(f"Parse error: {e}", "ERROR")
            continue

        cmd = parts[0].lower()
        args = parts[1:]

        # Exit
        if cmd in {"exit", "quit"}:
            break

        # Clear screen
        if cmd == "clear":
            _print_banner()
            continue

        # Help / version
        if cmd == "help":
            cprint(HELP_TEXT.rstrip(), "INFO")
            continue
        if cmd == "version":
            cprint(f"CrossFire {__version__} (Enhanced with Modules)", "SUCCESS")
            continue

        # Module commands
        if cmd == "list-modules":
            modules = module_manager.list_modules()
            if not modules:
                cprint("No modules found. Create modules in ./modules/{ModuleName}/main.py", "WARNING")
                continue
            
            cprint(f"Available Modules ({len(modules)}):", "CYAN")
            for i, (name, info) in enumerate(modules.items(), 1):
                cprint(f"  {i:2d}. {info['name']}", "CYAN")
                cprint(f"       Path: {info['path']}", "MUTED")
            cprint("\nUse 'module-info <name>' for details, 'module <name> [args]' to execute", "INFO")
            continue

        if cmd == "module-info":
            if not args:
                cprint("Usage: module-info <module_name>", "WARNING")
                continue
            
            info = module_manager.get_module_info(args[0])
            if not info:
                cprint(f"Module '{args[0]}' not found or failed to load", "ERROR")
                continue
            
            cprint(f"Module: {info['name']}", "SUCCESS")
            cprint(f"Description: {info['description']}", "INFO")
            cprint(f"Version: {info['version']}", "INFO")
            cprint(f"Author: {info['author']}", "INFO")
            if info['commands']:
                cprint(f"Commands: {', '.join(info['commands'])}", "INFO")
            if info['help_text'] != 'No help available':
                cprint(f"\nHelp:\n{info['help_text']}", "MUTED")
            continue

        if cmd == "module":
            if not args:
                cprint("Usage: module <module_name> [args...]", "WARNING")
                continue
            
            module_name = args[0]
            module_args = args[1:]
            
            result = module_manager.execute_module(module_name, module_args)
            if result != 0:
                cprint(f"Module '{module_name}' exited with code {result}", "WARNING")
            continue

        # Enhanced Search with parallel processing
        if cmd == "search":
            if not args:
                cprint("Usage: search <query> [--manager <name>] [--limit <N>]", "WARNING")
                continue
            opts = _parse_kv(args)
            # Build query string from args excluding options
            query_terms = [a for a in args if not a.startswith("--") and a not in opts.values()]
            query = " ".join(query_terms)
            limit = int(opts.get("limit", "20"))
            manager = opts.get("manager")
            
            results = search_engine.search(query, manager, limit)
            if not results:
                cprint(f"No packages found for '{query}'", "WARNING")
                continue
            cprint(f"Search Results for '{query}' (Found {len(results)})", "SUCCESS")
            cprint("=" * 70, "CYAN")
            for i, pkg in enumerate(results, 1):
                stars = min(5, max(1, int(pkg.relevance_score // 20)))
                cprint(f"\n{i:2d}. {pkg.name} ({_manager_human(pkg.manager)}) {'★' * stars}", "SUCCESS")
                if pkg.version:
                    cprint(f"      Version: {pkg.version}", "INFO")
                if pkg.description:
                    desc = pkg.description[:120] + "..." if len(pkg.description) > 120 else pkg.description
                    cprint(f"      {desc}", "MUTED")
                if pkg.homepage:
                    cprint(f"      {pkg.homepage}", "CYAN")
            continue

        # Enhanced Install (single package)
        if cmd == "install":
            if not args:
                cprint("Usage: install <pkg> [--manager <name>]", "WARNING")
                continue
            opts = _parse_kv(args)
            pkg = next((a for a in args if not a.startswith("--") and a not in opts.values()), None)
            if not pkg:
                cprint("Missing package name.", "ERROR")
                continue
            success, attempts = install_package(pkg, preferred_manager=opts.get("manager"))
            cprint(f"Install {'succeeded' if success else 'failed'} after {len(attempts)} attempt(s)",
                   "SUCCESS" if success else "ERROR")
            continue

        # Enhanced Batch Install
        if cmd == "install-batch":
            if not args:
                cprint("Usage: install-batch <pkg1,pkg2,pkg3> [--manager <name>] [--max-workers <N>]", "WARNING")
                continue
            opts = _parse_kv(args)
            packages_str = next((a for a in args if not a.startswith("--") and a not in opts.values()), None)
            if not packages_str:
                cprint("Missing package list.", "ERROR")
                continue
            
            packages = [pkg.strip() for pkg in packages_str.split(',') if pkg.strip()]
            if not packages:
                cprint("No valid packages specified.", "ERROR")
                continue
            
            max_workers = int(opts.get("max-workers", "4"))
            manager = opts.get("manager")
            
            results = install_packages_batch(packages, manager, max_workers)
            
            success_count = len(results['success'])
            total_count = results['packages_processed']
            cprint(f"Batch install complete: {success_count}/{total_count} successful in {results['total_time']:.1f}s",
                   "SUCCESS" if success_count == total_count else "WARNING")
            continue

        # Remove (single package)
        if cmd == "remove":
            if not args:
                cprint("Usage: remove <pkg> [--manager <name>]", "WARNING")
                continue
            opts = _parse_kv(args)
            pkg = next((a for a in args if not a.startswith("--") and a not in opts.values()), None)
            if not pkg:
                cprint("Missing package name.", "ERROR")
                continue
            success, attempts = remove_package(pkg, opts.get("manager"))
            cprint(f"Remove {'succeeded' if success else 'failed'} after {len(attempts)} attempt(s)",
                   "SUCCESS" if success else "ERROR")
            continue

        # Enhanced Batch Remove
        if cmd == "remove-batch":
            if not args:
                cprint("Usage: remove-batch <pkg1,pkg2,pkg3> [--max-workers <N>]", "WARNING")
                continue
            opts = _parse_kv(args)
            packages_str = next((a for a in args if not a.startswith("--") and a not in opts.values()), None)
            if not packages_str:
                cprint("Missing package list.", "ERROR")
                continue
            
            packages = [pkg.strip() for pkg in packages_str.split(',') if pkg.strip()]
            if not packages:
                cprint("No valid packages specified.", "ERROR")
                continue
            
            max_workers = int(opts.get("max-workers", "3"))
            results = remove_packages_batch(packages, max_workers=max_workers)
            
            success_count = len(results['success'])
            total_count = results['packages_processed']
            cprint(f"Batch remove complete: {success_count}/{total_count} successful",
                   "SUCCESS" if success_count == total_count else "WARNING")
            continue

        # Install from requirements file
        if cmd == "install-from":
            if not args:
                cprint("Usage: install-from <FILE> [--manager <n>] [--max-workers <N>]", "WARNING")
                continue
            opts = _parse_kv(args)
            file_path = next((a for a in args if not a.startswith("--") and a not in opts.values()), None)
            if not file_path:
                cprint("Missing file path.", "ERROR")
                continue
            
            manager = opts.get("manager")
            max_workers = int(opts.get("max-workers", "4"))
            
            results = install_from_requirements_file(file_path, manager, max_workers)
            success_count = len(results['success'])
            total_count = results['packages_processed']
            cprint(f"Requirements install complete: {success_count}/{total_count} successful",
                   "SUCCESS" if success_count == total_count else "WARNING")
            continue

        # Listing commands
        if cmd == "list-managers":
            status_info = list_managers_status()
            cprint("Package Manager Status:", "INFO")
            for manager, status in sorted(status_info.items()):
                color = "SUCCESS" if status == "Installed" else "MUTED"
                cprint(f" {manager}: {status}", color)
            continue

        if cmd == "list-installed":
            show_installed_packages()
            continue

        # Install manager
        if cmd == "install-manager":
            if not args:
                cprint("Usage: install-manager <name>", "WARNING")
                continue
            ok = install_manager(args[0].lower())
            cprint("Manager install successful" if ok else "Manager install failed",
                   "SUCCESS" if ok else "ERROR")
            continue

        # Update commands
        if cmd == "update-manager":
            if not args:
                cprint("Usage: update-manager <NAME|ALL>", "WARNING")
                continue
            target = args[0].upper()
            if target == "ALL":
                results = _update_all_managers()
            else:
                proper_name = None
                for name in MANAGER_INSTALL_HANDLERS.keys():
                    if name.upper() == target:
                        proper_name = name
                        break
                if not proper_name:
                    cprint(f"Unknown package manager: {args[0]}", "ERROR")
                    continue
                name, ok, msg = _update_manager(proper_name)
                results = {name: {"ok": str(ok).lower(), "msg": msg}}
            
            # Summarize results
            ok_all = all(r.get("ok") == "true" for r in results.values())
            for name, r in results.items():
                cprint(f"{name}: {r['msg']}", "SUCCESS" if r.get("ok") == "true" else "ERROR")
            cprint("All updates succeeded" if ok_all else "Some updates failed",
                   "SUCCESS" if ok_all else "WARNING")
            continue

        if cmd == "crossupdate":
            opts = _parse_kv(args)
            url = next((a for a in args if not a.startswith("--") and a not in opts.values()), None) or DEFAULT_UPDATE_URL
            ok = cross_update(url, verify_sha256=opts.get("sha256"))
            cprint("CrossFire self-update successful" if ok else "Self-update failed",
                   "SUCCESS" if ok else "ERROR")
            continue

        # Cleanup commands
        if cmd in {"cleanup", "cleanup-deep", "cleanup-pycache"}:
            if cmd == "cleanup":
                results = run_standard_cleanup()
                ok_any = any(r.get("ok") == "true" for r in results.values())
                cprint("Cleanup complete" if ok_any else "Nothing cleaned or errors occurred",
                       "SUCCESS" if ok_any else "WARNING")
            elif cmd == "cleanup-deep":
                results = cleanup_system()
                ok_any = any(r.get("ok") == "true" for r in results.values())
                cprint("Deep cleanup complete" if ok_any else "Deep cleanup encountered issues",
                       "SUCCESS" if ok_any else "WARNING")
            else:
                res = clear_python_cache()
                cprint(f"Python cache: {res['msg']}", "SUCCESS" if res.get("ok") == "true" else "ERROR")
            continue

        # Stats / health
        if cmd == "stats":
            show_statistics()
            continue
        if cmd == "health-check":
            results = health_check()
            cprint("Overall: " + results.get("overall_status", "unknown"),
                   "SUCCESS" if results.get("overall_status") == "healthy" else "WARNING")
            continue

        # Networking
        if cmd == "speed-test":
            opts = _parse_kv(args)
            duration = int(opts.get("duration", "10"))
            result = SpeedTest.test_download_speed(opts.get("url"), duration)
            cprint(json.dumps(result, indent=2), "INFO")
            continue
        if cmd == "ping-test":
            result = SpeedTest.ping_test()
            cprint(json.dumps(result, indent=2), "INFO")
            continue

        # Export
        if cmd == "export":
            if not args:
                cprint("Usage: export <MANAGER> [to <FILE>]", "WARNING")
                continue
            manager = args[0]
            out_file = None
            if len(args) >= 3 and args[1].lower() == "to":
                out_file = args[2]
            success = export_packages(manager, out_file)
            cprint("Export successful" if success else "Export failed",
                   "SUCCESS" if success else "ERROR")
            continue

        # Setup
        if cmd == "setup":
            target_dir = args[0] if args else None
            path_success = add_to_path_safely()
            installed_path = install_launcher(target_dir)
            if installed_path and path_success:
                cprint("Setup Complete! CrossFire available globally as 'crossfire'", "SUCCESS")
            else:
                cprint("Setup completed with some issues.", "WARNING")
            continue

        # Unknown command
        cprint(f"Unknown command: {cmd}. Type 'help' for a list of commands.", "ERROR")

    cprint("Bye!", "MUTED")
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    """Enhanced main execution entry point with module support."""
    parser = create_parser()
    args = parser.parse_args(argv)

    # Set logging modes
    LOG.quiet = args.quiet
    LOG.verbose = args.verbose
    LOG.json_mode = args.json
    
    try:
        # Interactive mode takes precedence if requested explicitly
        if args.interactive:
            if LOG.json_mode:
                cprint("Interactive mode ignores --json and prints human-readable output.", "MUTED")
            return interactive_shell()

        # Module system commands
        if args.list_modules:
            modules = module_manager.list_modules()
            if LOG.json_mode:
                output = {"modules": modules, "count": len(modules)}
                print(json.dumps(output, indent=2, ensure_ascii=False))
            else:
                if not modules:
                    cprint("No modules found.", "WARNING")
                    cprint("Create modules in ./modules/{ModuleName}/main.py", "INFO")
                    cprint("Each module should have a main(args) function", "INFO")
                    return 0
                
                cprint(f"Available Modules ({len(modules)}):", "CYAN")
                cprint("=" * 50, "CYAN")
                for i, (name, info) in enumerate(modules.items(), 1):
                    cprint(f"\n{i:2d}. {info['name']}", "SUCCESS")
                    cprint(f"     Path: {info['path']}", "MUTED")
                    cprint(f"     Status: {'Loaded' if info['loaded'] else 'Not loaded'}", "INFO")
                
                cprint("\nUsage:", "INFO")
                cprint("  crossfire --module-info <name>     # Show module details", "INFO")
                cprint("  crossfire --module <name> [args]   # Execute module", "INFO")
            return 0

        if args.module_info:
            info = module_manager.get_module_info(args.module_info)
            if LOG.json_mode:
                print(json.dumps(info or {}, indent=2, ensure_ascii=False))
            else:
                if not info:
                    cprint(f"Module '{args.module_info}' not found or failed to load", "ERROR")
                    return 1
                
                cprint(f"Module Information:", "CYAN")
                cprint("=" * 50, "CYAN")
                cprint(f"Name: {info['name']}", "SUCCESS")
                cprint(f"Version: {info['version']}", "INFO")
                cprint(f"Author: {info['author']}", "INFO")
                cprint(f"Description: {info['description']}", "INFO")
                
                if info['commands']:
                    cprint(f"Available Commands: {', '.join(info['commands'])}", "INFO")
                
                if info['help_text'] != 'No help available':
                    cprint(f"\nDetailed Help:", "CYAN")
                    cprint(info['help_text'], "MUTED")
                
                cprint(f"\nUsage: crossfire --module {info['name']} [arguments]", "INFO")
            return 0

        if args.module:
            return module_manager.execute_module(args.module, args.module_args)

        # Handle the setup command
        if args.setup is not None:
            if not LOG.quiet:
                cprint("Running production setup...", "INFO")
            
            path_success = add_to_path_safely()
            installed_path = install_launcher(args.setup if args.setup else None)
            
            if installed_path and path_success:
                if not LOG.quiet:
                    cprint(f"\nSetup Complete!", "SUCCESS")
                    cprint("    • CrossFire is now available globally as 'crossfire'", "SUCCESS")
                    cprint("    • Enhanced with parallel processing, batch operations & modules", "INFO")
                    
                    # Platform-specific restart instructions
                    if OS_NAME == "Windows":
                        cprint("    • Restart your command prompt or PowerShell", "INFO")
                        cprint("    • Or run: refreshenv (if using Chocolatey)", "INFO")
                    else:
                        cprint("    • Restart your terminal or run: source ~/.bashrc", "INFO")
                    
                    cprint("    • Try: crossfire -s 'python library' for enhanced search", "CYAN")
                    cprint("    • Try: crossfire --install-batch 'numpy,requests' for batch install", "CYAN")
                    cprint("    • Try: crossfire --list-modules to see available modules", "CYAN")
                    cprint("    • Database initialized for package tracking", "INFO")
            else:
                if not LOG.quiet:
                    cprint("Setup completed with some issues.", "WARNING")
            return 0

        # Enhanced batch installation
        if args.install_batch:
            packages = [pkg.strip() for pkg in args.install_batch.split(',') if pkg.strip()]
            if not packages:
                cprint("No valid packages specified for batch install", "ERROR")
                return 1
            
            results = install_packages_batch(
                packages, 
                args.manager, 
                args.max_workers, 
                args.fail_fast
            )
            
            if LOG.json_mode:
                print(json.dumps(results, indent=2, default=str))
            
            return 0 if len(results['success']) == results['packages_processed'] else 1

        # Enhanced batch removal
        if args.remove_batch:
            packages = [pkg.strip() for pkg in args.remove_batch.split(',') if pkg.strip()]
            if not packages:
                cprint("No valid packages specified for batch removal", "ERROR")
                return 1
            
            results = remove_packages_batch(packages, args.manager, args.max_workers)
            
            if LOG.json_mode:
                print(json.dumps(results, indent=2, default=str))
            
            return 0 if len(results['success']) == results['packages_processed'] else 1

        # Install manager command
        if args.install_manager:
            manager = args.install_manager.lower()
            success = install_manager(manager)
            if LOG.json_mode:
                print(json.dumps({"manager": manager, "success": success}, indent=2))
            return 0 if success else 1

        # Network testing commands
        if args.speed_test:
            test_url = args.test_url
            duration = args.test_duration
            result = SpeedTest.test_download_speed(test_url, duration)
            if LOG.json_mode:
                print(json.dumps(result, indent=2))
            return 0 if result.get("ok") else 1
        
        if args.ping_test:
            result = SpeedTest.ping_test()
            if LOG.json_mode:
                print(json.dumps(result, indent=2))
            return 0

        # Update commands
        if args.crossupdate is not None:
            url = args.crossupdate or DEFAULT_UPDATE_URL
            success = cross_update(url, verify_sha256=args.sha256)
            if LOG.json_mode:
                print(json.dumps({"crossupdate": {"success": success}}, indent=2))
            return 0 if success else 1
        
        if args.update_manager:
            target = args.update_manager.upper()
            if target == "ALL":
                results = _update_all_managers()
            else:
                # Convert target back to proper case for lookup
                proper_name = None
                for name in MANAGER_INSTALL_HANDLERS.keys():
                    if name.upper() == target:
                        proper_name = name
                        break
                
                if not proper_name:
                    cprint(f"Unknown package manager: {args.update_manager}", "ERROR")
                    return 1
                    
                name, ok, msg = _update_manager(proper_name)
                results = {name: {"ok": str(ok).lower(), "msg": msg}}
                if not LOG.quiet:
                    cprint(f"{name}: {msg}", "SUCCESS" if ok else "ERROR")
                
            if LOG.json_mode:
                print(json.dumps(results, indent=2, ensure_ascii=False))
            return 0 if all(r.get("ok") == "true" for r in results.values()) else 1

        # Enhanced cleanup commands
        if args.cleanup_pycache:
            result = clear_python_cache()
            if LOG.json_mode:
                print(json.dumps({"python_cache": result}, indent=2))
            else:
                if not LOG.quiet:
                    color = "SUCCESS" if result.get("ok") == "true" else "ERROR"
                    cprint(f"Python cache cleanup: {result['msg']}", color)
            return 0 if result.get("ok") == "true" else 1
        
        if args.cleanup_deep:
            # Enhanced deep cleanup
            results = cleanup_system()  # This includes all cleanup types
            if LOG.json_mode:
                print(json.dumps(results, indent=2, ensure_ascii=False))
            return 0 if any(r.get("ok") == "true" for r in results.values()) else 1
        
        if args.cleanup:
            # Regular cleanup (package managers only)
            results = run_standard_cleanup()
            if LOG.json_mode:
                print(json.dumps(results, indent=2, ensure_ascii=False))
            return 0 if any(r.get("ok") == "true" for r in results.values()) else 1

        # Information commands
        if args.list_managers:
            status_info = list_managers_status()
            if LOG.json_mode:
                print(json.dumps(status_info, indent=2, ensure_ascii=False))
            else:
                cprint("Package Manager Status:", "INFO")
                for manager, status in sorted(status_info.items()):
                    color = "SUCCESS" if status == "Installed" else "MUTED"
                    cprint(f" {manager}: {status}", color)
                cprint(f"\nInstall managers with: crossfire --install-manager <name>", "INFO")
            return 0
        
        if args.list_installed:
            show_installed_packages()
            return 0
        
        if args.stats:
            show_statistics()
            return 0
        
        if args.health_check:
            results = health_check()
            if LOG.json_mode:
                print(json.dumps(results, indent=2, default=str))
            return 0 if results["overall_status"] == "healthy" else 1

        # Enhanced search command with parallel processing
        if args.search:
            results = search_engine.search(args.search, args.manager, args.search_limit)
            
            if LOG.json_mode:
                output = {
                    "query": args.search, 
                    "results": [r.to_dict() for r in results],
                    "total_found": len(results),
                    "enhanced_features": ["parallel_search", "intelligent_caching", "optimized_networking", "module_system"]
                }
                print(json.dumps(output, indent=2, ensure_ascii=False))
            else:
                if not results:
                    cprint(f"No packages found for '{args.search}'", "WARNING")
                    return 1
                
                cprint(f"Search Results for '{args.search}' (Found {len(results)}) [Enhanced]", "SUCCESS")
                cprint("=" * 70, "CYAN")
                
                for i, pkg in enumerate(results, 1):
                    # Relevance indicator
                    stars = min(5, max(1, int(pkg.relevance_score // 20)))
                    relevance_stars = "★" * stars
                    
                    cprint(f"\n{i:2d}. {pkg.name} ({_manager_human(pkg.manager)}) {relevance_stars}", "SUCCESS")
                    if pkg.version:
                        cprint(f"      Version: {pkg.version}", "INFO")
                    if pkg.description:
                        desc = pkg.description[:120] + "..." if len(pkg.description) > 120 else pkg.description
                        cprint(f"      {desc}", "MUTED")
                    if pkg.homepage:
                        cprint(f"      {pkg.homepage}", "CYAN")
                
                cprint(f"\nInstall with: crossfire -i <package_name>", "INFO")
                cprint(f"Batch install: crossfire --install-batch '<pkg1,pkg2,pkg3>'", "INFO")
            return 0
        
        # Package management commands
        if args.install:
            success, attempts = install_package(args.install, preferred_manager=args.manager)
            if LOG.json_mode:
                output = {"package": args.install, "success": success, "attempts": len(attempts)}
                print(json.dumps(output, indent=2, ensure_ascii=False))
            return 0 if success else 1
        
        if args.remove:
            success, attempts = remove_package(args.remove, args.manager)
            if LOG.json_mode:
                output = {"package": args.remove, "success": success, "attempts": len(attempts)}
                print(json.dumps(output, indent=2, ensure_ascii=False))
            return 0 if success else 1
        
        if args.install_from:
            results = install_from_requirements_file(args.install_from, args.manager, args.max_workers)
            if LOG.json_mode:
                print(json.dumps(results, indent=2, default=str))
            return 0 if results.get("success", False) else 1
        
        if args.export:
            success = export_packages(args.export, args.output)
            return 0 if success else 1
        
        # No specific command given, show enhanced status
        return show_enhanced_status()
        
    except KeyboardInterrupt:
        if not LOG.quiet:
            cprint("\nOperation cancelled by user.", "WARNING")
        return 1
    except Exception as e:
        cprint(f"Unexpected error: {e}", "ERROR")
        if LOG.verbose:
            import traceback
            traceback.print_exc()
        return 1


if __name__ == "__main__":
    # Ensure we have required dependencies
    try:
        import requests
    except ImportError:
        print("Missing required dependency 'requests'. Install with: pip install requests")
        sys.exit(1)
    
    sys.exit(main())