# pages/report.py
"""
报告生成页面
"""
import streamlit as st
import pandas as pd
import os
import base64
from pathlib import Path
from datetime import datetime

from date_input_utils import (
    COMPACT_DATE_PLACEHOLDER,
    COMPACT_DATE_HELP,
    format_stored_date_for_input,
    validate_compact_date,
    validate_date_fields_in_mapping,
)

# 正确的导入：包含所有需要的函数
from database import (
    get_vehicles,
    get_vehicle_details,
    get_vehicle_test_results,  # 添加这一行
    get_all_test_items,        # 添加这一行
    get_main_categories,
    get_report_config,
    save_report_config,
    get_test_info_config,
    save_test_info_config,
    get_test_projects,
    save_test_projects,
    get_test_equipment,
    save_test_equipment,
    get_all_signature_images,
    save_signature_image,
    get_vehicle_test_data_for_report,
    get_test_info_config_batch,
    save_test_info_config_batch
)
from report_generator import generate_pdf_report
import config


def show_report_generation():
    """显示报告生成页面"""
    st.title("报告生成")

    vehicles = get_vehicles()

    if not vehicles:
        st.warning("⚠️ 请先添加车辆信息")
        return

    global_selected_id = st.session_state.get('global_selected_vehicle_id')

    vehicle_options = [
        f"{v[1]} | 底盘:{v[2]} | 质量:{v[3]} | 备注:{v[4]} (ID:{v[0]})"
        for v in vehicles
    ]

    default_index = 0
    if global_selected_id:
        for idx, option in enumerate(vehicle_options):
            if f"(ID:{global_selected_id})" in option:
                default_index = idx
                break

    def update_global_selection():
        selected_str = st.session_state.get("report_generation_vehicle_select")
        if selected_str and "(ID:" in selected_str:
            vehicle_id = selected_str.split("(ID:")[1].rstrip(")").strip()
            st.session_state['global_selected_vehicle_id'] = vehicle_id
            # 清除缓存
            if 'report_config_cache' in st.session_state:
                del st.session_state['report_config_cache']
            if 'test_info_batch_cache' in st.session_state:
                del st.session_state['test_info_batch_cache']

    selected_vehicle_str = st.selectbox(
        "选择要生成报告的车辆",
        vehicle_options,
        index=default_index,
        key="report_generation_vehicle_select",
        on_change=update_global_selection
    )

    if 'global_selected_vehicle_id' not in st.session_state and vehicles:
        st.session_state['global_selected_vehicle_id'] = vehicles[0][0]

    if not selected_vehicle_str:
        return

    # 提取车辆ID
    vehicle_id = selected_vehicle_str.split("(ID:")[1].rstrip(")").strip()

    # 提取车型
    model = selected_vehicle_str.split(" | ")[0]

    # 提取底盘号
    import re
    chassis_match = re.search(r'底盘:([^|]*)', selected_vehicle_str)
    chassis = chassis_match.group(1).strip() if chassis_match else ""

    st.subheader("报告配置")

    tab1, tab2, tab3, tab4 = st.tabs(["📄 封面配置", "🔍 试验一览", "📋 试验项目", "📊 测试信息"])

    with tab1:
        st.markdown('<div class="config-box">', unsafe_allow_html=True)
        st.subheader("封面配置")

        saved_header_config = get_report_config(vehicle_id, 'header')

        col1, col2 = st.columns(2)

        with col1:
            if saved_header_config:
                default_report_number = saved_header_config.get('编号', "SY-GCYZ-ZC-2025-147")
                default_report_name = saved_header_config.get('名称', f"{model}性能试验")
            else:
                default_report_number = "SY-GCYZ-ZC-2025-147"
                default_report_name = f"{model}性能试验"

            report_number = st.text_input(
                "编号",
                value=default_report_number,
                key=f"report_number_{vehicle_id}"
            )
            report_name = st.text_input(
                "名称",
                value=default_report_name,
                key=f"report_name_{vehicle_id}"
            )

        st.markdown('</div>', unsafe_allow_html=True)

        st.markdown('<div class="signature-box">', unsafe_allow_html=True)
        st.subheader("签名配置")

        saved_signatures = get_all_signature_images(vehicle_id)

        col1, col2, col3, col4 = st.columns(4)

        signature_config = {}

        prepared_date = format_stored_date_for_input(
            saved_header_config.get('编制日期', '') if saved_header_config else '')
        proofread_date = format_stored_date_for_input(
            saved_header_config.get('校对日期', '') if saved_header_config else '')
        review_date = format_stored_date_for_input(
            saved_header_config.get('审核日期', '') if saved_header_config else '')
        approve_date = format_stored_date_for_input(
            saved_header_config.get('批准日期', '') if saved_header_config else '')

        with col1:
            st.markdown("**编制**")
            if '编制签名' in saved_signatures:
                signature_path = saved_signatures['编制签名']['path']
                if Path(signature_path).exists():
                    try:
                        st.image(signature_path, width=80, caption="当前签名")
                    except:
                        st.info("签名图片加载失败")
                else:
                    st.info("签名文件不存在")

            prepared_signature = st.file_uploader(
                "上传新签名",
                type=['jpg', 'jpeg', 'png'],
                key=f"prepared_signature_{vehicle_id}",
                help="上传新的签名图片将替换原有签名"
            )
            prepared_date = st.text_input(
                "编制日期",
                value=prepared_date,
                key=f"prepared_date_{vehicle_id}",
                placeholder=COMPACT_DATE_PLACEHOLDER,
                help=COMPACT_DATE_HELP,
            )
            if prepared_signature:
                signature_config['编制签名'] = prepared_signature

        with col2:
            st.markdown("**校对**")
            if '校对签名' in saved_signatures:
                signature_path = saved_signatures['校对签名']['path']
                if Path(signature_path).exists():
                    try:
                        st.image(signature_path, width=80, caption="当前签名")
                    except:
                        st.info("签名图片加载失败")
                else:
                    st.info("签名文件不存在")

            proofread_signature = st.file_uploader(
                "上传新签名",
                type=['jpg', 'jpeg', 'png'],
                key=f"proofread_signature_{vehicle_id}",
                help="上传新的签名图片将替换原有签名"
            )
            proofread_date = st.text_input(
                "校对日期",
                value=proofread_date,
                key=f"proofread_date_{vehicle_id}",
                placeholder=COMPACT_DATE_PLACEHOLDER,
                help=COMPACT_DATE_HELP,
            )
            if proofread_signature:
                signature_config['校对签名'] = proofread_signature

        with col3:
            st.markdown("**审核**")
            if '审核签名' in saved_signatures:
                signature_path = saved_signatures['审核签名']['path']
                if Path(signature_path).exists():
                    try:
                        st.image(signature_path, width=80, caption="当前签名")
                    except:
                        st.info("签名图片加载失败")
                else:
                    st.info("签名文件不存在")

            review_signature = st.file_uploader(
                "上传新签名",
                type=['jpg', 'jpeg', 'png'],
                key=f"review_signature_{vehicle_id}",
                help="上传新的签名图片将替换原有签名"
            )
            review_date = st.text_input(
                "审核日期",
                value=review_date,
                key=f"review_date_{vehicle_id}",
                placeholder=COMPACT_DATE_PLACEHOLDER,
                help=COMPACT_DATE_HELP,
            )
            if review_signature:
                signature_config['审核签名'] = review_signature

        with col4:
            st.markdown("**批准**")
            if '批准签名' in saved_signatures:
                signature_path = saved_signatures['批准签名']['path']
                if Path(signature_path).exists():
                    try:
                        st.image(signature_path, width=80, caption="当前签名")
                    except:
                        st.info("签名图片加载失败")
                else:
                    st.info("签名文件不存在")

            approve_signature = st.file_uploader(
                "上传新签名",
                type=['jpg', 'jpeg', 'png'],
                key=f"approve_signature_{vehicle_id}",
                help="上传新的签名图片将替换原有签名"
            )
            approve_date = st.text_input(
                "批准日期",
                value=approve_date,
                key=f"approve_date_{vehicle_id}",
                placeholder=COMPACT_DATE_PLACEHOLDER,
                help=COMPACT_DATE_HELP,
            )
            if approve_signature:
                signature_config['批准签名'] = approve_signature

        col1, col2, col3 = st.columns([1, 1, 2])
        with col1:
            if st.button(
                    "💾 保存签名配置",
                    key=f"save_signature_config_{vehicle_id}",
                    use_container_width=True
            ):
                header_config = {
                    '编号': report_number,
                    '名称': report_name,
                    '编制日期': prepared_date,
                    '校对日期': proofread_date,
                    '审核日期': review_date,
                    '批准日期': approve_date
                }
                ok, errors, header_config = validate_date_fields_in_mapping(header_config)
                if not ok:
                    for err in errors:
                        st.error(err)
                else:
                    save_report_config(vehicle_id, 'header', header_config)

                    signature_types = {
                        '编制签名': prepared_signature,
                        '校对签名': proofread_signature,
                        '审核签名': review_signature,
                        '批准签名': approve_signature
                    }

                    saved_count = 0
                    for sig_type, sig_file in signature_types.items():
                        if sig_file:
                            success, message = save_signature_image(vehicle_id, sig_type, sig_file)
                            if success:
                                saved_count += 1
                            else:
                                st.warning(f"{sig_type}保存失败：{message}")

                    if saved_count > 0:
                        st.success(f"✅ 签名配置已保存！成功保存{saved_count}个签名图片")
                    else:
                        st.success("✅ 签名日期配置已保存（未更新签名图片）")

                    st.balloons()
                    st.rerun()

        st.markdown('</div>', unsafe_allow_html=True)

    with tab2:
        st.markdown('<div class="config-box">', unsafe_allow_html=True)
        st.subheader("试验一览配置")

        saved_overview_config = get_report_config(vehicle_id, 'overview')

        st.markdown("### 📊 测试项目统计")

        test_results = get_vehicle_test_results(vehicle_id)

        if test_results:
            main_category_stats = {}
            total_valid_items = 0

            for result in test_results:
                main_category = result[6]
                test_value = result[1]

                is_valid = test_value is not None and str(test_value).strip() != ""

                if main_category not in main_category_stats:
                    main_category_stats[main_category] = 0

                if is_valid:
                    main_category_stats[main_category] += 1
                    total_valid_items += 1

            if main_category_stats:
                category_order = config.MAIN_CATEGORY_ORDER

                sorted_stats = []

                for category in category_order:
                    if category in main_category_stats and main_category_stats[category] > 0:
                        sorted_stats.append((category, main_category_stats[category]))

                other_categories = sorted([c for c in main_category_stats.keys()
                                           if c not in category_order and main_category_stats[c] > 0])

                for category in other_categories:
                    sorted_stats.append((category, main_category_stats[category]))

                stats_text = f"试验共完成{total_valid_items}个测试项目，其中"

                stats_items = []
                for category, count in sorted_stats:
                    stats_items.append(f"{category}{count}项")

                if stats_items:
                    stats_text += "，".join(stats_items)
                else:
                    stats_text += "暂无有效测试数据"

                st.info(f"📈 **{stats_text}**")
            else:
                st.info("暂无测试数据统计信息")
        else:
            st.info("该车辆暂无测试数据")

        st.markdown("---")

        col1, col2 = st.columns(2)

        with col1:
            test_purpose = st.text_area(
                "试验目的",
                value=saved_overview_config.get('试验目的', ''),
                key=f"test_purpose_{vehicle_id}",
                height=60
            )
            task_source = st.text_input(
                "任务来源",
                value=saved_overview_config.get('任务来源', ''),
                key=f"task_source_{vehicle_id}"
            )
            project_cost = st.text_input(
                "项目费用",
                value=saved_overview_config.get('项目费用', ''),
                key=f"project_cost_{vehicle_id}"
            )
            chassis_number = st.text_input(
                "底盘号",
                value=chassis,
                key=f"chassis_number_{vehicle_id}",
                disabled=True
            )
            engine_model = st.text_input(
                "发动机型号",
                value=saved_overview_config.get('发动机型号', ''),
                key=f"engine_model_{vehicle_id}"
            )

        with col2:
            box_type = st.text_input(
                "车厢类型",
                value=saved_overview_config.get('车厢类型', ''),
                key=f"box_type_{vehicle_id}"
            )
            gvw = st.text_input(
                "GVW（kg）",
                value=saved_overview_config.get('GVW（kg）', ''),
                key=f"gvw_{vehicle_id}"
            )
            tire_pressure = st.text_input(
                "胎压（Kpa）",
                value=saved_overview_config.get('胎压（Kpa）', ''),
                key=f"tire_pressure_{vehicle_id}"
            )
            break_in_mileage = st.text_input(
                "磨合行驶里程（km）",
                value=saved_overview_config.get('磨合行驶里程（km）', ''),
                key=f"break_in_mileage_{vehicle_id}"
            )
            receive_time = st.text_input(
                "接车时间",
                value=format_stored_date_for_input(saved_overview_config.get('接车时间', '')),
                key=f"receive_time_{vehicle_id}",
                placeholder=COMPACT_DATE_PLACEHOLDER,
                help=COMPACT_DATE_HELP,
            )
            complete_time = st.text_input(
                "完成时间",
                value=format_stored_date_for_input(saved_overview_config.get('完成时间', '')),
                key=f"complete_time_{vehicle_id}",
                placeholder=COMPACT_DATE_PLACEHOLDER,
                help=COMPACT_DATE_HELP,
            )

        st.markdown("---")
        st.subheader("试验结论")

        saved_conclusion = saved_overview_config.get('试验结论', '')

        test_conclusion = st.text_area(
            "",
            value=saved_conclusion,
            height=80,
            key=f"test_conclusion_{vehicle_id}",
            help="请在此填写完整的试验结论"
        )

        col1, col2, col3 = st.columns([1, 1, 2])
        with col1:
            if st.button(
                    "💾 保存试验一览配置",
                    key=f"save_overview_config_{vehicle_id}",
                    use_container_width=True
            ):
                overview_config = {
                    '试验目的': test_purpose,
                    '任务来源': task_source,
                    '项目费用': project_cost,
                    '车型号': model,
                    '发动机型号': engine_model,
                    '底盘号': chassis,
                    '车厢类型': box_type,
                    'GVW（kg）': gvw,
                    '胎压（Kpa）': tire_pressure,
                    '磨合行驶里程（km）': break_in_mileage,
                    '接车时间': receive_time,
                    '完成时间': complete_time,
                    '试验结论': test_conclusion
                }
                ok, errors, overview_config = validate_date_fields_in_mapping(overview_config)
                if not ok:
                    for err in errors:
                        st.error(err)
                else:
                    save_report_config(vehicle_id, 'overview', overview_config)
                    st.success("✅ 试验一览配置已保存！")
                    st.balloons()
                    st.rerun()

        st.markdown('</div>', unsafe_allow_html=True)

    with tab3:
        st.markdown('<div class="config-box">', unsafe_allow_html=True)
        st.subheader("试验项目配置")

        projects_reset_key = f"projects_reset_{vehicle_id}"

        if projects_reset_key not in st.session_state:
            st.session_state[projects_reset_key] = 0

        existing_projects = get_test_projects(vehicle_id)

        if not existing_projects:
            existing_projects = [
                {'序号': 1, '项目名称': '参数测量', '执行标准': 'GB/T 12674 汽车质量（重量）参数测定方法'},
                {'序号': 2, '项目名称': '动力性试验', '执行标准': 'GB/T12543 汽车加速性能试验方法'},
                {'序号': 3, '项目名称': '油耗试验', '执行标准': 'JT719-2008 营运货车燃料消耗量限值及测量方法'},
                {'序号': 4, '项目名称': '制动试验', '执行标准': 'GB/T12676 商用车辆和挂车制动系统技术要求及试验方法'},
                {'序号': 5, '项目名称': '滑行试验', '执行标准': 'GB/T27840 商用车燃料消耗量测量方法'},
                {'序号': 6, '项目名称': '操纵稳定性试验', '执行标准': 'GB/T6323 汽车操纵稳定性试验方法'},
                {'序号': 7, '项目名称': '灯光试验', '执行标准': 'X001 LED远近光灯测试与评价方法'},
                {'序号': 8, '项目名称': '选换挡试验', '执行标准': 'X002 选换挡操纵性试验规范'}
            ]

        projects_df = pd.DataFrame(existing_projects)

        edited_projects_df = st.data_editor(
            projects_df,
            use_container_width=True,
            num_rows="dynamic",
            hide_index=True,
            column_config={
                "序号": st.column_config.NumberColumn(
                    "序号",
                    help="项目序号（手工输入，可为任意正整数，可不连续）",
                    min_value=0,
                    step=1,
                    required=True,
                    format="%d"
                ),
                "项目名称": st.column_config.TextColumn(
                    "项目名称",
                    help="试验项目名称",
                    required=True
                ),
                "执行标准": st.column_config.TextColumn(
                    "执行标准",
                    help="执行标准编号和名称"
                )
            },
            key=f"projects_editor_{vehicle_id}_{st.session_state[projects_reset_key]}"
        )

        col1, col2 = st.columns([1, 3])
        with col1:
            if st.button(f"💾 保存试验项目", key=f"save_projects_{vehicle_id}"):
                try:
                    if edited_projects_df.empty:
                        st.error("⚠️ 表格不能为空")
                        return

                    invalid_rows = []
                    for idx, row in edited_projects_df.iterrows():
                        try:
                            project_number = int(row['序号'])
                            if project_number <= 0:
                                invalid_rows.append((idx + 1, "序号必须为正整数"))
                        except:
                            invalid_rows.append((idx + 1, "序号必须是数字"))

                        if not str(row['项目名称']).strip():
                            invalid_rows.append((idx + 1, "项目名称不能为空"))

                    if invalid_rows:
                        error_msg = "发现以下问题：\n"
                        for row_num, error in invalid_rows:
                            error_msg += f"  第{row_num}行：{error}\n"
                        st.error(error_msg)
                        return

                    projects_data = []
                    for idx, row in edited_projects_df.iterrows():
                        projects_data.append({
                            '序号': int(row['序号']),
                            '项目名称': str(row['项目名称']).strip(),
                            '执行标准': str(row['执行标准']) if pd.notna(row['执行标准']) else ''
                        })

                    save_test_projects(vehicle_id, projects_data)
                    st.success("✅ 试验项目保存成功！")
                    st.balloons()
                    st.session_state[projects_reset_key] += 1
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ 保存失败：{str(e)}")

        with col2:
            if st.button("🔄 重新加载", key=f"reload_projects_{vehicle_id}"):
                st.session_state[projects_reset_key] += 1
                st.rerun()

        st.markdown("---")
        st.subheader("试验设备及设备精度配置")

        equipment_reset_key = f"equipment_reset_{vehicle_id}"

        if equipment_reset_key not in st.session_state:
            st.session_state[equipment_reset_key] = 0

        existing_equipment = get_test_equipment(vehicle_id)

        if not existing_equipment:
            existing_equipment = [
                {'序号': 1, '设备名称': 'Vbox', '设备精度': '车速≤0.1km/h、距离精度0.05%、时间精度0.01s'},
                {'序号': 2, '设备名称': '油耗仪', '设备精度': '精度0.5%FS'},
                {'序号': 3, '设备名称': '陀螺仪', '设备精度': '方向盘力矩精度0.05%RO、方向盘转角精度0.01°'},
                {'序号': 4, '设备名称': '踏板力计', '设备精度': '精度0.5%FS'},
                {'序号': 5, '设备名称': '轮荷仪', '设备精度': '精度0.2%FS'},
                {'序号': 6, '设备名称': '选换挡', '设备精度': '精度0.5%FS'}
            ]

        equipment_df = pd.DataFrame(existing_equipment)
        equipment_df = equipment_df[['序号', '设备名称', '设备精度']]

        edited_equipment_df = st.data_editor(
            equipment_df,
            use_container_width=True,
            num_rows="dynamic",
            hide_index=True,
            column_config={
                "序号": st.column_config.NumberColumn(
                    "序号",
                    help="设备显示顺序（手工输入，可为任意正整数，可不连续）",
                    min_value=0,
                    step=1,
                    required=True,
                    format="%d"
                ),
                "设备名称": st.column_config.TextColumn(
                    "设备名称",
                    help="试验设备名称",
                    required=True
                ),
                "设备精度": st.column_config.TextColumn(
                    "设备精度",
                    help="设备精度说明"
                )
            },
            key=f"equipment_editor_{vehicle_id}_{st.session_state[equipment_reset_key]}"
        )

        col1, col2 = st.columns([1, 3])
        with col1:
            if st.button(f"💾 保存试验设备", key=f"save_equipment_{vehicle_id}"):
                try:
                    if edited_equipment_df.empty:
                        st.error("⚠️ 表格不能为空")
                        return

                    invalid_rows = []
                    for idx, row in edited_equipment_df.iterrows():
                        try:
                            equipment_number = int(row['序号'])
                            if equipment_number <= 0:
                                invalid_rows.append((idx + 1, "序号必须为正整数"))
                        except:
                            invalid_rows.append((idx + 1, "序号必须是数字"))

                        if not str(row['设备名称']).strip():
                            invalid_rows.append((idx + 1, "设备名称不能为空"))

                    if invalid_rows:
                        error_msg = "发现以下问题：\n"
                        for row_num, error in invalid_rows:
                            error_msg += f"  第{row_num}行：{error}\n"
                        st.error(error_msg)
                        return

                    equipment_data = []
                    for idx, row in edited_equipment_df.iterrows():
                        equipment_data.append({
                            '序号': int(row['序号']),
                            '设备名称': str(row['设备名称']).strip(),
                            '设备精度': str(row['设备精度']) if pd.notna(row['设备精度']) else ''
                        })

                    save_test_equipment(vehicle_id, equipment_data)
                    st.success("✅ 试验设备保存成功！")
                    st.balloons()
                    st.session_state[equipment_reset_key] += 1
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ 保存失败：{str(e)}")

        with col2:
            if st.button("🔄 重新加载", key=f"reload_equipment_{vehicle_id}"):
                st.session_state[equipment_reset_key] += 1
                st.rerun()

        st.markdown('</div>', unsafe_allow_html=True)

    with tab4:
        st.markdown('<div class="config-box">', unsafe_allow_html=True)
        st.subheader("📊 测试信息配置")
        st.info("💡 在表格中为每个一级项目填写测试信息，可直接在Excel风格的表格中编辑")

        # 使用新函数批量获取配置
        batch_configs = get_test_info_config_batch(vehicle_id)

        # 转换为DataFrame用于显示
        df_data = []
        for row in batch_configs:
            df_row = {
                '一级项目': row.get('main_category', ''),
                '试验日期': format_stored_date_for_input(row.get('试验日期', '')),
                '总质量（kg）': row.get('总质量（kg）', ''),
                '试验地点': row.get('试验地点', ''),
                '天气': row.get('天气', ''),
                '里程（km）': row.get('里程（km）', ''),
                '备注': row.get('备注', '')
            }
            df_data.append(df_row)

        df = pd.DataFrame(df_data)

        # 创建重置键
        test_info_reset_key = f"test_info_editor_reset_{vehicle_id}"
        if test_info_reset_key not in st.session_state:
            st.session_state[test_info_reset_key] = 0

        # 改进复制粘贴功能
        st.markdown("#### ✏️ 测试信息编辑表格")
        st.caption(
            "双击单元格进行编辑，支持Excel复制粘贴；试验日期须为8位数字 YYYYMMDD（如 20260506）")

        # 添加复制粘贴提示
        with st.expander("📋 Excel复制粘贴使用说明", expanded=False):
            st.markdown("""
            ### 📝 Excel批量编辑技巧

            **从表格复制到Excel：**
            1. 点击表格左上角的全选按钮（或按 `Ctrl+A` 全选）
            2. 按 `Ctrl+C` 复制
            3. 在Excel中按 `Ctrl+V` 粘贴

            **从Excel粘贴到表格：**
            1. 在Excel中选中要复制的数据区域（**注意：不要复制"一级项目"列**）
            2. 按 `Ctrl+C` 复制
            3. 在表格中点击**起始单元格**（如第一个"试验日期"单元格）
            4. 按 `Ctrl+V` 粘贴

            **注意事项：**
            - 确保复制的列顺序与表格列顺序一致：试验日期、总质量（kg）、试验地点、天气、里程（km）、备注
            - "一级项目"列是只读的，不可编辑
            - 粘贴后会自动填充对应行，超出行数的数据会被忽略
            """)

        # 使用st.data_editor并启用复制粘贴
        edited_df = st.data_editor(
            df,
            use_container_width=True,
            num_rows="fixed",  # 固定行数，对应一级项目数量
            hide_index=True,
            column_config={
                "一级项目": st.column_config.TextColumn(
                    "一级项目",
                    help="一级测试项目类别",
                    disabled=True,  # 不允许编辑
                    width="medium"
                ),
                "试验日期": st.column_config.TextColumn(
                    "试验日期",
                    help=COMPACT_DATE_HELP,
                    width="small"
                ),
                "总质量（kg）": st.column_config.TextColumn(
                    "总质量（kg）",
                    help="试验时总质量",
                    width="small"
                ),
                "试验地点": st.column_config.TextColumn(
                    "试验地点",
                    help="试验地点",
                    width="small"
                ),
                "天气": st.column_config.TextColumn(
                    "天气",
                    help="天气状况",
                    width="small"
                ),
                "里程（km）": st.column_config.TextColumn(
                    "里程（km）",
                    help="试验里程",
                    width="small"
                ),
                "备注": st.column_config.TextColumn(
                    "备注",
                    help="其他说明",
                    width="medium"
                )
            },
            key=f"test_info_editor_{vehicle_id}_{st.session_state[test_info_reset_key]}"
        )

        # 操作按钮
        col1, col2, col3 = st.columns([1, 1, 3])
        with col1:
            if st.button("💾 保存所有配置", key=f"save_test_info_batch_{vehicle_id}", use_container_width=True):
                try:
                    # 构建批量保存数据
                    save_data = []
                    for idx, row in edited_df.iterrows():
                        save_data.append({
                            'main_category': row['一级项目'],
                            '试验日期': str(row.get('试验日期', '')).strip(),
                            '总质量（kg）': str(row.get('总质量（kg）', '')).strip(),
                            '试验地点': str(row.get('试验地点', '')).strip(),
                            '天气': str(row.get('天气', '')).strip(),
                            '里程（km）': str(row.get('里程（km）', '')).strip(),
                            '备注': str(row.get('备注', '')).strip()
                        })

                    # 调用批量保存函数
                    success, message = save_test_info_config_batch(vehicle_id, save_data)

                    if success:
                        st.success(f"✅ {message}")
                        st.balloons()
                        st.rerun()
                    else:
                        st.error(f"❌ {message}")
                except Exception as e:
                    st.error(f"❌ 保存失败：{str(e)}")

        with col2:
            if st.button("🔄 重新加载", key=f"reload_test_info_{vehicle_id}", use_container_width=True):
                st.rerun()

        # 已填写的测试数据预览
        st.markdown("---")
        st.markdown("### 📋 已填写的测试数据预览")

        # 从测试结果表获取该车辆的所有测试数据
        try:
            # 获取该车辆的所有测试结果
            test_results = get_vehicle_test_results(vehicle_id)

            # 筛选出有效数据（非空值）
            valid_test_data = []
            for result in test_results:
                # result格式: (test_item_id, value, test_date, name, unit, sub_category, main_category)
                test_value = result[1]
                # 检查是否为有效数据：非空、非空白字符串
                if test_value is not None and str(test_value).strip() != "":
                    valid_test_data.append({
                        '测试大类': result[6],
                        '二级目录': result[5],
                        '测试项目': result[3],
                        '单位': result[4],
                        '测试值': result[1],
                        '测试日期': result[2] if len(result) > 2 else ''
                    })

            # 显示预览表格
            if valid_test_data:
                # 转换为DataFrame显示
                preview_df = pd.DataFrame(valid_test_data)
                st.dataframe(
                    preview_df,
                    use_container_width=True,
                    height=min(400, len(valid_test_data) * 35 + 38),
                    hide_index=True
                )

                # 显示简单的统计信息
                col_stat1, col_stat2 = st.columns(2)
                with col_stat1:
                    st.metric("有效数据数量", len(valid_test_data))
                with col_stat2:
                    all_items = get_all_test_items()
                    completion_rate = len(valid_test_data) / len(all_items) * 100 if all_items else 0
                    st.metric("数据完整率", f"{completion_rate:.1f}%")
            else:
                st.info("该车辆暂无有效测试数据")

        except Exception as e:
            st.warning(f"无法加载测试数据预览: {str(e)}")

        st.markdown('</div>', unsafe_allow_html=True)

        # 在测试信息页面下方添加生成PDF报告按钮
        st.markdown("---")

        if st.button("🚀 生成PDF报告", type="primary", use_container_width=True, key=f"generate_report_{vehicle_id}"):
            with st.spinner("正在生成PDF报告..."):
                try:
                    saved_header_config = get_report_config(vehicle_id, 'header')
                    saved_overview_config = get_report_config(vehicle_id, 'overview')
                    saved_signatures = get_all_signature_images(vehicle_id)

                    # 获取封面配置中的值
                    report_number = saved_header_config.get('编号', "SY-GCYZ-ZC-2025-147")
                    report_name = saved_header_config.get('名称', f"{model}性能试验")
                    prepared_date = saved_header_config.get('编制日期', '')
                    proofread_date = saved_header_config.get('校对日期', '')
                    review_date = saved_header_config.get('审核日期', '')
                    approve_date = saved_header_config.get('批准日期', '')

                    # 获取试验一览配置中的值
                    test_purpose = saved_overview_config.get('试验目的', '')
                    task_source = saved_overview_config.get('任务来源', '')
                    project_cost = saved_overview_config.get('项目费用', '')
                    engine_model = saved_overview_config.get('发动机型号', '')
                    box_type = saved_overview_config.get('车厢类型', '')
                    gvw = saved_overview_config.get('GVW（kg）', '')
                    tire_pressure = saved_overview_config.get('胎压（Kpa）', '')
                    break_in_mileage = saved_overview_config.get('磨合行驶里程（km）', '')
                    receive_time = saved_overview_config.get('接车时间', '')
                    complete_time = saved_overview_config.get('完成时间', '')
                    test_conclusion = saved_overview_config.get('试验结论', '')

                    config_data = {
                        'header': {
                            '编号': report_number,
                            '名称': report_name,
                            '编制日期': prepared_date,
                            '校对日期': proofread_date,
                            '审核日期': review_date,
                            '批准日期': approve_date
                        },
                        'overview': {
                            '试验目的': test_purpose,
                            '任务来源': task_source,
                            '项目费用': project_cost,
                            '车型号': model,
                            '发动机型号': engine_model,
                            '底盘号': chassis,
                            '车厢类型': box_type,
                            'GVW（kg）': gvw,
                            '胎压（Kpa）': tire_pressure,
                            '磨合行驶里程（km）': break_in_mileage,
                            '接车时间': receive_time,
                            '完成时间': complete_time,
                            '试验结论': test_conclusion
                        },
                        'signatures': saved_signatures
                    }

                    # 构建测试信息数据（使用 batch_configs）
                    test_info_data = {}
                    for row in batch_configs:
                        cat_name = row.get('main_category')
                        test_info_data[cat_name] = {
                            '试验日期': format_stored_date_for_input(row.get('试验日期', '')),
                            '试验地点': row.get('试验地点', ''),
                            '里程（km）': row.get('里程（km）', ''),
                            '总质量（kg）': row.get('总质量（kg）', ''),
                            '天气': row.get('天气', ''),
                            '备注': row.get('备注', '')
                        }

                    # 调用生成报告函数
                    try:
                        report_path = generate_pdf_report(vehicle_id, config_data, test_info_data)

                        if report_path and Path(report_path).exists():
                            with open(report_path, "rb") as f:
                                pdf_content = f.read()

                            st.success("✅ PDF报告生成成功！")

                            st.download_button(
                                label="📥 下载PDF报告",
                                data=pdf_content,
                                file_name=Path(report_path).name,
                                mime="application/pdf",
                                use_container_width=True,
                                key=f"download_report_{vehicle_id}"
                            )

                            st.info(f"文件位置: `{report_path}`")
                            st.info(f"文件大小: {Path(report_path).stat().st_size / 1024:.1f} KB")
                            st.balloons()
                        else:
                            st.error("❌ PDF报告生成失败：未知错误")

                    except Exception as e:
                        error_msg = str(e)
                        st.error(f"❌ PDF报告生成失败")
                        with st.expander("🔍 查看错误详情"):
                            st.markdown(f"**错误信息**: {error_msg}")
                            if "测试数据" in error_msg:
                                st.warning("💡 请先在【测试数据录入】中上传测试数据")
                            elif "字体" in error_msg:
                                st.warning("💡 请检查字体文件配置")

                except Exception as e:
                    st.error(f"❌ 生成报告过程发生异常")
                    with st.expander("🔍 查看异常详情"):
                        st.code(str(e))