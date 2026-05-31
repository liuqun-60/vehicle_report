# database/__init__.py
"""
数据库操作模块
统一对外接口
"""

# 从core模块导入核心函数
from .core import (
    get_main_categories,
    get_sub_categories,
    get_test_items,
    get_all_test_items,
    get_vehicles,
    get_vehicle_details,
    get_vehicle_test_results,
    get_vehicle_test_data_for_report,
    save_vehicle,
    update_vehicle,
    delete_vehicle,
    save_test_result,
    save_report_config,
    get_report_config,
    save_test_info_config,
    get_test_info_config,
    save_report_image,
    get_report_images,
    delete_report_images,
    save_sample_car_image,
    get_sample_car_images,
    delete_sample_car_images,
    save_test_projects,
    get_test_projects,
    save_test_equipment,
    get_test_equipment,
    save_signature,
    get_signature,
    save_signature_image,
    get_signature_image_path,
    get_all_signature_images,
    get_vehicle_comparison_data,
    get_vehicles_with_filters,
    get_vehicle_test_comparison_data,
    copy_vehicle_configurations,
    get_test_item_by_name_and_unit,
    check_database_status,
    save_test_info_config_batch,
    get_test_info_config_batch,
    get_representative_test_item_id,
    get_main_category_name_by_representative_item,
    save_report_image_by_category,
    get_report_images_by_category,
    delete_report_images_by_category,
    check_vehicle_frozen,
    freeze_vehicle,
    unfreeze_vehicle
)

# 从initializer模块导入初始化函数
from .initializer import (
    init_database,
    check_and_fix_serial_numbers,
    get_database_stats,
    initialize_default_data
)

# 从exports模块导入导出函数
from .exports import (
    export_database_to_csv,
    export_test_template,
    export_multiple_vehicles_data,
    export_database_structure,
    export_selected_vehicles_full_data,
    export_performance_basic_data_csv,
)

# 从imports模块导入导入函数
from .imports import (
    import_database_from_csv,
    import_test_data,
    import_multiple_vehicles_from_csv,
    import_performance_basic_data_csv,
)

__all__ = [
    # Core
    'get_main_categories',
    'get_sub_categories',
    'get_test_items',
    'get_all_test_items',
    'get_vehicles',
    'get_vehicle_details',
    'get_vehicle_test_results',
    'get_vehicle_test_data_for_report',
    'save_vehicle',
    'update_vehicle',
    'delete_vehicle',
    'save_test_result',
    'save_report_config',
    'get_report_config',
    'save_test_info_config',
    'get_test_info_config',
    'save_report_image',
    'get_report_images',
    'delete_report_images',
    'save_sample_car_image',
    'get_sample_car_images',
    'delete_sample_car_images',
    'save_test_projects',
    'get_test_projects',
    'save_test_equipment',
    'get_test_equipment',
    'save_signature',
    'get_signature',
    'save_signature_image',
    'get_signature_image_path',
    'get_all_signature_images',
    'get_vehicle_comparison_data',
    'get_vehicles_with_filters',
    'get_vehicle_test_comparison_data',
    'copy_vehicle_configurations',
    'get_test_item_by_name_and_unit',
    'check_database_status',
    'save_test_info_config_batch',
    'get_test_info_config_batch',

    # Initializer
    'init_database',
    'check_and_fix_serial_numbers',
    'get_database_stats',
    'initialize_default_data',

    # Exports
    'export_database_to_csv',
    'export_test_template',
    'export_multiple_vehicles_data',
    'export_database_structure',
    'export_selected_vehicles_full_data',
    'export_performance_basic_data_csv',

    # Imports
    'import_database_from_csv',
    'import_test_data',
    'import_multiple_vehicles_from_csv',
    'import_performance_basic_data_csv',

    'get_representative_test_item_id',
    'get_main_category_name_by_representative_item',
    'save_report_image_by_category',
    'get_report_images_by_category',
    'delete_report_images_by_category',
    'check_vehicle_frozen',
    'freeze_vehicle',
    'unfreeze_vehicle',
]