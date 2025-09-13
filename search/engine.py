import sys
import os

# Add vendor directory to sys.path
VENDOR_DIR = os.path.join(os.path.dirname(__file__), "..", "vendor")
if VENDOR_DIR not in sys.path:
    sys.path.insert(0, VENDOR_DIR)

import vendor.requests as vendored_requests
sys.modules['requests'] = vendored_requests

import json
import time
import concurrent.futures as _fut
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Any
from pathlib import Path

import requests  # Now automatically points to vendor.requests
from requests.adapters import HTTPAdapter

# Fixed import - handle different urllib3 versions
try:
    from urllib3.util.retry import Retry
except ImportError:
    try:
        from urllib3.util import Retry
    except ImportError:
        # Create a simple fallback Retry class if urllib3 is not available
        class Retry:
            def __init__(self, total=3, backoff_factor=0.3, status_forcelist=None, allowed_methods=None):
                self.total = total
                self.backoff_factor = backoff_factor
                self.status_forcelist = status_forcelist or []
                self.allowed_methods = allowed_methods or ["GET", "POST"]

from core.config import CROSSFIRE_CACHE
from core.logger import cprint
from core.execution import run_command
from core.progress import ProgressBar
from managers.detection import _detect_installed_managers


@dataclass
class SearchResult:
    name: str
    description: str
    version: str
    manager: str
    homepage: Optional[str] = None
    relevance_score: float = 0.0
    
    def to_dict(self):
        return asdict(self)


class RealSearchEngine:
    def __init__(self):
        self.cache_timeout = 3600  # 1 hour cache
        self.session = self._create_optimized_session()
        self._cache = {}  # Memory cache
        
    def _create_optimized_session(self):
        """Create optimized requests session with connection pooling and retries"""
        session = requests.Session()
        
        # Configure retry strategy
        retry_strategy = Retry(
            total=3,
            backoff_factor=0.3,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET", "POST"]
        )
        
        # Configure adapter with connection pooling
        adapter = HTTPAdapter(
            max_retries=retry_strategy,
            pool_connections=10,
            pool_maxsize=10,
            pool_block=False
        )
        
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        
        # Optimize headers for compression and performance
        session.headers.update({
            'User-Agent': 'CrossFire/2.0 (Enhanced Package Manager)',
            'Accept-Encoding': 'gzip, br, deflate',
            'Connection': 'keep-alive',
            'Accept': 'application/json, */*',
            'Cache-Control': 'max-age=300'
        })
        
        return session
    
    def search(self, query: str, manager: Optional[str] = None, limit: int = 20) -> List[SearchResult]:
        """Enhanced search with parallel processing and intelligent caching."""
        # Check cache first
        cache_key = f"{query}_{manager}_{limit}"
        if cache_key in self._cache:
            cached_data, timestamp = self._cache[cache_key]
            if time.time() - timestamp < 900:  # 15 minute cache
                cprint(f"Using cached results for '{query}'", "INFO")
                return cached_data
        
        cprint(f"Searching for '{query}' across package repositories...", "INFO")
        
        all_results = []
        installed = _detect_installed_managers()
        
        # Determine target managers
        if manager:
            target_managers = [manager.lower()] if installed.get(manager.lower()) else []
        else:
            target_managers = [m for m, ok in installed.items() if ok]
        
        if not target_managers:
            cprint("No usable package managers available for searching.", "ERROR")
            return []
        
        # Map managers to their optimized search functions
        manager_funcs = {
            "pip": self._search_pypi_optimized,
            "npm": self._search_npm_optimized,
            "brew": self._search_brew_optimized,
            "apt": self._search_apt_optimized,
            "dnf": self._search_dnf_optimized,
            "yum": self._search_yum_optimized,
            "pacman": self._search_pacman_optimized,
            "zypper": self._search_zypper_optimized,
            "apk": self._search_apk_optimized,
            "choco": self._search_choco_optimized,
            "winget": self._search_winget_optimized,
            "snap": self._search_snap_optimized,
            "flatpak": self._search_flatpak_optimized,
        }
        
        # Execute searches in parallel with controlled concurrency
        with _fut.ThreadPoolExecutor(max_workers=min(5, len(target_managers))) as executor:
            future_to_manager = {}
            for mgr in target_managers:
                func = manager_funcs.get(mgr, lambda q: self._search_cli_fallback(mgr, q))
                future_to_manager[executor.submit(func, query)] = mgr
            
            progress = ProgressBar(len(future_to_manager), "Searching repositories", "repos")
            
            for future in _fut.as_completed(future_to_manager, timeout=45):
                mgr = future_to_manager[future]
                try:
                    results = future.result() or []
                    all_results.extend(results)
                    cprint(f"{mgr.upper()}: {len(results)} results", "SUCCESS" if results else "MUTED")
                except Exception as e:
                    cprint(f"{mgr.upper()}: Search failed - {str(e)[:50]}", "WARNING")
                finally:
                    progress.update()
            progress.finish()
        
        # Sort by relevance and limit results
        all_results.sort(key=lambda x: x.relevance_score, reverse=True)
        final_results = all_results[:limit]
        
        # Cache results
        self._cache[cache_key] = (final_results, time.time())
        
        # Clean old cache entries periodically
        if len(self._cache) > 50:
            self._cleanup_cache()
        
        return final_results

    def _cleanup_cache(self):
        """Remove old cache entries"""
        current_time = time.time()
        expired_keys = [
            key for key, (_, timestamp) in self._cache.items() 
            if current_time - timestamp > 1800  # 30 minutes
        ]
        for key in expired_keys:
            del self._cache[key]

    def _search_pypi_optimized(self, query: str) -> List[SearchResult]:
        """Optimized PyPI search with multiple strategies"""
        results = []
        
        # Strategy 1: Direct package lookup (fastest for exact matches)
        try:
            url = f"https://pypi.org/pypi/{query}/json"
            response = self.session.get(url, timeout=8)
            if response.status_code == 200:
                data = response.json()
                info = data.get("info", {})
                results.append(SearchResult(
                    name=info.get("name", query),
                    description=info.get("summary", "")[:200],
                    version=info.get("version", "unknown"),
                    manager="pip",
                    homepage=info.get("home_page") or info.get("project_url"),
                    relevance_score=95
                ))
                return results  # Exact match found, return immediately
        except:
            pass
        
        # Strategy 2: Try common variations
        variations = [
            query.lower(),
            query.replace('-', '_'),
            query.replace('_', '-'),
            f"python-{query.lower()}",
            f"py{query.lower()}"
        ]
        
        for i, variation in enumerate(variations[:3]):
            try:
                url = f"https://pypi.org/pypi/{variation}/json"
                response = self.session.get(url, timeout=5)
                if response.status_code == 200:
                    data = response.json()
                    info = data.get("info", {})
                    results.append(SearchResult(
                        name=info.get("name", variation),
                        description=info.get("summary", "")[:200],
                        version=info.get("version", "unknown"),
                        manager="pip",
                        homepage=info.get("home_page") or info.get("project_url"),
                        relevance_score=80 - (i * 10)  # Decrease score for variations
                    ))
                    if len(results) >= 3:  # Limit variations to avoid too many requests
                        break
            except:
                continue
        
        return results

    def _search_npm_optimized(self, query: str) -> List[SearchResult]:
        """Optimized NPM search"""
        try:
            url = "https://registry.npmjs.org/-/v1/search"
            params = {"text": query, "size": 10}
            
            response = self.session.get(url, params=params, timeout=12)
            if response.status_code != 200:
                return []
            
            data = response.json()
            results = []
            
            for obj in data.get("objects", []):
                pkg = obj.get("package", {})
                score = obj.get("score", {}).get("final", 0) * 100
                
                # Boost score for exact name matches
                if pkg.get("name", "").lower() == query.lower():
                    score += 20
                
                results.append(SearchResult(
                    name=pkg.get("name", ""),
                    description=pkg.get("description", "")[:200],
                    version=pkg.get("version", "unknown"),
                    manager="npm",
                    homepage=pkg.get("homepage") or pkg.get("repository", {}).get("url"),
                    relevance_score=min(100, score)
                ))
            
            return results
        except Exception as e:
            return []

    def _search_brew_optimized(self, query: str) -> List[SearchResult]:
        """Optimized Homebrew search with intelligent caching"""
        try:
            cache_file = Path(CROSSFIRE_CACHE) / "brew_formulae_v2.json"
            formulae = None
            
            # Check cache freshness (2 hours for formulae)
            if cache_file.exists() and (time.time() - cache_file.stat().st_mtime < 7200):
                try:
                    with open(cache_file) as f:
                        cached_data = json.load(f)
                        formulae = cached_data.get('formulae', [])
                except:
                    pass
            
            if not formulae:
                # Download fresh formulae data
                url = "https://formulae.brew.sh/api/formula.json"
                response = self.session.get(url, timeout=25)
                if response.status_code == 200:
                    formulae = response.json()
                    # Cache with metadata
                    cache_file.parent.mkdir(parents=True, exist_ok=True)
                    cache_data = {
                        'formulae': formulae,
                        'timestamp': time.time(),
                        'version': 2
                    }
                    with open(cache_file, 'w') as f:
                        json.dump(cache_data, f, indent=2)
                else:
                    return []
            
            # Intelligent search through formulae
            results = []
            query_lower = query.lower()
            
            for f in formulae:
                name = f.get("name", "").lower()
                desc = f.get("desc", "").lower()
                aliases = [alias.lower() for alias in f.get("aliases", [])]
                
                score = 0
                
                # Scoring algorithm
                if name == query_lower:
                    score = 100  # Exact match
                elif query_lower in aliases:
                    score = 95   # Alias match
                elif name.startswith(query_lower):
                    score = 85   # Name starts with query
                elif query_lower in name:
                    score = 70   # Query in name
                elif any(query_lower in alias for alias in aliases):
                    score = 60   # Query in alias
                elif query_lower in desc:
                    score = 40   # Query in description
                
                if score > 0:
                    results.append(SearchResult(
                        name=f.get("name", ""),
                        description=f.get("desc", "")[:200],
                        version=f.get("versions", {}).get("stable", "unknown"),
                        manager="brew",
                        homepage=f.get("homepage"),
                        relevance_score=score
                    ))
            
            # Return top 15 results sorted by relevance
            results.sort(key=lambda x: x.relevance_score, reverse=True)
            return results[:15]
            
        except Exception as e:
            return []

    # Optimized CLI-based searches for system package managers
    def _search_apt_optimized(self, query: str) -> List[SearchResult]:
        return self._search_cli_manager("apt", ["apt-cache", "search", "--names-only", query])
    
    def _search_dnf_optimized(self, query: str) -> List[SearchResult]:
        return self._search_cli_manager("dnf", ["dnf", "search", "--quiet", query])
    
    def _search_yum_optimized(self, query: str) -> List[SearchResult]:
        return self._search_cli_manager("yum", ["yum", "search", "--quiet", query])
    
    def _search_pacman_optimized(self, query: str) -> List[SearchResult]:
        return self._search_cli_manager("pacman", ["pacman", "-Ss", query])
    
    def _search_zypper_optimized(self, query: str) -> List[SearchResult]:
        return self._search_cli_manager("zypper", ["zypper", "search", "--match-words", query])
    
    def _search_apk_optimized(self, query: str) -> List[SearchResult]:
        return self._search_cli_manager("apk", ["apk", "search", "-x", query])
    
    def _search_choco_optimized(self, query: str) -> List[SearchResult]:
        return self._search_cli_manager("choco", ["choco", "search", query, "--limit-output", "--exact"])
    
    def _search_winget_optimized(self, query: str) -> List[SearchResult]:
        return self._search_cli_manager("winget", ["winget", "search", query, "--exact"])
    
    def _search_snap_optimized(self, query: str) -> List[SearchResult]:
        return self._search_cli_manager("snap", ["snap", "find", query])
    
    def _search_flatpak_optimized(self, query: str) -> List[SearchResult]:
        return self._search_cli_manager("flatpak", ["flatpak", "search", query])

    def _search_cli_manager(self, manager: str, cmd: List[str]) -> List[SearchResult]:
        """Optimized CLI-based search with better parsing"""
        try:
            result = run_command(cmd, timeout=15)  # Shorter timeout for responsiveness
            if not result.ok:
                return []
            
            results = []
            lines = result.out.splitlines()
            
            # Different parsing strategies for different managers
            if manager == "apt":
                for line in lines[:15]:  # Limit results
                    if " - " in line:
                        parts = line.split(" - ", 1)
                        name = parts[0].strip()
                        desc = parts[1].strip() if len(parts) > 1 else ""
                        results.append(SearchResult(
                            name=name, description=desc[:200], version="unknown",
                            manager=manager, relevance_score=20
                        ))
            elif manager in ["dnf", "yum"]:
                for line in lines[:15]:
                    if line.strip() and not line.startswith("="):
                        parts = line.split(":", 1)
                        if len(parts) >= 1:
                            name = parts[0].strip().split(".")[0]  # Remove architecture
                            desc = parts[1].strip() if len(parts) > 1 else ""
                            results.append(SearchResult(
                                name=name, description=desc[:200], version="unknown",
                                manager=manager, relevance_score=25
                            ))
            else:
                # Generic parsing for other managers
                for line in lines[:10]:
                    parts = line.strip().split(None, 1)
                    if len(parts) >= 1:
                        name = parts[0]
                        desc = parts[1] if len(parts) > 1 else ""
                        results.append(SearchResult(
                            name=name, description=desc[:200], version="unknown",
                            manager=manager, relevance_score=15
                        ))
            
            return results
        except Exception as e:
            return []

    def _search_cli_fallback(self, manager: str, query: str) -> List[SearchResult]:
        """Fallback search for unsupported managers"""
        return []

search_engine = RealSearchEngine()