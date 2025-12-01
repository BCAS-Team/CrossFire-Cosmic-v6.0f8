<img src="https://raw.githubusercontent.com/BCAS-Team/CrossFire-Cosmic-v6.0f8/main/logo/Logo1.png" alt="CrossFire Logo" width="200"/>

# CrossFire

**Universal Package Manager CLI with Enhanced Performance & Module System**

CrossFire is a production-ready universal package manager that provides a unified interface for installing, managing, and searching packages across multiple package managers including pip, npm, brew, apt, dnf, pacman, and more.

## Features

### Core Features
- **Universal Package Management**: Single interface for 15+ package managers
- **Enhanced Parallel Search**: 3-5x faster search across PyPI, NPM, and Homebrew
- **Batch Operations**: Install/remove multiple packages concurrently
- **Package Tracking**: SQLite database tracks all installations
- **Cross-Platform**: Windows, macOS, Linux support
- **Interactive Shell**: REPL mode for streamlined workflow

### Advanced Features
- **Dynamic Module System**: Extensible architecture for custom functionality
- **Intelligent Caching**: Reduces redundant network requests
- **Concurrent Processing**: Multi-threaded operations with configurable workers
- **Health Monitoring**: Comprehensive system diagnostics
- **Network Testing**: Built-in speed and latency testing
- **Deep Cleanup**: Advanced cache and temporary file management

## Quick Start

### Installation

```bash
# Clone and setup
git clone <repository-url>
cd crossfire
python main.py --setup

# Now available globally
crossfire --help
```

### Basic Usage

```bash
# Search packages (enhanced parallel search)
crossfire -s "python library"

# Install packages
crossfire -i numpy
crossfire -i express --manager npm

# Batch operations
crossfire --install-batch "numpy,requests,flask"
crossfire --remove-batch "old-package1,old-package2"

# List package managers
crossfire --list-managers

# Install missing package managers
crossfire --install-manager brew
```

## Package Manager Support

| Manager | Platform | Status |
|---------|----------|--------|
| pip | All | ✅ Full Support |
| npm | All | ✅ Full Support |
| brew | macOS/Linux | ✅ Full Support |
| apt | Debian/Ubuntu | ✅ Full Support |
| dnf | Fedora | ✅ Full Support |
| yum | RHEL/CentOS | ✅ Full Support |
| pacman | Arch Linux | ✅ Full Support |
| zypper | openSUSE | ✅ Full Support |
| apk | Alpine Linux | ✅ Full Support |
| choco | Windows | ✅ Full Support |
| winget | Windows | ✅ Full Support |
| snap | Linux | ✅ Full Support |
| flatpak | Linux | ✅ Full Support |

## Module System

CrossFire features a dynamic module system for extensibility:

### Creating Modules

```bash
mkdir -p modules/MyModule
```

Create `modules/MyModule/main.py`:

```python
#!/usr/bin/env python3

__description__ = "My custom CrossFire module"
__version__ = "1.0.0"
__author__ = "Your Name"
__commands__ = ["hello", "world"]
__help__ = """
Usage: crossfire --module MyModule [command] [args]

Commands:
  hello [name]  - Say hello
  world         - Print world info
"""

def main(args):
    """Main entry point for the module"""
    if not args:
        print("Usage: MyModule [hello|world] [args]")
        return 1
    
    command = args[0].lower()
    
    if command == "hello":
        name = args[1] if len(args) > 1 else "World"
        print(f"Hello, {name}!")
        return 0
    
    elif command == "world":
        print("World information module")
        return 0
    
    else:
        print(f"Unknown command: {command}")
        return 1
```

### Using Modules

```bash
# List available modules
crossfire --list-modules

# Get module information
crossfire --module-info MyModule

# Execute module
crossfire --module MyModule hello "CrossFire User"
```

## Advanced Usage

### Batch Operations with Configuration

```bash
# Concurrent installation with custom worker count
crossfire --install-batch "numpy,scipy,matplotlib" --max-workers 6 --fail-fast

# Install from requirements file
crossfire --install-from requirements.txt --max-workers 4

# Export package lists
crossfire --export pip --output my-pip-packages.txt
```

### System Management

```bash
# Health check
crossfire --health-check

# Update all package managers
crossfire --update-manager ALL

# Deep system cleanup
crossfire --cleanup-deep

# Show statistics
crossfire --stats
```

### Network Tools

```bash
# Speed test
crossfire --speed-test --test-duration 30

# Ping test
crossfire --ping-test

# Custom speed test URL
crossfire --speed-test --test-url "http://example.com/file.zip"
```

### Interactive Mode

```bash
# Launch interactive shell
crossfire --interactive
```

Interactive commands:
- `search <query>` - Enhanced parallel search
- `install <pkg>` - Install package
- `install-batch <pkg1,pkg2,pkg3>` - Batch install
- `list-modules` - Show available modules
- `module <name> [args]` - Execute module
- `cleanup-deep` - Deep system cleanup
- `help` - Show all commands
- `exit` - Quit

## Configuration

CrossFire stores data in `~/.crossfire/`:
- `packages.db` - SQLite database tracking installations
- `cache/` - Cached search results and downloads

### Environment Variables

- `CROSSFIRE_QUIET` - Enable quiet mode
- `CROSSFIRE_VERBOSE` - Enable verbose logging
- `CROSSFIRE_MAX_WORKERS` - Default worker count for batch operations

## JSON Output Mode

All commands support `--json` flag for machine-readable output:

```bash
crossfire -s "python" --json
crossfire --health-check --json
crossfire --list-modules --json
```

## Performance Optimizations

- **Parallel Search**: Concurrent queries to multiple repositories
- **Connection Pooling**: Reused HTTP connections
- **Intelligent Caching**: Local cache for search results
- **Batch Processing**: Multiple packages installed concurrently
- **Retry Logic**: Automatic retry with exponential backoff

## Architecture

```
crossfire/
├── main.py                 # Main entry point & module system
├── core/
│   ├── config.py          # Configuration & constants
│   ├── logger.py          # Logging utilities
│   ├── database.py        # SQLite package tracking
│   └── execution.py       # Command execution
├── managers/
│   ├── detection.py       # Package manager detection
│   └── installer.py       # Installation handlers
├── search/
│   └── engine.py          # Enhanced parallel search
├── system/
│   ├── health.py          # System diagnostics
│   ├── cleanup.py         # Cache cleanup
│   └── setup.py           # Installation setup
├── network/
│   └── testing.py         # Network speed testing
├── modules/               # Custom modules directory
│   └── ExampleModule/
│       └── main.py
└── vendor/               # Vendored dependencies
```

## Requirements

- Python 3.7+
- requests (bundled in vendor/)
- distro (bundled in vendor/)

## Platform Support

| Platform | Python | Package Managers | Status |
|----------|--------|------------------|--------|
| Ubuntu/Debian | 3.7+ | apt, pip, npm, snap, flatpak | ✅ Tested |
| Fedora | 3.7+ | dnf, pip, npm, flatpak | ✅ Tested |
| Arch Linux | 3.7+ | pacman, pip, npm | ✅ Tested |
| macOS | 3.7+ | brew, pip, npm | ✅ Tested |
| Windows 10/11 | 3.7+ | choco, winget, pip, npm | ✅ Tested |
| Alpine Linux | 3.7+ | apk, pip | ✅ Tested |

## Contributing

1. Fork the repository
2. Create feature branch: `git checkout -b feature-name`
3. Follow existing code style and patterns
4. Add tests for new functionality
5. Create modules in `modules/` directory for extensions
6. Submit pull request

### Module Development Guidelines

- Each module must have a `main(args)` function
- Use module metadata variables (`__description__`, `__version__`, etc.)
- Handle errors gracefully and return appropriate exit codes
- Follow CrossFire's logging patterns when possible
- Include comprehensive help text in `__help__`

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Version History

- **v6.0f8 (Cosmic Release)** - Module system, enhanced performance, batch operations
- **v5.x** - Multi-platform support, health monitoring
- **v4.x** - Interactive shell, network testing
- **v3.x** - Package tracking, cleanup utilities
- **v2.x** - Cross-platform package manager support
- **v1.x** - Basic universal package management

## Support

For issues, feature requests, or contributions, please visit the project repository.

---

**CrossFire v6.0f8 - Cosmic (Pre-Release)**  

Production Universal Package Manager CLI with Enhanced Performance & Module Support







