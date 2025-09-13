import json
from datetime import datetime, timedelta
from typing import Dict, Any

from core.database import package_db
from core.logger import cprint, LOG
from managers.detection import _detect_installed_managers, _manager_human


def get_package_statistics() -> Dict[str, Any]:
    """Get detailed package statistics."""
    packages = package_db.get_installed_packages()
    managers = _detect_installed_managers()
    
    stats = {
        "total_packages": len(packages),
        "packages_by_manager": {},
        "recent_installations": [],
        "available_managers": sum(1 for avail in managers.values() if avail),
        "total_supported_managers": len(managers)
    }
    
    # Group by manager
    for pkg in packages:
        manager = pkg['manager']
        stats["packages_by_manager"][manager] = stats["packages_by_manager"].get(manager, 0) + 1
    
    # Recent installations (last 7 days)
    try:
        week_ago = datetime.now() - timedelta(days=7)
        for pkg in packages:
            if pkg['install_date']:
                install_date = datetime.fromisoformat(pkg['install_date'].replace('Z', '+00:00'))
                if install_date > week_ago:
                    stats["recent_installations"].append({
                        "name": pkg['name'],
                        "manager": pkg['manager'],
                        "date": pkg['install_date']
                    })
    except:
        pass  # Handle date parsing errors gracefully
    
    return stats


def show_statistics():
    """Display detailed CrossFire statistics."""
    stats = get_package_statistics()
    
    if LOG.json_mode:
        print(json.dumps(stats, indent=2, default=str))
        return
    
    cprint(f"CrossFire Statistics", "SUCCESS")
    cprint("=" * 50, "CYAN")
    
    # Overview
    cprint(f"\nOverview", "INFO")
    cprint(f"  Total packages installed via CrossFire: {stats['total_packages']}", "SUCCESS")
    cprint(f"  Available package managers: {stats['available_managers']}/{stats['total_supported_managers']}", "SUCCESS")
    
    # Packages by manager
    if stats["packages_by_manager"]:
        cprint(f"\nPackages by Manager", "INFO")
        for manager, count in sorted(stats["packages_by_manager"].items(), key=lambda x: x[1], reverse=True):
            percentage = (count / stats['total_packages']) * 100
            bar_length = int(percentage / 5)  # Scale to 20 chars max
            bar = "█" * bar_length + "░" * (20 - bar_length)
            cprint(f"  {_manager_human(manager):15} │{bar}│ {count:3d} ({percentage:4.1f}%)", "SUCCESS")
    
    # Recent activity
    if stats["recent_installations"]:
        cprint(f"\nRecent Installations (Last 7 Days)", "INFO")
        for pkg in stats["recent_installations"][:5]:  # Show last 5
            date = pkg['date'][:10] if pkg['date'] else 'unknown'
            cprint(f"  • {pkg['name']} via {_manager_human(pkg['manager'])} on {date}", "SUCCESS")
        
        if len(stats["recent_installations"]) > 5:
            cprint(f"  ... and {len(stats['recent_installations']) - 5} more", "MUTED")


def show_installed_packages():
    """Show packages installed via CrossFire."""
    packages = package_db.get_installed_packages()
    
    if LOG.json_mode:
        print(json.dumps(packages, indent=2, default=str))
        return
    
    if not packages:
        cprint("No packages have been installed via CrossFire yet.", "INFO")
        cprint("Packages installed directly via other managers won't appear here.", "MUTED")
        return
    
    cprint(f"Packages Installed via CrossFire ({len(packages)})", "SUCCESS")
    cprint("=" * 70, "CYAN")
    
    # Group by manager
    by_manager = {}
    for pkg in packages:
        manager = pkg['manager']
        if manager not in by_manager:
            by_manager[manager] = []
        by_manager[manager].append(pkg)
    
    for manager in sorted(by_manager.keys()):
        pkgs = by_manager[manager]
        cprint(f"\n{_manager_human(manager)} ({len(pkgs)} packages)", "INFO")
        
        for i, pkg in enumerate(sorted(pkgs, key=lambda x: x['install_date'], reverse=True), 1):
            install_date = pkg['install_date'][:10] if pkg['install_date'] else 'unknown'
            version = pkg.get('version', 'unknown')
            
            cprint(f"  {i:2d}. {pkg['name']} "
                   f"v{version} "
                   f"(installed {install_date})", "SUCCESS")
    
    cprint(f"\nRemove with: crossfire -r <package_name>", "INFO")