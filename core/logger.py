import sys


class Colors:
    """ANSI color codes for console output."""
    INFO = "\033[94m"
    SUCCESS = "\033[92m"
    WARNING = "\033[93m"
    ERROR = "\033[91m"
    MUTED = "\033[90m"
    BOLD = "\033[1m"
    CYAN = "\033[96m"
    RESET = "\033[0m"


class Logger:
    def __init__(self):
        self.quiet = False
        self.verbose = False
        self.json_mode = False

    def cprint(self, text, color="INFO"):
        """Print colored text to console."""
        if self.json_mode:
            return
        if self.quiet and color in ["INFO", "WARNING"]:
            return
        if self.quiet and color in ["SUCCESS"]:
            return
        if not sys.stdout.isatty():
            sys.stdout.write(f"{text}\n")
            return
        
        color_code = getattr(Colors, color.upper(), Colors.INFO)
        print(f"{color_code}{text}{Colors.RESET}")


# Global logger instance
LOG = Logger()
cprint = LOG.cprint

# Update config with logger instance
import core.config
core.config.LOG = LOG