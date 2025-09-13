import stat
import sys
import subprocess
import os
import shutil
from pathlib import Path
from typing import Optional

from core.config import OS_NAME
from core.logger import cprint

def _add_to_windows_path(directory: str) -> bool:
    """Safely add directory to Windows PATH for current user and current session."""
    try:
        import winreg
        
        # Open the user environment key
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            "Environment",
            0,
            winreg.KEY_READ | winreg.KEY_WRITE
        )

        try:
            current_path, _ = winreg.QueryValueEx(key, "PATH")
        except FileNotFoundError:
            current_path = ""
        
        winreg.CloseKey(key)

        # Clean and normalize paths
        paths = [p.strip() for p in current_path.split(";") if p.strip()]
        directory_normalized = os.path.normpath(directory)
        
        # Check if directory is already in PATH (case-insensitive)
        path_exists = any(os.path.normpath(p).lower() == directory_normalized.lower() for p in paths)
        
        if not path_exists:
            paths.append(directory)
            new_path = ";".join(paths)
            
            # Update registry
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                "Environment",
                0,
                winreg.KEY_WRITE
            )
            
            try:
                winreg.SetValueEx(key, "PATH", 0, winreg.REG_EXPAND_SZ, new_path)
                cprint(f"Added to Windows registry PATH: {directory}", "SUCCESS")
            finally:
                winreg.CloseKey(key)
            
            # Update current session PATH
            os.environ["PATH"] = new_path + ";" + os.environ.get("PATH", "")
            
            # Notify system of environment change (best-effort)
            try:
                import ctypes
                HWND_BROADCAST = 0xFFFF
                WM_SETTINGCHANGE = 0x001A
                
                ctypes.windll.user32.SendMessageW(
                    HWND_BROADCAST,
                    WM_SETTINGCHANGE,
                    0,
                    "Environment"
                )
                cprint("System notified of PATH change", "SUCCESS")
            except Exception as e:
                cprint(f"Could not notify system of PATH change: {e}", "WARNING")
                
            # Provide instructions for immediate access (THIS IS THE CORRECTED PART)
            cprint("", "INFO")
            cprint("PATH updated! To use the 'crossfire' command immediately:", "INFO")
            cprint("  Option 1: Restart your terminal/PowerShell.", "INFO") 
            cprint("  Option 2: Copy and paste the command below into your current session:", "INFO")
            cprint(f"    $env:PATH += ';{directory}'", "INFO")
                
        else:
            cprint("Directory already in Windows PATH.", "INFO")
            
        return True
        
    except ImportError:
        cprint("winreg module not available (not on Windows?)", "ERROR")
        return False
    except PermissionError:
        cprint("Permission denied - try running as administrator", "ERROR")
        return False
    except Exception as e:
        cprint(f"Failed to add to Windows PATH: {e}", "ERROR")
        return False

def install_launcher(target_dir: Optional[str] = None) -> Optional[Path]:
    """Install a cross-platform launcher for the application, supporting multiple terminals on Linux."""
    cprint("Installing CrossFire launcher...", "INFO")

    try:
        if target_dir:
            install_dir = Path(target_dir).expanduser().resolve()
        elif OS_NAME == "Windows":
            install_dir = Path.home() / "AppData" / "Local" / "CrossFire"
        else:
            install_dir = Path.home() / ".local" / "bin"

        install_dir.mkdir(parents=True, exist_ok=True)

        main_script = Path(__file__).parent.parent / "main.py"
        if not main_script.exists():
            cprint("Error: main.py not found, cannot create launcher.", "ERROR")
            return None

        if OS_NAME == "Windows":
            launcher_path = install_dir / "crossfire.bat"
            if launcher_path.exists():
                launcher_path.unlink()
                
            python_path = sys.executable
            main_script_str = str(main_script).replace('\\', '\\\\')
            
            batch_content = f'''@echo off
REM CrossFire Launcher
"{python_path}" "{main_script_str}" %*
if errorlevel 1 (
    echo.
    echo Error running CrossFire.
)
'''
            launcher_path.write_text(batch_content, encoding='utf-8')
            cprint(f"Windows launcher created at {launcher_path}", "SUCCESS")

        else:
            # Detect popular Linux terminals
            TERMINALS = [
                "gnome-terminal", "guake", "konsole", "terminator", "kitty",
                "terminology", "hyper", "lxterminal", "urxvt", "tilda",
                "alacritty", "eterm", "lilyterm", "sakura", "xfce4-terminal",
                "xterm", "yakuake", "cool-retro-term"
            ]

            found_terminals = [term for term in TERMINALS if shutil.which(term)]
            if not found_terminals:
                cprint("No popular terminals detected; using default shell execution.", "WARNING")

            launcher_path = install_dir / "crossfire"
            if launcher_path.exists():
                launcher_path.unlink()

            # Create a launcher script that tries to open in the first available terminal
            terminal_cmds = []
            for term in found_terminals:
                if term in ["gnome-terminal", "xfce4-terminal", "guake", "terminator"]:
                    terminal_cmds.append(f'{term} -- bash -c "python3 {main_script}; exec bash"')
                elif term in ["konsole"]:
                    terminal_cmds.append(f'{term} -e bash -c "python3 {main_script}; exec bash"')
                elif term in ["alacritty", "kitty", "lxterminal", "urxvt", "sakura", "lilyterm", "cool-retro-term", "eterm", "terminology"]:
                    terminal_cmds.append(f'{term} -e python3 {main_script}')

            with open(launcher_path, "w") as f:
                f.write("#!/bin/bash\n")
                f.write("# Auto-detect terminal and run CrossFire\n")
                f.write("CMD_FOUND=0\n")
                for cmd in terminal_cmds:
                    f.write(f'if command -v {cmd.split()[0]} >/dev/null 2>&1; then\n')
                    f.write(f'    {cmd} &\n')
                    f.write(f'    CMD_FOUND=1\n')
                    f.write(f'    break\n')
                    f.write(f'fi\n')
                f.write('if [ $CMD_FOUND -eq 0 ]; then\n')
                f.write(f'    python3 {main_script}\n')
                f.write('fi\n')

            launcher_path.chmod(launcher_path.stat().st_mode | stat.S_IEXEC)
            cprint(f"Linux launcher created at {launcher_path}, will use the first available terminal.", "SUCCESS")

        return launcher_path

    except PermissionError:
        cprint("Permission denied while creating launcher. Try running as administrator or using sudo.", "ERROR")
        return None
    except Exception as e:
        cprint(f"Failed to install launcher: {e}", "ERROR")
        return None

def add_to_path_safely():
    """Add the launcher directory to PATH if needed."""
    launcher_path = install_launcher()
    if not launcher_path:
        return

    if OS_NAME == "Windows":
        if not _add_to_windows_path(str(launcher_path.parent)):
            cprint(f"Add '{launcher_path.parent}' to PATH manually for permanent access.", "INFO")
            cprint("To add manually: System Properties > Environment Variables > User Variables > PATH", "INFO")
    else:
        shell = os.environ.get("SHELL", "/bin/bash")
        profile_file = None
        path_line = None

        if "bash" in shell:
            profile_file = Path.home() / ".bashrc"
            path_line = f'export PATH="{launcher_path.parent}:$PATH"'
        elif "zsh" in shell:
            profile_file = Path.home() / ".zshrc"
            path_line = f'export PATH="{launcher_path.parent}:$PATH"'
        elif "fish" in shell:
            profile_file = Path.home() / ".config" / "fish" / "config.fish"
            path_line = f'set -gx PATH {launcher_path.parent} $PATH'
        elif "tcsh" in shell or "csh" in shell:
            profile_file = Path.home() / ".cshrc"
            path_line = f'setenv PATH {launcher_path.parent}:$PATH'
        elif "ksh" in shell:
            profile_file = Path.home() / ".kshrc"
            path_line = f'export PATH="{launcher_path.parent}:$PATH"'

        if profile_file and path_line:
            try:
                if profile_file.exists():
                    with open(profile_file, "r") as f:
                        content = f.read()
                    if path_line not in content:
                        with open(profile_file, "a") as fa:
                            fa.write(f"\n# Added by CrossFire\n{path_line}\n")
                        cprint(f"Added launcher to PATH in {profile_file}", "SUCCESS")
                else:
                    cprint(f"Shell profile {profile_file} doesn't exist, creating it...", "INFO")
                    profile_file.parent.mkdir(parents=True, exist_ok=True)
                    with open(profile_file, "w") as f:
                        f.write(f"# Created by CrossFire\n{path_line}\n")
                    cprint(f"Created {profile_file} with PATH entry", "SUCCESS")
            except Exception as e:
                cprint(f"Failed to modify shell profile for PATH: {e}", "WARNING")
        else:
            cprint(f"Please add '{launcher_path.parent}' to your PATH manually.", "INFO")