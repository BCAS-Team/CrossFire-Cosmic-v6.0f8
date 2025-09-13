import sqlite3
from pathlib import Path
from typing import List, Dict, Optional

from .config import CROSSFIRE_DB


class PackageDB:
    def __init__(self, db_path: Path = CROSSFIRE_DB):
        self.db_path = db_path
        self._init_db()
    
    def _init_db(self):
        """Initialize the SQLite database for package tracking."""
        conn = sqlite3.connect(self.db_path)
        conn.execute('''
            CREATE TABLE IF NOT EXISTS installed_packages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                version TEXT,
                manager TEXT NOT NULL,
                install_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                install_command TEXT,
                UNIQUE(name, manager)
            )
        ''')
        conn.commit()
        conn.close()
    
    def add_package(self, name: str, version: str, manager: str, command: str = ""):
        """Record a successfully installed package."""
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute('''
                INSERT OR REPLACE INTO installed_packages 
                (name, version, manager, install_command) 
                VALUES (?, ?, ?, ?)
            ''', (name, version or "unknown", manager, command))
            conn.commit()
        finally:
            conn.close()
    
    def remove_package(self, name: str, manager: str = None):
        """Remove a package record."""
        conn = sqlite3.connect(self.db_path)
        try:
            if manager:
                conn.execute('DELETE FROM installed_packages WHERE name = ? AND manager = ?', 
                           (name, manager))
            else:
                conn.execute('DELETE FROM installed_packages WHERE name = ?', (name,))
            conn.commit()
        finally:
            conn.close()
    
    def get_installed_packages(self, manager: str = None) -> List[Dict]:
        """Get list of installed packages."""
        conn = sqlite3.connect(self.db_path)
        try:
            if manager:
                cursor = conn.execute('''
                    SELECT name, version, manager, install_date 
                    FROM installed_packages 
                    WHERE manager = ? 
                    ORDER BY install_date DESC
                ''', (manager,))
            else:
                cursor = conn.execute('''
                    SELECT name, version, manager, install_date 
                    FROM installed_packages 
                    ORDER BY install_date DESC
                ''')
            
            columns = [desc[0] for desc in cursor.description]
            return [dict(zip(columns, row)) for row in cursor.fetchall()]
        finally:
            conn.close()
    
    def is_installed(self, name: str, manager: str = None) -> bool:
        """Check if a package is recorded as installed."""
        conn = sqlite3.connect(self.db_path)
        try:
            if manager:
                cursor = conn.execute(
                    'SELECT COUNT(*) FROM installed_packages WHERE name = ? AND manager = ?',
                    (name, manager)
                )
            else:
                cursor = conn.execute(
                    'SELECT COUNT(*) FROM installed_packages WHERE name = ?',
                    (name,)
                )
            return cursor.fetchone()[0] > 0
        finally:
            conn.close()


# Global database instance
package_db = PackageDB()