# pages/vehicle.py
"""
车辆管理页面
"""
import streamlit as st
import pandas as pd
import time
from datetime import datetime

from database import (
    get_vehicles, get_vehicle_details, save_vehicle, update_vehicle,
    copy_vehicle_configurations
)
from database.core import (
    check_vehicle_frozen, freeze_vehicle, unfreeze_vehicle, get_user_display_names,
)


def _vehicle_detail_fields(prefix, defaults=None):
    """车辆详情表单：三行两列（与耐久项目详情布局一致）"""
    d = defaults or {}
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**车型***")
        model = st.text_input(
            "车型", value=d.get('model', ''), key=f"{prefix}_model",
            label_visibility="collapsed", placeholder="",
        )
    with col2:
        st.markdown("**底盘号***")
        chassis = st.text_input(
            "底盘号", value=d.get('chassis_number', ''), key=f"{prefix}_chassis",
            label_visibility="collapsed", placeholder="",
        )

    col3, col4 = st.columns(2)
    with col3:
        st.markdown("**总质量***")
        weight = st.text_input(
            "总质量", value=d.get('curb_weight', ''), key=f"{prefix}_weight",
            label_visibility="collapsed", placeholder="",
        )
    with col4:
        st.markdown("**能源类型***")
        energy = st.text_input(
            "能源类型", value=d.get('energy_type', ''), key=f"{prefix}_energy",
            label_visibility="collapsed", placeholder="",
        )

    col5, col6 = st.columns(2)
    with col5:
        st.markdown("**车辆归属平台***")
        platform = st.text_input(
            "车辆归属平台", value=d.get('vehicle_platform', ''), key=f"{prefix}_platform",
            label_visibility="collapsed", placeholder="",
        )
    with col6:
        st.markdown("**备注**")
        notes = st.text_input(
            "备注", value=d.get('notes', ''), key=f"{prefix}_notes",
            label_visibility="collapsed",
            placeholder="",
        )
    return model, chassis, weight, energy, platform, notes


def _copy_vehicle_field_defaults(source_vehicle):
    """复制源车五个必填项，不含备注"""
    if not source_vehicle:
        return {}
    return {
        'model': source_vehicle['model'],
        'chassis_number': source_vehicle['chassis_number'],
        'curb_weight': source_vehicle.get('curb_weight') or '',
        'energy_type': source_vehicle.get('energy_type') or '',
        'vehicle_platform': source_vehicle.get('vehicle_platform') or '',
        'notes': '',
    }


def show_vehicle_management():
    """显示车辆管理页面"""
    st.title("车辆管理")

    tab1, tab2 = st.tabs(["📋 车辆列表", "➕ 新建车辆"])

    with tab1:
        st.subheader("所有车辆")

        vehicles = get_vehicles()

        if vehicles:
            creators = [v[7] or '' for v in vehicles]
            display_map = get_user_display_names(creators)
            df = pd.DataFrame(
                [
                    (
                        v[0], v[1], v[2], v[3], v[4], v[5], v[6],
                        display_map.get(v[7] or '', v[7] or ''),
                    )
                    for v in vehicles
                ],
                columns=["ID", "车型", "底盘号", "总质量", "备注", "能源类型", "车辆归属平台", "创建人"]
            )
            st.dataframe(df, use_container_width=True, hide_index=True, height=300)

            st.markdown("---")
            st.subheader("车辆详情")

            global_selected_id = st.session_state.get('global_selected_vehicle_id')

            # v[0]=ID, v[1]=车型, v[2]=底盘号, v[3]=总质量, v[4]=备注, v[5]=能源类型, v[6]=平台, v[7]=创建人
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
                selected_str = st.session_state.get("vehicle_management_detail_select")
                if selected_str and "(ID:" in selected_str:
                    vehicle_id = selected_str.split("(ID:")[1].rstrip(")").strip()
                    st.session_state['global_selected_vehicle_id'] = vehicle_id

            selected_vehicle_str = st.selectbox(
                "选择车辆查看详情",
                vehicle_options,
                index=default_index,
                key="vehicle_management_detail_select",
                on_change=update_global_selection
            )

            if selected_vehicle_str:
                # 提取车辆ID
                vehicle_id = selected_vehicle_str.split("(ID:")[1].rstrip(")").strip()

                # 提取车型
                model = selected_vehicle_str.split(" | ")[0]

                # 提取底盘号
                import re
                chassis_match = re.search(r'底盘:([^|]*)', selected_vehicle_str)
                chassis = chassis_match.group(1).strip() if chassis_match else ""
                vehicle_details = get_vehicle_details(vehicle_id)

                if vehicle_details:
                    creator = vehicle_details.get('creator_display') or vehicle_details.get('created_by') or '未记录'
                    st.caption(f"创建人：{creator}")

                    with st.form(f"edit_vehicle_{vehicle_id}"):
                        new_model, new_chassis_number, new_curb_weight, new_energy_type, new_vehicle_platform, new_notes = \
                            _vehicle_detail_fields(f"edit_{vehicle_id}", vehicle_details)

                        # st.markdown("---")
                        # col_info1, col_info2 = st.columns(2)
                        # with col_info1:
                        #     st.info(f"**车辆ID**: {vehicle_details['id']}")
                        #     st.info(f"**创建时间**: {vehicle_details['created_at']}")
                        # with col_info2:
                        #     st.info(f"**车型**: {vehicle_details['model']}")
                        #     st.info(f"**底盘号**: {vehicle_details['chassis_number']}")

                        col_btn1, col_btn2, col_btn3 = st.columns([1, 1, 2])
                        with col_btn1:
                            submitted = st.form_submit_button(
                                "💾 保存修改",
                                type="primary",
                                use_container_width=True
                            )
                        with col_btn2:
                            reset_btn = st.form_submit_button("🔄 重置", use_container_width=True)

                        if submitted:
                            validation_errors = []
                            if not new_model:
                                validation_errors.append("车型")
                            if not new_chassis_number:
                                validation_errors.append("底盘号")
                            if not new_curb_weight:
                                validation_errors.append("总质量")
                            if not (new_energy_type or "").strip():
                                validation_errors.append("能源类型")
                            if not (new_vehicle_platform or "").strip():
                                validation_errors.append("车辆归属平台")

                            if validation_errors:
                                st.error(f"⚠️ 请填写以下必填字段：{', '.join(validation_errors)}")
                            else:
                                try:
                                    vehicle_data = {
                                        'model': new_model,
                                        'chassis_number': new_chassis_number,
                                        'curb_weight': new_curb_weight,
                                        'notes': new_notes,
                                        'energy_type': new_energy_type.strip(),
                                        'vehicle_platform': new_vehicle_platform.strip(),
                                    }

                                    update_vehicle(vehicle_id, vehicle_data)
                                    st.success("✅ 车辆信息更新成功！")
                                    st.rerun()
                                except Exception as e:
                                    error_msg = str(e)
                                    if "冻结" in error_msg or "frozen" in error_msg.lower():
                                        st.markdown("""
                                            <div class="frozen-error-box">
                                                <h4>🔒 车辆已冻结</h4>
                                                <p>该车辆数据已被冻结，无法修改。如需修改请联系管理员解冻！</p>
                                            </div>
                                            """, unsafe_allow_html=True)
                                    else:
                                        st.error(f"❌ 更新失败：{error_msg}")

                        if reset_btn:
                            st.rerun()

                    # ========== 新增：冻结状态显示和操作 ==========
                    st.markdown("---")
                    st.subheader("🔒 数据状态")

                    is_frozen, status = check_vehicle_frozen(vehicle_id)

                    col_status1, col_status2 = st.columns([1, 2])
                    with col_status1:
                        if is_frozen:
                            st.markdown("🔴 **状态：已冻结**")
                        else:
                            st.markdown("🟢 **状态：激活中**")

                    # 测试人员可以冻结，管理员账号可以冻结和解冻
                    from auth import is_current_admin
                    is_admin_logged = is_current_admin()

                    if not is_frozen:
                        # 显示冻结按钮
                        if st.button("🔒 冻结该车辆数据", key=f"freeze_{vehicle_id}", use_container_width=True):
                            st.session_state[f'show_freeze_confirm_{vehicle_id}'] = True

                        # 确认对话框
                        if st.session_state.get(f'show_freeze_confirm_{vehicle_id}', False):
                            st.warning("⚠️ 您确定要冻结该车辆数据吗？冻结后所有数据将无法修改。")
                            st.markdown(f"""
                            **车辆信息确认：**
                            - **车辆ID**: {vehicle_details['id']}
                            - **创建时间**: {vehicle_details['created_at']}
                            - **车型**: {vehicle_details['model']}
                            - **底盘号**: {vehicle_details['chassis_number']}
                            - **备注**: {vehicle_details['notes'] or '无'}
                            """)

                            confirm_text = st.text_input(
                                "请输入'确认冻结'以继续",
                                key=f"freeze_confirm_text_{vehicle_id}"
                            )

                            col_confirm1, col_confirm2 = st.columns(2)
                            with col_confirm1:
                                if st.button("✅ 确认冻结", key=f"confirm_freeze_{vehicle_id}", use_container_width=True):
                                    if confirm_text == "确认冻结":
                                        success, message = freeze_vehicle(vehicle_id)
                                        if success:
                                            st.success(f"✅ {message}")
                                            st.session_state[f'show_freeze_confirm_{vehicle_id}'] = False
                                            st.rerun()
                                        else:
                                            st.error(message)
                                    else:
                                        st.error("请输入正确的确认文字")
                            with col_confirm2:
                                if st.button("❌ 取消", key=f"cancel_freeze_{vehicle_id}", use_container_width=True):
                                    st.session_state[f'show_freeze_confirm_{vehicle_id}'] = False
                                    st.rerun()
                    else:
                        # 已冻结状态，只有管理员可以解冻
                        if is_admin_logged:
                            if st.button("🔓 解冻车辆数据", key=f"unfreeze_{vehicle_id}", use_container_width=True):
                                success, message = unfreeze_vehicle(vehicle_id)
                                if success:
                                    st.success(f"✅ {message}")
                                    st.rerun()
                                else:
                                    st.error(message)
                        else:
                            st.info("该车辆已冻结，如需修改请联系管理员解冻。")
        else:
            st.info("暂无车辆数据，请点击【新建车辆】添加")

    with tab2:
        st.subheader("新建车辆")

        creation_mode = st.radio(
            "创建方式",
            ["🆕 全新创建", "📋 复制现有车辆配置"],
            horizontal=True
        )

        source_vehicle_id = None
        if creation_mode == "📋 复制现有车辆配置":
            existing_vehicles = get_vehicles()

            if not existing_vehicles:
                st.warning("暂无现有车辆可复制，请先创建车辆")
                creation_mode = "🆕 全新创建"
            else:
                vehicle_options = [f"{v[1]} - {v[2]} (ID: {v[0]})" for v in existing_vehicles]
                source_vehicle_str = st.selectbox("选择源车辆", vehicle_options)

                if source_vehicle_str:
                    parts = source_vehicle_str.split(" (ID: ")
                    source_vehicle_id = parts[1].replace(")", "")

                    source_vehicle = get_vehicle_details(source_vehicle_id)

                    if source_vehicle:
                        st.info(
                            "注：将复制源车的五个必填项（车型、底盘号、总质量、能源类型、车辆归属平台）及"
                            "试验配置（试验项目、设备、报告配置等），不复制备注与测试数据。"
                        )

        new_defaults = {}
        if creation_mode == "📋 复制现有车辆配置" and source_vehicle_id:
            src = get_vehicle_details(source_vehicle_id)
            new_defaults = _copy_vehicle_field_defaults(src)

        with st.form("new_vehicle_form", clear_on_submit=True):
            model, chassis_number, curb_weight, energy_type, vehicle_platform, notes = \
                _vehicle_detail_fields("new", new_defaults)

            submitted = st.form_submit_button("保存车辆信息", type="primary", use_container_width=True)

            if submitted:
                validation_errors = []
                if not model:
                    validation_errors.append("车型")
                if not chassis_number:
                    validation_errors.append("底盘号")
                if not curb_weight:
                    validation_errors.append("总质量")
                if not (energy_type or "").strip():
                    validation_errors.append("能源类型")
                if not (vehicle_platform or "").strip():
                    validation_errors.append("车辆归属平台")

                if validation_errors:
                    st.error(f"⚠️ 请填写以下必填字段：{', '.join(validation_errors)}")
                else:
                    vehicle_data = {
                        'model': model,
                        'chassis_number': chassis_number,
                        'curb_weight': curb_weight,
                        'notes': notes,
                        'energy_type': energy_type.strip(),
                        'vehicle_platform': vehicle_platform.strip(),
                    }

                    try:
                        new_vehicle_id = save_vehicle(vehicle_data)

                        if creation_mode == "📋 复制现有车辆配置" and source_vehicle_id:
                            with st.spinner("正在复制车辆配置..."):
                                success, message = copy_vehicle_configurations(source_vehicle_id, new_vehicle_id)
                                if success:
                                    st.success(f"✅ 车辆信息保存成功！并已复制配置")
                                else:
                                    st.success(f"✅ 车辆信息保存成功！但配置复制失败：{message}")
                        else:
                            st.success(f"✅ 车辆信息保存成功！")

                        st.info(f"车辆ID: {new_vehicle_id}")
                        st.session_state['global_selected_vehicle_id'] = new_vehicle_id
                        st.balloons()
                        time.sleep(1.5)
                        st.rerun()

                    except ValueError as ve:
                        st.error(f"❌ 验证失败：{str(ve)}")
                    except Exception as e:
                        st.error(f"❌ 保存失败：{str(e)}")

        st.markdown("---")
        st.markdown("### 📝 字段说明")
        st.markdown("""
        - **车型***：车辆型号
        - **底盘号***：车辆唯一识别码
        - **总质量***：车辆GVW质量（kg）
        - **备注**：可选的附加信息
        - **能源类型***：自由填写（新建与编辑均必填）
        - **车辆归属平台***：自由填写（新建与编辑均必填）
        """)