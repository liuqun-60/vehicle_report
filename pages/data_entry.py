# pages/data_entry.py
"""
测试数据录入页面
"""
import streamlit as st
import pandas as pd
from datetime import datetime

# 正确的导入：从具体的数据库模块文件导入函数
from database.core import (
    get_vehicles, get_vehicle_details, get_vehicle_test_results,
    get_all_test_items, get_report_config
)
from database.exports import (
    export_test_template, export_multiple_vehicles_data
)
from database.imports import (
    import_test_data, import_multiple_vehicles_from_csv
)


def show_data_entry():
    """显示测试数据录入页面"""
    st.title("测试数据录入")

    vehicles = get_vehicles()

    if not vehicles:
        st.warning("⚠️ 请先添加车辆信息")
        st.info("请在左侧菜单选择【车辆管理】→【新建车辆】")
        return

    # ========== 全局车辆选择状态管理 ==========
    # 获取当前全局选择的车辆ID
    global_selected_id = st.session_state.get('global_selected_vehicle_id')

    vehicle_options = [
        f"{v[1]} | 底盘:{v[2]} | 质量:{v[3]} | 备注:{v[4]} (ID:{v[0]})"
        for v in vehicles
    ]

    # 计算默认选项索引
    default_index = 0
    if global_selected_id:
        for idx, option in enumerate(vehicle_options):
            if f"(ID:{global_selected_id})" in option:
                default_index = idx
                break

    # 定义更新全局状态的函数
    def update_global_selection():
        # 使用固定key而不是f-string
        selected_str = st.session_state.get("data_entry_vehicle_select")
        if selected_str and "(ID:" in selected_str:
            vehicle_id = selected_str.split("(ID:")[1].rstrip(")").strip()
            st.session_state['global_selected_vehicle_id'] = vehicle_id

    # 显示选择框
    selected_vehicle_str = st.selectbox(
        "选择车辆",
        vehicle_options,
        index=default_index,
        key="data_entry_vehicle_select",  # 唯一key
        on_change=update_global_selection
    )

    # 如果session_state中没有全局选择，设置第一个车辆
    if 'global_selected_vehicle_id' not in st.session_state and vehicles:
        st.session_state['global_selected_vehicle_id'] = vehicles[0][0]

    # 解析选择的车辆
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
    # ========== 全局车辆选择状态管理结束 ==========

    tab1, tab2, tab3, tab4 = st.tabs(["📥 下载模板", "📤 上传数据", "📊 多车导出", "🚀 批量导入"])

    with tab1:
        st.subheader("下载测试模板")

        # 显示简单说明
        st.info("📄 模板包含该车辆所有已有测试数据，上传后会完全覆盖原有数据")

        # 获取车辆信息
        vehicle_info = get_vehicle_details(vehicle_id)
        model = vehicle_info['model'] if vehicle_info else "未知车型"
        chassis = vehicle_info['chassis_number'] if vehicle_info else "未知底盘号"

        # 获取测试结果，并统计有效数据（非空值）
        test_results = get_vehicle_test_results(vehicle_id)

        # 统计有效数据（非空值）
        valid_test_results = []
        for result in test_results:
            # result格式: (test_item_id, value, test_date, name, unit, sub_category, main_category)
            test_value = result[1]
            # 检查是否为有效数据：非空、非空白字符串
            if test_value is not None and str(test_value).strip() != "":
                valid_test_results.append(result)

        all_items = get_all_test_items()

        # 显示统计信息
        col1, col2 = st.columns(2)
        with col1:
            st.metric("总项目数", len(all_items))
        with col2:
            st.metric("有效数据", len(valid_test_results))

        # 直接下载按钮
        if st.button("📥 下载CSV模板（带已有数据）", use_container_width=True):
            try:
                csv_data = export_test_template(vehicle_id)

                st.download_button(
                    label="点击下载",
                    data=csv_data,
                    file_name=f"测试模板_{model}_{chassis}.csv",
                    mime="text/csv",
                    use_container_width=True
                )

            except Exception as e:
                st.error(f"下载失败：{str(e)}")

    with tab2:
        st.subheader("上传测试数据")

        uploaded_file = st.file_uploader(
            "选择填写好的CSV文件",
            type=['csv'],
            key="upload_test_data"
        )

        if uploaded_file is not None:
            st.info(f"📄 文件: {uploaded_file.name} ({uploaded_file.size / 1024:.1f} KB)")

            # 显示文件预览
            if st.button("预览文件内容", key="preview_test_data"):
                try:
                    # 尝试读取文件
                    uploaded_file.seek(0)
                    try:
                        content = uploaded_file.read().decode('utf-8-sig')
                    except:
                        uploaded_file.seek(0)
                        content = uploaded_file.read().decode('gbk')

                    # 显示前10行
                    lines = content.split('\n')[:11]
                    st.text_area("文件预览（前10行）", '\n'.join(lines), height=150)
                except Exception as e:
                    st.error(f"读取失败: {str(e)}")

            # 上传按钮
            if st.button("📤 上传测试数据", type="primary", use_container_width=True):
                with st.spinner("正在导入测试数据..."):
                    uploaded_file.seek(0)
                    csv_content = uploaded_file.read()

                    success, message = import_test_data(vehicle_id, csv_content)

                    if success:
                        st.success(f"✅ {message}")

                        # 重新获取测试结果并统计有效数据
                        test_results = get_vehicle_test_results(vehicle_id)
                        valid_test_results = []
                        for result in test_results:
                            test_value = result[1]
                            if test_value is not None and str(test_value).strip() != "":
                                valid_test_results.append(result)

                        all_items = get_all_test_items()
                        completion_rate = len(valid_test_results) / len(all_items) * 100 if all_items else 0

                        col1, col2 = st.columns(2)
                        with col1:
                            st.metric("有效测试数据", len(valid_test_results))
                        with col2:
                            st.metric("完成率", f"{completion_rate:.1f}%")
                    else:
                        if "冻结" in message or "frozen" in message.lower():
                            st.markdown("""
                                        <div class="frozen-error-box">
                                            <h4>🔒 车辆已冻结</h4>
                                            <p>该车辆数据已被冻结，无法导入测试数据。如需修改请联系管理员解冻！</p>
                                        </div>
                                        """, unsafe_allow_html=True)
                        else:
                            st.error(f"❌ {message}")

        # 显示当前数据
        st.markdown("---")
        st.subheader("当前测试数据")

        test_results = get_vehicle_test_results(vehicle_id)

        # 只显示有效数据
        valid_test_data = []
        for item in test_results:
            # item格式: (test_item_id, value, test_date, name, unit, sub_category, main_category)
            test_value = item[1]
            if test_value is not None and str(test_value).strip() != "":
                valid_test_data.append({
                    '测试大类': item[6],
                    '二级目录': item[5],
                    '测试项目': item[3],
                    '单位': item[4],
                    '测试值': item[1],
                    '测试日期': item[2]
                })

        if valid_test_data:
            # 转换为DataFrame显示
            preview_df = pd.DataFrame(valid_test_data)
            st.dataframe(preview_df, use_container_width=True, height=300)

            # 显示统计信息
            col1, col2 = st.columns(2)
            with col1:
                st.metric("有效数据数量", len(valid_test_data))
            with col2:
                all_items = get_all_test_items()
                completion_rate = len(valid_test_data) / len(all_items) * 100 if all_items else 0
                st.metric("数据完整率", f"{completion_rate:.1f}%")
        else:
            st.info("该车辆暂无有效测试数据")

    with tab3:
        st.markdown('<div class="export-box">', unsafe_allow_html=True)
        st.subheader("多车数据导出")
        # ========== 明确功能用途 ==========
        st.warning("🔍 **主要用途：为批量导入准备数据模板**")
        st.info("""
        💡 **功能说明：**

        **主要用途：**
        1. 导出多辆车的数据，作为批量导入的模板
        2. 保持数据结构和格式的一致性
        3. 方便在Excel中编辑和填充数据

        **导出格式特点：**
        - **第1行（表头）**：A-F列为固定结构（项目ID、序号、一级目录、二级目录、测试项目、单位）
        - **从G列开始**：每列对应一辆车，表头为该车的**车型**
        - **车辆信息行（共5行）**：
          - 第2行：车辆ID（唯一标识，用于数据覆盖）
          - 第3行：实验报告号
          - 第4行：报告名称
          - 第5行：底盘号
          - 第6行：总质量
        - **从第7行开始**：填充555个测试项目的测试值

        **注意事项：**
        - 车辆ID是唯一标识，相同ID会覆盖原有数据
        - 此格式专为批量导入设计
        - 如需数据分析，请使用【数据看板】功能
        """)

        # 获取所有车辆
        all_vehicles = get_vehicles()

        if len(all_vehicles) < 2:
            st.warning("至少需要2辆车才能进行多车数据导出")
            st.info("请先在【车辆管理】中添加更多车辆")
        else:
            # 多选车辆
            vehicle_options = [f"{v[1]} - {v[2]} (ID: {v[0]})" for v in all_vehicles]
            selected_vehicles = st.multiselect(
                "选择要导出的车辆（可多选）",
                vehicle_options,
                default=vehicle_options[:min(3, len(vehicle_options))]  # 默认选择前3辆
            )

            if selected_vehicles:
                # 解析车辆ID
                vehicle_ids = []
                for vehicle_str in selected_vehicles:
                    parts = vehicle_str.split(" (ID: ")
                    vehicle_id = parts[1].replace(")", "")
                    vehicle_ids.append(vehicle_id)

                st.info(f"已选择 {len(vehicle_ids)} 辆车（主要用于批量导入模板）")

                # 显示车辆信息预览
                preview_data = []
                for vehicle_str in selected_vehicles:
                    parts = vehicle_str.split(" (ID: ")
                    model_chassis = parts[0]
                    vehicle_id = parts[1].replace(")", "")

                    model, chassis = model_chassis.split(" - ")

                    # 获取车辆详细信息
                    vehicle_details = get_vehicle_details(vehicle_id)
                    curb_weight = vehicle_details['curb_weight'] if vehicle_details else ""

                    # 获取报告配置
                    report_config = get_report_config(vehicle_id, 'header')
                    report_number = report_config.get('编号', '')

                    preview_data.append({
                        '车辆ID': vehicle_id,
                        '车型': model,
                        '底盘号': chassis,
                        '总质量': curb_weight,
                        '能源类型': (vehicle_details or {}).get('energy_type', ''),
                        '车辆归属平台': (vehicle_details or {}).get('vehicle_platform', ''),
                        '实验报告号': report_number
                    })

                preview_df = pd.DataFrame(preview_data)
                st.dataframe(preview_df, use_container_width=True, hide_index=True, height=150)

                # 导出按钮
                if st.button("📊 生成批量导入模板", type="primary", use_container_width=True):
                    with st.spinner("正在生成批量导入模板..."):
                        csv_data = export_multiple_vehicles_data(vehicle_ids)

                        if csv_data:
                            # 生成文件名
                            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                            filename = f"批量导入模板_{timestamp}.csv"

                            st.success("✅ 批量导入模板生成成功！")
                            st.info("""
                            **文件使用说明：**
                            1. 每列对应一辆车的测试数据
                            2. 在每列的第9行及以下填写测试值（前8行为车辆元数据）
                            3. 保持文件格式不变
                            4. 使用【批量导入】功能导入此文件
                            """)

                            st.download_button(
                                label="📥 下载批量导入模板",
                                data=csv_data,
                                file_name=filename,
                                mime="text/csv",
                                use_container_width=True
                            )
                        else:
                            st.error("❌ 模板生成失败，请重试")

        st.markdown('</div>', unsafe_allow_html=True)

    with tab4:
        st.markdown('<div class="export-box">', unsafe_allow_html=True)
        st.subheader("🚀 批量导入多车数据")
        st.info("💡 使用多车导出格式批量导入车辆和测试数据")

        uploaded_batch_file = st.file_uploader(
            "上传多车数据CSV文件（格式与多车导出相同）",
            type=['csv'],
            key="upload_batch_data"
        )

        if uploaded_batch_file is not None:
            st.info(f"📄 文件: {uploaded_batch_file.name} ({uploaded_batch_file.size / 1024:.1f} KB)")

            # 预览文件前几行
            if st.button("预览文件结构"):
                try:
                    uploaded_batch_file.seek(0)
                    try:
                        content = uploaded_batch_file.read().decode('utf-8-sig')
                    except:
                        uploaded_batch_file.seek(0)
                        content = uploaded_batch_file.read().decode('gbk')

                    lines = content.split('\n')[:10]
                    st.text_area("文件预览（前10行）", '\n'.join(lines), height=150)

                    # 显示文件结构
                    st.info("文件应包含：")
                    st.markdown("""
                    - **第1行**：表头（项目ID, 序号, 一级目录, 二级目录, 测试项目, 单位, 车辆1, 车辆2...）
                    - **第2行**：车辆ID（对应每列）
                    - **第3行**：实验报告号（可为空）
                    - **第4行**：底盘号
                    - **第5行**：总质量
                    - **从第6行开始**：265个测试项目的测试值
                    """)
                except Exception as e:
                    st.error(f"读取失败: {str(e)}")

            if st.button("🚀 执行批量导入", type="primary", use_container_width=True):
                with st.spinner("正在批量导入车辆数据..."):
                    try:
                        uploaded_batch_file.seek(0)
                        try:
                            csv_content = uploaded_batch_file.read().decode('utf-8-sig')
                        except:
                            uploaded_batch_file.seek(0)
                            csv_content = uploaded_batch_file.read().decode('gbk')

                        # 调用批量导入函数
                        success, message = import_multiple_vehicles_from_csv(csv_content)

                        if success:
                            st.success(f"✅ {message}")
                            st.balloons()
                        else:
                            st.error(f"❌ {message}")

                    except Exception as e:
                        st.error(f"导入失败: {str(e)}")

        st.markdown('</div>', unsafe_allow_html=True)