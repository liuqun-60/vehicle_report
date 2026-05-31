# date_input_utils.py
"""统一日期输入格式：YYYYMMDD（8位数字），如 20260506"""
import re
from datetime import datetime

COMPACT_DATE_PLACEHOLDER = "20260506"
COMPACT_DATE_HELP = "8位数字日期：YYYYMMDD，如 20260506（不可使用 2026.5.6、2026-05-06 等格式）"

# 精确匹配的日期类字段名
_DATE_FIELD_EXACT = frozenset({
    '接车时间', '完成时间', '时间',  # 过程管控 CSV 列「时间」
})

_COMPACT_DATE_RE = re.compile(r'^\d{8}$')


def is_date_field_name(field_name: str) -> bool:
    if not field_name:
        return False
    name = str(field_name).strip()
    if name in _DATE_FIELD_EXACT:
        return True
    return name.endswith('日期')


def format_db_datetime(value, fmt='%Y-%m-%d %H:%M'):
    """SQLite 存 TEXT 时格式化显示；兼容 datetime 对象。"""
    if not value:
        return ''
    if hasattr(value, 'strftime'):
        return value.strftime(fmt)
    s = str(value).strip().replace('T', ' ')
    if fmt == '%Y-%m-%d %H:%M':
        return s[:16] if len(s) >= 16 else s
    if fmt == '%Y-%m-%d':
        return s[:10] if len(s) >= 10 else s
    return s


def format_stored_date_for_input(value) -> str:
    """将库中旧格式（如 YYYY-MM-DD）转为 YYYYMMDD 供输入框显示；无法识别则原样返回。"""
    if value is None:
        return ''
    s = str(value).strip()
    if not s:
        return ''
    if _COMPACT_DATE_RE.fullmatch(s):
        return s
    for fmt in ('%Y-%m-%d', '%Y/%m/%d'):
        try:
            return datetime.strptime(s, fmt).strftime('%Y%m%d')
        except ValueError:
            continue
    return s


def validate_compact_date(value, field_name='日期', allow_empty=True):
    """
    校验日期必须为 8 位数字 YYYYMMDD。
    返回 (ok: bool, normalized_or_error_msg: str)
    """
    s = str(value).strip() if value is not None else ''
    if not s:
        if allow_empty:
            return True, ''
        return False, f'{field_name}不能为空'

    if not _COMPACT_DATE_RE.fullmatch(s):
        return (
            False,
            f'「{field_name}」须为8位数字（YYYYMMDD），如 20260506；'
            f'不可使用 2026.5.6、2026-05-06 等格式',
        )

    try:
        datetime.strptime(s, '%Y%m%d')
        return True, s
    except ValueError:
        return False, f'「{field_name}」无效，请检查年月日是否正确（当前值：{s}）'


def validate_date_fields_in_mapping(data: dict, allow_empty=True):
    """
    校验字典中所有日期字段。
    返回 (ok, error_messages, normalized_data)
    """
    if not data:
        return True, [], {}

    normalized = dict(data)
    errors = []
    for key, val in data.items():
        if not is_date_field_name(key):
            continue
        ok, result = validate_compact_date(val, key, allow_empty=allow_empty)
        if not ok:
            errors.append(result)
        else:
            normalized[key] = result

    return len(errors) == 0, errors, normalized


def today_compact() -> str:
    return datetime.now().strftime('%Y%m%d')
