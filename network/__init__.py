"""
CrossFire Network Testing Module
Enhanced network diagnostics with parallel processing and comprehensive analysis
"""

from .testing import SpeedTest

__all__ = ['SpeedTest']

# Module version and feature flags
__version__ = '2.0.0'
__features__ = [
    'parallel_ping_testing',
    'adaptive_speed_testing', 
    'multiple_fallback_urls',
    'comprehensive_network_analysis',
    'enhanced_error_handling'
]