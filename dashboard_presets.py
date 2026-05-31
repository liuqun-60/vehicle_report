"""
数据看板筛选配置：全局共享，按配置名称保存/加载
"""
import json
from pathlib import Path

PRESETS_DIR = Path(__file__).resolve().parent / 'dashboard_presets'
SHARED_PRESETS_FILE = PRESETS_DIR / 'presets.json'

VEHICLE_FILTER_KEYS = {
    'report_filter': 'report_filter_input',
    'name_filter': 'name_filter_input',
    'model_filter': 'model_filter_input',
    'chassis_filter': 'chassis_filter_input',
    'min_weight': 'min_weight_input',
    'max_weight': 'max_weight_input',
    'energy_filter': 'energy_filter_select',
    'platform_filter': 'platform_filter_input',
}

TEST_PROJECT_KEYS = {
    'main_cat': 'dashboard_main_cat_select',
    'sub_cat': 'dashboard_sub_cat_select',
    'test_item': 'dashboard_test_item_select',
}

VEHICLE_FILTER_DEFAULTS = {
    'report_filter': '',
    'name_filter': '',
    'model_filter': '',
    'chassis_filter': '',
    'min_weight': 8000,
    'max_weight': 8500,
    'energy_filter': '（请选择）',
    'platform_filter': '',
}


def list_presets():
    if not SHARED_PRESETS_FILE.exists():
        return {}
    try:
        with open(SHARED_PRESETS_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def save_preset(preset_name, config):
    name = (preset_name or '').strip()
    if not name:
        raise ValueError('配置名称不能为空')
    PRESETS_DIR.mkdir(parents=True, exist_ok=True)
    presets = list_presets()
    presets[name] = config
    with open(SHARED_PRESETS_FILE, 'w', encoding='utf-8') as f:
        json.dump(presets, f, ensure_ascii=False, indent=2)


def delete_preset(preset_name):
    presets = list_presets()
    if preset_name in presets:
        del presets[preset_name]
        PRESETS_DIR.mkdir(parents=True, exist_ok=True)
        with open(SHARED_PRESETS_FILE, 'w', encoding='utf-8') as f:
            json.dump(presets, f, ensure_ascii=False, indent=2)
        return True
    return False


def collect_vehicle_filters_from_session(session_state):
    return {
        key: session_state.get(widget_key, VEHICLE_FILTER_DEFAULTS[key])
        for key, widget_key in VEHICLE_FILTER_KEYS.items()
    }


def collect_test_project_from_session(session_state):
    return {
        key: session_state.get(widget_key, '')
        for key, widget_key in TEST_PROJECT_KEYS.items()
    }


def build_preset_config(session_state):
    return {
        'vehicle_filters': collect_vehicle_filters_from_session(session_state),
        'test_project': collect_test_project_from_session(session_state),
    }


def apply_preset_to_session(session_state, config):
    """将配置写入 session_state，供页面控件直接读取并复现筛选条件"""
    vf = config.get('vehicle_filters') or {}
    for key, widget_key in VEHICLE_FILTER_KEYS.items():
        session_state[widget_key] = vf.get(key, VEHICLE_FILTER_DEFAULTS[key])
    # 兼容旧版配置（文本框能源筛选 → 下拉）
    if vf.get('energy_filter') and session_state.get('energy_filter_select') in ('', '（请选择）'):
        legacy = vf.get('energy_filter', '')
        if legacy and legacy != '（请选择）':
            session_state['energy_filter_select'] = legacy.split(',')[0].strip() or '（请选择）'

    tp = config.get('test_project') or {}
    for key, widget_key in TEST_PROJECT_KEYS.items():
        session_state[widget_key] = tp.get(key, '')
