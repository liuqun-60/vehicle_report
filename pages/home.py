# pages/home.py
"""
首页 - 性能试验报告看板
"""
import json
import re
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime
from pathlib import Path

from config import MAIN_CATEGORY_ORDER
from database.core import (
    get_all_test_items,
    get_main_categories,
    get_all_vehicles_info_batch,
    get_all_vehicles_test_results_batch,
    get_user_display_names,
)

DEVICE_LOAD_TYPES = ['参数测量类', '动燃性能类', '制动操稳类', '路谱采集类']
STABILITY_KEYWORD = '操纵稳定性'
MAPPING_FILE = Path(__file__).resolve().parent.parent / 'home_device_mapping.json'

# 首页饼图统一配色（柔和协调）
HOME_PIE_COLORS = [
    '#5470c6', '#91cc75', '#fac858', '#ee6666', '#73c0de',
    '#3ba272', '#fc8452', '#9a60b4', '#ea7ccc', '#6e7074',
    '#61a0a8', '#d48265', '#749f83', '#ca8622', '#bda29a',
]


def _load_device_mapping():
    if MAPPING_FILE.exists():
        try:
            with open(MAPPING_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if isinstance(data, dict):
                    return data
        except Exception:
            pass
    return {}


def _save_device_mapping(mapping):
    with open(MAPPING_FILE, 'w', encoding='utf-8') as f:
        json.dump(mapping, f, ensure_ascii=False, indent=2)


def _default_device_mapping(main_category_names):
    defaults = {}
    for name in main_category_names:
        if '参数' in name or '基本' in name:
            defaults[name] = '参数测量类'
        elif name in ('动力性', '经济性') or '动力' in name or '经济' in name or '油耗' in name:
            defaults[name] = '动燃性能类'
        elif STABILITY_KEYWORD in name or '制动' in name or '换挡' in name or '操稳' in name or '乘降' in name:
            defaults[name] = '制动操稳类'
        else:
            defaults[name] = '路谱采集类'
    return defaults


def _get_display_category_columns(raw_main_categories):
    ordered, seen = [], set()
    for cat in MAIN_CATEGORY_ORDER:
        if cat in raw_main_categories and cat not in seen:
            if STABILITY_KEYWORD in cat:
                if '操纵稳定性' not in seen:
                    ordered.append('操纵稳定性')
                    seen.add('操纵稳定性')
            else:
                ordered.append(cat)
                seen.add(cat)
    for cat in sorted(raw_main_categories):
        if cat in seen:
            continue
        if STABILITY_KEYWORD in cat:
            if '操纵稳定性' not in seen:
                ordered.append('操纵稳定性')
                seen.add('操纵稳定性')
        else:
            ordered.append(cat)
            seen.add(cat)
    return ordered


def _merge_category_stats(raw_stats):
    merged = {}
    for cat, count in raw_stats.items():
        key = '操纵稳定性' if STABILITY_KEYWORD in cat else cat
        merged[key] = merged.get(key, 0) + count
    return merged


def _parse_test_project_count(conclusion_text, computed_count):
    if conclusion_text:
        m = re.search(r'共完成\s*(\d+)\s*个测试项目', str(conclusion_text))
        if m:
            return int(m.group(1))
    return computed_count


def _parse_km_value(text):
    nums = re.findall(r'[\d.]+', str(text or '').replace(',', ''))
    return float(nums[0]) if nums else 0.0


def _normalize_chassis(chassis):
    """底盘号比对：去空格、统一大小写"""
    return re.sub(r'\s+', '', str(chassis or '').strip()).upper()


@st.cache_data(ttl=300, show_spinner=False)
def load_home_board_data():
    from db_config import connection_pool

    vehicles_info = get_all_vehicles_info_batch()
    header_configs, overview_configs = {}, {}
    try:
        with connection_pool.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT vehicle_id, config_key, config_value FROM report_configs WHERE config_type = 'header'"
            )
            for vid, key, val in cursor.fetchall():
                header_configs.setdefault(vid, {})[key] = val or ''
            cursor.execute(
                "SELECT vehicle_id, config_key, config_value FROM report_configs WHERE config_type = 'overview'"
            )
            for vid, key, val in cursor.fetchall():
                overview_configs.setdefault(vid, {})[key] = val or ''
    except Exception:
        pass

    test_results = get_all_vehicles_test_results_batch()
    all_items = get_all_test_items()
    item_to_maincat = {item[0]: item[4] for item in all_items}
    raw_main_cats = {item[4] for item in all_items if item[4]}
    for _id, name in get_main_categories():
        if name:
            raw_main_cats.add(name)

    return {
        'vehicles_info': vehicles_info,
        'header_configs': header_configs,
        'overview_configs': overview_configs,
        'test_results': test_results,
        'item_to_maincat': item_to_maincat,
        'raw_main_categories': sorted(raw_main_cats),
        'total_test_item_defs': len(all_items),
    }


def _build_performance_report_rows(board_data):
    """性能汇总：始终统计全部车辆"""
    vehicles_info = board_data['vehicles_info']
    header_configs = board_data['header_configs']
    overview_configs = board_data['overview_configs']
    test_results = board_data['test_results']
    item_to_maincat = board_data['item_to_maincat']
    display_cols = _get_display_category_columns(board_data['raw_main_categories'])

    rows = []
    for vehicle_id, vinfo in vehicles_info.items():
        header = header_configs.get(vehicle_id, {})
        overview = overview_configs.get(vehicle_id, {})
        raw_stats, computed_total = {}, 0
        for test_item_id, _value in test_results.get(vehicle_id, {}).items():
            main_cat = item_to_maincat.get(test_item_id)
            if main_cat:
                raw_stats[main_cat] = raw_stats.get(main_cat, 0) + 1
                computed_total += 1
        merged_stats = _merge_category_stats(raw_stats)
        project_count = _parse_test_project_count(overview.get('试验结论', ''), computed_total)
        row = {
            'vehicle_id': vehicle_id,
            '报告编号': header.get('编号', ''),
            '报告名称': header.get('名称', ''),
            '项目平台': vinfo.get('vehicle_platform', ''),
            '能源类型': vinfo.get('energy_type', ''),
            '任务来源': overview.get('任务来源', ''),
            '项目费用': overview.get('项目费用', ''),
            '车型号': vinfo.get('model', ''),
            '编制人': vinfo.get('creator_display') or vinfo.get('created_by') or '',
            '编制日期': header.get('编制日期', ''),
            '试验项目数': project_count,
            '_raw_category_stats': raw_stats,
            '_merged_category_stats': merged_stats,
            '_has_tests': computed_total > 0,
        }
        for col in display_cols:
            row[col] = merged_stats.get(col, 0)
        rows.append(row)
    rows.sort(key=lambda r: (r['报告编号'] or '', r['vehicle_id']))
    return rows, display_cols


def _build_load_rows(report_rows, device_mapping):
    load_rows = []
    for r in report_rows:
        n = r['试验项目数'] or 0
        device_counts = {t: 0 for t in DEVICE_LOAD_TYPES}
        for main_cat, count in r['_raw_category_stats'].items():
            load_type = device_mapping.get(main_cat)
            if load_type in device_counts:
                device_counts[load_type] += count
        load_row = {
            '报告编号': r['报告编号'], '报告名称': r['报告名称'],
            '个人负荷': round(n / 2, 2) if n else 0, '试验收入': n * 500,
        }
        for t in DEVICE_LOAD_TYPES:
            a = device_counts[t]
            load_row[t] = round(a / 16, 2) if a else 0
        load_rows.append(load_row)
    return load_rows


def _format_display_number(value, decimals=0):
    if decimals:
        return f"{value:,.{decimals}f}" if isinstance(value, float) else str(value)
    if isinstance(value, float) and value == int(value):
        value = int(value)
    return f"{int(value):,}" if isinstance(value, (int, float)) else str(value)


def _stat_card_html(value, label, unit, variant):
    return f"""
    <div class="kpi-card kpi-{variant}">
        <div class="kpi-label">{label}</div>
        <div class="kpi-value">{value}<span class="kpi-unit">{unit}</span></div>
    </div>
    """


def _normalize_label(text, fallback='未填写'):
    s = str(text or '').strip()
    return s if s else fallback


def _count_by_key(rows, key):
    counts = {}
    for row in rows:
        label = _normalize_label(row.get(key))
        counts[label] = counts.get(label, 0) + 1
    return counts


def _sum_category_tests(report_rows):
    totals = {}
    for row in report_rows:
        for cat, count in row.get('_merged_category_stats', {}).items():
            totals[cat] = totals.get(cat, 0) + count
    return totals


def _sum_device_load(load_rows):
    totals = {t: 0.0 for t in DEVICE_LOAD_TYPES}
    for row in load_rows:
        for t in DEVICE_LOAD_TYPES:
            totals[t] += float(row.get(t) or 0)
    return totals


PIE_MAX_SLICES = 10
PIE_CHART_HEIGHT = 340


def _prepare_pie_data(counts_dict, sort_desc=True, max_items=PIE_MAX_SLICES):
    items = [(k, v) for k, v in counts_dict.items() if v and v > 0]
    if sort_desc:
        items.sort(key=lambda x: x[1], reverse=True)
    if not items:
        return [], [], False
    truncated = len(items) > max_items
    if truncated:
        items = items[:max_items]
    labels, values = zip(*items)
    return list(labels), list(values), truncated


def _make_home_pie(labels, values, title, value_suffix='', truncated=False):
    if not labels:
        return None
    display_title = f"{title}（前{PIE_MAX_SLICES}项）" if truncated else title
    slice_colors = [HOME_PIE_COLORS[i % len(HOME_PIE_COLORS)] for i in range(len(labels))]
    total = sum(values)
    use_decimals = any(isinstance(v, float) and v != int(v) for v in values)
    value_fmt = ':,.2f' if use_decimals else ':,.0f'
    suffix_part = value_suffix.replace('%', '%%') if value_suffix else ''
    texttemplate = f'%{{label}}<br>%{{value{value_fmt}}}{suffix_part} (%{{percent}})'
    n = len(labels)
    pull = [0.05 if i == 0 else 0.02 for i in range(n)]

    fig = go.Figure(data=[go.Pie(
        labels=labels,
        values=values,
        hole=0.38,
        rotation=28,
        direction='clockwise',
        sort=True,
        marker=dict(colors=slice_colors, line=dict(color='#ffffff', width=2)),
        textinfo='none',
        texttemplate=texttemplate,
        textposition='outside',
        insidetextorientation='horizontal',
        textfont=dict(size=13, color='#334155'),
        outsidetextfont=dict(size=13, color='#334155'),
        hovertemplate=(
            '%{label}<br>数值: %{value'
            + value_fmt
            + '}' + value_suffix + '<br>占比: %{percent}<extra></extra>'
        ),
        pull=pull,
        domain=dict(x=[0.08, 0.92], y=[0.02, 0.98]),
        automargin=True,
    )])
    fig.update_layout(
        title=dict(
            text=display_title,
            x=0,
            xanchor='left',
            y=0.98,
            yanchor='top',
            font=dict(size=15, color='#1a2c3e'),
            pad=dict(l=4, t=2),
        ),
        height=PIE_CHART_HEIGHT,
        margin=dict(l=8, r=8, t=40, b=8),
        showlegend=False,
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        annotations=[dict(
            text=(
                f'<b>{_format_display_number(total, 1 if use_decimals else 0)}</b>'
                f'<br><span style="font-size:11px;color:#64748b">合计</span>'
            ),
            x=0.5, y=0.5, font=dict(size=17, color='#1a2c3e'), showarrow=False,
        )],
    )
    return fig


def _render_pie_pair(left_labels, left_values, left_title, right_labels, right_values, right_title,
                     left_suffix='', right_suffix='', left_truncated=False, right_truncated=False):
    left_fig = _make_home_pie(left_labels, left_values, left_title, left_suffix, left_truncated)
    right_fig = _make_home_pie(right_labels, right_values, right_title, right_suffix, right_truncated)
    c1, c2 = st.columns(2, gap='small')
    with c1:
        if left_fig:
            st.plotly_chart(left_fig, use_container_width=True, config={'displayModeBar': False})
        else:
            st.caption(f"{left_title}：暂无数据")
    with c2:
        if right_fig:
            st.plotly_chart(right_fig, use_container_width=True, config={'displayModeBar': False})
        else:
            st.caption(f"{right_title}：暂无数据")


def _render_single_pie(labels, values, title, value_suffix='', truncated=False):
    fig = _make_home_pie(labels, values, title, value_suffix, truncated)
    if fig:
        _, mid, _ = st.columns([0.55, 1.5, 0.55], gap='small')
        with mid:
            st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})
    else:
        st.caption(f"{title}：暂无数据")


def _render_kpi_cards(board_data, report_rows):
    st.markdown('<div class="board-section">📈 统计概览</div>', unsafe_allow_html=True)

    total_vehicles = len(board_data.get('vehicles_info', {}))
    completed_vehicles = sum(1 for r in report_rows if r.get('_has_tests'))
    total_completed_tests = sum(r.get('试验项目数') or 0 for r in report_rows)
    total_item_defs = board_data.get('total_test_item_defs', 0)

    st.markdown(
        '<div class="kpi-section-title"><span class="kpi-dot perf"></span>性能试验</div>',
        unsafe_allow_html=True,
    )
    p1, p2, p3, p4 = st.columns(4)
    with p1:
        st.markdown(_stat_card_html(_format_display_number(completed_vehicles), '完成车辆试验', '辆', 'p1'), unsafe_allow_html=True)
    with p2:
        st.markdown(_stat_card_html(_format_display_number(total_completed_tests), '完成测试项目', '项', 'p2'), unsafe_allow_html=True)
    with p3:
        st.markdown(_stat_card_html(_format_display_number(total_item_defs), '标准测试项目库', '项', 'p3'), unsafe_allow_html=True)
    with p4:
        rate = f"{completed_vehicles / total_vehicles * 100:.0f}%" if total_vehicles else "—"
        st.markdown(_stat_card_html(rate, '车辆完成率', '', 'p4'), unsafe_allow_html=True)


def show_home_page(user_type):
    st.markdown("""
    <style>
    .home-title { font-size: 1.75rem; font-weight: 700; color: #1a2c3e; margin-bottom: 0.25rem; }
    .home-sub { color: #6c757d; font-size: 0.95rem; margin-bottom: 0.5rem; }
    .board-section {
        font-size: 1.15rem; font-weight: 600; color: #1a2c3e;
        padding: 6px 0 6px 12px; border-left: 4px solid #4f6af0;
        margin: 1rem 0 0.5rem 0;
    }
    .kpi-section-title {
        font-size: 0.92rem; font-weight: 600; color: #5c6b82;
        letter-spacing: 0.04em; margin: 0 0 10px 2px;
    }
    .kpi-dot {
        display: inline-block; width: 7px; height: 7px; border-radius: 50%;
        margin-right: 8px; vertical-align: middle;
    }
    .kpi-dot.perf { background: linear-gradient(135deg, #3b82f6, #06b6d4); }
    .kpi-dot.dur { background: linear-gradient(135deg, #10b981, #34d399); }
    .kpi-card {
        border-radius: 14px; padding: 18px 16px 14px 16px; min-height: 96px;
        box-shadow: 0 10px 28px rgba(30, 64, 120, 0.12);
        border: 1px solid rgba(255,255,255,0.45);
        position: relative; overflow: hidden;
    }
    .kpi-card::after {
        content: ''; position: absolute; right: -20px; top: -20px;
        width: 80px; height: 80px; border-radius: 50%;
        background: rgba(255,255,255,0.12);
    }
    .kpi-label { font-size: 0.82rem; color: rgba(255,255,255,0.88); font-weight: 500; margin-bottom: 6px; }
    .kpi-value { font-size: 1.85rem; font-weight: 700; color: #fff; line-height: 1.1; letter-spacing: -0.02em; }
    .kpi-unit { font-size: 0.95rem; font-weight: 500; margin-left: 4px; opacity: 0.9; }
    .kpi-p1 { background: linear-gradient(135deg, #1d4ed8 0%, #2563eb 45%, #0ea5e9 100%); }
    .kpi-p2 { background: linear-gradient(135deg, #5b21b6 0%, #7c3aed 50%, #a78bfa 100%); }
    .kpi-p3 { background: linear-gradient(135deg, #0369a1 0%, #0284c7 50%, #38bdf8 100%); }
    .kpi-p4 { background: linear-gradient(135deg, #4338ca 0%, #6366f1 55%, #818cf8 100%); }
    .kpi-d1 { background: linear-gradient(135deg, #047857 0%, #059669 50%, #34d399 100%); }
    .kpi-d2 { background: linear-gradient(135deg, #b45309 0%, #d97706 50%, #fbbf24 100%); }
    .kpi-d3 { background: linear-gradient(135deg, #0e7490 0%, #0891b2 50%, #22d3ee 100%); }
    .kpi-d4 { background: linear-gradient(135deg, #be185d 0%, #db2777 50%, #f472b6 100%); }
    div[data-testid="stPlotlyChart"] {
        background: linear-gradient(180deg, #f8fafc 0%, #ffffff 100%);
        border: 1px solid #e2e8f0;
        border-radius: 12px;
        padding: 2px 2px 0 2px;
        margin-top: 2px;
    }
    </style>
    """, unsafe_allow_html=True)

    col_t, col_d = st.columns([4, 1])
    with col_t:
        st.markdown('<p class="home-title">📊 试验报告看板</p>', unsafe_allow_html=True)
        st.markdown('<p class="home-sub">性能试验报告汇总 · 统计全部车辆（与用户权限无关）</p>', unsafe_allow_html=True)
    with col_d:
        st.markdown(
            f"<p style='text-align:right;color:#6c757d;padding-top:1.2rem;'>{datetime.now().strftime('%Y年%m月%d日')}</p>",
            unsafe_allow_html=True,
        )

    with st.spinner("正在加载看板数据..."):
        board_data = load_home_board_data()

    if not board_data['vehicles_info']:
        st.warning("暂无性能车辆数据。")
        return

    raw_main_cats = board_data['raw_main_categories']
    saved_mapping = _load_device_mapping() or _default_device_mapping(raw_main_cats)

    report_rows, display_category_cols = _build_performance_report_rows(board_data)
    device_mapping = {
        cat: st.session_state.get(f"device_map_{cat}", saved_mapping.get(cat, DEVICE_LOAD_TYPES[0]))
        for cat in raw_main_cats
    }
    load_rows = _build_load_rows(report_rows, device_mapping) if report_rows else []
    load_columns = ['序号', '报告编号', '报告名称', '个人负荷', '试验收入'] + DEVICE_LOAD_TYPES
    load_records = [{**row, '序号': i} for i, row in enumerate(load_rows, 1)]
    load_df = pd.DataFrame(load_records, columns=load_columns) if load_records else pd.DataFrame(columns=load_columns)

    _render_kpi_cards(board_data, report_rows)

    # ========== 性能试验报告汇总 ==========
    st.markdown('<div class="board-section">📋 性能试验报告汇总</div>', unsafe_allow_html=True)
    if report_rows:
        summary_columns = [
            '序号', '报告编号', '报告名称', '项目平台', '能源类型', '任务来源', '项目费用',
            '车型号', '编制人', '编制日期', '试验项目数',
        ] + display_category_cols
        summary_records = []
        for i, r in enumerate(report_rows, 1):
            rec = {k: r.get(k, '') for k in summary_columns if k != '序号'}
            rec['序号'] = i
            summary_records.append({col: rec.get(col, '') for col in summary_columns})
        summary_df = pd.DataFrame(summary_records, columns=summary_columns)
        st.dataframe(summary_df, use_container_width=True, hide_index=True, height=min(400, len(summary_df) * 34 + 40))
        st.download_button(
            "📥 导出性能汇总 CSV", summary_df.to_csv(index=False).encode('utf-8-sig'),
            file_name=f"性能试验报告汇总_{datetime.now().strftime('%Y%m%d')}.csv", mime="text/csv",
        )
        perf_platform_labels, perf_platform_values, perf_platform_trunc = _prepare_pie_data(
            _count_by_key(report_rows, '项目平台'))
        perf_cat_labels, perf_cat_values, perf_cat_trunc = _prepare_pie_data(_sum_category_tests(report_rows))
        _render_pie_pair(
            perf_platform_labels, perf_platform_values, '归属平台车辆分布',
            perf_cat_labels, perf_cat_values, '一级目录测试数据占比',
            right_suffix=' 项',
            left_truncated=perf_platform_trunc, right_truncated=perf_cat_trunc,
        )
    else:
        st.info("暂无性能车辆数据")

    with st.expander("⚙️ 设备负荷分类配置", expanded=False):
        cols = st.columns(2)
        for idx, cat_name in enumerate(raw_main_cats):
            current = saved_mapping.get(cat_name, DEVICE_LOAD_TYPES[0])
            if current not in DEVICE_LOAD_TYPES:
                current = DEVICE_LOAD_TYPES[0]
            with cols[idx % 2]:
                st.selectbox(cat_name, DEVICE_LOAD_TYPES, index=DEVICE_LOAD_TYPES.index(current), key=f"device_map_{cat_name}")
        b1, b2 = st.columns([1, 3])
        with b1:
            if st.button("💾 保存分类", type="primary"):
                _save_device_mapping({cat: st.session_state.get(f"device_map_{cat}") for cat in raw_main_cats})
                st.rerun()
        with b2:
            if st.button("🔄 恢复默认分类"):
                _save_device_mapping(_default_device_mapping(raw_main_cats))
                st.rerun()

    if report_rows:
        st.markdown('<div class="board-section">📊 性能负荷统计</div>', unsafe_allow_html=True)
        st.dataframe(load_df, use_container_width=True, hide_index=True, height=min(320, len(load_df) * 34 + 40))
        device_totals = _sum_device_load(load_rows)
        device_labels, device_values, device_trunc = _prepare_pie_data(device_totals)
        _render_single_pie(device_labels, device_values, '设备负荷分类占比', truncated=device_trunc)
