from .detection import (
    _detect_installed_managers,
    _manager_human,
    _system_manager_priority,
    _ordered_install_manager_candidates,
    list_managers_status
)
from .commands import INSTALL_HANDLERS, REMOVE_HANDLERS
from .installer import install_package, remove_package, install_manager

__all__ = [
    '_detect_installed_managers',
    '_manager_human', 
    '_system_manager_priority',
    '_ordered_install_manager_candidates',
    'list_managers_status',
    'INSTALL_HANDLERS',
    'REMOVE_HANDLERS', 
    'install_package',
    'remove_package',
    'install_manager'
]


