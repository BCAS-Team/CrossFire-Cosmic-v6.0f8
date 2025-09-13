import urllib.request
import shutil
from typing import Dict, Any

from core.config import CROSSFIRE_DIR, CROSSFIRE_DB
from core.logger import cprint, LOG
from core.database import package_db
from managers.detection import _detect_installed_managers


def health_check() -> Dict[str, Any]:
    """Run comprehensive system health check."""
    cprint("Running system health check...", "INFO")
    
    results = {
        "overall_status": "healthy",
        "checks": {},
        "recommendations": []
    }
    
    # Check package managers
    managers = _detect_installed_managers()
    manager_count = sum(1 for available in managers.values() if available)
    
    results["checks"]["package_managers"] = {
        "status": "good" if manager_count >= 2 else "warning" if manager_count >= 1 else "error",
        "available_count": manager_count,
        "total_supported": len(managers),
        "available": [m for m, avail in managers.items() if avail]
    }
    
    if manager_count == 0:
        results["recommendations"].append("Install at least one package manager (pip, npm, brew, apt, etc.)")
        results["overall_status"] = "unhealthy"
    elif manager_count == 1:
        results["recommendations"].append("Consider installing additional package managers for better coverage")
    
    # Check network connectivity
    try:
        urllib.request.urlopen("https://google.com", timeout=10)
        results["checks"]["internet"] = {"status": "good", "message": "Internet connection available"}
    except:
        results["checks"]["internet"] = {"status": "error", "message": "No internet connection"}
        results["recommendations"].append("Check your internet connection")
        results["overall_status"] = "unhealthy"
    
    # Check CrossFire database
    try:
        installed_packages = package_db.get_installed_packages()
        results["checks"]["database"] = {
            "status": "good",
            "installed_packages": len(installed_packages),
            "database_path": str(CROSSFIRE_DB)
        }
    except Exception as e:
        results["checks"]["database"] = {
            "status": "error", 
            "message": f"Database error: {e}"
        }
        results["recommendations"].append("Database may be corrupted - consider clearing CrossFire data")
    
    # Check disk space
    try:
        free_space = shutil.disk_usage(CROSSFIRE_DIR).free
        free_space_gb = free_space / (1024**3)
        
        if free_space_gb < 0.1:  # Less than 100MB
            results["checks"]["disk_space"] = {
                "status": "error",
                "free_space_gb": round(free_space_gb, 2)
            }
            results["recommendations"].append("Very low disk space - clean up files")
            results["overall_status"] = "unhealthy"
        elif free_space_gb < 1:  # Less than 1GB
            results["checks"]["disk_space"] = {
                "status": "warning",
                "free_space_gb": round(free_space_gb, 2)
            }
            results["recommendations"].append("Low disk space - consider cleanup")
        else:
            results["checks"]["disk_space"] = {
                "status": "good",
                "free_space_gb": round(free_space_gb, 2)
            }
    except:
        results["checks"]["disk_space"] = {"status": "unknown", "message": "Could not check disk space"}
    
    # Set final status
    if any(check.get("status") == "error" for check in results["checks"].values()):
        results["overall_status"] = "unhealthy"
    elif any(check.get("status") == "warning" for check in results["checks"].values()):
        results["overall_status"] = "needs_attention"
    
    # Display results
    if not LOG.json_mode:
        status_colors = {"healthy": "SUCCESS", "needs_attention": "WARNING", "unhealthy": "ERROR"}
        status_icons = {"healthy": "Healthy", "needs_attention": "Needs Attention", "unhealthy": "Unhealthy"}
        
        overall_status = results["overall_status"]
        cprint(f"Overall Status: {status_icons[overall_status].upper()}", status_colors[overall_status])
        
        for check_name, check_result in results["checks"].items():
            status = check_result.get("status", "unknown")
            icon = {"good": "Good", "warning": "Warning", "error": "Error", "unknown": "Unknown"}[status]
            cprint(f"  {check_name.replace('_', ' ').title()}: {icon}", 
                   {"good": "SUCCESS", "warning": "WARNING", "error": "ERROR", "unknown": "INFO"}[status])
        
        if results["recommendations"]:
            cprint("\nRecommendations:", "CYAN")
            for i, rec in enumerate(results["recommendations"], 1):
                cprint(f"  {i}. {rec}", "INFO")
    
    return results