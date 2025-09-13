import sys
import time
import shutil
import threading

from .logger import LOG


class ProgressBar:
    def __init__(self, total, description, unit):
        self.total = total
        self.description = description
        self.unit = unit
        self.current = 0
        self.start_time = time.time()
        self.lock = threading.Lock()
        self.bar_length = 50
        self.terminal_width = shutil.get_terminal_size((80, 20)).columns

    def update(self, step=1):
        with self.lock:
            self.current = min(self.current + step, self.total)
            self._draw_bar()

    def _draw_bar(self):
        if LOG.json_mode or not sys.stdout.isatty():
            return
        
        progress = self.current / self.total if self.total > 0 else 0
        percent = progress * 100
        filled_length = int(self.bar_length * progress)
        bar = '█' * filled_length + '-' * (self.bar_length - filled_length)
        
        elapsed = time.time() - self.start_time
        eta_str = "N/A"
        speed_str = ""
        
        if progress > 0 and elapsed > 0:
            remaining = (elapsed / progress) - elapsed if progress < 1 else 0
            if remaining > 3600:
                eta_str = f"{remaining/3600:.1f}h"
            elif remaining > 60:
                eta_str = f"{remaining/60:.1f}m"
            else:
                eta_str = f"{remaining:.1f}s"
            
            # Calculate speed
            if self.unit == "B" and elapsed > 0:  # Bytes
                speed = self.current / elapsed
                if speed > 1024**2:
                    speed_str = f" @ {speed/1024**2:.1f} MB/s"
                elif speed > 1024:
                    speed_str = f" @ {speed/1024:.1f} KB/s"
                else:
                    speed_str = f" @ {speed:.0f} B/s"
            
        full_msg = f"{self.description}: |{bar}| {percent:.1f}% ({self.current}/{self.total} {self.unit}){speed_str} - ETA: {eta_str}"
        
        if len(full_msg) > self.terminal_width:
            full_msg = full_msg[:self.terminal_width - 4] + "..."
        
        sys.stdout.write(f"\r{full_msg}")
        sys.stdout.flush()

    def finish(self):
        if not LOG.json_mode and sys.stdout.isatty():
            sys.stdout.write("\n")
            sys.stdout.flush()