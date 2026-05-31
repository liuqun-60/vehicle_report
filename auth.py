"""
用户认证模块
"""
import streamlit as st
from datetime import datetime
import logging
import time

logger = logging.getLogger(__name__)


def init_auth():
    """初始化认证模块"""
    if 'logged_in' not in st.session_state:
        st.session_state['logged_in'] = False
    if 'username' not in st.session_state:
        st.session_state['username'] = None
    if 'is_admin_user' not in st.session_state:
        st.session_state['is_admin_user'] = False


def create_default_admin():
    """创建默认管理员账号（如果用户表为空）"""
    try:
        from db_config import connection_pool
        with connection_pool.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM users WHERE username = %s", ('admin',))
            count = cursor.fetchone()[0]

            if count == 0:
                cursor.execute('''
                    INSERT INTO users (username, password, full_name, is_admin)
                    VALUES (%s, %s, %s, %s)
                ''', ('admin', 'admin123', '系统管理员', True))
                conn.commit()
                print("✅ 已创建默认管理员账号: admin / admin123")
                return True
    except Exception as e:
        print(f"创建默认管理员失败: {e}")
    return False


def login(username, password):
    """用户登录验证"""
    try:
        from db_config import connection_pool
        with connection_pool.get_connection() as conn:
            cursor = conn.cursor(dictionary=True)
            cursor.execute('''
                SELECT * FROM users
                WHERE username = %s AND password = %s AND is_active = TRUE
            ''', (username, password))
            user = cursor.fetchone()

            if user:
                # 更新最后登录时间
                cursor.execute('''
                    UPDATE users SET last_login = %s WHERE id = %s
                ''', (datetime.now(), user['id']))
                conn.commit()

                st.session_state['logged_in'] = True
                st.session_state['username'] = user['username']
                st.session_state['full_name'] = user.get('full_name', user['username'])
                st.session_state['is_admin_user'] = user.get('is_admin', False)
                
                # ========== 新增：根据账号类型自动设置用户类型 ==========
                if user.get('is_admin', False):
                    st.session_state['user_type'] = "👑 管理员"
                    st.session_state['current_page'] = 'admin_home' # 管理员直接进入管理员首页
                else:
                    st.session_state['user_type'] = "👤 工程师"
                    st.session_state['current_page'] = 'home' # 普通用户进入首页
                
                return True, "登录成功"
            else:
                return False, "用户名或密码错误"
    except Exception as e:
        logger.error(f"登录失败: {e}")
        return False, f"登录失败: {str(e)}"


def logout():
    """用户登出"""
    st.session_state['logged_in'] = False
    st.session_state['username'] = None
    st.session_state['full_name'] = None
    st.session_state['is_admin_user'] = False


def is_current_admin():
    """当前登录用户是否为管理员"""
    return bool(st.session_state.get('is_admin_user'))


def get_current_username():
    """当前登录用户名"""
    return st.session_state.get('username') or ''


def get_owner_filter_username():
    """
    数据归属过滤：管理员返回 None（可见全部），普通用户返回自己的用户名。
    数据看板不使用此函数。
    """
    if not st.session_state.get('logged_in'):
        return None
    if is_current_admin():
        return None
    return get_current_username()


def change_password(username, old_password, new_password):
    """修改密码"""
    try:
        from db_config import connection_pool
        with connection_pool.get_connection() as conn:
            cursor = conn.cursor()
            # 验证旧密码
            cursor.execute('''
                SELECT id FROM users WHERE username = %s AND password = %s
            ''', (username, old_password))
            if not cursor.fetchone():
                return False, "旧密码错误"

            # 更新密码
            cursor.execute('''
                UPDATE users SET password = %s WHERE username = %s
            ''', (new_password, username))
            conn.commit()
            return True, "密码修改成功"
    except Exception as e:
        return False, f"修改失败: {str(e)}"


def get_all_users():
    """获取所有用户"""
    try:
        from db_config import connection_pool
        with connection_pool.get_connection() as conn:
            cursor = conn.cursor(dictionary=True)
            cursor.execute('''
                SELECT id, username, password, full_name, is_active, is_admin, created_at, last_login
                FROM users ORDER BY created_at DESC
            ''')
            return cursor.fetchall()
    except Exception as e:
        logger.error(f"获取用户列表失败: {e}")
        return []


def create_user(username, password, full_name='', is_admin=False):
    """创建新用户"""
    try:
        from db_config import connection_pool
        with connection_pool.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO users (username, password, full_name, is_admin)
                VALUES (%s, %s, %s, %s)
            ''', (username, password, full_name, is_admin))
            conn.commit()
            return True, f"用户 {username} 创建成功"
    except Exception as e:
        if "Duplicate entry" in str(e):
            return False, f"用户名 {username} 已存在"
        return False, f"创建失败: {str(e)}"


def update_user(user_id, password=None, full_name=None, is_active=None, is_admin=None):
    """更新用户信息"""
    try:
        from db_config import connection_pool
        with connection_pool.get_connection() as conn:
            cursor = conn.cursor()
            updates = []
            params = []

            if password is not None:
                updates.append("password = %s")
                params.append(password)
            if full_name is not None:
                updates.append("full_name = %s")
                params.append(full_name)
            if is_active is not None:
                updates.append("is_active = %s")
                params.append(is_active)
            if is_admin is not None:
                updates.append("is_admin = %s")
                params.append(is_admin)

            if updates:
                params.append(user_id)
                cursor.execute(f'''
                    UPDATE users SET {', '.join(updates)} WHERE id = %s
                ''', params)
                conn.commit()
            return True, "用户更新成功"
    except Exception as e:
        return False, f"更新失败: {str(e)}"

def delete_user(user_id):
    """删除用户"""
    try:
        from db_config import connection_pool
        with connection_pool.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM users WHERE id = %s", (user_id,))
            conn.commit()
            return True, "用户删除成功"
    except Exception as e:
        return False, f"删除失败: {str(e)}"


def show_user_management():
    """显示用户管理界面（管理员功能）- 简化版，显示密码"""
    st.markdown("""
    <style>
    .user-management-header {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 20px;
        border-radius: 15px;
        margin-bottom: 20px;
    }
    .password-cell {
        font-family: 'Courier New', monospace;
        background: #f8f9fa;
        padding: 4px 8px;
        border-radius: 4px;
        font-size: 13px;
    }
    </style>
    """, unsafe_allow_html=True)

    st.markdown("""
    <div class="user-management-header">
        <h2 style="color: white; margin: 0;">👥 用户管理</h2>
        <p style="color: rgba(255,255,255,0.9); margin: 10px 0 0 0;">管理系统用户账号，可查看和修改密码</p>
    </div>
    """, unsafe_allow_html=True)

    tab1, tab2 = st.tabs(["📋 用户列表", "➕ 新增用户"])

    with tab1:
        users = get_all_users()
        if users:
            import pandas as pd
            from date_input_utils import format_db_datetime

            # 构建显示数据
            display_data = []
            for u in users:
                display_data.append({
                    'ID': u['id'],
                    '用户名': u['username'],
                    '姓名': u.get('full_name', '') or '未设置',
                    '密码': u['password'],
                    '状态': '✅ 启用' if u.get('is_active', True) else '❌ 禁用',
                    '创建时间': format_db_datetime(u['created_at']),
                    '最后登录': format_db_datetime(u.get('last_login')) or '从未登录'
                })

            df = pd.DataFrame(display_data)

            # 显示表格
            st.dataframe(
                df,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "ID": st.column_config.TextColumn("ID", width="small"),
                    "用户名": st.column_config.TextColumn("用户名", width="medium"),
                    "姓名": st.column_config.TextColumn("姓名", width="medium"),
                    "密码": st.column_config.TextColumn("密码", width="medium"),
                    "状态": st.column_config.TextColumn("状态", width="small"),
                    "创建时间": st.column_config.TextColumn("创建时间", width="medium"),
                    "最后登录": st.column_config.TextColumn("最后登录", width="medium"),
                }
            )

            st.markdown("---")
            st.subheader("✏️ 编辑用户")

            # 选择用户
            user_options = [f"{u['username']} ({u.get('full_name', '未设置姓名')})" for u in users]
            selected_user_str = st.selectbox("选择要编辑的用户", user_options, key="user_edit_select")

            if selected_user_str:
                selected_username = selected_user_str.split(" ")[0]
                selected_user = next((u for u in users if u['username'] == selected_username), None)

                if selected_user:
                    with st.form("edit_user_form"):
                        st.markdown(f"### 编辑用户: {selected_user['username']}")

                        col1, col2 = st.columns(2)

                        with col1:
                            new_full_name = st.text_input(
                                "姓名",
                                value=selected_user.get('full_name') or '',
                                placeholder="显示名称"
                            )
                            new_password = st.text_input(
                                "新密码",
                                type="password",
                                placeholder="留空则不修改",
                                help="输入新密码以修改，留空保持原密码"
                            )

                        with col2:
                            new_is_active = st.checkbox(
                                "启用账号",
                                value=selected_user.get('is_active', True),
                                help="取消勾选将禁用该账号"
                            )
                            # 显示当前密码
                            st.info(f"当前密码: `{selected_user['password']}`")

                        col_btn1, col_btn2, col_btn3 = st.columns(3)

                        with col_btn1:
                            submitted = st.form_submit_button("💾 保存修改", use_container_width=True)
                            if submitted:
                                success, message = update_user(
                                    selected_user['id'],
                                    password=new_password if new_password else None,
                                    full_name=new_full_name,
                                    is_active=new_is_active,
                                    is_admin=None  # 不再修改管理员权限
                                )
                                if success:
                                    st.success(message)
                                    st.rerun()
                                else:
                                    st.error(message)

                        with col_btn2:
                            if st.form_submit_button("🗑️ 删除用户", use_container_width=True):
                                if selected_user['username'] == 'admin':
                                    st.error("不能删除默认管理员账号")
                                else:
                                    success, message = delete_user(selected_user['id'])
                                    if success:
                                        st.success(message)
                                        st.rerun()
                                    else:
                                        st.error(message)

                        with col_btn3:
                            if st.form_submit_button("🔄 重置密码为123456", use_container_width=True):
                                success, message = update_user(
                                    selected_user['id'],
                                    password='123456',
                                    full_name=None,
                                    is_active=None,
                                    is_admin=None
                                )
                                if success:
                                    st.success(f"密码已重置为 123456")
                                    st.rerun()
                                else:
                                    st.error(message)

        else:
            st.info("暂无用户数据")

    with tab2:
        st.subheader("➕ 创建新用户")

        with st.form("create_user_form"):
            col1, col2 = st.columns(2)

            with col1:
                new_username = st.text_input(
                    "用户名 *",
                    placeholder="登录账号，如: zhangsan"
                )
                new_full_name = st.text_input(
                    "姓名",
                    placeholder="显示名称，如: 张三"
                )

            with col2:
                new_password = st.text_input(
                    "密码 *",
                    type="password",
                    placeholder="初始密码",
                    value="123456"
                )
                st.caption("默认密码为 123456，可自行修改")

            st.markdown("---")

            submitted = st.form_submit_button("🚀 创建用户", type="primary", use_container_width=True)

            if submitted:
                if not new_username or not new_password:
                    st.error("❌ 用户名和密码不能为空")
                elif len(new_username) < 3:
                    st.error("❌ 用户名至少3个字符")
                else:
                    success, message = create_user(
                        new_username,
                        new_password,
                        new_full_name,
                        is_admin=False  # 固定为非管理员
                    )
                    if success:
                        st.success(f"✅ {message}")
                        st.balloons()
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error(f"❌ {message}")

        # 批量导入提示
        st.markdown("---")
        st.info("""
        💡 **提示**：
        - 所有用户默认拥有相同的操作权限
        - 管理员功能通过侧边栏的"管理员登录"密码验证访问
        - 默认管理员账号: `admin` / `admin123`
        """)
