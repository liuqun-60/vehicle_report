# config.py - 全局配置（Streamlit Cloud 演示版）
"""
系统全局配置文件
"""

# ========== 管理员配置 ==========
ADMIN_PASSWORD = "Aa333333"  # 管理员密码
ADMIN_SESSION_TIMEOUT = 30  # 管理员会话超时时间（分钟）

# ========== 页面显示配置 ==========
ITEMS_PER_PAGE = 50  # 每页显示的项目数
MAX_TABLE_HEIGHT = 400  # 表格最大高度（像素）
MAX_PREVIEW_ROWS = 10  # 文件预览最大行数

# ========== 图表配置 ==========
CHART_COLORS = {
    'primary': 'royalblue',
    'secondary': 'darkblue',
    'accent': 'red',
    'success': 'green',
    'warning': 'orange'
}

# ========== 文件上传配置 ==========
ALLOWED_IMAGE_EXTENSIONS = ['jpg', 'jpeg', 'png', 'gif', 'bmp']
MAX_IMAGE_SIZE_MB = 10  # 最大图片大小（MB）
MAX_UPLOAD_FILES = 20  # 单次最大上传文件数

# ========== 报告配置 ==========
REPORT_PAGE_SIZE = 'A4'  # 报告页面大小
REPORT_MARGIN_MM = 20  # 报告页边距（mm）
REPORT_FONT_SIZE = {
    'title': 26,
    'section': 18,
    'sub_section': 16,
    'normal': 11,
    'small': 9
}

# ========== 数据看板配置 ==========
DASHBOARD_CHART_HEIGHT = 500  # 默认图表高度
DASHBOARD_SCATTER_POINT_SIZE = {
    'small': 6,
    'medium': 8,
    'large': 12
}

# ========== 测试信息字段配置 ==========
TEST_INFO_FIELDS = ['试验日期', '试验地点', '里程（km）', '总质量（kg）', '天气', '备注']

# ========== 签名类型配置 ==========
SIGNATURE_TYPES = ['编制签名', '校对签名', '审核签名', '批准签名']
SIGNATURE_DISPLAY_NAMES = ['编制', '校对', '审核', '批准']

# ========== 一级目录显示顺序 ==========
MAIN_CATEGORY_ORDER = [
    '基本参数测量',
    '动力性',
    '经济性',
    '制动性能',
    '滑行性能',
    '操纵稳定性',
    '选换挡操作性',
    '乘降性',
    '灯具配光测试'
]

# ========== 导出导入配置 ==========
EXCEL_EXPORT_SHEETS = {
    'main_categories': '一级目录',
    'sub_categories': '二级目录',
    'test_items': '测试项目',
    'vehicles': '车辆信息',
    'test_results': '测试结果',
    'report_configs': '报告配置',
    'test_info_configs': '测试信息配置',
    'test_projects': '试验项目',
    'test_equipment': '试验设备',
    'report_signatures': '报告签名',
    'report_images': '报告图片记录',
    'sample_car_images': '样车照片记录'
}