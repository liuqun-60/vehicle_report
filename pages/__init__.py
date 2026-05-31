# pages/__init__.py
"""
页面模块包
导出所有页面显示函数
"""

from .home import show_home_page
from .admin import show_admin_home, show_database_management, show_delete_vehicles, show_frozen_vehicles_management
from .vehicle import show_vehicle_management
from .data_entry import show_data_entry
from .image import show_image_management
from .report import show_report_generation
from .dashboard import show_data_dashboard

__all__ = [
    'show_home_page',
    'show_admin_home',
    'show_database_management',
    'show_delete_vehicles',
    'show_vehicle_management',
    'show_data_entry',
    'show_image_management',
    'show_report_generation',
    'show_data_dashboard',
    'show_frozen_vehicles_management',
]