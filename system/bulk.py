import re
from datetime import datetime
from pathlib import Path
from typing import Dict, Any

from core.logger import cprint
from core.progress import ProgressBar
from core.database import package_db
from managers.installer import install_package
from managers.detection import _manager_human


def bulk_install_from_file(file_path: str) -> Dict[str, Any]:
    """Install packages from a requirements file."""
    cprint(f"Installing packages from: {file_path}", "INFO")
    
    try:
        path = Path(file_path)
        if not path.exists():
            cprint(f"File not found: {file_path}", "ERROR")
            return {"success": False, "error": "File not found"}
        
        content = path.read_text().strip()
        lines = [line.strip() for line in content.splitlines() 
                if line.strip() and not line.startswith('#')]
        
        if not lines:
            cprint("No packages found in file", "WARNING")
            return {"success": False, "error": "No packages found"}
        
        cprint(f"Found {len(lines)} packages to install", "INFO")
        
        results = {
            "total_packages": len(lines),
            "successful": 0,
            "failed": 0,
            "results": []
        }
        
        progress = ProgressBar(len(lines), "Installing packages", "packages")
        
        for line in lines:
            # Parse package name (handle version specifiers)
            pkg_name = re.split(r'[=<>!]', line)[0].strip()
            
            cprint(f"Installing {pkg_name}...", "INFO")
            success, attempts = install_package(line)
            
            result = {
                "package": line,
                "success": success,
                "attempts": len(attempts)
            }
            results["results"].append(result)
            
            if success:
                results["successful"] += 1
            else:
                results["failed"] += 1
            
            progress.update(1)
        
        progress.finish()
        
        # Summary
        cprint(f"\nInstallation Summary:", "CYAN")
        cprint(f"  Successful: {results['successful']}/{results['total_packages']}", "SUCCESS")
        cprint(f"  Failed: {results['failed']}/{results['total_packages']}", "ERROR" if results['failed'] > 0 else "SUCCESS")
        
        return results
        
    except Exception as e:
        cprint(f"Error reading file: {e}", "ERROR")
        return {"success": False, "error": str(e)}


def export_packages(manager: str, output_file: str = None) -> bool:
    """Export installed packages to a requirements file."""
    cprint(f"Exporting packages from {_manager_human(manager)}...", "INFO")
    
    try:
        packages = package_db.get_installed_packages(manager)
        
        if not packages:
            cprint(f"No packages installed via {_manager_human(manager)} found in CrossFire database", "WARNING")
            return False
        
        # Generate requirements content
        lines = []
        for pkg in sorted(packages, key=lambda x: x['name']):
            if pkg['version'] and pkg['version'] != 'unknown':
                lines.append(f"{pkg['name']}=={pkg['version']}")
            else:
                lines.append(pkg['name'])
        
        content = '\n'.join(lines) + '\n'
        
        # Determine output file
        if output_file:
            out_path = Path(output_file)
        else:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            out_path = Path(f"crossfire_{manager}_requirements_{timestamp}.txt")
        
        # Write file
        out_path.write_text(content)
        
        cprint(f"Exported {len(packages)} packages to: {out_path}", "SUCCESS")
        cprint(f"Install with: crossfire --install-from {out_path}", "INFO")
        
        return True
        
    except Exception as e:
        cprint(f"Export failed: {e}", "ERROR")
        return False