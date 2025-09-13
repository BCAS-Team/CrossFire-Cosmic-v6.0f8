# Module metadata for CrossFire integration
__version__ = "1.0.0f2"
__author__ = "XTERNAL Team"
__description__ = "Advanced download manager with multi-protocol support, VPN/proxy integration, and batch operations"
__commands__ = ["download", "batch", "ftp", "youtube", "settings", "diagnostics"]
__help__ = """
XTERNAL - CrossFire DownloadManager Module

Usage:
    crossfire --module XTERNAL [options]

Options:
    --interactive       Launch interactive downloader interface (default)
    --url <URL>         Download a single URL
    --batch <file>      Batch download from file
    --help             Show this help

Examples:
    crossfire --module XTERNAL
    crossfire --module XTERNAL --url https://example.com/file.zip
    crossfire --module XTERNAL --batch urls.txt
"""

APP_INFO = {
    'name': 'XTERNAL',
    'full_name': 'XTERNAL - CrossFire DownloadManager',
    'version': '1.0.0f2',
    'edition': 'Lite Edition',
    'user_agent_base': 'Xternal-DownloadManager'
}

import os
import sys
import time
import requests
import threading
import subprocess
import shutil
import json
import hashlib
import urllib.parse
from concurrent.futures import ThreadPoolExecutor
from ftplib import FTP
from pathlib import Path
from datetime import datetime
import socket
import ssl
import argparse
from typing import List
import configparser
import getpass

# Import CrossFire modules if available
try:
    # Add parent directory to path to access crossfire modules
    parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if parent_dir not in sys.path:
        sys.path.insert(0, parent_dir)
    
    from core.logger import cprint
    from core.config import LOG
    CROSSFIRE_INTEGRATION = True
except ImportError:
    # Fallback if crossfire modules aren't available
    def cprint(text, color="INFO"):
        print(text)
    
    class LOG:
        quiet = False
        verbose = False
        json_mode = False
    
    CROSSFIRE_INTEGRATION = False

class Colors:
    PRIMARY = '\033[38;5;39m'
    SUCCESS = '\033[38;5;46m'
    WARNING = '\033[38;5;208m'
    ERROR = '\033[38;5;196m'
    INFO = '\033[38;5;75m'
    ACCENT = '\033[38;5;141m'
    MUTED = '\033[38;5;244m'
    WHITE = '\033[97m'
    BOLD = '\033[1m'
    DIM = '\033[2m'
    UNDERLINE = '\033[4m'
    END = '\033[0m'

try:
    import yt_dlp
    YTDLP_AVAILABLE = True
except ImportError:
    YTDLP_AVAILABLE = False

try:
    import paramiko
    SFTP_AVAILABLE = True
except ImportError:
    SFTP_AVAILABLE = False

# Configuration file path
CONFIG_FILE = os.path.expanduser("~/.xternal_config.ini")

# Default configuration
DEFAULT_CONFIG = {
    'version': APP_INFO['version'],
    'vpn_enabled': False,
    'vpn_type': 'wireguard',
    'vpn_config_path': '',
    'proxy_enabled': False,
    'proxy_type': 'http',
    'proxy_host': '',
    'proxy_port': '8080',
    'proxy_auth': False,
    'proxy_username': '',
    'proxy_password': '',
    'download_dir': os.path.expanduser('~/Downloads/XTERNAL'),
    'max_threads': 16,
    'chunk_size': 1048576,
    'timeout': 30,
    'retries': 3,
    'verify_ssl': True,
    'user_agent': f"{APP_INFO['user_agent_base']}/{APP_INFO['version']}",
    'auto_rename': True,
    'bandwidth_limit': 0,
    'concurrent_downloads': 4,
    'hash_verification': True,
    'download_history': True,
    'notification_sound': True,
    'auto_extract': False,
    'schedule_downloads': False,
    'mirror_urls': [],
    'blocked_extensions': ['.exe', '.scr', '.bat', '.cmd'],
    'allowed_protocols': ['http', 'https', 'ftp', 'ftps', 'sftp'],
    'temp_dir': os.path.expanduser('~/Downloads/XTERNAL/temp'),
    'log_level': 'INFO',
    'log_file': os.path.expanduser('~/.xternal.log'),
    'auto_cleanup': True,
    'resume_downloads': True,
    'check_disk_space': True,
    'min_disk_space_mb': 100,
    'connection_pool_size': 10,
    'dns_servers': ['8.8.8.8', '1.1.1.1'],
    'download_rate_limit_kbps': 0,
    'upload_rate_limit_kbps': 0
}

CONFIG = DEFAULT_CONFIG.copy()

STATS = {
    'total_downloads': 0,
    'total_bytes': 0,
    'session_start': time.time(),
    'failed_downloads': 0,
    'average_speed': 0
}

DOWNLOAD_HISTORY = []

def load_config():
    """Load configuration from file"""
    global CONFIG
    if os.path.exists(CONFIG_FILE):
        try:
            config_parser = configparser.ConfigParser()
            config_parser.read(CONFIG_FILE)
            
            if 'XTERNAL' in config_parser:
                section = config_parser['XTERNAL']
                for key in CONFIG:
                    if key in section:
                        value = section[key]
                        # Convert types appropriately
                        if isinstance(CONFIG[key], bool):
                            CONFIG[key] = value.lower() in ('true', '1', 'yes', 'on')
                        elif isinstance(CONFIG[key], int):
                            CONFIG[key] = int(value)
                        elif isinstance(CONFIG[key], list):
                            CONFIG[key] = [item.strip() for item in value.split(',') if item.strip()]
                        else:
                            CONFIG[key] = value
        except Exception as e:
            print(f"{Colors.WARNING}Warning: Failed to load config: {e}{Colors.END}")

def save_config():
    """Save configuration to file"""
    try:
        config_parser = configparser.ConfigParser()
        config_parser['XTERNAL'] = {}
        section = config_parser['XTERNAL']
        
        for key, value in CONFIG.items():
            if isinstance(value, list):
                section[key] = ', '.join(str(v) for v in value)
            else:
                section[key] = str(value)
        
        os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
        with open(CONFIG_FILE, 'w') as f:
            config_parser.write(f)
        
        return True
    except Exception as e:
        print(f"{Colors.ERROR}Error saving config: {e}{Colors.END}")
        return False

def clear():
    os.system('cls' if os.name == 'nt' else 'clear')

def print_header():
    clear()
    width = 80
    print(f"{Colors.PRIMARY}{'═' * width}{Colors.END}")
    print(f"{Colors.PRIMARY}║{Colors.BOLD}{Colors.WHITE}{APP_INFO['full_name']:^78}{Colors.END}{Colors.PRIMARY}║{Colors.END}")
    print(f"{Colors.PRIMARY}║{Colors.ACCENT}{f'Version {APP_INFO['version']} - {APP_INFO['edition']}':^78}{Colors.END}{Colors.PRIMARY}║{Colors.END}")
    print(f"{Colors.PRIMARY}{'═' * width}{Colors.END}")
    
    vpn_status = f"{Colors.SUCCESS}●{Colors.END} VPN" if CONFIG['vpn_enabled'] else f"{Colors.ERROR}●{Colors.END} VPN"
    proxy_status = f"{Colors.SUCCESS}●{Colors.END} PROXY" if CONFIG['proxy_enabled'] else f"{Colors.ERROR}●{Colors.END} PROXY"
    ssl_status = f"{Colors.SUCCESS}●{Colors.END} SSL" if CONFIG['verify_ssl'] else f"{Colors.WARNING}●{Colors.END} SSL"
    
    status_line = f"Status: {vpn_status} | {proxy_status} | {ssl_status} | "
    status_line += f"{Colors.INFO}Threads: {CONFIG['max_threads']}{Colors.END} | "
    status_line += f"{Colors.INFO}Downloads: {STATS['total_downloads']}{Colors.END}"
    print(f"{Colors.MUTED}{status_line}")
    print()

def loading_animation(text, duration=2, style="dots"):
    animations = {
        "dots": ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"],
        "bars": ["▁", "▃", "▄", "▅", "▆", "▇", "█", "▇", "▆", "▅", "▄", "▃"],
        "arrows": ["←", "↖", "↑", "↗", "→", "↘", "↓", "↙"],
        "pulse": ["●", "◐", "◑", "◒", "◓", "◔", "◕", "○"]
    }
    
    frames = animations.get(style, animations["dots"])
    
    print(f"{Colors.INFO}▶ {text}{Colors.END}", end="", flush=True)
    
    start_time = time.time()
    i = 0
    while time.time() - start_time < duration:
        print(f"\r{Colors.INFO}▶ {text} {Colors.ACCENT}{frames[i % len(frames)]}{Colors.END}", end="", flush=True)
        time.sleep(0.1)
        i += 1
    
    print(f"\r{Colors.SUCCESS}✓ {text} Complete{Colors.END}")

def check_disk_space(path, required_mb):
    """Check available disk space"""
    try:
        import shutil
        total, used, free = shutil.disk_usage(path)
        free_mb = free / (1024 * 1024)
        return free_mb >= required_mb, free_mb
    except:
        return True, 0  # Assume OK if can't check

def get_system_info():
    try:
        import platform
        try:
            import psutil
            
            info = {
                'os': f"{platform.system()} {platform.release()}",
                'python': platform.python_version(),
                'cpu_cores': os.cpu_count(),
                'memory_total': f"{psutil.virtual_memory().total / 1024**3:.1f} GB",
                'memory_available': f"{psutil.virtual_memory().available / 1024**3:.1f} GB",
                'disk_space': f"{psutil.disk_usage('.').free / 1024**3:.1f} GB free"
            }
        except ImportError:
            info = {
                'os': f"{platform.system()} {platform.release()}",
                'python': platform.python_version(),
                'cpu_cores': os.cpu_count(),
                'note': 'Install psutil for detailed system info'
            }
        return info
    except ImportError:
        return {'error': 'platform module not available'}

def check_network_advanced():
    results = {}
    
    try:
        start = time.time()
        socket.gethostbyname('google.com')
        results['dns_response'] = f"{(time.time() - start) * 1000:.1f}ms"
    except:
        results['dns_response'] = "Failed"
    
    try:
        ip_response = requests.get("https://api.ipify.org", timeout=5)
        results['public_ip'] = ip_response.text
        
        geo_response = requests.get(f"https://ipinfo.io/{results['public_ip']}/json", timeout=5)
        geo_data = geo_response.json()
        
        results['location'] = f"{geo_data.get('city', 'Unknown')}, {geo_data.get('country', 'Unknown')}"
        results['isp'] = geo_data.get('org', 'Unknown')
        results['timezone'] = geo_data.get('timezone', 'Unknown')
        
        vpn_indicators = ['vpn', 'proxy', 'tor', 'tunnel', 'anonymous']
        org_lower = geo_data.get('org', '').lower()
        results['vpn_detected'] = any(indicator in org_lower for indicator in vpn_indicators)
        
    except Exception as e:
        results['error'] = str(e)
    
    try:
        start_time = time.time()
        test_response = requests.get("https://httpbin.org/bytes/1048576", timeout=15)
        end_time = time.time()
        
        duration = end_time - start_time
        speed_mbps = (1 * 8) / duration
        results['download_speed'] = f"{speed_mbps:.1f} Mbps"
        
    except:
        results['download_speed'] = "Test failed"
    
    return results

def validate_url(url):
    try:
        parsed = urllib.parse.urlparse(url)
        
        if parsed.scheme not in CONFIG['allowed_protocols']:
            return False, f"Protocol '{parsed.scheme}' not allowed"
        
        if not parsed.netloc:
            return False, "Invalid hostname"
        
        suspicious_domains = ['localhost', '127.0.0.1', '0.0.0.0']
        if parsed.netloc.lower() in suspicious_domains and not url.startswith('http://localhost'):
            return False, "Suspicious domain detected"
        
        path = parsed.path.lower()
        blocked_ext = [ext for ext in CONFIG['blocked_extensions'] if path.endswith(ext)]
        if blocked_ext:
            return False, f"Blocked file type: {blocked_ext[0]}"
        
        return True, "Valid URL"
        
    except Exception as e:
        return False, f"URL validation error: {str(e)}"

def calculate_file_hash(filepath, algorithm='sha256'):
    hash_algo = hashlib.new(algorithm)
    try:
        with open(filepath, 'rb') as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_algo.update(chunk)
        return hash_algo.hexdigest()
    except Exception as e:
        return None

def get_file_info_advanced(url):
    try:
        session = requests.Session()
        
        if CONFIG['proxy_enabled']:
            proxy_url = f"{CONFIG['proxy_type']}://"
            if CONFIG['proxy_auth']:
                proxy_url += f"{CONFIG['proxy_username']}:{CONFIG['proxy_password']}@"
            proxy_url += f"{CONFIG['proxy_host']}:{CONFIG['proxy_port']}"
            session.proxies = {'http': proxy_url, 'https': proxy_url}
        
        session.headers.update({'User-Agent': CONFIG['user_agent']})
        
        response = session.head(url, timeout=CONFIG['timeout'], verify=CONFIG['verify_ssl'])
        
        info = {
            'status_code': response.status_code,
            'file_size': int(response.headers.get('content-length', 0)),
            'content_type': response.headers.get('content-type', 'unknown'),
            'last_modified': response.headers.get('last-modified', 'unknown'),
            'server': response.headers.get('server', 'unknown'),
            'supports_resume': 'accept-ranges' in response.headers,
            'filename': extract_filename(url, response.headers),
            'headers': dict(response.headers)
        }
        
        size_bytes = info['file_size']
        if size_bytes > 0:
            for unit in ['B', 'KB', 'MB', 'GB']:
                if size_bytes < 1024:
                    info['file_size_formatted'] = f"{size_bytes:.1f} {unit}"
                    break
                size_bytes /= 1024
        else:
            info['file_size_formatted'] = "Unknown"
        
        return info, None
        
    except Exception as e:
        return None, str(e)

def extract_filename(url, headers):
    if 'content-disposition' in headers:
        disposition = headers['content-disposition']
        if 'filename=' in disposition:
            filename = disposition.split('filename=')[1].strip('"').strip("'")
            return urllib.parse.unquote(filename)
    
    parsed_url = urllib.parse.urlparse(url)
    filename = os.path.basename(parsed_url.path)
    
    if filename:
        return urllib.parse.unquote(filename)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"download_{timestamp}"

def professional_download(url, custom_filename=None, show_progress=True):
    is_valid, validation_msg = validate_url(url)
    if not is_valid:
        print(f"{Colors.ERROR}✗ URL Validation Failed: {validation_msg}{Colors.END}")
        return False
    
    loading_animation("Analyzing download target")
    file_info, error = get_file_info_advanced(url)
    
    if error:
        print(f"{Colors.ERROR}✗ Failed to get file info: {error}{Colors.END}")
        return False
    
    filename = custom_filename or file_info['filename']
    filepath = os.path.join(CONFIG['download_dir'], filename)
    
    # Check disk space
    if CONFIG['check_disk_space']:
        required_mb = (file_info['file_size'] / 1024 / 1024) + CONFIG['min_disk_space_mb']
        has_space, free_mb = check_disk_space(CONFIG['download_dir'], required_mb)
        if not has_space:
            print(f"{Colors.ERROR}✗ Insufficient disk space: {free_mb:.1f}MB free, {required_mb:.1f}MB required{Colors.END}")
            return False
    
    if CONFIG['auto_rename'] and os.path.exists(filepath):
        base, ext = os.path.splitext(filename)
        counter = 1
        while os.path.exists(filepath):
            new_filename = f"{base}_{counter}{ext}"
            filepath = os.path.join(CONFIG['download_dir'], new_filename)
            counter += 1
        filename = os.path.basename(filepath)
    
    os.makedirs(CONFIG['download_dir'], exist_ok=True)
    
    print(f"\n{Colors.INFO}╭─ Download Information{Colors.END}")
    print(f"{Colors.INFO}├─{Colors.END} {Colors.WHITE}Filename:{Colors.END} {filename}")
    print(f"{Colors.INFO}├─{Colors.END} {Colors.WHITE}Size:{Colors.END} {file_info['file_size_formatted']}")
    print(f"{Colors.INFO}├─{Colors.END} {Colors.WHITE}Type:{Colors.END} {file_info['content_type']}")
    print(f"{Colors.INFO}├─{Colors.END} {Colors.WHITE}Server:{Colors.END} {file_info['server']}")
    print(f"{Colors.INFO}├─{Colors.END} {Colors.WHITE}Resume Support:{Colors.END} {'Yes' if file_info['supports_resume'] else 'No'}")
    threads_text = CONFIG['max_threads'] if file_info['file_size'] > 10*1024*1024 else 1
    print(f"{Colors.INFO}╰─{Colors.END} {Colors.WHITE}Threads:{Colors.END} {threads_text}")
    
    confirm = input(f"\n{Colors.ACCENT}Continue download? (Y/n): {Colors.END}").lower()
    if confirm == 'n':
        return False
    
    start_time = time.time()
    success = False
    
    try:
        if file_info['file_size'] > 10 * 1024 * 1024 and file_info['supports_resume']:
            success = threaded_download_advanced(url, filepath, file_info, show_progress)
        else:
            success = simple_download_advanced(url, filepath, file_info, show_progress)
        
        if success:
            end_time = time.time()
            duration = end_time - start_time
            avg_speed = (file_info['file_size'] / 1024 / 1024) / duration if duration > 0 else 0
            
            STATS['total_downloads'] += 1
            STATS['total_bytes'] += file_info['file_size']
            STATS['average_speed'] = (STATS['average_speed'] + avg_speed) / 2
            
            if CONFIG['download_history']:
                DOWNLOAD_HISTORY.append({
                    'url': url,
                    'filename': filename,
                    'size': file_info['file_size'],
                    'duration': duration,
                    'speed': avg_speed,
                    'timestamp': datetime.now().isoformat()
                })
            
            if CONFIG['hash_verification'] and file_info['file_size'] < 100 * 1024 * 1024:
                print(f"{Colors.INFO}▶ Verifying file integrity...{Colors.END}")
                file_hash = calculate_file_hash(filepath)
                if file_hash:
                    print(f"{Colors.SUCCESS}✓ SHA256: {file_hash[:16]}...{Colors.END}")
            
            print(f"\n{Colors.SUCCESS}╭─ Download Complete{Colors.END}")
            print(f"{Colors.SUCCESS}├─{Colors.END} {Colors.WHITE}File:{Colors.END} {filename}")
            print(f"{Colors.SUCCESS}├─{Colors.END} {Colors.WHITE}Time:{Colors.END} {duration:.1f}s")
            print(f"{Colors.SUCCESS}├─{Colors.END} {Colors.WHITE}Speed:{Colors.END} {avg_speed:.1f} MB/s")
            print(f"{Colors.SUCCESS}╰─{Colors.END} {Colors.WHITE}Location:{Colors.END} {filepath}")
            
            return True
            
    except KeyboardInterrupt:
        print(f"\n{Colors.WARNING}⚠ Download interrupted by user{Colors.END}")
        return False
    except Exception as e:
        print(f"{Colors.ERROR}✗ Download failed: {str(e)}{Colors.END}")
        STATS['failed_downloads'] += 1
        return False

def simple_download_advanced(url, filepath, file_info, show_progress=True):
    resume_pos = 0
    if os.path.exists(filepath) and CONFIG['resume_downloads']:
        resume_pos = os.path.getsize(filepath)
        if resume_pos == file_info['file_size']:
            print(f"{Colors.SUCCESS}✓ File already complete{Colors.END}")
            return True
    
    session = requests.Session()
    
    if CONFIG['proxy_enabled']:
        proxy_url = f"{CONFIG['proxy_type']}://"
        if CONFIG['proxy_auth']:
            proxy_url += f"{CONFIG['proxy_username']}:{CONFIG['proxy_password']}@"
        proxy_url += f"{CONFIG['proxy_host']}:{CONFIG['proxy_port']}"
        session.proxies = {'http': proxy_url, 'https': proxy_url}
    
    headers = {'User-Agent': CONFIG['user_agent']}
    if resume_pos > 0:
        headers['Range'] = f'bytes={resume_pos}-'
    
    mode = 'ab' if resume_pos > 0 else 'wb'
    
    response = session.get(url, headers=headers, stream=True, timeout=CONFIG['timeout'], verify=CONFIG['verify_ssl'])
    response.raise_for_status()
    
    total_size = file_info['file_size']
    downloaded = resume_pos
    last_time = time.time()
    
    with open(filepath, mode) as f:
        for chunk in response.iter_content(chunk_size=CONFIG['chunk_size']):
            if chunk:
                f.write(chunk)
                downloaded += len(chunk)
                
                # Rate limiting
                if CONFIG['download_rate_limit_kbps'] > 0:
                    current_time = time.time()
                    elapsed = current_time - last_time
                    expected_time = len(chunk) / (CONFIG['download_rate_limit_kbps'] * 1024)
                    if elapsed < expected_time:
                        time.sleep(expected_time - elapsed)
                    last_time = current_time
                
                if show_progress and total_size > 0:
                    progress = (downloaded / total_size) * 100
                    bar_length = 40
                    filled = int(bar_length * progress / 100)
                    bar = '█' * filled + '▒' * (bar_length - filled)
                    speed = downloaded / (time.time() - STATS['session_start']) / 1024 / 1024
                    
                    progress_line = f"[{bar}] {progress:.1f}% "
                    progress_line += f"({downloaded//1024//1024}MB/{total_size//1024//1024}MB) "
                    progress_line += f"{speed:.1f}MB/s"
                    print(f"\r{Colors.PRIMARY}{progress_line}{Colors.END}", end="", flush=True)
    
    if show_progress:
        print()
    
    return True

def threaded_download_advanced(url, filepath, file_info, show_progress=True):
    num_threads = min(CONFIG['max_threads'], 16)
    file_size = file_info['file_size']
    chunk_size = file_size // num_threads
    
    download_tasks = []
    for i in range(num_threads):
        start = i * chunk_size
        end = start + chunk_size - 1 if i < num_threads - 1 else file_size - 1
        download_tasks.append((start, end, i))
    
    progress_data = {'downloaded': [0] * num_threads}
    progress_lock = threading.Lock()
    
    def download_chunk(start_byte, end_byte, thread_id):
        try:
            session = requests.Session()
            
            if CONFIG['proxy_enabled']:
                proxy_url = f"{CONFIG['proxy_type']}://"
                if CONFIG['proxy_auth']:
                    proxy_url += f"{CONFIG['proxy_username']}:{CONFIG['proxy_password']}@"
                proxy_url += f"{CONFIG['proxy_host']}:{CONFIG['proxy_port']}"
                session.proxies = {'http': proxy_url, 'https': proxy_url}
            
            headers = {
                'Range': f'bytes={start_byte}-{end_byte}',
                'User-Agent': CONFIG['user_agent']
            }
            
            response = session.get(url, headers=headers, stream=True, timeout=CONFIG['timeout'], verify=CONFIG['verify_ssl'])
            response.raise_for_status()
            
            temp_file = f"{filepath}.part{thread_id}"
            with open(temp_file, 'wb') as f:
                for chunk in response.iter_content(chunk_size=CONFIG['chunk_size']):
                    if chunk:
                        f.write(chunk)
                        with progress_lock:
                            progress_data['downloaded'][thread_id] += len(chunk)
            
            return temp_file
            
        except Exception as e:
            print(f"{Colors.ERROR}Thread {thread_id} error: {str(e)}{Colors.END}")
            return None
    
    print(f"{Colors.INFO}▶ Starting {num_threads} download threads...{Colors.END}")
    
    with ThreadPoolExecutor(max_workers=num_threads) as executor:
        futures = [executor.submit(download_chunk, start, end, tid) for start, end, tid in download_tasks]
        
        start_time = time.time()
        while not all(f.done() for f in futures):
            if show_progress:
                total_downloaded = sum(progress_data['downloaded'])
                progress = (total_downloaded / file_size) * 100 if file_size > 0 else 0
                elapsed = time.time() - start_time
                speed = total_downloaded / elapsed / 1024 / 1024 if elapsed > 0 else 0
                
                bar_length = 50
                filled = int(bar_length * progress / 100)
                bar = '█' * filled + '░' * (bar_length - filled)
                
                progress_line = f"[{bar}] {progress:.1f}% "
                progress_line += f"({total_downloaded//1024//1024}MB/{file_size//1024//1024}MB) "
                progress_line += f"{speed:.1f}MB/s"
                print(f"\r{Colors.PRIMARY}{progress_line}{Colors.END}", end="", flush=True)
            
            time.sleep(0.1)
        
        if show_progress:
            print()
        
        temp_files = [f.result() for f in futures if f.result()]
    
    if len(temp_files) == num_threads:
        print(f"{Colors.INFO}▶ Combining file chunks...{Colors.END}")
        with open(filepath, 'wb') as outfile:
            for i in range(num_threads):
                temp_file = f"{filepath}.part{i}"
                if os.path.exists(temp_file):
                    with open(temp_file, 'rb') as infile:
                        shutil.copyfileobj(infile, outfile)
                    os.remove(temp_file)
        return True
    else:
        print(f"{Colors.ERROR}✗ Some chunks failed to download{Colors.END}")
        for i in range(num_threads):
            temp_file = f"{filepath}.part{i}"
            if os.path.exists(temp_file):
                os.remove(temp_file)
        return False

def advanced_ftp_download():
    print(f"\n{Colors.ACCENT}╭─ FTP/FTPS Download Configuration{Colors.END}")
    
    host = input(f"{Colors.ACCENT}├─{Colors.END} FTP Host: ")
    port = input(f"{Colors.ACCENT}├─{Colors.END} Port (21): ") or "21"
    username = input(f"{Colors.ACCENT}├─{Colors.END} Username (anonymous): ") or "anonymous"
    password = getpass.getpass(f"{Colors.ACCENT}├─{Colors.END} Password: ") or ""
    remote_path = input(f"{Colors.ACCENT}├─{Colors.END} Remote file path: ")
    use_ftps = input(f"{Colors.ACCENT}╰─{Colors.END} Use FTPS? (y/N): ").lower() == 'y'
    
    if not host or not remote_path:
        print(f"{Colors.ERROR}✗ Host and remote path are required{Colors.END}")
        return
    
    try:
        loading_animation("Establishing FTP connection")
        
        if use_ftps:
            from ftplib import FTP_TLS
            ftp = FTP_TLS()
        else:
            ftp = FTP()
        
        ftp.connect(host, int(port))
        ftp.login(username, password)
        
        if use_ftps:
            ftp.prot_p()
        
        try:
            file_size = ftp.size(remote_path)
        except:
            file_size = 0
        
        filename = os.path.basename(remote_path)
        local_path = os.path.join(CONFIG['download_dir'], filename)
        os.makedirs(CONFIG['download_dir'], exist_ok=True)
        
        print(f"\n{Colors.INFO}Downloading: {filename}")
        if file_size > 0:
            print(f"{Colors.INFO}Size: {file_size / 1024 / 1024:.1f} MB{Colors.END}")
        
        start_time = time.time()
        downloaded = 0
        
        def progress_callback(data):
            nonlocal downloaded
            downloaded += len(data)
            if file_size > 0:
                progress = (downloaded / file_size) * 100
                speed = downloaded / (time.time() - start_time) / 1024 / 1024
                print(f"\r{Colors.PRIMARY}Progress: {progress:.1f}% - {speed:.1f} MB/s{Colors.END}", end="", flush=True)
        
        with open(local_path, 'wb') as f:
            if file_size > 0:
                ftp.retrbinary(f'RETR {remote_path}', lambda data: (f.write(data), progress_callback(data)))
            else:
                ftp.retrbinary(f'RETR {remote_path}', f.write)
        
        ftp.quit()
        
        duration = time.time() - start_time
        speed = (downloaded / 1024 / 1024) / duration if duration > 0 else 0
        
        print(f"\n{Colors.SUCCESS}✓ FTP download complete!")
        print(f"{Colors.SUCCESS}  File: {filename}")
        print(f"{Colors.SUCCESS}  Time: {duration:.1f}s")
        print(f"{Colors.SUCCESS}  Speed: {speed:.1f} MB/s{Colors.END}")
        
        STATS['total_downloads'] += 1
        STATS['total_bytes'] += downloaded
        
    except Exception as e:
        print(f"{Colors.ERROR}✗ FTP download failed: {str(e)}{Colors.END}")

def youtube_download():
    """Advanced YouTube/Video download with yt-dlp"""
    if not YTDLP_AVAILABLE:
        print(f"{Colors.ERROR}✗ yt-dlp not available. Install with: pip install yt-dlp{Colors.END}")
        return False
    
    print(f"\n{Colors.ACCENT}╭─ YouTube/Video Download{Colors.END}")
    
    url = input(f"{Colors.ACCENT}├─{Colors.END} Video URL: ")
    if not url.strip():
        print(f"{Colors.ERROR}✗ URL is required{Colors.END}")
        return False
    
    print(f"{Colors.ACCENT}├─{Colors.END} Quality Options:")
    print(f"{Colors.ACCENT}│{Colors.END}  1. Best quality (default)")
    print(f"{Colors.ACCENT}│{Colors.END}  2. Audio only (MP3)")
    print(f"{Colors.ACCENT}│{Colors.END}  3. 1080p (if available)")
    print(f"{Colors.ACCENT}│{Colors.END}  4. 720p")
    print(f"{Colors.ACCENT}│{Colors.END}  5. 480p")
    print(f"{Colors.ACCENT}│{Colors.END}  6. Custom format")
    
    quality = input(f"{Colors.ACCENT}╰─{Colors.END} Select quality (1): ") or "1"
    
    # Configure yt-dlp options
    ydl_opts = {
        'outtmpl': os.path.join(CONFIG['download_dir'], '%(title)s.%(ext)s'),
        'writeinfojson': True,
        'writesubtitles': True,
        'writeautomaticsub': True,
        'subtitleslangs': ['en'],
    }
    
    # Set quality based on user choice
    if quality == "1":
        ydl_opts['format'] = 'best[height<=?1080]'
    elif quality == "2":
        ydl_opts.update({
            'format': 'bestaudio/best',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }]
        })
    elif quality == "3":
        ydl_opts['format'] = 'best[height<=?1080]'
    elif quality == "4":
        ydl_opts['format'] = 'best[height<=?720]'
    elif quality == "5":
        ydl_opts['format'] = 'best[height<=?480]'
    elif quality == "6":
        custom_format = input(f"{Colors.INFO}Enter custom format (e.g., 'best[ext=mp4]'): {Colors.END}")
        if custom_format:
            ydl_opts['format'] = custom_format
    
    # Add proxy support if enabled
    if CONFIG['proxy_enabled']:
        proxy_url = f"{CONFIG['proxy_type']}://"
        if CONFIG['proxy_auth']:
            proxy_url += f"{CONFIG['proxy_username']}:{CONFIG['proxy_password']}@"
        proxy_url += f"{CONFIG['proxy_host']}:{CONFIG['proxy_port']}"
        ydl_opts['proxy'] = proxy_url
    
    # Progress hook
    def progress_hook(d):
        if d['status'] == 'downloading':
            if 'total_bytes' in d:
                progress = (d.get('downloaded_bytes', 0) / d['total_bytes']) * 100
                speed = d.get('speed', 0)
                speed_str = f"{speed/1024/1024:.1f} MB/s" if speed else "-- MB/s"
                
                bar_length = 40
                filled = int(bar_length * progress / 100)
                bar = '█' * filled + '░' * (bar_length - filled)
                
                print(f"\r{Colors.PRIMARY}[{bar}] {progress:.1f}% - {speed_str}{Colors.END}", end="", flush=True)
            else:
                # For streams without total size info
                downloaded = d.get('downloaded_bytes', 0)
                speed = d.get('speed', 0)
                speed_str = f"{speed/1024/1024:.1f} MB/s" if speed else "-- MB/s"
                print(f"\r{Colors.PRIMARY}Downloaded: {downloaded/1024/1024:.1f}MB - {speed_str}{Colors.END}", end="", flush=True)
        elif d['status'] == 'finished':
            print(f"\n{Colors.SUCCESS}✓ Download completed: {d['filename']}{Colors.END}")
    
    ydl_opts['progress_hooks'] = [progress_hook]
    
    try:
        # Create download directory
        os.makedirs(CONFIG['download_dir'], exist_ok=True)
        
        print(f"\n{Colors.INFO}▶ Analyzing video...{Colors.END}")
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # Get video info first
            try:
                info = ydl.extract_info(url, download=False)
                
                print(f"\n{Colors.INFO}╭─ Video Information{Colors.END}")
                print(f"{Colors.INFO}├─{Colors.END} {Colors.WHITE}Title:{Colors.END} {info.get('title', 'Unknown')[:60]}")
                print(f"{Colors.INFO}├─{Colors.END} {Colors.WHITE}Uploader:{Colors.END} {info.get('uploader', 'Unknown')}")
                print(f"{Colors.INFO}├─{Colors.END} {Colors.WHITE}Duration:{Colors.END} {info.get('duration_string', 'Unknown')}")
                print(f"{Colors.INFO}├─{Colors.END} {Colors.WHITE}View Count:{Colors.END} {info.get('view_count', 'Unknown')}")
                
                # Show available formats
                if 'formats' in info:
                    print(f"{Colors.INFO}├─{Colors.END} {Colors.WHITE}Available Formats:{Colors.END}")
                    formats = info['formats'][-5:]  # Show last 5 formats
                    for fmt in formats:
                        resolution = fmt.get('resolution', 'audio only')
                        filesize = fmt.get('filesize', 0)
                        size_str = f"{filesize/1024/1024:.1f}MB" if filesize else "Unknown size"
                        print(f"{Colors.INFO}│{Colors.END}   {resolution} ({fmt.get('ext', 'unknown')}) - {size_str}")
                
                print(f"{Colors.INFO}╰─{Colors.END} {Colors.WHITE}URL:{Colors.END} {url}")
                
                confirm = input(f"\n{Colors.ACCENT}Continue download? (Y/n): {Colors.END}").lower()
                if confirm == 'n':
                    return False
                
                start_time = time.time()
                
                # Download the video
                print(f"\n{Colors.INFO}▶ Starting download...{Colors.END}")
                ydl.download([url])
                
                duration = time.time() - start_time
                print(f"\n{Colors.SUCCESS}✓ Video download completed in {duration:.1f}s{Colors.END}")
                
                # Update stats
                STATS['total_downloads'] += 1
                if 'filesize' in info:
                    STATS['total_bytes'] += info['filesize']
                
                # Add to history
                if CONFIG['download_history']:
                    DOWNLOAD_HISTORY.append({
                        'url': url,
                        'filename': info.get('title', 'Unknown'),
                        'size': info.get('filesize', 0),
                        'duration': duration,
                        'speed': 0,  # yt-dlp handles speed internally
                        'timestamp': datetime.now().isoformat(),
                        'type': 'youtube'
                    })
                
                return True
                
            except Exception as e:
                print(f"{Colors.ERROR}✗ Failed to get video info: {str(e)}{Colors.END}")
                return False
                
    except Exception as e:
        print(f"{Colors.ERROR}✗ YouTube download failed: {str(e)}{Colors.END}")
        STATS['failed_downloads'] += 1
        return False

def batch_download_manager():
    print(f"\n{Colors.ACCENT}╭─ Batch Download Manager{Colors.END}")
    
    print(f"{Colors.ACCENT}├─{Colors.END} Input Methods:")
    print(f"{Colors.ACCENT}│{Colors.END}  1. Manual URL entry")
    print(f"{Colors.ACCENT}│{Colors.END}  2. Import from file")
    print(f"{Colors.ACCENT}│{Colors.END}  3. Import from clipboard")
    
    method = input(f"{Colors.ACCENT}╰─{Colors.END} Select method (1): ") or "1"
    
    urls = []
    
    if method == "1":
        print(f"{Colors.INFO}Enter URLs (one per line, empty line to finish):{Colors.END}")
        while True:
            url = input().strip()
            if not url:
                break
            urls.append(url)
    
    elif method == "2":
        file_path = input(f"{Colors.INFO}Enter file path: {Colors.END}")
        try:
            with open(file_path, 'r') as f:
                urls = [line.strip() for line in f if line.strip()]
        except Exception as e:
            print(f"{Colors.ERROR}✗ Failed to read file: {e}{Colors.END}")
            return
    
    elif method == "3":
        try:
            import pyperclip
            clipboard_content = pyperclip.paste()
            urls = [line.strip() for line in clipboard_content.split('\n') if line.strip()]
        except ImportError:
            print(f"{Colors.ERROR}✗ pyperclip not available. Install with: pip install pyperclip{Colors.END}")
            return
    
    if not urls:
        print(f"{Colors.WARNING}⚠ No URLs provided{Colors.END}")
        return
    
    print(f"\n{Colors.INFO}Found {len(urls)} URLs to download{Colors.END}")
    
    concurrent = input(f"{Colors.INFO}Max concurrent downloads (4): {Colors.END}") or "4"
    try:
        concurrent = max(1, min(10, int(concurrent)))
    except ValueError:
        concurrent = 4
    
    successful = 0
    failed = 0
    
    print(f"\n{Colors.PRIMARY}Starting batch download with {concurrent} concurrent downloads...{Colors.END}")
    
    for i, url in enumerate(urls, 1):
        print(f"\n{Colors.ACCENT}[{i}/{len(urls)}] Processing: {url[:60]}...{Colors.END}")
        
        if professional_download(url, show_progress=False):
            successful += 1
        else:
            failed += 1
    
    print(f"\n{Colors.SUCCESS}╭─ Batch Download Complete{Colors.END}")
    print(f"{Colors.SUCCESS}├─{Colors.END} Successful: {successful}")
    print(f"{Colors.SUCCESS}├─{Colors.END} Failed: {failed}")
    print(f"{Colors.SUCCESS}╰─{Colors.END} Total: {len(urls)}")

def advanced_settings_menu():
    """Comprehensive advanced settings menu"""
    while True:
        print_header()
        print(f"{Colors.ACCENT}╭─ Advanced Settings{Colors.END}")
        print(f"{Colors.ACCENT}├─{Colors.END} Network & Connection")
        print(f"{Colors.ACCENT}│{Colors.END}  {Colors.SUCCESS}1.{Colors.END} Download Directories")
        print(f"{Colors.ACCENT}│{Colors.END}  {Colors.SUCCESS}2.{Colors.END} Network Configuration")
        print(f"{Colors.ACCENT}│{Colors.END}  {Colors.SUCCESS}3.{Colors.END} Proxy Settings")
        print(f"{Colors.ACCENT}│{Colors.END}  {Colors.SUCCESS}4.{Colors.END} VPN Integration")
        print(f"{Colors.ACCENT}├─{Colors.END} Performance & Security")
        print(f"{Colors.ACCENT}│{Colors.END}  {Colors.SUCCESS}5.{Colors.END} Download Behavior")
        print(f"{Colors.ACCENT}│{Colors.END}  {Colors.SUCCESS}6.{Colors.END} Security Options")
        print(f"{Colors.ACCENT}│{Colors.END}  {Colors.SUCCESS}7.{Colors.END} Rate Limiting")
        print(f"{Colors.ACCENT}├─{Colors.END} System Management")
        print(f"{Colors.ACCENT}│{Colors.END}  {Colors.SUCCESS}8.{Colors.END} File Management")
        print(f"{Colors.ACCENT}│{Colors.END}  {Colors.SUCCESS}9.{Colors.END} System Resources")
        print(f"{Colors.ACCENT}│{Colors.END}  {Colors.SUCCESS}10.{Colors.END} Logging & History")
        print(f"{Colors.ACCENT}├─{Colors.END} Configuration")
        print(f"{Colors.ACCENT}│{Colors.END}  {Colors.SUCCESS}11.{Colors.END} Import/Export Config")
        print(f"{Colors.ACCENT}│{Colors.END}  {Colors.SUCCESS}12.{Colors.END} Reset to Defaults")
        print(f"{Colors.ACCENT}╰─{Colors.END}  {Colors.WARNING}13.{Colors.END} Back to Main Menu")
        
        choice = input(f"\n{Colors.BOLD}▶ Select option (1-13): {Colors.END}")
        
        if choice == '1':
            configure_directories()
        elif choice == '2':
            configure_network()
        elif choice == '3':
            configure_proxy()
        elif choice == '4':
            configure_vpn()
        elif choice == '5':
            configure_download_behavior()
        elif choice == '6':
            configure_security()
        elif choice == '7':
            configure_rate_limiting()
        elif choice == '8':
            configure_file_management()
        elif choice == '9':
            configure_system_resources()
        elif choice == '10':
            configure_logging()
        elif choice == '11':
            import_export_config()
        elif choice == '12':
            reset_to_defaults()
        elif choice == '13':
            break
        else:
            print(f"{Colors.ERROR}✗ Invalid option{Colors.END}")
            time.sleep(1)

def configure_directories():
    """Configure download and temporary directories"""
    print(f"\n{Colors.ACCENT}╭─ Directory Configuration{Colors.END}")
    
    print(f"{Colors.INFO}Current Settings:{Colors.END}")
    print(f"{Colors.INFO}├─{Colors.END} Download Directory: {CONFIG['download_dir']}")
    print(f"{Colors.INFO}╰─{Colors.END} Temp Directory: {CONFIG['temp_dir']}")
    
    print(f"\n{Colors.ACCENT}╭─ Options{Colors.END}")
    print(f"{Colors.ACCENT}├─{Colors.END} 1. Change download directory")
    print(f"{Colors.ACCENT}├─{Colors.END} 2. Change temp directory")
    print(f"{Colors.ACCENT}├─{Colors.END} 3. Create directory structure")
    print(f"{Colors.ACCENT}╰─{Colors.END} 4. Check directory permissions")
    
    choice = input(f"\n{Colors.BOLD}Select option (1-4): {Colors.END}")
    
    if choice == '1':
        new_dir = input(f"{Colors.INFO}Enter new download directory: {Colors.END}")
        if new_dir:
            expanded_dir = os.path.expanduser(new_dir)
            try:
                os.makedirs(expanded_dir, exist_ok=True)
                CONFIG['download_dir'] = expanded_dir
                print(f"{Colors.SUCCESS}✓ Download directory updated: {expanded_dir}{Colors.END}")
                save_config()
            except Exception as e:
                print(f"{Colors.ERROR}✗ Failed to create directory: {e}{Colors.END}")
    
    elif choice == '2':
        new_temp = input(f"{Colors.INFO}Enter new temp directory: {Colors.END}")
        if new_temp:
            expanded_temp = os.path.expanduser(new_temp)
            try:
                os.makedirs(expanded_temp, exist_ok=True)
                CONFIG['temp_dir'] = expanded_temp
                print(f"{Colors.SUCCESS}✓ Temp directory updated: {expanded_temp}{Colors.END}")
                save_config()
            except Exception as e:
                print(f"{Colors.ERROR}✗ Failed to create temp directory: {e}{Colors.END}")
    
    elif choice == '3':
        dirs_to_create = [
            'downloads/video',
            'downloads/audio',
            'downloads/documents',
            'downloads/archives',
            'temp',
            'logs'
        ]
        
        base_dir = CONFIG['download_dir']
        for dir_name in dirs_to_create:
            full_path = os.path.join(base_dir, dir_name)
            try:
                os.makedirs(full_path, exist_ok=True)
                print(f"{Colors.SUCCESS}✓ Created: {full_path}{Colors.END}")
            except Exception as e:
                print(f"{Colors.ERROR}✗ Failed to create {full_path}: {e}{Colors.END}")
    
    elif choice == '4':
        dirs_to_check = [CONFIG['download_dir'], CONFIG['temp_dir']]
        for directory in dirs_to_check:
            if os.path.exists(directory):
                readable = os.access(directory, os.R_OK)
                writable = os.access(directory, os.W_OK)
                executable = os.access(directory, os.X_OK)
                
                perms = f"R{'✓' if readable else '✗'} W{'✓' if writable else '✗'} X{'✓' if executable else '✗'}"
                print(f"{Colors.INFO}{directory}: {perms}{Colors.END}")
            else:
                print(f"{Colors.WARNING}{directory}: Does not exist{Colors.END}")
    
    input(f"\n{Colors.MUTED}Press Enter to continue...{Colors.END}")

def configure_network():
    """Configure network settings"""
    print(f"\n{Colors.ACCENT}╭─ Network Configuration{Colors.END}")
    
    print(f"{Colors.INFO}Current Settings:{Colors.END}")
    print(f"{Colors.INFO}├─{Colors.END} Timeout: {CONFIG['timeout']}s")
    print(f"{Colors.INFO}├─{Colors.END} Retries: {CONFIG['retries']}")
    print(f"{Colors.INFO}├─{Colors.END} SSL Verification: {CONFIG['verify_ssl']}")
    print(f"{Colors.INFO}├─{Colors.END} User Agent: {CONFIG['user_agent']}")
    print(f"{Colors.INFO}╰─{Colors.END} Connection Pool: {CONFIG['connection_pool_size']}")
    
    print(f"\n1. Timeout (current: {CONFIG['timeout']}s)")
    new_timeout = input(f"   New timeout in seconds (Enter to skip): ")
    if new_timeout.isdigit():
        CONFIG['timeout'] = int(new_timeout)
        print(f"{Colors.SUCCESS}✓ Timeout updated to {CONFIG['timeout']}s{Colors.END}")
    
    print(f"\n2. Retries (current: {CONFIG['retries']})")
    new_retries = input(f"   New retry count (Enter to skip): ")
    if new_retries.isdigit():
        CONFIG['retries'] = int(new_retries)
        print(f"{Colors.SUCCESS}✓ Retries updated to {CONFIG['retries']}{Colors.END}")
    
    print(f"\n3. SSL Verification (current: {CONFIG['verify_ssl']})")
    ssl_choice = input(f"   Enable SSL verification? (y/n, Enter to skip): ").lower()
    if ssl_choice in ['y', 'n']:
        CONFIG['verify_ssl'] = ssl_choice == 'y'
        print(f"{Colors.SUCCESS}✓ SSL verification {'enabled' if CONFIG['verify_ssl'] else 'disabled'}{Colors.END}")
    
    print(f"\n4. User Agent (current: {CONFIG['user_agent'][:50]}...)")
    new_ua = input(f"   New User Agent (Enter to skip): ")
    if new_ua.strip():
        CONFIG['user_agent'] = new_ua.strip()
        print(f"{Colors.SUCCESS}✓ User Agent updated{Colors.END}")
    
    print(f"\n5. Connection Pool Size (current: {CONFIG['connection_pool_size']})")
    new_pool = input(f"   New pool size (Enter to skip): ")
    if new_pool.isdigit():
        CONFIG['connection_pool_size'] = max(1, min(50, int(new_pool)))
        print(f"{Colors.SUCCESS}✓ Connection pool updated to {CONFIG['connection_pool_size']}{Colors.END}")
    
    save_config()
    input(f"\n{Colors.MUTED}Press Enter to continue...{Colors.END}")

def configure_proxy():
    """Configure proxy settings"""
    print(f"\n{Colors.ACCENT}╭─ Proxy Configuration{Colors.END}")
    
    current_status = "Enabled" if CONFIG['proxy_enabled'] else "Disabled"
    print(f"{Colors.INFO}Current Status: {current_status}{Colors.END}")
    
    if CONFIG['proxy_enabled']:
        print(f"{Colors.INFO}├─{Colors.END} Type: {CONFIG['proxy_type']}")
        print(f"{Colors.INFO}├─{Colors.END} Host: {CONFIG['proxy_host']}")
        print(f"{Colors.INFO}├─{Colors.END} Port: {CONFIG['proxy_port']}")
        auth_status = "Yes" if CONFIG['proxy_auth'] else "No"
        print(f"{Colors.INFO}╰─{Colors.END} Authentication: {auth_status}")
    
    enable = input(f"\nEnable proxy? (y/n): ").lower() == 'y'
    CONFIG['proxy_enabled'] = enable
    
    if enable:
        CONFIG['proxy_type'] = input(f"Proxy type (http/https/socks4/socks5) [{CONFIG['proxy_type']}]: ") or CONFIG['proxy_type']
        CONFIG['proxy_host'] = input(f"Proxy host [{CONFIG['proxy_host']}]: ") or CONFIG['proxy_host']
        
        port_input = input(f"Proxy port [{CONFIG['proxy_port']}]: ")
        if port_input.isdigit():
            CONFIG['proxy_port'] = port_input
        
        auth_enable = input(f"Enable authentication? (y/n): ").lower() == 'y'
        CONFIG['proxy_auth'] = auth_enable
        
        if auth_enable:
            CONFIG['proxy_username'] = input(f"Username [{CONFIG['proxy_username']}]: ") or CONFIG['proxy_username']
            CONFIG['proxy_password'] = getpass.getpass(f"Password: ") or CONFIG['proxy_password']
    
    print(f"{Colors.SUCCESS}✓ Proxy configuration {'enabled' if enable else 'disabled'}{Colors.END}")
    save_config()
    input(f"\n{Colors.MUTED}Press Enter to continue...{Colors.END}")

def configure_vpn():
    """Configure VPN integration"""
    print(f"\n{Colors.ACCENT}╭─ VPN Integration{Colors.END}")
    
    current_status = "Enabled" if CONFIG['vpn_enabled'] else "Disabled"
    print(f"{Colors.INFO}Current Status: {current_status}{Colors.END}")
    
    if CONFIG['vpn_enabled']:
        print(f"{Colors.INFO}├─{Colors.END} Type: {CONFIG['vpn_type']}")
        print(f"{Colors.INFO}╰─{Colors.END} Config Path: {CONFIG['vpn_config_path']}")
    
    enable = input(f"\nEnable VPN integration? (y/n): ").lower() == 'y'
    CONFIG['vpn_enabled'] = enable
    
    if enable:
        print(f"\nVPN Types:")
        print(f"1. WireGuard")
        print(f"2. OpenVPN")
        print(f"3. IKEv2/IPSec")
        
        vpn_choice = input(f"Select VPN type (1-3): ")
        vpn_types = {'1': 'wireguard', '2': 'openvpn', '3': 'ikev2'}
        CONFIG['vpn_type'] = vpn_types.get(vpn_choice, 'wireguard')
        
        config_path = input(f"VPN config file path (optional): ")
        if config_path and os.path.exists(config_path):
            CONFIG['vpn_config_path'] = config_path
        
        print(f"{Colors.WARNING}Note: VPN integration requires manual setup and appropriate software{Colors.END}")
    
    print(f"{Colors.SUCCESS}✓ VPN integration {'enabled' if enable else 'disabled'}{Colors.END}")
    save_config()
    input(f"\n{Colors.MUTED}Press Enter to continue...{Colors.END}")

def configure_download_behavior():
    """Configure download behavior settings"""
    print(f"\n{Colors.ACCENT}╭─ Download Behavior{Colors.END}")
    
    print(f"{Colors.INFO}Current Settings:{Colors.END}")
    print(f"{Colors.INFO}├─{Colors.END} Max Threads: {CONFIG['max_threads']}")
    print(f"{Colors.INFO}├─{Colors.END} Chunk Size: {CONFIG['chunk_size']} bytes")
    print(f"{Colors.INFO}├─{Colors.END} Concurrent Downloads: {CONFIG['concurrent_downloads']}")
    print(f"{Colors.INFO}├─{Colors.END} Auto Rename: {CONFIG['auto_rename']}")
    print(f"{Colors.INFO}├─{Colors.END} Resume Downloads: {CONFIG['resume_downloads']}")
    print(f"{Colors.INFO}╰─{Colors.END} Auto Extract: {CONFIG['auto_extract']}")
    
    print(f"\n1. Max Threads (1-32)")
    threads = input(f"   New value [{CONFIG['max_threads']}]: ")
    if threads.isdigit():
        CONFIG['max_threads'] = max(1, min(32, int(threads)))
    
    print(f"\n2. Chunk Size (bytes)")
    chunk = input(f"   New value [{CONFIG['chunk_size']}]: ")
    if chunk.isdigit():
        CONFIG['chunk_size'] = max(1024, int(chunk))
    
    print(f"\n3. Concurrent Downloads (1-10)")
    concurrent = input(f"   New value [{CONFIG['concurrent_downloads']}]: ")
    if concurrent.isdigit():
        CONFIG['concurrent_downloads'] = max(1, min(10, int(concurrent)))
    
    print(f"\n4. Auto Rename Duplicates")
    rename = input(f"   Enable? (y/n) [{'y' if CONFIG['auto_rename'] else 'n'}]: ").lower()
    if rename in ['y', 'n']:
        CONFIG['auto_rename'] = rename == 'y'
    
    print(f"\n5. Resume Interrupted Downloads")
    resume = input(f"   Enable? (y/n) [{'y' if CONFIG['resume_downloads'] else 'n'}]: ").lower()
    if resume in ['y', 'n']:
        CONFIG['resume_downloads'] = resume == 'y'
    
    print(f"\n6. Auto Extract Archives")
    extract = input(f"   Enable? (y/n) [{'y' if CONFIG['auto_extract'] else 'n'}]: ").lower()
    if extract in ['y', 'n']:
        CONFIG['auto_extract'] = extract == 'y'
    
    print(f"{Colors.SUCCESS}✓ Download behavior updated{Colors.END}")
    save_config()
    input(f"\n{Colors.MUTED}Press Enter to continue...{Colors.END}")

def configure_security():
    """Configure security options"""
    print(f"\n{Colors.ACCENT}╭─ Security Options{Colors.END}")
    
    print(f"{Colors.INFO}Current Settings:{Colors.END}")
    print(f"{Colors.INFO}├─{Colors.END} Hash Verification: {CONFIG['hash_verification']}")
    print(f"{Colors.INFO}├─{Colors.END} SSL Verification: {CONFIG['verify_ssl']}")
    print(f"{Colors.INFO}├─{Colors.END} Allowed Protocols: {', '.join(CONFIG['allowed_protocols'])}")
    print(f"{Colors.INFO}╰─{Colors.END} Blocked Extensions: {', '.join(CONFIG['blocked_extensions'])}")
    
    print(f"\n1. Hash Verification")
    hash_verify = input(f"   Enable file hash verification? (y/n) [{'y' if CONFIG['hash_verification'] else 'n'}]: ").lower()
    if hash_verify in ['y', 'n']:
        CONFIG['hash_verification'] = hash_verify == 'y'
    
    print(f"\n2. SSL/TLS Verification")
    ssl_verify = input(f"   Enable SSL certificate verification? (y/n) [{'y' if CONFIG['verify_ssl'] else 'n'}]: ").lower()
    if ssl_verify in ['y', 'n']:
        CONFIG['verify_ssl'] = ssl_verify == 'y'
    
    print(f"\n3. Manage Allowed Protocols")
    print(f"   Current: {', '.join(CONFIG['allowed_protocols'])}")
    modify_protocols = input(f"   Modify allowed protocols? (y/n): ").lower() == 'y'
    if modify_protocols:
        all_protocols = ['http', 'https', 'ftp', 'ftps', 'sftp']
        new_protocols = []
        for protocol in all_protocols:
            allow = input(f"   Allow {protocol}? (y/n): ").lower() == 'y'
            if allow:
                new_protocols.append(protocol)
        if new_protocols:
            CONFIG['allowed_protocols'] = new_protocols
    
    print(f"\n4. Manage Blocked Extensions")
    print(f"   Current: {', '.join(CONFIG['blocked_extensions'])}")
    modify_blocked = input(f"   Modify blocked extensions? (y/n): ").lower() == 'y'
    if modify_blocked:
        print(f"   Enter blocked extensions (comma-separated, with dots): ")
        blocked_input = input(f"   Example: .exe,.scr,.bat: ")
        if blocked_input.strip():
            CONFIG['blocked_extensions'] = [ext.strip() for ext in blocked_input.split(',') if ext.strip()]
    
    print(f"{Colors.SUCCESS}✓ Security options updated{Colors.END}")
    save_config()
    input(f"\n{Colors.MUTED}Press Enter to continue...{Colors.END}")

def configure_rate_limiting():
    """Configure rate limiting and bandwidth settings"""
    print(f"\n{Colors.ACCENT}╭─ Rate Limiting & Bandwidth{Colors.END}")
    
    print(f"{Colors.INFO}Current Settings:{Colors.END}")
    print(f"{Colors.INFO}├─{Colors.END} Download Rate Limit: {CONFIG['download_rate_limit_kbps']} KB/s (0 = unlimited)")
    print(f"{Colors.INFO}├─{Colors.END} Upload Rate Limit: {CONFIG['upload_rate_limit_kbps']} KB/s (0 = unlimited)")
    print(f"{Colors.INFO}╰─{Colors.END} Bandwidth Limit: {CONFIG['bandwidth_limit']} KB/s (0 = unlimited)")
    
    print(f"\n1. Download Rate Limit (KB/s)")
    download_limit = input(f"   New limit (0 for unlimited) [{CONFIG['download_rate_limit_kbps']}]: ")
    if download_limit.isdigit():
        CONFIG['download_rate_limit_kbps'] = int(download_limit)
    
    print(f"\n2. Upload Rate Limit (KB/s)")
    upload_limit = input(f"   New limit (0 for unlimited) [{CONFIG['upload_rate_limit_kbps']}]: ")
    if upload_limit.isdigit():
        CONFIG['upload_rate_limit_kbps'] = int(upload_limit)
    
    print(f"\n3. Overall Bandwidth Limit (KB/s)")
    bandwidth_limit = input(f"   New limit (0 for unlimited) [{CONFIG['bandwidth_limit']}]: ")
    if bandwidth_limit.isdigit():
        CONFIG['bandwidth_limit'] = int(bandwidth_limit)
    
    print(f"\n4. Quick Presets")
    print(f"   1. Unlimited (default)")
    print(f"   2. Conservative (1000 KB/s)")
    print(f"   3. Limited (500 KB/s)")
    print(f"   4. Minimal (100 KB/s)")
    
    preset = input(f"   Select preset (1-4, Enter to skip): ")
    presets = {
        '1': {'download': 0, 'upload': 0, 'bandwidth': 0},
        '2': {'download': 1000, 'upload': 500, 'bandwidth': 1000},
        '3': {'download': 500, 'upload': 250, 'bandwidth': 500},
        '4': {'download': 100, 'upload': 50, 'bandwidth': 100}
    }
    
    if preset in presets:
        CONFIG['download_rate_limit_kbps'] = presets[preset]['download']
        CONFIG['upload_rate_limit_kbps'] = presets[preset]['upload']
        CONFIG['bandwidth_limit'] = presets[preset]['bandwidth']
        print(f"{Colors.SUCCESS}✓ Applied {['', 'unlimited', 'conservative', 'limited', 'minimal'][int(preset)]} preset{Colors.END}")
    
    print(f"{Colors.SUCCESS}✓ Rate limiting updated{Colors.END}")
    save_config()
    input(f"\n{Colors.MUTED}Press Enter to continue...{Colors.END}")

def configure_file_management():
    """Configure file management settings"""
    print(f"\n{Colors.ACCENT}╭─ File Management{Colors.END}")
    
    print(f"{Colors.INFO}Current Settings:{Colors.END}")
    print(f"{Colors.INFO}├─{Colors.END} Auto Cleanup: {CONFIG['auto_cleanup']}")
    print(f"{Colors.INFO}├─{Colors.END} Check Disk Space: {CONFIG['check_disk_space']}")
    print(f"{Colors.INFO}├─{Colors.END} Min Disk Space: {CONFIG['min_disk_space_mb']} MB")
    print(f"{Colors.INFO}╰─{Colors.END} Auto Extract: {CONFIG['auto_extract']}")
    
    print(f"\n1. Auto Cleanup Temporary Files")
    cleanup = input(f"   Enable? (y/n) [{'y' if CONFIG['auto_cleanup'] else 'n'}]: ").lower()
    if cleanup in ['y', 'n']:
        CONFIG['auto_cleanup'] = cleanup == 'y'
    
    print(f"\n2. Check Available Disk Space")
    check_disk = input(f"   Enable? (y/n) [{'y' if CONFIG['check_disk_space'] else 'n'}]: ").lower()
    if check_disk in ['y', 'n']:
        CONFIG['check_disk_space'] = check_disk == 'y'
    
    if CONFIG['check_disk_space']:
        print(f"\n3. Minimum Disk Space Required (MB)")
        min_space = input(f"   New value [{CONFIG['min_disk_space_mb']}]: ")
        if min_space.isdigit():
            CONFIG['min_disk_space_mb'] = max(10, int(min_space))
    
    print(f"\n4. Auto Extract Archives")
    auto_extract = input(f"   Enable automatic extraction? (y/n) [{'y' if CONFIG['auto_extract'] else 'n'}]: ").lower()
    if auto_extract in ['y', 'n']:
        CONFIG['auto_extract'] = auto_extract == 'y'
    
    print(f"\n5. File Organization")
    organize = input(f"   Create organized folder structure? (y/n): ").lower() == 'y'
    if organize:
        base_dir = CONFIG['download_dir']
        folders = ['Audio', 'Video', 'Documents', 'Archives', 'Images', 'Software', 'Other']
        for folder in folders:
            folder_path = os.path.join(base_dir, folder)
            os.makedirs(folder_path, exist_ok=True)
        print(f"{Colors.SUCCESS}✓ Created organized folder structure{Colors.END}")
    
    print(f"{Colors.SUCCESS}✓ File management updated{Colors.END}")
    save_config()
    input(f"\n{Colors.MUTED}Press Enter to continue...{Colors.END}")

def configure_system_resources():
    """Configure system resource usage"""
    print(f"\n{Colors.ACCENT}╭─ System Resources{Colors.END}")
    
    # Get system info for recommendations
    try:
        import psutil
        cpu_count = psutil.cpu_count()
        memory_gb = psutil.virtual_memory().total / (1024**3)
        disk_free_gb = psutil.disk_usage('.').free / (1024**3)
        
        print(f"{Colors.INFO}System Information:{Colors.END}")
        print(f"{Colors.INFO}├─{Colors.END} CPU Cores: {cpu_count}")
        print(f"{Colors.INFO}├─{Colors.END} Memory: {memory_gb:.1f} GB")
        print(f"{Colors.INFO}╰─{Colors.END} Free Disk: {disk_free_gb:.1f} GB")
        
    except ImportError:
        cpu_count = os.cpu_count() or 4
        print(f"{Colors.INFO}CPU Cores: {cpu_count} (install psutil for detailed info){Colors.END}")
    
    print(f"\n{Colors.INFO}Current Settings:{Colors.END}")
    print(f"{Colors.INFO}├─{Colors.END} Max Threads: {CONFIG['max_threads']}")
    print(f"{Colors.INFO}├─{Colors.END} Chunk Size: {CONFIG['chunk_size']} bytes")
    print(f"{Colors.INFO}├─{Colors.END} Connection Pool: {CONFIG['connection_pool_size']}")
    print(f"{Colors.INFO}╰─{Colors.END} Concurrent Downloads: {CONFIG['concurrent_downloads']}")
    
    print(f"\n1. Optimize for System")
    optimize = input(f"   Auto-optimize settings for this system? (y/n): ").lower() == 'y'
    if optimize:
        # Conservative optimization based on system resources
        CONFIG['max_threads'] = min(16, max(4, cpu_count * 2))
        CONFIG['chunk_size'] = 1048576  # 1MB chunks
        CONFIG['connection_pool_size'] = min(20, max(5, cpu_count))
        CONFIG['concurrent_downloads'] = min(6, max(2, cpu_count // 2))
        print(f"{Colors.SUCCESS}✓ Settings optimized for system{Colors.END}")
    else:
        print(f"\n2. Manual Configuration")
        
        threads = input(f"   Max threads (1-32) [{CONFIG['max_threads']}]: ")
        if threads.isdigit():
            CONFIG['max_threads'] = max(1, min(32, int(threads)))
        
        chunk_size = input(f"   Chunk size in KB (64-8192) [{CONFIG['chunk_size']//1024}]: ")
        if chunk_size.isdigit():
            CONFIG['chunk_size'] = max(65536, min(8388608, int(chunk_size) * 1024))
        
        pool_size = input(f"   Connection pool size (1-50) [{CONFIG['connection_pool_size']}]: ")
        if pool_size.isdigit():
            CONFIG['connection_pool_size'] = max(1, min(50, int(pool_size)))
        
        concurrent = input(f"   Concurrent downloads (1-10) [{CONFIG['concurrent_downloads']}]: ")
        if concurrent.isdigit():
            CONFIG['concurrent_downloads'] = max(1, min(10, int(concurrent)))
    
    print(f"{Colors.SUCCESS}✓ System resources configured{Colors.END}")
    save_config()
    input(f"\n{Colors.MUTED}Press Enter to continue...{Colors.END}")

def configure_logging():
    """Configure logging and history settings"""
    print(f"\n{Colors.ACCENT}╭─ Logging & History{Colors.END}")
    
    print(f"{Colors.INFO}Current Settings:{Colors.END}")
    print(f"{Colors.INFO}├─{Colors.END} Download History: {CONFIG['download_history']}")
    print(f"{Colors.INFO}├─{Colors.END} Log Level: {CONFIG['log_level']}")
    print(f"{Colors.INFO}├─{Colors.END} Log File: {CONFIG['log_file']}")
    print(f"{Colors.INFO}╰─{Colors.END} Notification Sound: {CONFIG['notification_sound']}")
    
    print(f"\n1. Download History")
    history = input(f"   Enable download history? (y/n) [{'y' if CONFIG['download_history'] else 'n'}]: ").lower()
    if history in ['y', 'n']:
        CONFIG['download_history'] = history == 'y'
    
    print(f"\n2. Log Level")
    print(f"   1. DEBUG (verbose)")
    print(f"   2. INFO (normal)")
    print(f"   3. WARNING (errors only)")
    print(f"   4. ERROR (critical only)")
    
    log_choice = input(f"   Select log level (1-4): ")
    log_levels = {'1': 'DEBUG', '2': 'INFO', '3': 'WARNING', '4': 'ERROR'}
    if log_choice in log_levels:
        CONFIG['log_level'] = log_levels[log_choice]
    
    print(f"\n3. Log File Location")
    new_log = input(f"   New log file path [{CONFIG['log_file']}]: ")
    if new_log.strip():
        CONFIG['log_file'] = os.path.expanduser(new_log.strip())
    
    print(f"\n4. Notification Sound")
    sound = input(f"   Enable notification sounds? (y/n) [{'y' if CONFIG['notification_sound'] else 'n'}]: ").lower()
    if sound in ['y', 'n']:
        CONFIG['notification_sound'] = sound == 'y'
    
    print(f"\n5. Clear History")
    clear_history = input(f"   Clear download history? (y/n): ").lower() == 'y'
    if clear_history:
        global DOWNLOAD_HISTORY
        DOWNLOAD_HISTORY.clear()
        print(f"{Colors.SUCCESS}✓ Download history cleared{Colors.END}")
    
    print(f"{Colors.SUCCESS}✓ Logging configuration updated{Colors.END}")
    save_config()
    input(f"\n{Colors.MUTED}Press Enter to continue...{Colors.END}")

def import_export_config():
    """Import/Export configuration"""
    print(f"\n{Colors.ACCENT}╭─ Configuration Import/Export{Colors.END}")
    
    print(f"{Colors.ACCENT}├─{Colors.END} 1. Export current configuration")
    print(f"{Colors.ACCENT}├─{Colors.END} 2. Import configuration from file")
    print(f"{Colors.ACCENT}├─{Colors.END} 3. Export download history")
    print(f"{Colors.ACCENT}╰─{Colors.END} 4. Import download history")
    
    choice = input(f"\n{Colors.BOLD}Select option (1-4): {Colors.END}")
    
    if choice == '1':
        export_path = input(f"Export path [./xternal_config.json]: ") or "./xternal_config.json"
        try:
            with open(export_path, 'w') as f:
                json.dump(CONFIG, f, indent=2)
            print(f"{Colors.SUCCESS}✓ Configuration exported to {export_path}{Colors.END}")
        except Exception as e:
            print(f"{Colors.ERROR}✗ Export failed: {e}{Colors.END}")
    
    elif choice == '2':
        import_path = input(f"Import path: ")
        if os.path.exists(import_path):
            try:
                with open(import_path, 'r') as f:
                    imported_config = json.load(f)
                
                # Update CONFIG with imported values
                for key, value in imported_config.items():
                    if key in CONFIG:
                        CONFIG[key] = value
                
                save_config()
                print(f"{Colors.SUCCESS}✓ Configuration imported from {import_path}{Colors.END}")
            except Exception as e:
                print(f"{Colors.ERROR}✗ Import failed: {e}{Colors.END}")
        else:
            print(f"{Colors.ERROR}✗ File not found{Colors.END}")
    
    elif choice == '3':
        export_path = input(f"Export path [./download_history.json]: ") or "./download_history.json"
        try:
            with open(export_path, 'w') as f:
                json.dump(DOWNLOAD_HISTORY, f, indent=2)
            print(f"{Colors.SUCCESS}✓ Download history exported to {export_path}{Colors.END}")
        except Exception as e:
            print(f"{Colors.ERROR}✗ Export failed: {e}{Colors.END}")
    
    elif choice == '4':
        import_path = input(f"Import path: ")
        if os.path.exists(import_path):
            try:
                with open(import_path, 'r') as f:
                    DOWNLOAD_HISTORY.clear()
                    DOWNLOAD_HISTORY.extend(json.load(f))
                print(f"{Colors.SUCCESS}✓ Download history imported from {import_path}{Colors.END}")
            except Exception as e:
                print(f"{Colors.ERROR}✗ Import failed: {e}{Colors.END}")
        else:
            print(f"{Colors.ERROR}✗ File not found{Colors.END}")
    
    input(f"\n{Colors.MUTED}Press Enter to continue...{Colors.END}")

def reset_to_defaults():
    """Reset configuration to defaults"""
    print(f"\n{Colors.WARNING}╭─ Reset Configuration{Colors.END}")
    print(f"{Colors.WARNING}├─{Colors.END} This will reset ALL settings to defaults")
    print(f"{Colors.WARNING}├─{Colors.END} Download history will be preserved")
    print(f"{Colors.WARNING}╰─{Colors.END} This action cannot be undone")
    
    confirm = input(f"\n{Colors.ACCENT}Are you sure? Type 'RESET' to confirm: {Colors.END}")
    if confirm == 'RESET':
        global CONFIG
        CONFIG = DEFAULT_CONFIG.copy()
        save_config()
        print(f"{Colors.SUCCESS}✓ Configuration reset to defaults{Colors.END}")
    else:
        print(f"{Colors.INFO}Reset cancelled{Colors.END}")
    
    input(f"\n{Colors.MUTED}Press Enter to continue...{Colors.END}")

def create_parser():
    """Create argument parser for the XTERNAL module."""
    parser = argparse.ArgumentParser(
        description=__description__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        add_help=False  # We'll handle help manually
    )
    
    parser.add_argument(
        "--interactive", 
        action="store_true", 
        help="Launch interactive downloader interface (default)"
    )
    
    parser.add_argument(
        "--url",
        help="Download a single URL"
    )
    
    parser.add_argument(
        "--batch",
        help="Batch download from file"
    )
    
    parser.add_argument(
        "--help", 
        action="store_true",
        help="Show help message"
    )
    
    return parser

def xternal_main_menu():
    """Original XTERNAL main menu functionality"""
    # Load configuration at startup
    load_config()
    
    try:
        while True:
            print_header()
            
            print(f"{Colors.PRIMARY}╭─ Main Menu{Colors.END}")
            print(f"{Colors.PRIMARY}├─{Colors.END} Download Options")
            print(f"{Colors.PRIMARY}│{Colors.END}  {Colors.SUCCESS}1.{Colors.END} HTTP/HTTPS Download")
            print(f"{Colors.PRIMARY}│{Colors.END}  {Colors.SUCCESS}2.{Colors.END} FTP/FTPS Download")
            unavailable_text = f" {Colors.ERROR}(Unavailable){Colors.END}" if not YTDLP_AVAILABLE else ""
            print(f"{Colors.PRIMARY}│{Colors.END}  {Colors.SUCCESS}3.{Colors.END} YouTube/Video Download{unavailable_text}")
            print(f"{Colors.PRIMARY}│{Colors.END}  {Colors.SUCCESS}4.{Colors.END} Batch Download Manager")
            print(f"{Colors.PRIMARY}├─{Colors.END} System Management")
            print(f"{Colors.PRIMARY}│{Colors.END}  {Colors.ACCENT}5.{Colors.END} Advanced Settings")
            print(f"{Colors.PRIMARY}│{Colors.END}  {Colors.ACCENT}6.{Colors.END} Network Diagnostics")
            print(f"{Colors.PRIMARY}│{Colors.END}  {Colors.ACCENT}7.{Colors.END} Download History")
            print(f"{Colors.PRIMARY}╰─{Colors.END}  {Colors.WARNING}8.{Colors.END} Return to CrossFire")
            
            choice = input(f"\n{Colors.BOLD}▶ Select option (1-8): {Colors.END}")
            
            if choice == '1':
                url = input(f"\n{Colors.PRIMARY}Enter download URL: {Colors.END}")
                if url:
                    professional_download(url)
                    input(f"\n{Colors.MUTED}Press Enter to continue...{Colors.END}")
            
            elif choice == '2':
                advanced_ftp_download()
                input(f"\n{Colors.MUTED}Press Enter to continue...{Colors.END}")
            
            elif choice == '3':
                if YTDLP_AVAILABLE:
                    youtube_download()
                else:
                    print(f"{Colors.ERROR}✗ yt-dlp not available{Colors.END}")
                    print(f"{Colors.INFO}Install with: pip install yt-dlp{Colors.END}")
                    
                    # Offer to install yt-dlp
                    install = input(f"{Colors.ACCENT}Install yt-dlp now? (y/N): {Colors.END}").lower()
                    if install == 'y':
                        try:
                            print(f"{Colors.INFO}▶ Installing yt-dlp...{Colors.END}")
                            subprocess.check_call([sys.executable, '-m', 'pip', 'install', 'yt-dlp'])
                            print(f"{Colors.SUCCESS}✓ yt-dlp installed successfully! Please restart XTERNAL.{Colors.END}")
                        except subprocess.CalledProcessError as e:
                            print(f"{Colors.ERROR}✗ Installation failed: {str(e)}{Colors.END}")
                
                input(f"\n{Colors.MUTED}Press Enter to continue...{Colors.END}")
            
            elif choice == '4':
                batch_download_manager()
                input(f"\n{Colors.MUTED}Press Enter to continue...{Colors.END}")
            
            elif choice == '5':
                advanced_settings_menu()
            
            elif choice == '6':
                print(f"\n{Colors.INFO}╭─ Network Diagnostics{Colors.END}")
                loading_animation("Running network diagnostics", duration=1)
                
                system_info = get_system_info()
                network_info = check_network_advanced()
                
                print(f"\n{Colors.INFO}├─ System Information{Colors.END}")
                for key, value in system_info.items():
                    if key != 'error':
                        print(f"{Colors.INFO}│{Colors.END}  {key.replace('_', ' ').title()}: {value}")
                    else:
                        print(f"{Colors.WARNING}│{Colors.END}  {value}")
                
                print(f"\n{Colors.INFO}├─ Network Information{Colors.END}")
                for key, value in network_info.items():
                    if key != 'error':
                        display_key = key.replace('_', ' ').title()
                        color = Colors.SUCCESS if key == 'vpn_detected' and value else Colors.END
                        print(f"{Colors.INFO}│{Colors.END}  {display_key}: {color}{value}{Colors.END}")
                
                print(f"\n{Colors.INFO}╰─ Performance Metrics{Colors.END}")
                print(f"{Colors.INFO} {Colors.END}  Session Downloads: {STATS['total_downloads']}")
                print(f"{Colors.INFO} {Colors.END}  Total Data: {STATS['total_bytes'] / 1024 / 1024:.1f} MB")
                print(f"{Colors.INFO} {Colors.END}  Average Speed: {STATS['average_speed']:.1f} MB/s")
                print(f"{Colors.INFO} {Colors.END}  Failed Downloads: {STATS['failed_downloads']}")
                
                input(f"\n{Colors.MUTED}Press Enter to continue...{Colors.END}")
            
            elif choice == '7':
                if not DOWNLOAD_HISTORY:
                    print(f"{Colors.WARNING}⚠ No download history available{Colors.END}")
                else:
                    print(f"\n{Colors.INFO}╭─ Download History ({len(DOWNLOAD_HISTORY)} items){Colors.END}")
                    for i, item in enumerate(DOWNLOAD_HISTORY[-10:], 1):
                        timestamp = datetime.fromisoformat(item['timestamp']).strftime("%m/%d %H:%M")
                        size_mb = item['size'] / 1024 / 1024
                        print(f"{Colors.INFO}├─{Colors.END} [{i}] {item['filename'][:40]}")
                        print(f"{Colors.INFO}│{Colors.END}     Size: {size_mb:.1f}MB | Speed: {item['speed']:.1f}MB/s | {timestamp}")
                    print(f"{Colors.INFO}╰─{Colors.END} Showing last 10 downloads")
                
                input(f"\n{Colors.MUTED}Press Enter to continue...{Colors.END}")
            
            elif choice == '8':
                print(f"{Colors.SUCCESS}✓ Returning to CrossFire...{Colors.END}")
                return 0
            
            else:
                print(f"{Colors.ERROR}✗ Invalid option. Please select 1-8.{Colors.END}")
                time.sleep(1)
                
    except KeyboardInterrupt:
        print(f"\n\n{Colors.WARNING}▶ XTERNAL interrupted by user{Colors.END}")
        return 1
    except Exception as e:
        print(f"\n{Colors.ERROR}✗ XTERNAL error: {str(e)}{Colors.END}")
        return 1

def main(args: List[str]) -> int:
    """
    Main entry point for the XTERNAL module when called from CrossFire.
    
    Args:
        args: Command line arguments passed from CrossFire
        
    Returns:
        int: Exit code (0 for success, non-zero for error)
    """
    try:
        # Load configuration at startup
        load_config()
        
        parser = create_parser()
        
        # If no args provided, default to interactive mode
        if not args:
            args = ["--interactive"]
        
        # Handle help manually since we disabled argparse's help
        if "--help" in args or "-h" in args:
            print(__help__)
            return 0
        
        try:
            parsed_args = parser.parse_args(args)
        except SystemExit as e:
            # argparse calls sys.exit(), catch it and return the code
            return e.code if e.code else 1
        
        # Handle different execution modes
        if parsed_args.url:
            print(f"{Colors.INFO}XTERNAL - Single URL Download Mode{Colors.END}")
            success = professional_download(parsed_args.url)
            return 0 if success else 1
        
        elif parsed_args.batch:
            print(f"{Colors.INFO}XTERNAL - Batch Download Mode{Colors.END}")
            if not os.path.exists(parsed_args.batch):
                print(f"{Colors.ERROR}✗ Batch file not found: {parsed_args.batch}{Colors.END}")
                return 1
            
            try:
                with open(parsed_args.batch, 'r') as f:
                    urls = [line.strip() for line in f if line.strip()]
                
                if not urls:
                    print(f"{Colors.WARNING}⚠ No URLs found in batch file{Colors.END}")
                    return 1
                
                successful = 0
                for i, url in enumerate(urls, 1):
                    print(f"\n{Colors.ACCENT}[{i}/{len(urls)}] Processing: {url[:60]}...{Colors.END}")
                    if professional_download(url, show_progress=False):
                        successful += 1
                
                print(f"\n{Colors.SUCCESS}✓ Batch complete: {successful}/{len(urls)} successful{Colors.END}")
                return 0 if successful == len(urls) else 1
                
            except Exception as e:
                print(f"{Colors.ERROR}✗ Batch processing error: {e}{Colors.END}")
                return 1
        
        else:
            # Default to interactive mode
            print(f"{Colors.SUCCESS}✓ XTERNAL Download Manager Loaded{Colors.END}")
            return xternal_main_menu()
    
    except Exception as e:
        print(f"{Colors.ERROR}✗ XTERNAL module error: {str(e)}{Colors.END}")
        return 1


# Allow module to be run standalone for testing
if __name__ == "__main__":
    import sys
    exit_code = main(sys.argv[1:])
    sys.exit(exit_code)