# app.py - 主程序入口（Streamlit Cloud 演示版）
import streamlit as st
from datetime import datetime, timedelta
import logging, time
from auth import init_auth, create_default_admin, login, logout, change_password, show_user_management

st.set_page_config(
    page_title="X试验报告管理系统",
    page_icon="🚗",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={}
)

st.markdown("""
<style>
div[data-testid="stSidebarNav"] {display: none;}
* { cursor: default !important; }
button, [role="button"], input, textarea, select { cursor: auto !important; }
.frozen-warning-box {
    background-color: #fff3cd; border: 2px solid #ffc107;
    border-left: 6px solid #ff9800; border-radius: 8px;
    padding: 16px 20px; margin: 15px 0;
}
.frozen-warning-box h4 { color: #856404; margin: 0 0 8px 0; font-size: 16px; font-weight: bold; }
.frozen-warning-box p { color: #856404; margin: 0; font-size: 14px; }
.frozen-error-box {
    background-color: #f8d7da; border: 2px solid #f5c6cb;
    border-left: 6px solid #dc3545; border-radius: 8px;
    padding: 16px 20px; margin: 15px 0;
}
.frozen-error-box h4 { color: #721c24; margin: 0 0 8px 0; font-size: 16px; font-weight: bold; }
.frozen-error-box p { color: #721c24; margin: 0; font-size: 14px; }
.demo-banner {
    background: linear-gradient(135deg, #0ea5e9 0%, #6366f1 100%);
    border-radius: 10px; padding: 10px 16px; margin-bottom: 12px;
    color: white; font-size: 13px; text-align: center;
}
</style>
""", unsafe_allow_html=True)

from database import init_database, get_vehicles
from db_config import connection_pool

from pages import (
    show_home_page, show_admin_home, show_vehicle_management,
    show_data_entry, show_image_management, show_report_generation,
    show_data_dashboard,
    show_database_management, show_delete_vehicles
)


def main():
    st.markdown(
        '<div class="demo-banner">☁️ Streamlit Cloud 演示版 · SQLite 本地数据库 · 默认账号 admin/admin123</div>',
        unsafe_allow_html=True,
    )

    try:
        connection_pool.initialize()
        if 'db_initialized' not in st.session_state:
            init_database()
            st.session_state['db_initialized'] = True
    except Exception as e:
        st.error(f"数据库初始化失败: {str(e)}")
        return

    init_auth()
    create_default_admin()

    is_logged_in = st.session_state.get('logged_in', False)

    with st.sidebar:
        if not is_logged_in:
            st.markdown("### 🔐 登录系统")
            st.markdown("---")
            with st.form("sidebar_login_form", clear_on_submit=False):
                username = st.text_input("用户名", placeholder="请输入用户名", key="sidebar_login_username")
                password = st.text_input("密码", type="password", placeholder="请输入密码", key="sidebar_login_password")
                submitted = st.form_submit_button("登 录", type="primary", use_container_width=True)
                if submitted:
                    if not username or not password:
                        st.error("请输入用户名和密码")
                    else:
                        success, message = login(username, password)
                        if success:
                            st.success("登录成功！")
                            time.sleep(0.5)
                            st.rerun()
                        else:
                            st.error(message)
            st.markdown("---")
            st.markdown("""
            <div style="font-size: 12px; color: #888; text-align: center; padding: 10px;">
                X · X<br>试验报告管理系统 · 演示版
            </div>
            """, unsafe_allow_html=True)
        else:
            if 'global_selected_vehicle_id' not in st.session_state:
                vehicles = get_vehicles()
                if vehicles:
                    st.session_state['global_selected_vehicle_id'] = vehicles[0][0]

            st.markdown("### 🚗 X试验报告系统")
            st.markdown(f"👤 **{st.session_state.get('full_name', st.session_state.get('username', ''))}**")
            if st.session_state.get('is_admin_user', False):
                st.markdown("🔴 **管理员账号**")
            else:
                st.markdown("🟢 **工程师账号**")
            st.markdown("---")

            is_admin = st.session_state.get('is_admin_user', False)
            if is_admin:
                menu_options = [
                    ("👑 管理员首页", "admin_home"),
                    ("👥 用户管理", "user_management"),
                    ("📋 性能基础数据维护", "perf_basic_data"),
                    ("🗄️ 性能数据库管理", "database_management"),
                    ("🗑️ 删除车辆", "delete_vehicles"),
                    ("🔓 冻结车辆管理", "frozen_vehicles"),
                    ("", None),
                    ("🏠 **首页**", "home"),
                    ("", None),
                    ("🚗 **汽车性能数据**", None),
                    ("   🚗 车辆管理", "vehicles"),
                    ("   📝 测试数据录入", "data_entry"),
                    ("   🖼️ 图片管理", "images"),
                    ("   📄 报告生成", "report"),
                    ("   📊 数据看板", "dashboard"),
                ]
            else:
                menu_options = [
                    ("🏠 **首页**", "home"),
                    ("", None),
                    ("🚗 **汽车性能数据**", None),
                    ("   🚗 车辆管理", "vehicles"),
                    ("   📝 测试数据录入", "data_entry"),
                    ("   🖼️ 图片管理", "images"),
                    ("   📄 报告生成", "report"),
                    ("   📊 数据看板", "dashboard"),
                ]

            for option_text, option_key in menu_options:
                if option_key is None:
                    st.markdown(option_text)
                elif option_text == "":
                    st.markdown("---")
                else:
                    button_type = "primary" if st.session_state.get('current_page') == option_key else "secondary"
                    if st.button(option_text, key=f"menu_{option_key}", use_container_width=True, type=button_type):
                        st.session_state['current_page'] = option_key
                        st.rerun()

            st.markdown("---")
            with st.expander("🔧 账户设置", expanded=False):
                if st.button("🔑 修改密码", use_container_width=True, key="sidebar_change_password"):
                    st.session_state['show_change_password'] = True
                if st.button("🚪 登出", use_container_width=True, key="sidebar_logout"):
                    logout()
                    st.rerun()

            if st.session_state.get('show_change_password', False):
                with st.form("change_password_form_sidebar"):
                    st.subheader("修改密码")
                    old_pwd = st.text_input("旧密码", type="password")
                    new_pwd = st.text_input("新密码", type="password")
                    confirm_pwd = st.text_input("确认新密码", type="password")
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.form_submit_button("确认修改"):
                            if new_pwd != confirm_pwd:
                                st.error("两次输入的新密码不一致")
                            elif not old_pwd or not new_pwd:
                                st.error("密码不能为空")
                            else:
                                success, message = change_password(
                                    st.session_state['username'], old_pwd, new_pwd
                                )
                                if success:
                                    st.success(message)
                                    st.session_state['show_change_password'] = False
                                    st.rerun()
                                else:
                                    st.error(message)
                    with col2:
                        if st.form_submit_button("取消"):
                            st.session_state['show_change_password'] = False
                            st.rerun()

    if not is_logged_in:
        st.markdown("""
        <style>
        .preview-banner {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            border-radius: 16px; padding: 16px 24px; margin-bottom: 24px;
            display: flex; align-items: center; justify-content: space-between;
        }
        .preview-banner span { color: white; font-size: 14px; }
        .preview-badge {
            background: rgba(255,255,255,0.2); padding: 4px 12px;
            border-radius: 20px; color: white; font-size: 12px;
        }
        </style>
        <div class="preview-banner">
            <span>🔒 请先在左侧登录，即可访问完整功能</span>
            <span class="preview-badge">预览模式</span>
        </div>
        """, unsafe_allow_html=True)
        from pages.home import show_home_page
        show_home_page("👤 工程师")
    else:
        current_page = st.session_state.get('current_page', 'home')
        is_admin = st.session_state.get('is_admin_user', False)
        admin_pages = [
            'admin_home', 'user_management', 'perf_basic_data',
            'database_management', 'delete_vehicles', 'frozen_vehicles',
        ]
        if not is_admin and current_page in admin_pages:
            st.session_state['current_page'] = 'home'
            st.rerun()

        if current_page == 'home':
            from pages.home import show_home_page
            show_home_page(st.session_state.get('user_type', '👤 工程师'))
        elif current_page == 'admin_home':
            show_admin_home()
        elif current_page == 'user_management':
            show_user_management()
        elif current_page == 'frozen_vehicles':
            from pages.admin import show_frozen_vehicles_management
            show_frozen_vehicles_management()
        elif current_page == 'perf_basic_data':
            from pages.admin_perf_basic import show_performance_basic_data_maintenance
            show_performance_basic_data_maintenance()
        elif current_page == 'database_management':
            show_database_management()
        elif current_page == 'delete_vehicles':
            show_delete_vehicles()
        elif current_page == 'vehicles':
            show_vehicle_management()
        elif current_page == 'dashboard':
            show_data_dashboard()
        elif current_page == 'data_entry':
            show_data_entry()
        elif current_page == 'images':
            show_image_management()
        elif current_page == 'report':
            show_report_generation()


if __name__ == "__main__":
    main()
