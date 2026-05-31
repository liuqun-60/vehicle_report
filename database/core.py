# database/core.py
"""
核心数据库操作函数
基础的增删改查操作
"""
import os
import logging
from datetime import datetime
from pathlib import Path

from db_config import connection_pool

logger = logging.getLogger(__name__)


def _get_owner_filter():
    try:
        from auth import get_owner_filter_username
        return get_owner_filter_username()
    except Exception:
        return None


def _get_current_creator():
    try:
        from auth import get_current_username
        return get_current_username()
    except Exception:
        return ''


def _check_vehicle_owner_access(vehicle_id):
    """非管理员只能访问自己创建的车辆"""
    owner = _get_owner_filter()
    if owner is None:
        return True
    try:
        with connection_pool.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT created_by FROM vehicles WHERE id = %s", (vehicle_id,))
            row = cursor.fetchone()
            if not row:
                return False
            created_by = row[0] or ''
            return created_by == owner
    except Exception as e:
        logger.error(f"检查车辆权限失败: {e}")
        return False


def get_user_display_names(usernames=None):
    """批量解析用户名 → 显示姓名（无姓名则用用户名）"""
    if not usernames:
        return {}
    unique = list({u for u in usernames if u})
    if not unique:
        return {}
    try:
        with connection_pool.get_connection() as conn:
            cursor = conn.cursor(dictionary=True)
            placeholders = ','.join(['%s'] * len(unique))
            cursor.execute(
                f"SELECT username, full_name FROM users WHERE username IN ({placeholders})",
                unique
            )
            mapping = {}
            for row in cursor.fetchall():
                mapping[row['username']] = (row.get('full_name') or '').strip() or row['username']
            for u in unique:
                mapping.setdefault(u, u)
            return mapping
    except Exception as e:
        logger.error(f"获取用户显示名失败: {e}")
        return {u: u for u in unique}


# database/core.py

def check_vehicle_frozen(vehicle_id):
    """检查车辆是否已冻结，返回 (is_frozen, status)"""
    try:
        with connection_pool.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT status FROM vehicles WHERE id = %s", (vehicle_id,))
            result = cursor.fetchone()
            if result:
                status = result[0] or 'active'
                # 兼容多种冻结状态表示方式
                is_frozen = status == 'frozen' or status == '冻结' or status == 'FROZEN'
                return is_frozen, status
            return False, 'active'
    except Exception as e:
        logger.error(f"检查车辆冻结状态失败: {e}")
        return False, 'active'


# database/core.py

def require_vehicle_active(vehicle_id):
    """
    要求车辆处于激活状态才能执行写操作
    如果已冻结，抛出异常
    """
    if not _check_vehicle_owner_access(vehicle_id):
        raise PermissionError("无权操作该车辆")
    is_frozen, status = check_vehicle_frozen(vehicle_id)
    if is_frozen:
        raise PermissionError("⚠️ 车辆已冻结，如需修改请联系管理员！")


def freeze_vehicle(vehicle_id):
    """冻结车辆"""
    if not _check_vehicle_owner_access(vehicle_id):
        return False, "无权操作该车辆"
    try:
        with connection_pool.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE vehicles SET status = 'frozen' WHERE id = %s", (vehicle_id,))
            conn.commit()
            return True, "车辆已冻结"
    except Exception as e:
        logger.error(f"冻结车辆失败: {e}")
        return False, f"冻结失败: {str(e)}"


def unfreeze_vehicle(vehicle_id):
    """解冻车辆"""
    try:
        with connection_pool.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE vehicles SET status = 'active' WHERE id = %s", (vehicle_id,))
            conn.commit()
            return True, "车辆已解冻"
    except Exception as e:
        logger.error(f"解冻车辆失败: {e}")
        return False, f"解冻失败: {str(e)}"


# ========== 目录相关函数 ==========

def get_main_categories():
    """获取所有一级目录"""
    try:
        with connection_pool.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, name FROM main_categories ORDER BY display_order")
            return cursor.fetchall()
    except Exception as e:
        logger.error(f"获取一级目录失败: {e}")
        return []


def get_sub_categories(main_category_id):
    """获取指定一级目录下的二级目录"""
    try:
        with connection_pool.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT id, name FROM sub_categories 
                WHERE main_category_id = %s 
                ORDER BY display_order
            ''', (main_category_id,))
            return cursor.fetchall()
    except Exception as e:
        logger.error(f"获取二级目录失败: {e}")
        return []


# ========== 测试项目相关函数 ==========

def get_test_items(sub_category_id):
    """获取指定二级目录下的测试项目"""
    try:
        with connection_pool.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT id, name, unit, data_type FROM test_items 
                WHERE sub_category_id = %s 
                ORDER BY display_order
            ''', (sub_category_id,))
            return cursor.fetchall()
    except Exception as e:
        logger.error(f"获取测试项目失败: {e}")
        return []


def get_all_test_items():
    """获取所有测试项目"""
    try:
        with connection_pool.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT ti.id, ti.name, ti.unit, sc.name as sub_category, mc.name as main_category
                FROM test_items ti
                JOIN sub_categories sc ON ti.sub_category_id = sc.id
                JOIN main_categories mc ON sc.main_category_id = mc.id
                ORDER BY ti.display_order
            ''')
            return cursor.fetchall()
    except Exception as e:
        logger.error(f"获取所有测试项目失败: {e}")
        return []


def get_test_item_by_name_and_unit(name, unit):
    """根据测试项目名称和单位获取测试项目ID"""
    try:
        with connection_pool.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT id FROM test_items 
                WHERE name = %s AND unit = %s
                LIMIT 1
            ''', (name, unit))
            result = cursor.fetchone()
            return result[0] if result else None
    except Exception as e:
        logger.error(f"获取测试项目ID失败: {e}")
        return None


# ========== 车辆相关函数 ==========

def _validate_vehicle_data(vehicle_data):
    """校验车辆必填字段"""
    if not vehicle_data.get('model'):
        raise ValueError("车型不能为空")
    if not vehicle_data.get('chassis_number'):
        raise ValueError("底盘号不能为空")
    if not vehicle_data.get('curb_weight'):
        raise ValueError("整备质量不能为空")
    if not str(vehicle_data.get('energy_type', '')).strip():
        raise ValueError("能源类型不能为空")
    if not str(vehicle_data.get('vehicle_platform', '')).strip():
        raise ValueError("车辆归属平台不能为空")


def get_vehicles():
    """获取车辆列表（普通用户仅自己的；管理员全部）"""
    try:
        with connection_pool.get_connection() as conn:
            cursor = conn.cursor()
            owner = _get_owner_filter()
            sql = """SELECT id, model, chassis_number, curb_weight, notes,
                            energy_type, vehicle_platform, created_by
                     FROM vehicles"""
            params = []
            if owner:
                sql += " WHERE created_by = %s"
                params.append(owner)
            sql += " ORDER BY created_at DESC"
            cursor.execute(sql, params)
            return cursor.fetchall()
    except Exception as e:
        logger.error(f"获取车辆失败: {e}")
        return []


def get_vehicles_with_filters(model_filter=None, chassis_filter=None, min_weight=None, max_weight=None):
    """根据筛选条件获取车辆列表"""
    try:
        with connection_pool.get_connection() as conn:
            cursor = conn.cursor()
            query = """
                SELECT id, model, chassis_number, curb_weight, notes,
                       energy_type, vehicle_platform, created_by
                FROM vehicles 
                WHERE 1=1
            """
            params = []

            owner = _get_owner_filter()
            if owner:
                query += " AND created_by = %s"
                params.append(owner)

            if model_filter:
                query += " AND model LIKE %s"
                params.append(f"%{model_filter}%")

            if chassis_filter:
                query += " AND chassis_number LIKE %s"
                params.append(f"%{chassis_filter}%")

            query += " ORDER BY created_at DESC"

            cursor.execute(query, params)
            vehicles = cursor.fetchall()

            if min_weight is not None or max_weight is not None:
                filtered_vehicles = []
                for vehicle in vehicles:
                    vehicle_id, model, chassis, weight_str, notes = vehicle[0], vehicle[1], vehicle[2], vehicle[3], vehicle[4]
                    weight_value = None
                    if weight_str:
                        try:
                            import re
                            numbers = re.findall(r'\d+', str(weight_str))
                            if numbers:
                                weight_value = float(numbers[0])
                        except:
                            pass

                    weight_ok = True
                    if min_weight is not None and weight_value is not None:
                        if weight_value < min_weight:
                            weight_ok = False
                    if max_weight is not None and weight_value is not None:
                        if weight_value > max_weight:
                            weight_ok = False

                    if weight_ok:
                        filtered_vehicles.append(vehicle)

                return filtered_vehicles

            return vehicles
    except Exception as e:
        logger.error(f"筛选车辆失败: {e}")
        return []


def get_vehicle_details(vehicle_id):
    """获取车辆详细信息"""
    try:
        with connection_pool.get_connection() as conn:
            cursor = conn.cursor()
            if not _check_vehicle_owner_access(vehicle_id):
                return None

            cursor.execute('''
                SELECT id, model, chassis_number, curb_weight, notes,
                       energy_type, vehicle_platform, created_at, created_by
                FROM vehicles WHERE id = %s
            ''', (vehicle_id,))
            vehicle = cursor.fetchone()

            if vehicle:
                created_by = vehicle[8] or ''
                display_map = get_user_display_names([created_by]) if created_by else {}
                return {
                    'id': vehicle[0],
                    'model': vehicle[1],
                    'chassis_number': vehicle[2],
                    'curb_weight': vehicle[3],
                    'notes': vehicle[4] or '',
                    'energy_type': vehicle[5] or '',
                    'vehicle_platform': vehicle[6] or '',
                    'created_at': vehicle[7],
                    'created_by': created_by,
                    'creator_display': display_map.get(created_by, created_by),
                }
            return None
    except Exception as e:
        logger.error(f"获取车辆详情失败: {e}")
        return None


def save_vehicle(vehicle_data):
    """保存车辆信息"""
    try:
        with connection_pool.get_connection() as conn:
            cursor = conn.cursor()
            # 按创建时间生成唯一ID
            vehicle_id = f"V{datetime.now().strftime('%Y%m%d%H%M%S')}"

            _validate_vehicle_data(vehicle_data)
            created_by = _get_current_creator()

            cursor.execute('''
                INSERT INTO vehicles (id, model, chassis_number, curb_weight, notes,
                                      energy_type, vehicle_platform, created_by)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ''', (vehicle_id, vehicle_data['model'], vehicle_data['chassis_number'],
                  vehicle_data['curb_weight'], vehicle_data.get('notes', ''),
                  str(vehicle_data.get('energy_type', '')).strip(),
                  str(vehicle_data.get('vehicle_platform', '')).strip(),
                  created_by))
            conn.commit()
            return vehicle_id
    except ValueError as ve:
        logger.error(f"车辆数据验证失败: {ve}")
        raise ve
    except Exception as e:
        logger.error(f"保存车辆失败: {e}")
        raise


def update_vehicle(vehicle_id, vehicle_data):
    """更新车辆信息"""
    if not _check_vehicle_owner_access(vehicle_id):
        raise PermissionError("无权修改该车辆")
    require_vehicle_active(vehicle_id)
    try:
        with connection_pool.get_connection() as conn:
            cursor = conn.cursor()

            _validate_vehicle_data(vehicle_data)

            cursor.execute('''
                UPDATE vehicles 
                SET model = %s, chassis_number = %s, curb_weight = %s, notes = %s,
                    energy_type = %s, vehicle_platform = %s
                WHERE id = %s
            ''', (
                vehicle_data['model'],
                vehicle_data['chassis_number'],
                vehicle_data['curb_weight'],
                vehicle_data.get('notes', ''),
                str(vehicle_data.get('energy_type', '')).strip(),
                str(vehicle_data.get('vehicle_platform', '')).strip(),
                vehicle_id
            ))
            conn.commit()
            return True
    except ValueError as ve:
        logger.error(f"车辆数据验证失败: {ve}")
        raise ve
    except Exception as e:
        logger.error(f"更新车辆失败: {e}")
        raise


def delete_vehicle(vehicle_id):
    """删除车辆及其所有相关数据"""
    require_vehicle_active(vehicle_id)
    try:
        with connection_pool.get_connection() as conn:
            cursor = conn.cursor()

            # 删除相关数据（由于设置了ON DELETE CASCADE，只需删除车辆记录即可）
            cursor.execute('DELETE FROM vehicles WHERE id = %s', (vehicle_id,))

            # 删除图片文件
            import shutil
            uploads_dir = Path(f"uploads/{vehicle_id}")
            if uploads_dir.exists():
                shutil.rmtree(uploads_dir)

            conn.commit()
            return True, "车辆删除成功"
    except Exception as e:
        try:
            conn.rollback()
        except Exception:
            pass
        logger.error(f"删除车辆失败: {e}")
        return False, f"删除车辆失败：{str(e)}"


def copy_vehicle_configurations(source_vehicle_id, new_vehicle_id):
    """复制源车辆的配置到新车辆"""
    if not _check_vehicle_owner_access(source_vehicle_id):
        return False, "无权复制该源车辆配置"
    try:
        with connection_pool.get_connection() as conn:
            cursor = conn.cursor()

            # 复制报告配置
            cursor.execute('''
                INSERT INTO report_configs (vehicle_id, config_type, config_key, config_value)
                SELECT %s, config_type, config_key, config_value
                FROM report_configs
                WHERE vehicle_id = %s
            ''', (new_vehicle_id, source_vehicle_id))

            # 复制测试信息配置
            cursor.execute('''
                INSERT INTO test_info_configs (vehicle_id, main_category_id, info_key, info_value)
                SELECT %s, main_category_id, info_key, info_value
                FROM test_info_configs
                WHERE vehicle_id = %s
            ''', (new_vehicle_id, source_vehicle_id))

            # 复制试验项目
            cursor.execute('''
                INSERT INTO test_projects (vehicle_id, project_number, project_name, execution_standard, display_order)
                SELECT %s, project_number, project_name, execution_standard, display_order
                FROM test_projects
                WHERE vehicle_id = %s
            ''', (new_vehicle_id, source_vehicle_id))

            # 复制试验设备
            cursor.execute('''
                INSERT INTO test_equipment (vehicle_id, equipment_name, equipment_accuracy, display_order)
                SELECT %s, equipment_name, equipment_accuracy, display_order
                FROM test_equipment
                WHERE vehicle_id = %s
            ''', (new_vehicle_id, source_vehicle_id))

            conn.commit()
            return True, "车辆配置复制成功"
    except Exception as e:
        try:
            conn.rollback()
        except Exception:
            pass
        logger.error(f"复制车辆配置失败: {e}")
        return False, f"复制配置失败：{str(e)}"


# ========== 测试结果相关函数 ==========

def get_vehicle_test_results(vehicle_id, only_valid=False):
    """获取指定车辆的所有测试结果"""
    try:
        with connection_pool.get_connection() as conn:
            cursor = conn.cursor()
            base_query = '''
                SELECT tr.test_item_id, tr.value, tr.test_date, ti.name, ti.unit, 
                       sc.name as sub_category, mc.name as main_category
                FROM test_results tr
                JOIN test_items ti ON tr.test_item_id = ti.id
                JOIN sub_categories sc ON ti.sub_category_id = sc.id
                JOIN main_categories mc ON sc.main_category_id = mc.id
                WHERE tr.vehicle_id = %s
            '''

            if only_valid:
                base_query += " AND tr.value IS NOT NULL AND tr.value != '' AND TRIM(tr.value) != ''"

            base_query += " ORDER BY ti.display_order"

            cursor.execute(base_query, (vehicle_id,))
            return cursor.fetchall()
    except Exception as e:
        logger.error(f"获取车辆测试结果失败: {e}")
        return []


def get_vehicle_test_data_for_report(vehicle_id):
    """获取车辆测试数据用于生成报告（自动重新编号）"""
    try:
        with connection_pool.get_connection() as conn:
            cursor = conn.cursor(dictionary=True)
            cursor.execute('''
                SELECT 
                    mc.name as main_category,
                    sc.name as sub_category,
                    ti.name as test_item,
                    ti.unit,
                    tr.value,
                    ti.display_order
                FROM test_items ti
                JOIN sub_categories sc ON ti.sub_category_id = sc.id
                JOIN main_categories mc ON sc.main_category_id = mc.id
                LEFT JOIN test_results tr ON ti.id = tr.test_item_id AND tr.vehicle_id = %s
                ORDER BY ti.display_order
            ''', (vehicle_id,))

            results = cursor.fetchall()
            report_data = {}

            for row in results:
                main_cat = row['main_category']
                value = row['value']

                if value and str(value).strip():
                    if main_cat not in report_data:
                        report_data[main_cat] = []

                    report_data[main_cat].append({
                        '二级项目': row['sub_category'],
                        '测试项目': row['test_item'],
                        '测试项目单位': row['unit'],
                        '数据': value
                    })

            for main_cat, items in report_data.items():
                for idx, item in enumerate(items, start=1):
                    item['序号'] = idx

            return report_data
    except Exception as e:
        logger.error(f"获取报告数据失败: {e}")
        return {}


def get_vehicle_test_comparison_data(vehicle_ids, test_item_id=None):
    """获取车辆测试对比数据"""
    try:
        if not vehicle_ids:
            return []

        with connection_pool.get_connection() as conn:
            cursor = conn.cursor()
            vehicles_info = []

            for vehicle_id in vehicle_ids:
                cursor.execute(
                    "SELECT id, model, chassis_number, curb_weight FROM vehicles WHERE id = %s",
                    (vehicle_id,)
                )
                result = cursor.fetchone()
                if result:
                    vehicles_info.append({
                        'id': result[0],
                        'model': result[1],
                        'chassis_number': result[2],
                        'curb_weight': result[3]
                    })

            if not test_item_id:
                return []

            comparison_data = []
            for vehicle_info in vehicles_info:
                cursor.execute('''
                    SELECT tr.value, ti.name, ti.unit
                    FROM test_results tr
                    JOIN test_items ti ON tr.test_item_id = ti.id
                    WHERE tr.vehicle_id = %s AND tr.test_item_id = %s
                ''', (vehicle_info['id'], test_item_id))

                result = cursor.fetchone()
                if result:
                    test_value = result[0]
                    test_name = result[1]
                    test_unit = result[2]

                    try:
                        numeric_value = float(test_value)
                    except:
                        numeric_value = None

                    comparison_data.append({
                        'vehicle_id': vehicle_info['id'],
                        'model': vehicle_info['model'],
                        'chassis_number': vehicle_info['chassis_number'],
                        'curb_weight': vehicle_info['curb_weight'],
                        'test_item_id': test_item_id,
                        'test_item_name': test_name,
                        'test_item_unit': test_unit,
                        'test_value': test_value,
                        'numeric_value': numeric_value
                    })

            return comparison_data
    except Exception as e:
        logger.error(f"获取车辆测试对比数据失败: {e}")
        return []


def get_vehicle_comparison_data(vehicle_ids):
    """获取车辆对比数据"""
    try:
        with connection_pool.get_connection() as conn:
            cursor = conn.cursor(dictionary=True)

            cursor.execute('''
                SELECT ti.id, ti.name, ti.unit, sc.name as sub_category, mc.name as main_category
                FROM test_items ti
                JOIN sub_categories sc ON ti.sub_category_id = sc.id
                JOIN main_categories mc ON sc.main_category_id = mc.id
                ORDER BY ti.display_order
            ''')
            test_items = cursor.fetchall()

            vehicles_info = []
            for vehicle_id in vehicle_ids:
                cursor.execute("SELECT model, chassis_number, curb_weight FROM vehicles WHERE id = %s", (vehicle_id,))
                vehicle_info = cursor.fetchone()
                if vehicle_info:
                    vehicles_info.append({
                        'id': vehicle_id,
                        'model': vehicle_info['model'],
                        'chassis_number': vehicle_info['chassis_number'],
                        'curb_weight': vehicle_info['curb_weight']
                    })

            comparison_data = []
            for item in test_items:
                item_id = item['id']
                row_data = {
                    '测试大类': item['main_category'],
                    '二级目录': item['sub_category'],
                    '测试项目': item['name'],
                    '单位': item['unit']
                }

                for vehicle in vehicles_info:
                    cursor.execute('''
                        SELECT value FROM test_results 
                        WHERE vehicle_id = %s AND test_item_id = %s
                    ''', (vehicle['id'], item_id))
                    result = cursor.fetchone()
                    value = result['value'] if result else ""
                    column_name = f"{vehicle['model']}_{vehicle['chassis_number']}"
                    row_data[column_name] = value

                comparison_data.append(row_data)

            return comparison_data, vehicles_info
    except Exception as e:
        logger.error(f"获取车辆对比数据失败: {e}")
        return [], []


# database/core.py - 在 save_test_result 函数末尾添加

def save_test_result(vehicle_id, test_item_id, value, test_date=None):
    """保存测试结果 - 使用ON DUPLICATE KEY UPDATE实现覆盖"""
    require_vehicle_active(vehicle_id)  # 确保这行存在
    try:
        with connection_pool.get_connection() as conn:
            cursor = conn.cursor()
            if test_date is None:
                test_date = datetime.now().strftime("%Y%m%d")

            cursor.execute('''
                INSERT INTO test_results (vehicle_id, test_item_id, value, test_date)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT(vehicle_id, test_item_id) DO UPDATE SET
                    value = excluded.value,
                    test_date = excluded.test_date
            ''', (vehicle_id, test_item_id, value, test_date))
            conn.commit()

            # 更新统计表
            update_vehicle_stats(vehicle_id)

            # 清除数据看板缓存
            try:
                import streamlit as st
                keys_to_clear = ['vehicles_info', 'all_test_results', 'report_configs', 'vehicle_stats']
                for key in keys_to_clear:
                    if key in st.session_state:
                        del st.session_state[key]
            except:
                pass

    except PermissionError:
        raise
    except Exception as e:
        logger.error(f"保存测试结果失败: {e}")
        raise
# ========== 报告配置相关函数 ==========

def save_report_config(vehicle_id, config_type, config_data):
    """保存报告配置 - 使用ON DUPLICATE KEY UPDATE实现覆盖"""
    require_vehicle_active(vehicle_id)
    from date_input_utils import validate_date_fields_in_mapping
    ok, errors, config_data = validate_date_fields_in_mapping(config_data)
    if not ok:
        raise ValueError('；'.join(errors))
    try:
        with connection_pool.get_connection() as conn:
            cursor = conn.cursor()
            for key, value in config_data.items():
                cursor.execute('''
                    INSERT INTO report_configs (vehicle_id, config_type, config_key, config_value)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT(vehicle_id, config_type, config_key) DO UPDATE SET
                        config_value = excluded.config_value
                ''', (vehicle_id, config_type, key, value))
            conn.commit()
    except Exception as e:
        logger.error(f"保存报告配置失败: {e}")
        raise


def get_report_config(vehicle_id, config_type):
    """获取报告配置"""
    try:
        with connection_pool.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT config_key, config_value FROM report_configs 
                WHERE vehicle_id = %s AND config_type = %s
            ''', (vehicle_id, config_type))
            results = cursor.fetchall()
            return {row[0]: row[1] for row in results} if results else {}
    except Exception as e:
        logger.error(f"获取报告配置失败: {e}")
        return {}


# ========== 测试信息配置相关函数 ==========

def save_test_info_config(vehicle_id, main_category_id, info_data):
    """保存测试信息配置 - 使用ON DUPLICATE KEY UPDATE实现覆盖"""
    require_vehicle_active(vehicle_id)
    try:
        with connection_pool.get_connection() as conn:
            cursor = conn.cursor()

            for key, value in info_data.items():
                if value and value.strip():
                    cursor.execute('''
                        INSERT INTO test_info_configs (vehicle_id, main_category_id, info_key, info_value)
                        VALUES (%s, %s, %s, %s)
                        ON CONFLICT(vehicle_id, main_category_id, info_key) DO UPDATE SET
                            info_value = excluded.info_value
                    ''', (vehicle_id, main_category_id, key, value.strip()))

            conn.commit()
    except Exception as e:
        logger.error(f"保存测试信息配置失败: {e}")
        raise


def get_test_info_config(vehicle_id, main_category_id):
    """获取测试信息配置"""
    try:
        with connection_pool.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT info_key, info_value FROM test_info_configs 
                WHERE vehicle_id = %s AND main_category_id = %s
            ''', (vehicle_id, main_category_id))

            results = cursor.fetchall()
            config_dict = {row[0]: row[1] for row in results} if results else {}

            from config import TEST_INFO_FIELDS
            for key in TEST_INFO_FIELDS:
                if key not in config_dict:
                    config_dict[key] = ''

            return config_dict
    except Exception as e:
        logger.error(f"获取测试信息配置失败: {e}")
        from config import TEST_INFO_FIELDS
        return {key: '' for key in TEST_INFO_FIELDS}


# ========== 图片管理相关函数 ==========

def save_report_image(vehicle_id, main_category_id, image_name, image_path):
    """保存报告图片"""
    require_vehicle_active(vehicle_id)
    try:
        with connection_pool.get_connection() as conn:
            cursor = conn.cursor()

            # 获取当前最大display_order
            cursor.execute('''
                SELECT COALESCE(MAX(display_order), 0) FROM report_images 
                WHERE vehicle_id = %s AND main_category_id = %s
            ''', (vehicle_id, main_category_id))
            max_order = cursor.fetchone()[0]

            cursor.execute('''
                INSERT INTO report_images (vehicle_id, main_category_id, image_name, image_path, display_order)
                VALUES (%s, %s, %s, %s, %s)
            ''', (vehicle_id, main_category_id, image_name, image_path, max_order + 1))
            conn.commit()
    except Exception as e:
        logger.error(f"保存报告图片失败: {e}")
        raise


# database/core.py - 在 save_report_image 函数附近添加

def save_report_image_by_category(vehicle_id, main_category_name, image_name, image_path):
    """
    根据一级目录名称保存报告图片
    改为：存储到该一级目录的代表测试项目ID下
    """
    require_vehicle_active(vehicle_id)
    try:
        representative_item_id = get_representative_test_item_id(main_category_name)
        if not representative_item_id:
            raise ValueError(f"未找到一级目录 {main_category_name} 的代表测试项目")

        with connection_pool.get_connection() as conn:
            cursor = conn.cursor()

            # 获取当前最大display_order
            cursor.execute('''
                SELECT COALESCE(MAX(display_order), 0) FROM report_images 
                WHERE vehicle_id = %s AND main_category_id = %s
            ''', (vehicle_id, representative_item_id))
            max_order = cursor.fetchone()[0]

            cursor.execute('''
                INSERT INTO report_images (vehicle_id, main_category_id, image_name, image_path, display_order)
                VALUES (%s, %s, %s, %s, %s)
            ''', (vehicle_id, representative_item_id, image_name, image_path, max_order + 1))
            conn.commit()
            return True
    except Exception as e:
        logger.error(f"保存报告图片失败: {e}")
        raise


def get_report_images_by_category(vehicle_id, main_category_name):
    """
    根据一级目录名称获取报告图片
    改为：从该一级目录的代表测试项目ID下读取
    """
    try:
        representative_item_id = get_representative_test_item_id(main_category_name)
        if not representative_item_id:
            return []

        with connection_pool.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT image_name, image_path FROM report_images 
                WHERE vehicle_id = %s AND main_category_id = %s
                ORDER BY display_order, id
            ''', (vehicle_id, representative_item_id))
            return cursor.fetchall()
    except Exception as e:
        logger.error(f"获取报告图片失败: {e}")
        return []

def get_report_images(vehicle_id, main_category_id):
    """获取报告图片"""
    try:
        with connection_pool.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT image_name, image_path FROM report_images 
                WHERE vehicle_id = %s AND main_category_id = %s
                ORDER BY display_order, id
            ''', (vehicle_id, main_category_id))
            return cursor.fetchall()
    except Exception as e:
        logger.error(f"获取报告图片失败: {e}")
        return []


def delete_report_images(vehicle_id, main_category_id):
    """删除报告图片"""
    require_vehicle_active(vehicle_id)
    try:
        with connection_pool.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                DELETE FROM report_images 
                WHERE vehicle_id = %s AND main_category_id = %s
            ''', (vehicle_id, main_category_id))
            conn.commit()
    except Exception as e:
        logger.error(f"删除报告图片失败: {e}")
        raise


def save_sample_car_image(vehicle_id, image_name, image_path):
    """保存样车照片"""
    require_vehicle_active(vehicle_id)
    try:
        with connection_pool.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO sample_car_images (vehicle_id, image_name, image_path)
                VALUES (%s, %s, %s)
            ''', (vehicle_id, image_name, image_path))
            conn.commit()
    except Exception as e:
        logger.error(f"保存样车照片失败: {e}")
        raise


def get_sample_car_images(vehicle_id):
    """获取样车照片"""
    try:
        with connection_pool.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT image_name, image_path FROM sample_car_images 
                WHERE vehicle_id = %s
                ORDER BY id
            ''', (vehicle_id,))
            return cursor.fetchall()
    except Exception as e:
        logger.error(f"获取样车照片失败: {e}")
        return []


def delete_sample_car_images(vehicle_id):
    """删除样车照片"""
    require_vehicle_active(vehicle_id)
    try:
        with connection_pool.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                DELETE FROM sample_car_images 
                WHERE vehicle_id = %s
            ''', (vehicle_id,))
            conn.commit()
    except Exception as e:
        logger.error(f"删除样车照片失败: {e}")
        raise


# ========== 试验项目相关函数 ==========

def save_test_projects(vehicle_id, projects_data):
    """保存试验项目 - 先删除后插入（全量覆盖）"""
    require_vehicle_active(vehicle_id)
    try:
        with connection_pool.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM test_projects WHERE vehicle_id = %s', (vehicle_id,))

            for project in projects_data:
                cursor.execute('''
                    INSERT INTO test_projects (vehicle_id, project_number, project_name, execution_standard, display_order)
                    VALUES (%s, %s, %s, %s, %s)
                ''', (
                    vehicle_id,
                    int(project['序号']),
                    str(project['项目名称']).strip(),
                    str(project.get('执行标准', '')).strip(),
                    int(project['序号'])
                ))

            conn.commit()
            return True
    except Exception as e:
        try:
            conn.rollback()
        except Exception:
            pass
        logger.error(f"保存试验项目失败: {e}")
        raise ValueError(f"保存试验项目失败：{str(e)}")


def get_test_projects(vehicle_id):
    """获取试验项目"""
    try:
        with connection_pool.get_connection() as conn:
            cursor = conn.cursor(dictionary=True)
            cursor.execute('''
                SELECT project_number, project_name, execution_standard 
                FROM test_projects 
                WHERE vehicle_id = %s
                ORDER BY display_order, project_number
            ''', (vehicle_id,))

            projects = []
            for row in cursor.fetchall():
                projects.append({
                    '序号': row['project_number'],
                    '项目名称': row['project_name'],
                    '执行标准': row['execution_standard']
                })
            return projects
    except Exception as e:
        logger.error(f"获取试验项目失败: {e}")
        return []


def save_test_equipment(vehicle_id, equipment_data):
    """保存试验设备 - 先删除后插入（全量覆盖）"""
    require_vehicle_active(vehicle_id)
    try:
        with connection_pool.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM test_equipment WHERE vehicle_id = %s', (vehicle_id,))

            for equipment in equipment_data:
                cursor.execute('''
                    INSERT INTO test_equipment (vehicle_id, equipment_name, equipment_accuracy, display_order)
                    VALUES (%s, %s, %s, %s)
                ''', (
                    vehicle_id,
                    str(equipment['设备名称']).strip(),
                    str(equipment.get('设备精度', '')).strip(),
                    int(equipment['序号'])
                ))

            conn.commit()
            return True
    except Exception as e:
        try:
            conn.rollback()
        except Exception:
            pass
        logger.error(f"保存试验设备失败: {e}")
        raise ValueError(f"保存试验设备失败：{str(e)}")


def get_test_equipment(vehicle_id):
    """获取试验设备"""
    try:
        with connection_pool.get_connection() as conn:
            cursor = conn.cursor(dictionary=True)
            cursor.execute('''
                SELECT equipment_name, equipment_accuracy, display_order 
                FROM test_equipment 
                WHERE vehicle_id = %s
                ORDER BY display_order
            ''', (vehicle_id,))

            equipment_list = []
            results = cursor.fetchall()

            for idx, row in enumerate(results, start=1):
                equipment_list.append({
                    '序号': idx,
                    '设备名称': row['equipment_name'],
                    '设备精度': row['equipment_accuracy']
                })

            return equipment_list
    except Exception as e:
        logger.error(f"获取试验设备失败: {e}")
        return []


# ========== 签名相关函数 ==========

def save_signature(vehicle_id, signature_type, signature_name, signature_path, signature_date):
    """保存签名 - 使用ON DUPLICATE KEY UPDATE实现覆盖"""
    require_vehicle_active(vehicle_id)
    try:
        with connection_pool.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO report_signatures 
                (vehicle_id, signature_type, signature_name, signature_path, signature_date)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT(vehicle_id, signature_type) DO UPDATE SET
                    signature_name = excluded.signature_name,
                    signature_path = excluded.signature_path,
                    signature_date = excluded.signature_date
            ''', (vehicle_id, signature_type, signature_name, signature_path, signature_date))
            conn.commit()
    except Exception as e:
        logger.error(f"保存签名失败: {e}")
        raise


def get_signature(vehicle_id, signature_type):
    """获取签名"""
    try:
        with connection_pool.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT signature_name, signature_path, signature_date 
                FROM report_signatures 
                WHERE vehicle_id = %s AND signature_type = %s
            ''', (vehicle_id, signature_type))

            result = cursor.fetchone()
            if result:
                return {
                    'signature_name': result[0],
                    'signature_path': result[1],
                    'signature_date': result[2]
                }
            return None
    except Exception as e:
        logger.error(f"获取签名失败: {e}")
        return None


def save_signature_image(vehicle_id, signature_type, signature_file):
    """保存签名图片到文件系统并记录到数据库"""
    require_vehicle_active(vehicle_id)
    try:
        with connection_pool.get_connection() as conn:
            cursor = conn.cursor()
            signature_dir = Path(f"uploads/{vehicle_id}/signatures")
            signature_dir.mkdir(parents=True, exist_ok=True)

            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

            if hasattr(signature_file, 'name'):
                file_extension = os.path.splitext(signature_file.name)[1] if signature_file.name else '.png'
                filename = f"{signature_type}_{timestamp}{file_extension}"
            else:
                filename = f"{signature_type}_{timestamp}.png"

            file_path = signature_dir / filename

            if hasattr(signature_file, 'read'):
                with open(file_path, "wb") as f:
                    f.write(signature_file.read())
            elif isinstance(signature_file, str):
                import shutil
                shutil.copy2(signature_file, file_path)
            else:
                with open(file_path, "wb") as f:
                    if isinstance(signature_file, bytes):
                        f.write(signature_file)
                    else:
                        f.write(signature_file.getvalue() if hasattr(signature_file, 'getvalue') else bytes(signature_file))

            if hasattr(signature_file, 'name'):
                signature_name = signature_file.name
            else:
                signature_name = filename

            cursor.execute('''
                INSERT INTO report_signatures 
                (vehicle_id, signature_type, signature_name, signature_path, signature_date)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT(vehicle_id, signature_type) DO UPDATE SET
                    signature_name = excluded.signature_name,
                    signature_path = excluded.signature_path,
                    signature_date = excluded.signature_date
            ''', (vehicle_id, signature_type, signature_name, str(file_path),
                  datetime.now().strftime("%Y%m%d")))

            conn.commit()
            return True, str(file_path)
    except Exception as e:
        import traceback
        logger.error(f"保存签名图片错误: {traceback.format_exc()}")
        return False, f"保存签名图片失败：{str(e)}"


def get_signature_image_path(vehicle_id, signature_type):
    """获取签名图片路径"""
    try:
        with connection_pool.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT signature_path FROM report_signatures 
                WHERE vehicle_id = %s AND signature_type = %s
            ''', (vehicle_id, signature_type))
            result = cursor.fetchone()
            return result[0] if result else None
    except Exception as e:
        logger.error(f"获取签名图片路径失败: {e}")
        return None


def get_all_signature_images(vehicle_id):
    """获取车辆的所有签名图片"""
    try:
        with connection_pool.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT signature_type, signature_path, signature_date 
                FROM report_signatures 
                WHERE vehicle_id = %s
            ''', (vehicle_id,))

            signatures = {}
            for row in cursor.fetchall():
                signature_type = row[0]
                signature_path = row[1]
                signature_date = row[2]
                signatures[signature_type] = {
                    'path': signature_path,
                    'date': signature_date
                }

            return signatures
    except Exception as e:
        logger.error(f"获取所有签名图片失败: {e}")
        return {}


# ========== 状态检查函数 ==========

def check_database_status():
    """检查数据库状态"""
    try:
        with connection_pool.get_connection() as conn:
            cursor = conn.cursor()
            tables_to_check = ['main_categories', 'sub_categories', 'test_items', 'vehicles']
            status = {}
            for table in tables_to_check:
                cursor.execute(f"SELECT COUNT(*) FROM {table}")
                count = cursor.fetchone()[0]
                status[table] = count
            return True, status
    except Exception as e:
        return False, f"数据库状态检查失败: {str(e)}"


# database/core.py - 修改 save_test_info_config_batch 函数

def save_test_info_config_batch(vehicle_id, test_info_data):
    """
    批量保存测试信息配置
    改为：根据一级目录名称，存储到对应的代表测试项目ID下
    """
    require_vehicle_active(vehicle_id)
    from date_input_utils import validate_compact_date
    for row_data in test_info_data:
        raw_date = row_data.get('试验日期', '')
        if raw_date is not None and str(raw_date).strip():
            ok, normalized = validate_compact_date(raw_date, '试验日期')
            if not ok:
                return False, normalized
            row_data['试验日期'] = normalized
    try:
        with connection_pool.get_connection() as conn:
            cursor = conn.cursor()

            saved_count = 0
            for row_data in test_info_data:
                main_category_name = row_data.get('main_category')
                if not main_category_name:
                    continue

                # 获取该一级目录的代表测试项目ID
                representative_item_id = get_representative_test_item_id(main_category_name)
                if not representative_item_id:
                    logger.warning(f"未找到一级目录 {main_category_name} 的代表测试项目")
                    continue

                # 字段映射
                field_mapping = {
                    '试验日期': '试验日期',
                    '总质量（kg）': '总质量（kg）',
                    '试验地点': '试验地点',
                    '天气': '天气',
                    '里程（km）': '里程（km）',
                    '备注': '备注'
                }

                for info_key, display_name in field_mapping.items():
                    value = row_data.get(display_name, '')
                    if value and str(value).strip():
                        # 使用代表测试项目ID作为 main_category_id
                        cursor.execute('''
                            INSERT INTO test_info_configs 
                            (vehicle_id, main_category_id, info_key, info_value)
                            VALUES (%s, %s, %s, %s)
                            ON CONFLICT(vehicle_id, main_category_id, info_key) DO UPDATE SET
                                info_value = excluded.info_value
                        ''', (vehicle_id, representative_item_id, info_key, str(value).strip()))
                        saved_count += 1
                    else:
                        # 如果值为空，可以选择删除该配置（可选）
                        cursor.execute('''
                            DELETE FROM test_info_configs 
                            WHERE vehicle_id = %s AND main_category_id = %s AND info_key = %s
                        ''', (vehicle_id, representative_item_id, info_key))

            conn.commit()
            return True, f"成功保存 {saved_count} 条测试信息配置"

    except Exception as e:
        logger.error(f"批量保存测试信息配置失败: {e}")
        return False, f"保存失败：{str(e)}"


# database/core.py - 修改 get_test_info_config_batch 函数

def get_test_info_config_batch(vehicle_id):
    """
    批量获取测试信息配置 - 返回表格格式数据
    改为：根据代表测试项目ID反查一级目录名称
    """
    try:
        with connection_pool.get_connection() as conn:
            cursor = conn.cursor(dictionary=True)

            # 获取所有一级目录
            cursor.execute("SELECT id, name FROM main_categories ORDER BY display_order")
            main_categories = cursor.fetchall()

            # 获取该车辆的所有测试信息配置
            # 注意：现在 main_category_id 存的是测试项目ID
            cursor.execute('''
                SELECT main_category_id, info_key, info_value
                FROM test_info_configs
                WHERE vehicle_id = %s
            ''', (vehicle_id,))
            config_rows = cursor.fetchall()

            # 整理数据：按代表测试项目ID分组
            config_dict = {}
            for row in config_rows:
                item_id = row['main_category_id']
                if item_id not in config_dict:
                    config_dict[item_id] = {}
                config_dict[item_id][row['info_key']] = row['info_value']

            # 构建表格数据
            table_data = []
            field_columns = ['试验日期', '总质量（kg）', '试验地点', '天气', '里程（km）', '备注']

            for cat in main_categories:
                cat_name = cat['name']
                cat_id = cat['id']  # 这是一级目录的ID，仅用于显示顺序

                # 获取该一级目录的代表测试项目ID
                representative_item_id = get_representative_test_item_id(cat_name)

                row_data = {
                    'main_category': cat_name,
                    'main_category_id': cat_id,
                }

                # 从 config_dict 中查找配置
                if representative_item_id and representative_item_id in config_dict:
                    item_config = config_dict[representative_item_id]
                    for field in field_columns:
                        row_data[field] = item_config.get(field, '')
                else:
                    for field in field_columns:
                        row_data[field] = ''

                table_data.append(row_data)

            return table_data

    except Exception as e:
        logger.error(f"批量获取测试信息配置失败: {e}")
        return []


def update_vehicle_stats(vehicle_id):
    """
    更新指定车辆的统计信息
    作用：在保存/删除测试数据时调用，保持统计表与test_results表同步
    """
    try:
        with connection_pool.get_connection() as conn:
            cursor = conn.cursor()

            # 1. 获取车辆基本信息
            cursor.execute("SELECT model, chassis_number FROM vehicles WHERE id = %s", (vehicle_id,))
            vehicle = cursor.fetchone()
            if not vehicle:
                return

            model, chassis_number = vehicle

            # 2. 统计有效测试数据数量（非空、非空白字符串）
            cursor.execute('''
                SELECT COUNT(*) FROM test_results 
                WHERE vehicle_id = %s 
                AND value IS NOT NULL 
                AND value != '' 
                AND TRIM(value) != ''
            ''', (vehicle_id,))
            valid_count = cursor.fetchone()[0]

            # 3. 总项目数（固定555个）
            total_items = 555

            # 4. 计算完成率
            completion_rate = round(valid_count / total_items * 100, 2) if total_items > 0 else 0

            # 5. 更新统计表（存在则更新，不存在则插入）
            cursor.execute('''
                INSERT INTO vehicle_stats (vehicle_id, model, chassis_number, valid_count, total_items, completion_rate)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT(vehicle_id) DO UPDATE SET
                    model = excluded.model,
                    chassis_number = excluded.chassis_number,
                    valid_count = excluded.valid_count,
                    completion_rate = excluded.completion_rate
            ''', (vehicle_id, model, chassis_number, valid_count, total_items, completion_rate))

            conn.commit()

    except Exception as e:
        logger.error(f"更新车辆统计失败: {e}")


# database/core.py - 在文件末尾添加

def get_all_vehicles_test_results_batch(vehicle_ids=None):
    """
    批量获取所有车辆的测试结果
    一次性查询，避免循环查询

    Args:
        vehicle_ids: 车辆ID列表，为None时查询所有车辆

    Returns:
        dict: {vehicle_id: {test_item_id: value}}
    """
    try:
        with connection_pool.get_connection() as conn:
            cursor = conn.cursor()

            # 构建查询条件
            if vehicle_ids:
                placeholders = ','.join(['%s'] * len(vehicle_ids))
                query = f'''
                    SELECT vehicle_id, test_item_id, value 
                    FROM test_results 
                    WHERE vehicle_id IN ({placeholders})
                    AND value IS NOT NULL 
                    AND value != '' 
                    AND TRIM(value) != ''
                '''
                cursor.execute(query, vehicle_ids)
            else:
                cursor.execute('''
                    SELECT vehicle_id, test_item_id, value 
                    FROM test_results 
                    WHERE value IS NOT NULL 
                    AND value != '' 
                    AND TRIM(value) != ''
                ''')

            results = cursor.fetchall()

            # 组织成字典结构
            test_data = {}
            for row in results:
                vehicle_id = row[0]
                test_item_id = row[1]
                value = row[2]

                if vehicle_id not in test_data:
                    test_data[vehicle_id] = {}
                test_data[vehicle_id][test_item_id] = value

            return test_data

    except Exception as e:
        logger.error(f"批量获取测试结果失败: {e}")
        return {}


def get_all_vehicles_info_batch():
    """
    批量获取所有车辆的详细信息
    一次性查询，避免循环查询

    Returns:
        dict: {vehicle_id: {model, chassis_number, curb_weight, notes, created_at}}
    """
    try:
        with connection_pool.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT id, model, chassis_number, curb_weight, notes,
                       energy_type, vehicle_platform, created_at, created_by
                FROM vehicles 
                ORDER BY created_at DESC
            ''')
            results = cursor.fetchall()

            creators = [row[8] or '' for row in results if row[8]]
            display_map = get_user_display_names(creators)

            vehicles_info = {}
            for row in results:
                created_by = row[8] or ''
                vehicles_info[row[0]] = {
                    'id': row[0],
                    'model': row[1],
                    'chassis_number': row[2],
                    'curb_weight': row[3] or '',
                    'notes': row[4] or '',
                    'energy_type': row[5] or '',
                    'vehicle_platform': row[6] or '',
                    'created_at': row[7],
                    'created_by': created_by,
                    'creator_display': display_map.get(created_by, created_by),
                }

            return vehicles_info

    except Exception as e:
        logger.error(f"批量获取车辆信息失败: {e}")
        return {}


def get_all_report_configs_batch():
    """
    批量获取所有车辆的报告配置
    一次性查询，避免循环查询

    Returns:
        dict: {vehicle_id: {config_key: config_value}}
    """
    try:
        with connection_pool.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT vehicle_id, config_key, config_value 
                FROM report_configs 
                WHERE config_type = 'header'
            ''')
            results = cursor.fetchall()

            report_configs = {}
            for row in results:
                vehicle_id = row[0]
                config_key = row[1]
                config_value = row[2]

                if vehicle_id not in report_configs:
                    report_configs[vehicle_id] = {}
                report_configs[vehicle_id][config_key] = config_value

            return report_configs

    except Exception as e:
        logger.error(f"批量获取报告配置失败: {e}")
        return {}


# database/core.py - 在文件末尾添加

def get_representative_test_item_id(main_category_name):
    """
    获取一级目录的代表测试项目ID（该目录下 display_order 最小的项目）

    Args:
        main_category_name: 一级目录名称，如"动力性"

    Returns:
        测试项目ID，如"TI0010"，如果没有则返回 None
    """
    try:
        from db_config import connection_pool
        with connection_pool.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT ti.id
                FROM test_items ti
                JOIN sub_categories sc ON ti.sub_category_id = sc.id
                JOIN main_categories mc ON sc.main_category_id = mc.id
                WHERE mc.name = %s
                ORDER BY ti.display_order
                LIMIT 1
            ''', (main_category_name,))
            result = cursor.fetchone()
            return result[0] if result else None
    except Exception as e:
        logger.error(f"获取代表测试项目失败: {e}")
        return None


def get_main_category_name_by_representative_item(test_item_id):
    """
    根据代表测试项目ID反查一级目录名称

    Args:
        test_item_id: 测试项目ID，如"TI0010"

    Returns:
        一级目录名称，如"动力性"，如果没有则返回 None
    """
    try:
        from db_config import connection_pool
        with connection_pool.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT mc.name
                FROM test_items ti
                JOIN sub_categories sc ON ti.sub_category_id = sc.id
                JOIN main_categories mc ON sc.main_category_id = mc.id
                WHERE ti.id = %s
            ''', (test_item_id,))
            result = cursor.fetchone()
            return result[0] if result else None
    except Exception as e:
        logger.error(f"反查一级目录名称失败: {e}")
        return None


# database/core.py - 在文件末尾添加

def delete_report_images_by_category(vehicle_id, main_category_name):
    """
    根据一级目录名称删除报告图片
    """
    require_vehicle_active(vehicle_id)
    try:
        representative_item_id = get_representative_test_item_id(main_category_name)
        if not representative_item_id:
            return

        with connection_pool.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                DELETE FROM report_images 
                WHERE vehicle_id = %s AND main_category_id = %s
            ''', (vehicle_id, str(representative_item_id)))  # 确保是字符串
            conn.commit()
    except Exception as e:
        logger.error(f"删除报告图片失败: {e}")
        raise