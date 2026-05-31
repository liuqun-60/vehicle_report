# pages/admin.py - Streamlit Cloud 演示版

import streamlit as st
import pandas as pd
import io
from datetime import datetime, timedelta
from pathlib import Path
import os
import time

from database.core import (
    get_vehicles,
    get_vehicle_details,
    delete_vehicle,
    get_all_test_items,
    get_vehicle_test_results,
    get_report_images,
    get_main_categories
)
from database.exports import (
    export_database_to_csv,
    export_multiple_vehicles_data,
    export_test_template,
    export_database_structure,
)
from database.imports import (
    import_database_from_csv,
    import_test_data,
    import_multiple_vehicles_from_csv,
)
from database.initializer import (
    get_cached_database_stats,
    get_cached_vehicle_count,
    get_cached_test_result_count
)

# 导入数据看板的初始化函数
from pages.dashboard import init_dashboard_data

import config


# ========== 新增：管理员专用缓存函数 ==========
@st.cache_data(ttl=300, show_spinner=False)
def get_cached_vehicle_stats_list():
    """缓存车辆统计数据列表（直接从数据库查询，避免依赖session_state）"""
    try:
        from db_config import connection_pool
        with connection_pool.get_connection() as conn:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("""
                SELECT 
                    vehicle_id, model, chassis_number, curb_weight,
                    valid_count, completion_rate, updated_at
                FROM vehicle_stats
                ORDER BY completion_rate DESC
            """)
            return cursor.fetchall()
    except Exception as e:
        return []


@st.cache_data(ttl=300, show_spinner=False)
def get_cached_vehicles_info():
    """缓存车辆详细信息（直接从数据库查询）"""
    try:
        from db_config import connection_pool
        with connection_pool.get_connection() as conn:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("""
                SELECT id, model, chassis_number, curb_weight, notes,
                       energy_type, vehicle_platform, created_at, created_by
                FROM vehicles
                ORDER BY created_at DESC
            """)
            results = cursor.fetchall()
            return {row['id']: row for row in results}
    except Exception as e:
        return {}


@st.cache_data(ttl=300, show_spinner=False)
def get_cached_test_results_summary():
    """缓存测试结果汇总（只统计数量，不加载全部数据）"""
    try:
        from db_config import connection_pool
        with connection_pool.get_connection() as conn:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("""
                SELECT vehicle_id, COUNT(*) as test_count
                FROM test_results
                WHERE value IS NOT NULL AND value != '' AND TRIM(value) != ''
                GROUP BY vehicle_id
            """)
            results = cursor.fetchall()
            return {row['vehicle_id']: row['test_count'] for row in results}
    except Exception as e:
        return {}


@st.cache_data(ttl=300, show_spinner=False)
def get_cached_image_counts():
    """缓存图片数量统计"""
    try:
        from db_config import connection_pool
        with connection_pool.get_connection() as conn:
            cursor = conn.cursor()
            # 获取所有一级目录
            cursor.execute("SELECT id FROM main_categories")
            main_cats = cursor.fetchall()

            # 统计每个车辆的图片数
            result = {}
            cursor.execute("SELECT vehicle_id, COUNT(*) as cnt FROM report_images GROUP BY vehicle_id")
            for row in cursor.fetchall():
                result[row[0]] = result.get(row[0], 0) + row[1]
            cursor.execute("SELECT vehicle_id, COUNT(*) as cnt FROM sample_car_images GROUP BY vehicle_id")
            for row in cursor.fetchall():
                result[row[0]] = result.get(row[0], 0) + row[1]
            return result
    except Exception as e:
        return {}

# 在文件开头添加（其他缓存函数附近）
@st.cache_data(ttl=300, show_spinner=False)
def get_database_size():
    """获取数据库实际大小"""
    try:
        from db_config import DB_PATH
        if DB_PATH.exists():
            size_bytes = DB_PATH.stat().st_size
            if size_bytes < 1024 * 1024:
                return f"{size_bytes / 1024:.1f} KB"
            return f"{size_bytes / 1024 / 1024:.2f} MB"
        return "0 KB"
    except Exception:
        return "计算失败"


def show_admin_home():
    """显示管理员首页 - 优化版"""
    st.title("👑 管理员控制面板")

    # 在 show_admin_home() 函数开头，获取 vehicle_stats 之前添加
    from database.initializer import get_cached_vehicle_count

    # 使用缓存函数获取数据
    vehicle_stats = get_cached_vehicle_stats_list()
    test_counts = get_cached_test_results_summary()

    total_vehicles = get_cached_vehicle_count()
    total_valid_tests = sum(test_counts.values())

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("""
        <div class="admin-box">
            <h3>📋 管理员功能</h3>
            <p>您已进入管理员模式，可以执行以下高级操作：</p>
            <ul>
                <li><strong>🗄️ 数据库管理</strong>：完整备份和恢复数据库</li>
                <li><strong>🗑️ 删除车辆</strong>：彻底删除车辆及相关数据</li>
            </ul>
            <p><em>⚠️ 所有操作都需要谨慎执行</em></p>
        </div>
        """, unsafe_allow_html=True)

    with col2:
        st.markdown("""
        <div class="admin-box">
            <h3>📊 系统状态</h3>
        </div>
        """, unsafe_allow_html=True)

        col_a, col_b = st.columns(2)
        with col_a:
            st.metric("车辆数量", total_vehicles)
            st.metric("有效测试数据", total_valid_tests)
        with col_b:
            # 获取图片数量
            image_counts = get_cached_image_counts()
            total_images = sum(image_counts.values())
            st.metric("图片记录", total_images)
            st.metric("数据库大小", get_database_size())

    st.markdown("---")
    st.markdown("### 🚀 快速操作")

    col1, col2 = st.columns(2)

    with col1:
        if st.button("🗄️ 进入数据库管理", use_container_width=True):
            st.session_state['current_page'] = 'database_management'
            st.rerun()

    with col2:
        if st.button("🗑️ 删除车辆", use_container_width=True):
            st.session_state['current_page'] = 'delete_vehicles'
            st.rerun()

    st.markdown("---")
    st.markdown("### ⚠️ 重要提醒")
    st.warning("""
    **管理员操作注意事项：**
    1. **数据库备份**：在执行任何重要操作前，请先备份数据库
    2. **删除操作**：删除车辆会永久删除所有相关数据，无法恢复
    3. **导入操作**：导入数据会覆盖现有数据，请确保数据正确
    4. **操作时间**：建议在非工作时间进行系统维护操作
    """)


def show_database_management():
    """显示数据库管理页面 - 优化版"""
    st.title("🗄️ 数据库管理")

    # 使用缓存函数获取数据
    vehicle_stats = get_cached_vehicle_stats_list()
    test_counts = get_cached_test_results_summary()
    image_counts = get_cached_image_counts()
    vehicles_info = get_cached_vehicles_info()
    all_test_items = get_all_test_items()  # 这个已经很快，直接调用

    total_vehicles = get_cached_vehicle_count()
    total_valid_tests = sum(test_counts.values())
    total_images = sum(image_counts.values())
    total_test_items = len(all_test_items)

    tab1, tab2, tab3 = st.tabs([
        "📊 数据库状态",
        "📤 导出测试项目结构及结果",
        "📥 更新测试项目结构",
    ])

    with tab1:
        st.markdown('<div class="admin-box">', unsafe_allow_html=True)
        st.subheader("数据库状态信息")

        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("数据库大小", get_database_size())
        with col2:
            st.metric("表数量", 12)
        with col3:
            st.metric("总记录数", total_valid_tests + total_vehicles)
        with col4:
            st.metric("数据库文件", "SQLite")

        st.markdown("---")
        st.subheader("详细统计")

        stats_data = [
            {"项目": "车辆总数", "数量": total_vehicles, "说明": "已添加的测试车辆"},
            {"项目": "测试项目", "数量": total_test_items, "说明": "系统定义的测试项目"},
            {"项目": "测试数据记录", "数量": total_valid_tests, "说明": "所有车辆的有效测试结果"},
            {"项目": "测试图片", "数量": total_images, "说明": "上传的测试相关图片"}
        ]
        stats_df = pd.DataFrame(stats_data)
        st.dataframe(stats_df, use_container_width=True, hide_index=True)

        st.markdown('</div>', unsafe_allow_html=True)

    with tab2:
        st.markdown('<div class="admin-box">', unsafe_allow_html=True)
        st.subheader("导出数据库")

        st.markdown("#### 📤 CSV导出（测试项目结构）")
        st.info("""
        导出测试项目结构CSV文件，可用于编辑和更新测试项目

        【操作步骤】
        - 导出CSV：点击下方按钮下载当前数据库的测试项目结构
        - 编辑文件：用Excel打开CSV，根据需要修改/新增/删除项目（注意序号必须保持1-N连续）
        - 导入更新：切换到【导入数据库更新】标签页，上传修改后的CSV文件
        """)

        csv_data = export_database_to_csv()
        if csv_data:
            st.download_button(
                label="📥 下载CSV文件",
                data=csv_data,
                file_name=f"database_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv",
                use_container_width=True
            )
        else:
            st.error("❌ 生成CSV备份失败")

        st.markdown("---")
        st.markdown("#### 📊 完整测试数据导出")
        st.info(f"当前共有 {total_vehicles} 辆车的测试数据")

        if st.button("📤 导出所有车辆测试数据", use_container_width=True):
            with st.spinner("正在生成完整数据文件..."):
                vehicle_ids = list(vehicles_info.keys())
                csv_data = export_multiple_vehicles_data(vehicle_ids)

                if csv_data:
                    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                    st.success(f"✅ 数据导出成功！共导出 {len(vehicle_ids)} 辆车的测试数据")
                    st.download_button(
                        label="📥 下载完整数据CSV",
                        data=csv_data,
                        file_name=f"所有车辆测试数据_{timestamp}.csv",
                        mime="text/csv",
                        use_container_width=True
                    )
                else:
                    st.error("❌ 数据导出失败")

        st.markdown('</div>', unsafe_allow_html=True)

    with tab3:
        st.markdown('<div class="admin-box">', unsafe_allow_html=True)
        st.subheader("导入数据库更新")
        st.warning("⚠️ 导入将更新数据库结构，请谨慎操作！")

        uploaded_file = st.file_uploader(
            "选择数据库CSV文件",
            type=['csv'],
            key="upload_database_csv"
        )

        if uploaded_file is not None:
            st.info(f"📄 文件: {uploaded_file.name} ({uploaded_file.size / 1024:.1f} KB)")

            if st.button("预览文件内容", key="preview_database"):
                try:
                    uploaded_file.seek(0)
                    try:
                        content = uploaded_file.read().decode('utf-8-sig')
                    except:
                        uploaded_file.seek(0)
                        content = uploaded_file.read().decode('gbk')
                    lines = content.split('\n')[:11]
                    st.text_area("文件预览（前10行）", '\n'.join(lines), height=150)
                except Exception as e:
                    st.error(f"读取失败: {str(e)}")

            st.warning("建议先备份当前数据库再进行导入操作")

            if st.checkbox("我已了解风险，确认导入"):
                if st.button("🚀 导入数据库更新", type="primary", use_container_width=True):
                    with st.spinner("正在导入数据库..."):
                        uploaded_file.seek(0)
                        csv_content = uploaded_file.read()
                        success, message = import_database_from_csv(csv_content)

                        if success:
                            st.success(f"✅ {message}")
                            st.balloons()
                            # 清除所有缓存
                            st.cache_data.clear()
                        else:
                            st.error(f"❌ {message}")

        st.markdown('</div>', unsafe_allow_html=True)


def show_delete_vehicles():
    """显示删除车辆页面"""
    st.title("🗑️ 删除车辆")
    st.markdown('<div class="delete-box">', unsafe_allow_html=True)

    st.warning("⚠️ 警告：删除操作将永久删除相关数据，此操作不可恢复！")

    st.markdown("### 删除性能车辆")

    from database.core import get_vehicles, get_vehicle_details, get_vehicle_test_results
    from database.core import get_all_test_items

    vehicles = get_vehicles()

    if not vehicles:
        st.info("暂无性能车辆数据")
    else:
        vehicle_options = [
            f"{v[1]} | 底盘:{v[2]} | 质量:{v[3]} | 备注:{v[4]} (ID:{v[0]})"
            for v in vehicles
        ]
        selected_vehicle_str = st.selectbox("选择要删除的性能车辆", vehicle_options,
                                            key="admin_delete_vehicle_select")

        if selected_vehicle_str:
            vehicle_id = selected_vehicle_str.split("(ID:")[1].rstrip(")").strip()
            vehicle_info = get_vehicle_details(vehicle_id)

            if vehicle_info:
                test_results = get_vehicle_test_results(vehicle_id)
                valid_test_count = 0
                for result in test_results:
                    test_value = result[1]
                    if test_value is not None and str(test_value).strip() != "":
                        valid_test_count += 1

                from database.core import get_report_images, get_sample_car_images
                from database.core import get_main_categories

                total_images = 0
                main_categories = get_main_categories()
                for cat_id, cat_name in main_categories:
                    report_images = get_report_images(vehicle_id, cat_id)
                    total_images += len(report_images)
                sample_images = get_sample_car_images(vehicle_id)
                total_images += len(sample_images)

                col1, col2 = st.columns([2, 1])

                with col1:
                    st.markdown(f"""
                    <div style="background-color: #f8f9fa; border: 1px solid #dee2e6; 
                                border-radius: 5px; padding: 15px; margin: 10px 0;">
                        <h4>{vehicle_info['model']}</h4>
                        <p><strong>底盘号:</strong> {vehicle_info['chassis_number']}</p>
                        <p><strong>总质量:</strong> {vehicle_info['curb_weight']}</p>
                        <p><strong>能源类型:</strong> {vehicle_info.get('energy_type') or '未填写'}</p>
                        <p><strong>车辆归属平台:</strong> {vehicle_info.get('vehicle_platform') or '未填写'}</p>
                        <p><strong>创建时间:</strong> {vehicle_info['created_at']}</p>
                    </div>
                    """, unsafe_allow_html=True)

                with col2:
                    all_items = get_all_test_items()
                    total_test_items = len(all_items)
                    completion_rate = (valid_test_count / total_test_items * 100) if total_test_items > 0 else 0
                    st.metric("测试数据", valid_test_count)
                    st.metric("图片数量", total_images)
                    st.metric("完成率", f"{completion_rate:.1f}%")
                    st.metric("车辆ID", vehicle_id)

                with st.expander("📋 查看待删除数据详情", expanded=False):
                    if valid_test_count > 0:
                        st.info(f"该车辆共有 {valid_test_count} 条测试数据，{total_images} 张图片")
                    else:
                        st.info("该车辆暂无测试数据")

                st.markdown("---")
                st.markdown("""
                <div style="background-color: #f8d7da; border: 2px solid #dc3545; 
                            border-radius: 5px; padding: 15px; margin: 15px 0;">
                    <h4 style="color: #721c24;">⚠️ 最终确认</h4>
                    <p>删除后将无法恢复！</p>
                </div>
                """, unsafe_allow_html=True)

                confirm_delete = st.checkbox("我确认要删除此性能车辆及其所有相关数据",
                                             key=f"confirm_vehicle_{vehicle_id}")

                if confirm_delete:
                    if st.button("🗑️ 永久删除此性能车辆", type="primary", use_container_width=True):
                        with st.spinner("正在删除车辆及相关数据..."):
                            from database.core import delete_vehicle
                            success, message = delete_vehicle(vehicle_id)
                            if success:
                                st.success(f"✅ {message}")
                                st.cache_data.clear()
                                time.sleep(1)
                                st.rerun()
                            else:
                                st.error(f"❌ {message}")

    st.markdown('</div>', unsafe_allow_html=True)


def show_frozen_vehicles_management():
    """显示冻结车辆管理（管理员功能）- 支持搜索和多选解冻"""
    st.markdown("""
    <style>
    .frozen-header {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 20px;
        border-radius: 15px;
        margin-bottom: 20px;
    }
    .vehicle-card {
        background: white;
        border-radius: 12px;
        padding: 20px;
        margin-bottom: 15px;
        box-shadow: 0 2px 10px rgba(0,0,0,0.05);
        border: 1px solid #e9ecef;
    }
    .vehicle-card:hover {
        box-shadow: 0 4px 15px rgba(0,0,0,0.1);
        border-color: #667eea;
    }
    .status-badge {
        display: inline-block;
        padding: 4px 12px;
        border-radius: 20px;
        font-size: 0.8rem;
        font-weight: 600;
    }
    .status-frozen {
        background: #fee2e2;
        color: #dc2626;
    }
    .status-active {
        background: #d1fae5;
        color: #059669;
    }
    </style>
    """, unsafe_allow_html=True)

    st.markdown("""
    <div class="frozen-header">
        <h2 style="color: white; margin: 0;">🔓 冻结车辆管理</h2>
        <p style="color: rgba(255,255,255,0.9); margin: 10px 0 0 0;">管理所有已冻结的车辆，支持搜索和多选批量解冻</p>
    </div>
    """, unsafe_allow_html=True)

    from database.core import get_vehicles, check_vehicle_frozen, unfreeze_vehicle, get_vehicle_details

    vehicles = get_vehicles()
    frozen_vehicles = []

    for v in vehicles:
        is_frozen, _ = check_vehicle_frozen(v[0])
        if is_frozen:
            details = get_vehicle_details(v[0])
            if details:
                frozen_vehicles.append(details)

    if not frozen_vehicles:
        st.info("✅ 当前没有已冻结的车辆")
        return

    # 搜索框
    st.markdown("### 🔍 搜索筛选")
    col_search1, col_search2, col_search3 = st.columns(3)

    with col_search1:
        search_model = st.text_input("车型", placeholder="")
    with col_search2:
        search_chassis = st.text_input("底盘号", placeholder="输入底盘号关键词")
    with col_search3:
        search_id = st.text_input("车辆ID", placeholder="输入车辆ID")

    # 筛选车辆
    filtered_vehicles = []
    for v in frozen_vehicles:
        match = True
        if search_model and search_model.lower() not in str(v.get('model', '')).lower():
            match = False
        if search_chassis and search_chassis.lower() not in str(v.get('chassis_number', '')).lower():
            match = False
        if search_id and search_id.lower() not in str(v.get('id', '')).lower():
            match = False
        if match:
            filtered_vehicles.append(v)

    st.markdown(f"### 📋 已冻结车辆列表 ({len(filtered_vehicles)}/{len(frozen_vehicles)})")

    if not filtered_vehicles:
        st.info("没有符合筛选条件的车辆")
        return

    # 批量操作栏
    st.markdown("---")
    col_batch1, col_batch2, col_batch3 = st.columns([2, 1, 2])

    with col_batch1:
        select_all = st.checkbox("全选当前筛选结果", key="select_all_frozen")

    with col_batch2:
        if st.button("🔄 刷新列表", use_container_width=True):
            st.rerun()

    # 显示车辆列表
    selected_vehicles = []

    for idx, v in enumerate(filtered_vehicles):
        with st.container():
            col1, col2, col3, col4 = st.columns([0.5, 3, 2, 1])

            with col1:
                if select_all:
                    selected = st.checkbox("选择", value=True, key=f"select_frozen_{v['id']}")
                else:
                    selected = st.checkbox("选择", key=f"select_frozen_{v['id']}")
                if selected:
                    selected_vehicles.append(v['id'])

            with col2:
                st.markdown(f"""
                <div style="display: flex; align-items: center; gap: 15px;">
                    <div>
                        <h4 style="margin: 0 0 5px 0;">{v.get('model', '未知车型')}</h4>
                        <p style="margin: 0; color: #6c757d; font-size: 0.9rem;">
                            底盘号: {v.get('chassis_number', '未知')} | ID: {v.get('id', '')}
                        </p>
                    </div>
                </div>
                """, unsafe_allow_html=True)

            with col3:
                st.markdown(f"""
                <div style="padding-top: 10px;">
                    <span class="status-badge status-frozen">🔒 已冻结</span>
                    <p style="margin: 8px 0 0 0; font-size: 0.85rem; color: #6c757d;">
                        创建时间: {v.get('created_at', '未知')}
                    </p>
                </div>
                """, unsafe_allow_html=True)

            with col4:
                if st.button("🔓 解冻", key=f"unfreeze_single_{v['id']}", use_container_width=True):
                    success, message = unfreeze_vehicle(v['id'])
                    if success:
                        st.success(f"✅ {v.get('model', '车辆')} 已解冻")
                        st.rerun()
                    else:
                        st.error(message)

            st.markdown("---")

    # 批量解冻
    if selected_vehicles:
        st.markdown("### 🚀 批量操作")
        col_batch_confirm1, col_batch_confirm2 = st.columns([3, 1])

        with col_batch_confirm1:
            st.info(f"已选择 {len(selected_vehicles)} 辆车，点击右侧按钮批量解冻")

        with col_batch_confirm2:
            if st.button(f"🔓 批量解冻 ({len(selected_vehicles)})", type="primary", use_container_width=True):
                success_count = 0
                fail_count = 0

                with st.spinner(f"正在解冻 {len(selected_vehicles)} 辆车..."):
                    for vid in selected_vehicles:
                        success, _ = unfreeze_vehicle(vid)
                        if success:
                            success_count += 1
                        else:
                            fail_count += 1

                if success_count > 0:
                    st.success(f"✅ 成功解冻 {success_count} 辆车" + (f"，{fail_count} 辆失败" if fail_count > 0 else ""))
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error(f"❌ 解冻失败")

