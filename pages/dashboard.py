# pages/dashboard.py
"""
数据看板页面 - 优化版
使用批量查询 + Session State 缓存，保留所有原有功能
"""
import re
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import numpy as np
from datetime import datetime

from database.core import (
    get_all_test_items,
    get_main_categories,
    get_all_vehicles_test_results_batch,
    get_all_vehicles_info_batch,
    get_all_report_configs_batch,
)
from database.exports import export_multiple_vehicles_data

import config
from dashboard_presets import (
    list_presets,
    save_preset,
    delete_preset,
    build_preset_config,
    apply_preset_to_session,
)
def extract_weight(weight_str):
    if not weight_str:
        return None
    try:
        numbers = re.findall(r'\d+\.?\d*', str(weight_str))
        return float(numbers[0]) if numbers else None
    except (ValueError, TypeError):
        return None


def _collect_energy_types(stats_df):
    types = set()
    for val in stats_df['能源类型'].fillna('').astype(str):
        s = val.strip()
        types.add(s if s else '未填写')
    return sorted(types, key=lambda x: (x == '未填写', x))


def _parse_test_value(raw):
    if raw is None:
        return None
    try:
        return float(raw)
    except (ValueError, TypeError):
        return None


def _parse_keywords(filter_str):
    if not filter_str or not str(filter_str).strip():
        return []
    return [k.strip() for k in str(filter_str).replace('，', ',').split(',') if k.strip()]


def _filter_tonnage_range_label(min_weight, max_weight):
    """吨位区间与筛选条件中的上下限一致"""
    return f"{int(min_weight)}-{int(max_weight)}"


def _percentile_or_none(values, pct):
    if not values:
        return None
    return round(float(np.percentile(values, pct)), 2)


def _min_or_none(values):
    if not values:
        return None
    return round(float(min(values)), 2)


def _max_or_none(values):
    if not values:
        return None
    return round(float(max(values)), 2)


def _build_raw_data_df(filtered_df, all_test_results, report_configs, test_item_id, test_item_name, test_item_unit):
    """仅展示所选测试项目有有效数值的车辆"""
    col_name = f"{test_item_name}（{test_item_unit}）"
    rows = []
    seq = 0
    for _, row in filtered_df.iterrows():
        vid = row['车辆ID']
        val = _parse_test_value(all_test_results.get(vid, {}).get(test_item_id))
        if val is None:
            continue
        seq += 1
        header = report_configs.get(vid, {})
        energy = (row.get('能源类型') or '')
        if isinstance(energy, str):
            energy = energy.strip() or '未填写'
        rows.append({
            '序号': seq,
            '车辆ID': vid,
            '报告编号': row.get('报告编号') or header.get('编号', ''),
            '报告名称': header.get('名称', ''),
            '项目平台': row.get('车辆归属平台', '') or '',
            '能源类型': energy,
            '车型号': row['车型'],
            col_name: val,
        })
    return pd.DataFrame(rows)


def _platforms_for_values(filtered_df, vehicle_ids, skip_ids, all_test_results, item_id):
    """统计参与该测试项目有效数据的车辆归属平台（去重）"""
    platforms = set()
    vid_set = set(vehicle_ids)
    for _, row in filtered_df.iterrows():
        vid = row['车辆ID']
        if vid not in vid_set or vid in skip_ids:
            continue
        if _parse_test_value(all_test_results.get(vid, {}).get(item_id)) is None:
            continue
        plat = row.get('车辆归属平台', '')
        if isinstance(plat, str):
            plat = plat.strip() or '未填写'
        else:
            plat = '未填写'
        platforms.add(plat)
    return '、'.join(sorted(platforms)) if platforms else '未填写'


def _compute_target_value_stats_df(
    filtered_df,
    all_test_results,
    all_test_items,
    excluded_vehicle_ids,
    min_weight,
    max_weight,
    selected_item_id=None,
):
    """推荐目标值统计表：吨位区间取自筛选条件，车辆归属平台按实际数据统计"""
    tonnage_label = _filter_tonnage_range_label(min_weight, max_weight)
    excluded_vehicle_ids = excluded_vehicle_ids or set()

    energies = sorted(filtered_df['能源类型'].fillna('未填写').astype(str).unique())
    rows = []
    seq = 0

    for energy in energies:
        vehicle_ids = filtered_df[filtered_df['能源类型'] == energy]['车辆ID'].tolist()
        for item in all_test_items:
            item_id, item_name, item_unit = item[0], item[1], item[2]
            skip_ids = excluded_vehicle_ids if selected_item_id and item_id == selected_item_id else set()

            values = []
            for vid in vehicle_ids:
                if vid in skip_ids:
                    continue
                val = _parse_test_value(all_test_results.get(vid, {}).get(item_id))
                if val is not None:
                    values.append(val)

            platform_label = _platforms_for_values(
                filtered_df, vehicle_ids, skip_ids, all_test_results, item_id
            )

            seq += 1
            median_val = _percentile_or_none(values, 50)
            rows.append({
                '序号': seq,
                '能源类型': energy,
                '吨位区间(kg)': tonnage_label,
                '车辆归属平台': platform_label,
                '测试项目': item_name,
                '单位': item_unit,
                '最小值': _min_or_none(values),
                '最大值': _max_or_none(values),
                '中位数': median_val,
                '推荐目标值(50%分位)': median_val,
                '75%分位': _percentile_or_none(values, 75),
                '90%分位': _percentile_or_none(values, 90),
                '样本数': len(values),
            })

    if not rows:
        return pd.DataFrame()

    column_order = [
        '序号', '能源类型', '吨位区间(kg)', '车辆归属平台',
        '测试项目', '单位', '最小值', '最大值', '中位数',
        '推荐目标值(50%分位)', '75%分位', '90%分位', '样本数',
    ]
    return pd.DataFrame(rows)[column_order]


def _export_state_keys(key_suffix):
    return {
        'prompt': f'dashboard_filtered_export_prompt_{key_suffix}',
        'ready': f'dashboard_filtered_export_ready_{key_suffix}',
        'csv': f'dashboard_filtered_export_csv_{key_suffix}',
        'filename': f'dashboard_filtered_export_filename_{key_suffix}',
    }


def _clear_filtered_export_state(key_suffix):
    """下载后关闭密码/下载面板，恢复为仅显示导出按钮"""
    keys = _export_state_keys(key_suffix)
    for k in keys.values():
        st.session_state.pop(k, None)


def _render_filtered_vehicles_export_col(filtered_df, key_suffix):
    """数据导出列：触发导出（密码与下载面板在下方展开）"""
    keys = _export_state_keys(key_suffix)
    if st.session_state.get(keys['ready']) or st.session_state.get(keys['prompt']):
        return

    if st.button(
        "📤 导出筛选车辆全部测试数据",
        key=f'dashboard_filtered_export_btn_{key_suffix}',
        use_container_width=True,
    ):
        st.session_state[keys['prompt']] = True
        st.rerun()


def _render_filtered_vehicles_export_panel(filtered_df, key_suffix):
    """密码输入 / 生成完成后的下载区（类似报告生成后的下载）"""
    keys = _export_state_keys(key_suffix)

    if st.session_state.get(keys['ready']) and st.session_state.get(keys['csv']):
        st.success("✅ 文件已生成成功！")
        st.download_button(
            label="📥 请下载数据",
            data=st.session_state[keys['csv']],
            file_name=st.session_state.get(keys['filename'], '筛选车辆测试数据.csv'),
            mime="text/csv",
            use_container_width=True,
            key=f'dashboard_filtered_export_dl_{key_suffix}',
            on_click=_clear_filtered_export_state,
            args=(key_suffix,),
        )
        return

    if not st.session_state.get(keys['prompt']):
        return

    with st.container(border=True):
        st.markdown("**导出筛选车辆全部测试数据**")
        pwd = st.text_input(
            "请输入导出密码",
            type="password",
            key=f'dashboard_filtered_export_pwd_{key_suffix}',
        )
        col_ok, col_cancel = st.columns(2)
        with col_ok:
            confirm = st.button("确认导出", key=f'dashboard_filtered_export_confirm_{key_suffix}', use_container_width=True)
        with col_cancel:
            cancel = st.button("取消", key=f'dashboard_filtered_export_cancel_{key_suffix}', use_container_width=True)

        if cancel:
            _clear_filtered_export_state(key_suffix)
            st.rerun()

        if confirm:
            if pwd != config.ADMIN_PASSWORD:
                st.error("密码错误，无法导出")
            else:
                vehicle_ids = filtered_df['车辆ID'].tolist()
                with st.spinner("正在生成导出文件..."):
                    csv_data = export_multiple_vehicles_data(vehicle_ids)
                if csv_data:
                    st.session_state[keys['csv']] = csv_data
                    st.session_state[keys['filename']] = (
                        f"筛选车辆测试数据_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
                    )
                    st.session_state[keys['prompt']] = False
                    st.session_state[keys['ready']] = True
                    st.rerun()
                else:
                    st.error("导出失败，请稍后重试")


def _render_recommend_target_stats_table(stats_df):
    """推荐目标值统计表（DataFrame 展示，格式同原目标值看板）"""
    st.markdown("#### 📋 推荐目标值统计表")
    if stats_df.empty:
        st.warning("未能计算出目标值，请检查数据")
    else:
        st.dataframe(
            stats_df,
            use_container_width=True,
            hide_index=True,
            height=min(400, len(stats_df) * 35 + 38),
        )


def _render_stats_metrics(values, section_title=None):
    arr = np.array([float(v) for v in values if v is not None and not pd.isna(v)], dtype=float)
    if len(arr) == 0:
        st.warning("没有有效数值用于统计")
        return False
    q25, q50, q75 = np.percentile(arr, [25, 50, 75])
    stats_data = [
        ("数据量", str(len(arr))),
        ("最大值", f"{arr.max():.2f}"),
        ("最小值", f"{arr.min():.2f}"),
        ("标准差", f"{arr.std():.2f}"),
        ("75%分位", f"{q75:.2f}"),
        ("50%分位", f"{q50:.2f}"),
        ("25%分位", f"{q25:.2f}"),
        ("平均数", f"{arr.mean():.2f}"),
    ]
    if section_title:
        st.markdown(section_title)
    cols = st.columns(len(stats_data))
    for col, (label, value) in zip(cols, stats_data):
        with col:
            st.metric(label, value)
    return True


def _render_unified_numeric_summary(values):
    """箱线图下方统计摘要"""
    _render_stats_metrics(values, "**统计摘要**")


def _render_dashboard_preset_controls():
    """保存/加载看板筛选配置（全局共享，车辆筛选 + 测试项目）"""
    presets = list_presets()

    st.markdown("### 💾 筛选配置")
    st.caption("全员共享：保存时请命名；加载后自动复现车辆筛选与测试项目，无需再手动筛选。")

    pc1, pc2, pc3, pc4 = st.columns([2, 1, 2, 1])
    preset_names = sorted(presets.keys())

    with pc1:
        selected_preset = st.selectbox(
            "已保存的配置",
            ["（请选择）"] + preset_names if preset_names else ["（暂无）"],
            key="dashboard_preset_select",
            label_visibility="collapsed",
        )
    with pc2:
        if st.button("📂 加载配置", use_container_width=True, key="dashboard_load_preset_btn"):
            if selected_preset in ("（请选择）", "（暂无）", None):
                st.warning("请先选择要加载的配置")
            elif selected_preset not in presets:
                st.error("配置不存在或已被删除")
            else:
                apply_preset_to_session(st.session_state, presets[selected_preset])
                st.success(f"已加载配置「{selected_preset}」")
                st.rerun()
    with pc3:
        new_preset_name = st.text_input(
            "配置名称",
            placeholder="输入名称后点击保存",
            key="dashboard_new_preset_name",
            label_visibility="collapsed",
        )
    with pc4:
        if st.button("💾 保存配置", use_container_width=True, key="dashboard_save_preset_btn"):
            name = (new_preset_name or "").strip()
            if not name:
                st.warning("请输入配置名称")
            else:
                try:
                    save_preset(name, build_preset_config(st.session_state))
                    st.success(f"已保存配置「{name}」")
                    st.rerun()
                except Exception as e:
                    st.error(f"保存失败: {e}")

    if preset_names:
        with st.expander("管理已保存配置", expanded=False):
            del_col1, del_col2 = st.columns([3, 1])
            with del_col1:
                to_delete = st.selectbox(
                    "删除配置",
                    preset_names,
                    key="dashboard_preset_delete_select",
                    label_visibility="collapsed",
                )
            with del_col2:
                if st.button("🗑️ 删除", key="dashboard_delete_preset_btn"):
                    if delete_preset(to_delete):
                        st.success(f"已删除「{to_delete}」")
                        st.rerun()
                    else:
                        st.error("删除失败")


def init_dashboard_data():
    """
    初始化数据看板所需的所有数据
    使用 session_state 缓存，避免重复查询
    """
    # 1. 车辆基本信息（批量查询）
    if 'vehicles_info' not in st.session_state:
        with st.spinner("正在加载车辆信息..."):
            st.session_state.vehicles_info = get_all_vehicles_info_batch()

    # 2. 车辆测试结果（批量查询）
    if 'all_test_results' not in st.session_state:
        with st.spinner("正在加载测试数据..."):
            st.session_state.all_test_results = get_all_vehicles_test_results_batch()

    # 3. 报告配置（批量查询）
    if 'report_configs' not in st.session_state:
        with st.spinner("正在加载报告配置..."):
            st.session_state.report_configs = get_all_report_configs_batch()

    # 4. 所有测试项目（缓存）
    if 'all_test_items' not in st.session_state:
        st.session_state.all_test_items = get_all_test_items()

    # 5. 所有一级目录（缓存）
    if 'main_categories' not in st.session_state:
        st.session_state.main_categories = get_main_categories()

    # 6. 车辆统计信息（从已有数据计算）
    if 'vehicle_stats' not in st.session_state:
        with st.spinner("正在计算统计信息..."):
            stats = []
            for vehicle_id, vehicle_info in st.session_state.vehicles_info.items():
                test_results = st.session_state.all_test_results.get(vehicle_id, {})
                valid_count = len(test_results)
                total_items = 555
                completion_rate = round(valid_count / total_items * 100, 2) if total_items > 0 else 0

                report_config = st.session_state.report_configs.get(vehicle_id, {})
                report_number = report_config.get('编号', '')

                # 计算各一级项目的统计
                category_counts = {}
                # 构建测试项目ID到一级目录的映射
                item_to_maincat = {}
                for item in st.session_state.all_test_items:
                    item_to_maincat[item[0]] = item[4]

                for test_item_id in test_results.keys():
                    main_cat = item_to_maincat.get(test_item_id)
                    if main_cat:
                        category_counts[main_cat] = category_counts.get(main_cat, 0) + 1

                stats.append({
                    'vehicle_id': vehicle_id,
                    'model': vehicle_info['model'],
                    'chassis_number': vehicle_info['chassis_number'],
                    'curb_weight': vehicle_info['curb_weight'],
                    'energy_type': vehicle_info.get('energy_type', ''),
                    'vehicle_platform': vehicle_info.get('vehicle_platform', ''),
                    'report_number': report_number,
                    'valid_count': valid_count,
                    'completion_rate': completion_rate,
                    'category_counts': category_counts
                })

            st.session_state.vehicle_stats = stats


def show_data_dashboard():
    """显示数据看板页面"""
    st.title("📊 数据看板")

    # 初始化数据
    init_dashboard_data()

    # 获取数据引用
    vehicles_info = st.session_state.vehicles_info
    all_test_results = st.session_state.all_test_results
    vehicle_stats = st.session_state.vehicle_stats
    main_categories = st.session_state.main_categories
    all_test_items = st.session_state.all_test_items

    if not vehicle_stats:
        st.warning("暂无车辆数据，请先在【车辆管理】中添加车辆并上传测试数据")
        return

    _render_dashboard_preset_controls()
    st.divider()

    # ========== 转换为DataFrame便于筛选 ==========
    stats_df = pd.DataFrame([
        {
            '车辆ID': s['vehicle_id'],
            '车型': s['model'],
            '底盘号': s['chassis_number'],
            '总质量': s['curb_weight'],
            '能源类型': s.get('energy_type', ''),
            '车辆归属平台': s.get('vehicle_platform', ''),
            '报告编号': s['report_number'],
            '有效测试项': s['valid_count'],
            '完成率(%)': s['completion_rate']
        }
        for s in vehicle_stats
    ])
    stats_df['能源类型'] = stats_df['能源类型'].apply(
        lambda x: (str(x).strip() if pd.notna(x) and str(x).strip() else '未填写')
    )

    # ========== 车辆筛选区域 ==========
    st.markdown("### 🔍 车辆筛选")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown("**报告编号**")
        report_filter = st.text_input(
            "报告编号",
            placeholder="支持多值，用逗号分隔",
            help="示例: SY-2025-001, SY-2025-002",
            label_visibility="collapsed",
            key="report_filter_input"
        )

    with col2:
        st.markdown("**报告名称**")
        name_filter = st.text_input(
            "报告名称",
            placeholder="支持多值，用逗号分隔",
            help="支持多值，用逗号分隔",
            label_visibility="collapsed",
            key="name_filter_input"
        )

    with col3:
        st.markdown("**车型号**")
        model_filter = st.text_input(
            "车型号",
            placeholder="支持多值，用逗号分隔",
            help="支持多值，用逗号分隔",
            label_visibility="collapsed",
            key="model_filter_input"
        )

    col4, col5, col6 = st.columns(3)

    with col4:
        st.markdown("**底盘号**")
        chassis_filter = st.text_input(
            "底盘号",
            placeholder="支持多值，用逗号分隔",
            help="示例: SN304795, SN304800",
            label_visibility="collapsed",
            key="chassis_filter_input"
        )

    with col5:
        st.markdown("**吨位下限(kg)**")
        min_weight = st.number_input(
            "吨位下限",
            min_value=0,
            value=0,
            step=100,
            label_visibility="collapsed",
            key="min_weight_input",
        )

    with col6:
        st.markdown("**吨位上限(kg)**")
        max_weight = st.number_input(
            "吨位上限",
            min_value=0,
            value=18000,
            step=100,
            label_visibility="collapsed",
            key="max_weight_input",
        )

    col7, col8, _ = st.columns(3)

    with col7:
        st.markdown("**能源类型**")
        energy_options = ["（请选择）"] + _collect_energy_types(stats_df)
        selected_energy = st.selectbox(
            "能源类型",
            energy_options,
            label_visibility="collapsed",
            key="energy_filter_select",
            help="仅能选择一种能源类型；留空表示不限",
        )

    with col8:
        st.markdown("**车辆归属平台**")
        platform_filter = st.text_input(
            "车辆归属平台",
            placeholder="可输入车型，逗号分隔；留空不限",
            label_visibility="collapsed",
            key="platform_filter_input",
        )

    # ========== 应用筛选 ==========
    filtered_df = stats_df.copy()

    def multi_value_filter(series, filter_str):
        if not filter_str or not filter_str.strip():
            return True
        keywords = filter_str.replace('，', ',').split(',')
        keywords = [k.strip() for k in keywords if k.strip()]
        if not keywords:
            return True

        def contains_any(value):
            if not value or pd.isna(value):
                return False
            value_str = str(value)
            return any(kw in value_str for kw in keywords)

        return series.apply(contains_any)

    if report_filter:
        filtered_df = filtered_df[multi_value_filter(filtered_df['报告编号'], report_filter)]

    if name_filter:
        keywords = [k.strip() for k in name_filter.replace('，', ',').split(',') if k.strip()]
        if keywords:
            def check_report_name(vehicle_id):
                report_config = st.session_state.report_configs.get(vehicle_id, {})
                report_name = report_config.get('名称', '')
                if report_name:
                    return any(kw in str(report_name) for kw in keywords)
                return False

            filtered_df = filtered_df[filtered_df['车辆ID'].apply(check_report_name)]

    if model_filter:
        filtered_df = filtered_df[multi_value_filter(filtered_df['车型'], model_filter)]

    if chassis_filter:
        filtered_df = filtered_df[multi_value_filter(filtered_df['底盘号'], chassis_filter)]

    if selected_energy and selected_energy != "（请选择）":
        filtered_df = filtered_df[filtered_df['能源类型'] == selected_energy]

    if platform_filter:
        filtered_df = filtered_df[multi_value_filter(filtered_df['车辆归属平台'], platform_filter)]

    filtered_df = filtered_df.copy()
    filtered_df['weight_num'] = filtered_df['总质量'].apply(extract_weight)
    filtered_df = filtered_df[
        filtered_df['weight_num'].notna()
        & (filtered_df['weight_num'] >= min_weight)
        & (filtered_df['weight_num'] <= max_weight)
    ]
    filtered_df = filtered_df.drop(columns=['weight_num'])

    if filtered_df.empty:
        st.warning("没有符合条件的车辆")
        return

    st.success(f"当前显示 {len(filtered_df)} 辆车")

    report_configs = st.session_state.report_configs

    # ========== 车辆信息汇总表格（筛选后保留原统计）==========
    st.markdown("### 📋 车辆信息汇总")

    main_category_names = [cat[1] for cat in main_categories]

    summary_data = []
    for _, row in filtered_df.iterrows():
        vehicle_id = row['车辆ID']
        stat = next((s for s in vehicle_stats if s['vehicle_id'] == vehicle_id), None)

        if stat:
            report_config = report_configs.get(vehicle_id, {})
            report_name = report_config.get('名称', '')

            row_data = {
                '报告编号': stat['report_number'],
                '报告名称': report_name,
                '车型': stat['model'],
                '底盘号': stat['chassis_number'],
                '总质量': stat['curb_weight'],
                '能源类型': row.get('能源类型', '') or stat.get('energy_type', '') or '未填写',
                '车辆归属平台': stat.get('vehicle_platform', ''),
            }
            for cat_name in main_category_names:
                row_data[cat_name] = stat['category_counts'].get(cat_name, 0)
            row_data['总计'] = stat['valid_count']
            summary_data.append(row_data)

    if summary_data:
        column_order = [
            '报告编号', '报告名称', '车型', '底盘号', '总质量',
            '能源类型', '车辆归属平台'
        ] + main_category_names + ['总计']
        summary_df = pd.DataFrame(summary_data)[column_order]

        st.dataframe(
            summary_df,
            use_container_width=True,
            hide_index=True,
            height=min(400, len(summary_data) * 35 + 38)
        )

        total_vehicles = len(summary_data)
        total_tests = summary_df['总计'].sum()
        avg_tests = total_tests / total_vehicles if total_vehicles > 0 else 0

        col_stat1, col_stat2, col_stat3 = st.columns(3)
        with col_stat1:
            st.metric("车辆总数", total_vehicles)
        with col_stat2:
            st.metric("测试项总数", total_tests)
        with col_stat3:
            st.metric("平均测试项/车", f"{avg_tests:.1f}")

    st.divider()

    # ========== 组织测试项目结构 ==========
    organized_items = {}
    for item in all_test_items:
        main_cat = item[4]
        sub_cat = item[3]
        item_name = item[1]
        unit = item[2]
        item_id = item[0]

        if main_cat not in organized_items:
            organized_items[main_cat] = {}
        if sub_cat not in organized_items[main_cat]:
            organized_items[main_cat][sub_cat] = []

        organized_items[main_cat][sub_cat].append({
            'id': item_id,
            'name': item_name,
            'unit': unit
        })

    # ========== 选择测试项目 ==========
    st.markdown("### 🎯 选择测试项目进行对比")

    main_categories_list = sorted(list(organized_items.keys()))
    selected_main_cat = st.selectbox(
        "选择一级目录",
        main_categories_list,
        key="dashboard_main_cat_select"
    )

    if selected_main_cat:
        sub_categories_list = sorted(list(organized_items[selected_main_cat].keys()))
        selected_sub_cat = st.selectbox(
            "选择二级目录",
            sub_categories_list,
            key="dashboard_sub_cat_select"
        )

        if selected_sub_cat:
            test_items = organized_items[selected_main_cat][selected_sub_cat]
            test_item_options = [f"{item['name']} ({item['unit']})" for item in test_items]
            selected_test_item_str = st.selectbox(
                "选择测试项目",
                test_item_options,
                key="dashboard_test_item_select"
            )

            if selected_test_item_str:
                test_item_parts = selected_test_item_str.rsplit(" (", 1)
                test_item_name = test_item_parts[0]
                test_item_unit = test_item_parts[1][:-1] if len(test_item_parts) > 1 else ""

                test_item_id = None
                for item in test_items:
                    if item['name'] == test_item_name and item['unit'] == test_item_unit:
                        test_item_id = item['id']
                        break

                if test_item_id:
                    comparison_data = []
                    for _, row in filtered_df.iterrows():
                        vehicle_id = row['车辆ID']
                        test_value = all_test_results.get(vehicle_id, {}).get(test_item_id)
                        numeric_value = _parse_test_value(test_value)
                        if numeric_value is not None:
                            comparison_data.append({
                                '车辆ID': vehicle_id,
                                '车型': row['车型'],
                                '底盘号': row['底盘号'],
                                '总质量': row['总质量'],
                                '测试项目': test_item_name,
                                '单位': test_item_unit,
                                '测试值': test_value,
                                '数值': numeric_value,
                            })

                    if not comparison_data:
                        st.warning("所选车辆均无此测试项目的有效数值")
                        return

                    raw_df = _build_raw_data_df(
                        filtered_df, all_test_results, report_configs,
                        test_item_id, test_item_name, test_item_unit,
                    )
                    st.markdown("### 📋 当前数据表格")
                    st.caption("仅展示所选测试项目有有效数据的车辆")
                    st.dataframe(
                        raw_df,
                        use_container_width=True,
                        hide_index=True,
                        height=min(420, len(raw_df) * 35 + 38),
                    )

                    comparison_df = pd.DataFrame(comparison_data)
                    comparison_df['显示索引'] = range(1, len(comparison_df) + 1)
                    comparison_df['原始索引'] = comparison_df.index

                    # ========== 异常点管理（简化版：双击删除） ==========
                    if 'excluded_points' not in st.session_state:
                        st.session_state.excluded_points = {}

                    current_test_key = f"{test_item_id}_{test_item_name}"
                    if current_test_key not in st.session_state.excluded_points:
                        st.session_state.excluded_points[current_test_key] = []

                    comparison_df_clean = comparison_df.copy()
                    excluded_indices = st.session_state.excluded_points[current_test_key]

                    if excluded_indices:
                        comparison_df_clean = comparison_df_clean[
                            ~comparison_df_clean['原始索引'].isin(excluded_indices)].reset_index(drop=True)
                        comparison_df_clean['显示索引'] = range(1, len(comparison_df_clean) + 1)

                    selected_item = {'id': test_item_id, 'name': test_item_name, 'unit': test_item_unit}

                    # ========== 图表设置 ==========
                    if len(comparison_df_clean) > 0:
                        st.markdown("### 📈 图表设置")

                        col_set1, col_set2 = st.columns(2)

                        with col_set1:
                            x_axis_option = st.radio(
                                "选择横坐标",
                                ["车型", "底盘号"],
                                horizontal=True,
                                key=f"x_axis_{current_test_key}"
                            )

                        with col_set2:
                            chart_height = st.slider("图表高度", 400, 800, 500, 50,
                                                     key=f"chart_height_{current_test_key}")

                        # ========== 数据可视化 ==========
                        st.markdown("### 📊 数据可视化")

                        tab1, tab2 = st.tabs(["📊 散点图", "📦 箱线图"])

                        with tab1:
                            scatter_data = comparison_df_clean.copy()

                            if x_axis_option == "车型":
                                x_data = scatter_data['车型'].tolist()
                                x_label = "车型"
                            else:
                                x_data = scatter_data['底盘号'].tolist()
                                x_label = "底盘号"

                            if len(scatter_data) > 100:
                                marker_size = 6
                                marker_opacity = 0.5
                            elif len(scatter_data) > 50:
                                marker_size = 8
                                marker_opacity = 0.6
                            else:
                                marker_size = 12
                                marker_opacity = 0.8

                            # 构建悬停文本和 customdata
                            hover_texts = []
                            display_indices = []
                            original_indices = []
                            for idx, row in scatter_data.iterrows():
                                hover_text = (
                                    f"序号: {row['显示索引']}<br>"
                                    f"车型: {row['车型']}<br>"
                                    f"底盘号: {row['底盘号']}<br>"
                                    f"总质量: {row['总质量']}<br>"
                                    f"测试值: {row['测试值']} {row['单位']}<br>"
                                    f"<b>💡 双击此点可删除</b>"
                                )
                                hover_texts.append(hover_text)
                                display_indices.append(row['显示索引'])
                                original_indices.append(row['原始索引'])

                            fig_scatter = go.Figure()

                            fig_scatter.add_trace(go.Scatter(
                                x=x_data,
                                y=scatter_data['数值'],
                                mode='markers',
                                marker=dict(
                                    size=marker_size,
                                    color='royalblue',
                                    opacity=marker_opacity,
                                    line=dict(width=1, color='darkblue')
                                ),
                                text=hover_texts,
                                hoverinfo='text',
                                customdata=original_indices,  # 存储原始索引
                                name='测试值'
                            ))

                            if scatter_data['数值'].notna().any():
                                p50_value = float(np.percentile(scatter_data['数值'].dropna(), 50))
                                fig_scatter.add_hline(
                                    y=p50_value,
                                    line_dash="dash",
                                    line_color="green",
                                    annotation_text=f"50%分位: {p50_value:.2f}",
                                    annotation_position="bottom right",
                                )

                            title_text = f"{test_item_name} 散点图 (共{len(scatter_data)}个点"
                            if excluded_indices:
                                title_text += f"，已排除{len(excluded_indices)}个"
                            title_text += ")"

                            fig_scatter.update_layout(
                                title=title_text,
                                xaxis_title=x_label,
                                yaxis_title=f"{test_item_name} ({test_item_unit})",
                                height=chart_height,
                                showlegend=True,
                                hovermode='closest',
                                template='plotly_white',
                            )

                            if len(scatter_data) > 20:
                                fig_scatter.update_xaxes(tickangle=45, tickmode='array')

                            # ========== 双击删除功能 ==========
                            clicked_point = st.plotly_chart(
                                fig_scatter,
                                use_container_width=True,
                                key=f"scatter_{current_test_key}",
                                on_select="rerun",
                                selection_mode="points"
                            )

                            # 处理双击选中的点
                            if clicked_point is not None:
                                selected_original_idx = None

                                if hasattr(clicked_point, 'selection') and clicked_point.selection is not None:
                                    if hasattr(clicked_point.selection, 'points') and clicked_point.selection.points:
                                        point = clicked_point.selection.points[0]
                                        if isinstance(point, dict):
                                            selected_original_idx = point.get('customdata')
                                        elif hasattr(point, 'customdata'):
                                            selected_original_idx = point.customdata
                                elif isinstance(clicked_point, dict):
                                    selection = clicked_point.get('selection', {})
                                    points = selection.get('points', [])
                                    if points:
                                        point = points[0]
                                        if isinstance(point, dict):
                                            selected_original_idx = point.get('customdata')
                                        elif hasattr(point, 'customdata'):
                                            selected_original_idx = point.customdata

                                if selected_original_idx is not None:
                                    current_excluded = st.session_state.excluded_points[current_test_key]
                                    if selected_original_idx not in current_excluded:
                                        current_excluded.append(selected_original_idx)
                                        st.session_state.excluded_points[current_test_key] = current_excluded
                                        st.success(f"✅ 已删除序号 {selected_original_idx + 1} 的数据点")
                                        st.rerun()
                                    else:
                                        st.info("该点已被删除")

                            # 显示使用提示和恢复按钮
                            col_tip1, col_tip2 = st.columns([3, 1])
                            with col_tip1:
                                st.info("💡 **双击图表上的任意点即可删除该数据点**")
                            with col_tip2:
                                if excluded_indices and st.button("🔄 恢复全部", key=f"restore_{current_test_key}"):
                                    st.session_state.excluded_points[current_test_key] = []
                                    st.success("已恢复所有数据点")
                                    st.rerun()

                            # 显示已删除的点
                            if excluded_indices:
                                with st.expander(f"📋 已删除的点 ({len(excluded_indices)}个)", expanded=False):
                                    excluded_df = comparison_df[comparison_df['原始索引'].isin(excluded_indices)]
                                    st.dataframe(
                                        excluded_df[['显示索引', '车型', '底盘号', '测试值', '单位']],
                                        use_container_width=True,
                                        hide_index=True
                                    )

                            scatter_values = scatter_data['数值'].dropna().tolist()
                            _render_unified_numeric_summary(scatter_values)

                        with tab2:
                            all_values = []
                            for _, row in comparison_df_clean.iterrows():
                                if row['数值'] is not None and not pd.isna(row['数值']):
                                    all_values.append(row['数值'])

                            if all_values:
                                fig_box = go.Figure()

                                hover_texts = []
                                for idx, row in comparison_df_clean.iterrows():
                                    if row['数值'] is not None and not pd.isna(row['数值']):
                                        hover_text = (
                                            f"序号: {row['显示索引']}<br>"
                                            f"车型: {row['车型']}<br>"
                                            f"底盘号: {row['底盘号']}<br>"
                                            f"总质量: {row['总质量']}<br>"
                                            f"测试值: {row['测试值']} {row['单位']}"
                                        )
                                        hover_texts.append(hover_text)

                                fig_box.add_trace(go.Box(
                                    y=all_values,
                                    x=[test_item_name] * len(all_values),
                                    boxpoints='all',
                                    jitter=0.3,
                                    pointpos=-1.8,
                                    marker=dict(
                                        size=6 if len(all_values) > 100 else 8,
                                        opacity=0.5 if len(all_values) > 100 else 0.7,
                                        color='royalblue'
                                    ),
                                    line=dict(width=2, color='darkblue'),
                                    hoverinfo='text',
                                    hovertext=hover_texts,
                                    name=test_item_name,
                                    boxmean='sd'
                                ))

                                median_value = np.median(all_values)
                                fig_box.add_hline(
                                    y=median_value,
                                    line_dash="dot",
                                    line_color="green",
                                    annotation_text=f"中位数: {median_value:.2f}",
                                    annotation_position="top right"
                                )

                                fig_box.update_layout(
                                    title=f"{test_item_name} 箱线图 (共{len(all_values)}个有效点)",
                                    xaxis_title="测试项目",
                                    yaxis_title=f"{test_item_name} ({test_item_unit})",
                                    height=chart_height,
                                    showlegend=False,
                                    template='plotly_white',
                                    boxmode='overlay'
                                )

                                fig_box.update_xaxes(showticklabels=False)

                                st.plotly_chart(fig_box, use_container_width=True)
                                _render_unified_numeric_summary(all_values)
                            else:
                                st.warning("没有有效数据用于统计")

                        # ========== 推荐目标值统计表（位于统计摘要下方，格式同原目标值看板）==========
                        excluded_vehicle_ids = set()
                        if excluded_indices:
                            excluded_vehicle_ids = set(
                                comparison_df.loc[comparison_df['原始索引'].isin(excluded_indices), '车辆ID']
                            )
                        target_stats_df = _compute_target_value_stats_df(
                            filtered_df,
                            all_test_results,
                            all_test_items,
                            excluded_vehicle_ids,
                            min_weight,
                            max_weight,
                            selected_item_id=test_item_id,
                        )
                        _render_recommend_target_stats_table(target_stats_df)

                    # ========== 数据导出 ==========
                    st.markdown("---")
                    st.markdown("### 📥 数据导出")

                    col_exp1, col_exp2, col_exp3 = st.columns(3)

                    with col_exp1:
                        csv_data_clean = comparison_df_clean.drop(['显示索引', '原始索引'], axis=1).to_csv(index=False).encode('utf-8-sig')
                        st.download_button(
                            label="📊 导出清理后数据",
                            data=csv_data_clean,
                            file_name=f"清理后数据_{test_item_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                            mime="text/csv",
                            use_container_width=True
                        )

                    with col_exp2:
                        csv_data_original = comparison_df.drop(['显示索引', '原始索引'], axis=1).to_csv(index=False).encode('utf-8-sig')
                        st.download_button(
                            label="📊 导出原始数据",
                            data=csv_data_original,
                            file_name=f"原始数据_{test_item_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                            mime="text/csv",
                            use_container_width=True
                        )

                    with col_exp3:
                        _render_filtered_vehicles_export_col(filtered_df, test_item_id)

                    _render_filtered_vehicles_export_panel(filtered_df, test_item_id)
