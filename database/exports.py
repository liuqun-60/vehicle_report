# database/exports.py
"""
数据导出功能 - 修改版，适应新表结构
"""
import io
import csv
import logging
import pandas as pd
from datetime import datetime
from db_config import connection_pool

logger = logging.getLogger(__name__)


def export_database_to_csv():
    """导出测试项目结构CSV（项目ID、序号、一级目录、二级目录、测试项目、单位）- 修复版"""
    try:
        with connection_pool.get_connection() as conn:
            cursor = conn.cursor(dictionary=True)

            # 获取所有测试项目，按display_order排序
            cursor.execute('''
                SELECT 
                    ti.id as `项目ID`,
                    ti.display_order as `序号`,
                    mc.name as `一级目录`,
                    sc.name as `二级目录`,
                    ti.name as `测试项目`,
                    ti.unit as `单位`
                FROM test_items ti
                JOIN sub_categories sc ON ti.sub_category_id = sc.id
                JOIN main_categories mc ON sc.main_category_id = mc.id
                ORDER BY ti.display_order
            ''')

            items = cursor.fetchall()

            # 创建CSV内容
            output = io.StringIO()
            writer = csv.writer(output)

            # 写入表头 - 只保留需要的6列
            writer.writerow(['项目ID', '序号', '一级目录', '二级目录', '测试项目', '单位'])

            # 写入数据 - 只写入数据，不添加任何说明
            for item in items:
                writer.writerow([
                    item['项目ID'],
                    item['序号'],
                    item['一级目录'],
                    item['二级目录'],
                    item['测试项目'],
                    item['单位'] or ''  # 处理None情况
                ])

            csv_content = output.getvalue()
            output.close()

            return csv_content.encode('utf-8-sig')

    except Exception as e:
        logger.error(f"导出数据库结构失败: {e}")
        return None


def export_test_template(vehicle_id):
    """导出测试模板"""
    try:
        with connection_pool.get_connection() as conn:
            cursor = conn.cursor(dictionary=True)

            from .initializer import check_and_fix_serial_numbers
            success, message = check_and_fix_serial_numbers()
            if not success:
                return f"⚠️ 数据库序号有问题，请先联系管理员修复：\n{message}".encode('utf-8-sig')

            cursor.execute('''
                SELECT 
                    ti.id as `项目ID`,
                    ti.display_order as `序号`,
                    mc.name as `一级目录`,
                    sc.name as `二级目录`,
                    ti.name as `测试项目`,
                    ti.unit as `单位`
                FROM test_items ti
                JOIN sub_categories sc ON ti.sub_category_id = sc.id
                JOIN main_categories mc ON sc.main_category_id = mc.id
                ORDER BY ti.display_order
            ''')
            items = cursor.fetchall()

            # 获取现有数据
            cursor.execute('''
                SELECT test_item_id, value 
                FROM test_results 
                WHERE vehicle_id = %s
            ''', (vehicle_id,))
            results = cursor.fetchall()
            existing_data = {result['test_item_id']: result['value'] for result in results}

            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow(['项目ID', '序号', '一级目录', '二级目录', '测试项目', '单位', '测试值'])

            for item in items:
                item_id = item['项目ID']
                test_value = existing_data.get(item_id, '')
                writer.writerow([
                    item_id,
                    item['序号'],
                    item['一级目录'],
                    item['二级目录'],
                    item['测试项目'],
                    item['单位'],
                    test_value
                ])

            csv_content = output.getvalue()
            output.close()
            return csv_content.encode('utf-8-sig')
    except Exception as e:
        logger.error(f"导出测试模板失败: {e}")
        return f"导出失败: {str(e)}".encode('utf-8-sig')


# database/exports.py - 修改 export_multiple_vehicles_data 函数

def export_multiple_vehicles_data(vehicle_ids):
    """导出多辆车的测试数据（新格式：表头为车型，第2行开始为车辆信息）"""
    try:
        with connection_pool.get_connection() as conn:
            cursor = conn.cursor(dictionary=True)

            # 获取所有测试项目，按display_order排序
            cursor.execute('''
                SELECT 
                    ti.id as `项目ID`,
                    ti.display_order as `序号`,
                    mc.name as `一级目录`,
                    sc.name as `二级目录`,
                    ti.name as `测试项目`,
                    ti.unit as `单位`
                FROM test_items ti
                JOIN sub_categories sc ON ti.sub_category_id = sc.id
                JOIN main_categories mc ON sc.main_category_id = mc.id
                ORDER BY ti.display_order
            ''')
            test_items = cursor.fetchall()

            if not test_items:
                return None

            output = io.StringIO()
            writer = csv.writer(output)

            # ========== 第1行：表头 ==========
            # A-F固定列
            header_row = ['项目ID', '序号', '一级目录', '二级目录', '测试项目', '单位']

            vehicles_data = []
            for vehicle_id in vehicle_ids:
                # 获取车辆基本信息
                cursor.execute(
                    """SELECT id, model, chassis_number, curb_weight,
                              energy_type, vehicle_platform
                       FROM vehicles WHERE id = %s""",
                    (vehicle_id,))
                vehicle_info = cursor.fetchone()
                if not vehicle_info:
                    continue

                # 获取报告配置
                from .core import get_report_config
                report_config = get_report_config(vehicle_id, 'header')
                report_number = report_config.get('编号', '')
                report_name = report_config.get('名称', '')

                vehicles_data.append({
                    'vehicle_id': vehicle_info['id'],
                    'model': vehicle_info['model'],
                    'chassis_number': vehicle_info['chassis_number'],
                    'curb_weight': vehicle_info['curb_weight'] or '',
                    'energy_type': vehicle_info.get('energy_type') or '',
                    'vehicle_platform': vehicle_info.get('vehicle_platform') or '',
                    'report_number': report_number,
                    'report_name': report_name
                })
                # 表头：车型名称作为列标识
                header_row.append(vehicle_info['model'])

            if not vehicles_data:
                return None

            writer.writerow(header_row)

            # ========== 第2行：车辆ID ==========
            row2 = ['', '', '', '', '', '']
            for vehicle in vehicles_data:
                row2.append(vehicle['vehicle_id'])
            writer.writerow(row2)

            # ========== 第3行：报告编号 ==========
            row3 = ['', '', '', '', '', '']
            for vehicle in vehicles_data:
                row3.append(vehicle['report_number'])
            writer.writerow(row3)

            # ========== 第4行：报告名称 ==========
            row4 = ['', '', '', '', '', '']
            for vehicle in vehicles_data:
                row4.append(vehicle['report_name'])
            writer.writerow(row4)

            # ========== 第5行：底盘号 ==========
            row5 = ['', '', '', '', '', '']
            for vehicle in vehicles_data:
                row5.append(vehicle['chassis_number'])
            writer.writerow(row5)

            # ========== 第6行：总质量 ==========
            row6 = ['', '', '', '', '', '']
            for vehicle in vehicles_data:
                row6.append(vehicle['curb_weight'])
            writer.writerow(row6)

            # ========== 第7行：能源类型 ==========
            row7 = ['', '', '', '', '', '']
            for vehicle in vehicles_data:
                row7.append(vehicle['energy_type'])
            writer.writerow(row7)

            # ========== 第8行：车辆归属平台 ==========
            row8 = ['', '', '', '', '', '']
            for vehicle in vehicles_data:
                row8.append(vehicle['vehicle_platform'])
            writer.writerow(row8)

            # ========== 从第9行开始：测试数据 ==========
            for item in test_items:
                item_id = item['项目ID']
                data_row = [
                    item_id,
                    item['序号'],
                    item['一级目录'],
                    item['二级目录'],
                    item['测试项目'],
                    item['单位']
                ]

                for vehicle in vehicles_data:
                    cursor.execute('''
                        SELECT value FROM test_results 
                        WHERE vehicle_id = %s AND test_item_id = %s
                    ''', (vehicle['vehicle_id'], item_id))
                    result = cursor.fetchone()
                    test_value = result['value'] if result else ''
                    data_row.append(test_value)

                writer.writerow(data_row)

            csv_content = output.getvalue()
            output.close()
            return csv_content.encode('utf-8-sig')
    except Exception as e:
        logger.error(f"导出多车数据失败: {e}")
        return None


def export_database_structure():
    """导出数据库结构（用于查看）"""
    try:
        with connection_pool.get_connection() as conn:
            cursor = conn.cursor(dictionary=True)
            output = io.StringIO()
            writer = csv.writer(output)

            writer.writerow(['表名', '字段名', '类型', '是否主键', '说明'])

            tables = [
                'main_categories', 'sub_categories', 'test_items', 'vehicles',
                'test_results', 'report_configs', 'test_info_configs',
                'test_projects', 'test_equipment', 'report_signatures',
                'report_images', 'sample_car_images'
            ]

            for table in tables:
                cursor.execute(f"DESCRIBE `{table}`")
                columns = cursor.fetchall()
                for col in columns:
                    writer.writerow([
                        table,
                        col['Field'],
                        col['Type'],
                        '是' if col['Key'] == 'PRI' else '否',
                        ''
                    ])

            csv_content = output.getvalue()
            output.close()
            return csv_content.encode('utf-8-sig')
    except Exception as e:
        logger.error(f"导出数据库结构失败: {e}")
        return None


# database/exports.py - 添加以下函数

def export_selected_vehicles_full_data(vehicle_ids):
    """
    导出选中车辆的全部性能测试结果

    Args:
        vehicle_ids: 车辆ID列表

    Returns:
        CSV格式的字节数据
    """
    try:
        with connection_pool.get_connection() as conn:
            cursor = conn.cursor(dictionary=True)

            # 获取所有测试项目，按display_order排序
            cursor.execute('''
                SELECT 
                    ti.id as `项目ID`,
                    ti.display_order as `序号`,
                    mc.name as `一级目录`,
                    sc.name as `二级目录`,
                    ti.name as `测试项目`,
                    ti.unit as `单位`
                FROM test_items ti
                JOIN sub_categories sc ON ti.sub_category_id = sc.id
                JOIN main_categories mc ON sc.main_category_id = mc.id
                ORDER BY ti.display_order
            ''')
            test_items = cursor.fetchall()

            if not test_items:
                return None

            # 获取车辆信息
            vehicles_data = []
            for vehicle_id in vehicle_ids:
                cursor.execute('''
                    SELECT id, model, chassis_number, curb_weight,
                           energy_type, vehicle_platform
                    FROM vehicles WHERE id = %s
                ''', (vehicle_id,))
                vehicle_info = cursor.fetchone()
                if not vehicle_info:
                    continue

                # 获取报告编号
                from .core import get_report_config
                report_config = get_report_config(vehicle_id, 'header')
                report_number = report_config.get('编号', '')

                vehicles_data.append({
                    'vehicle_id': vehicle_info['id'],
                    'model': vehicle_info['model'],
                    'chassis_number': vehicle_info['chassis_number'],
                    'curb_weight': vehicle_info['curb_weight'] or '',
                    'energy_type': vehicle_info.get('energy_type') or '',
                    'vehicle_platform': vehicle_info.get('vehicle_platform') or '',
                    'report_number': report_number
                })

            if not vehicles_data:
                return None

            # 创建CSV内容
            output = io.StringIO()
            writer = csv.writer(output)

            # 第1行：表头（基础信息 + 车辆列）
            header_row = ['项目ID', '序号', '一级目录', '二级目录', '测试项目', '单位']
            for vehicle in vehicles_data:
                header_row.append(f"{vehicle['model']}")
            writer.writerow(header_row)

            # 第2行：车辆ID
            row2 = ['', '', '', '', '', '']
            for vehicle in vehicles_data:
                row2.append(vehicle['vehicle_id'])
            writer.writerow(row2)

            # 第3行：实验报告号
            row3 = ['', '', '', '', '', '']
            for vehicle in vehicles_data:
                row3.append(vehicle['report_number'])
            writer.writerow(row3)

            # 第4行：底盘号
            row4 = ['', '', '', '', '', '']
            for vehicle in vehicles_data:
                row4.append(vehicle['chassis_number'])
            writer.writerow(row4)

            # 第5行：总质量
            row5 = ['', '', '', '', '', '']
            for vehicle in vehicles_data:
                row5.append(vehicle['curb_weight'])
            writer.writerow(row5)

            # 第6行：能源类型
            row6 = ['', '', '', '', '', '']
            for vehicle in vehicles_data:
                row6.append(vehicle['energy_type'])
            writer.writerow(row6)

            # 第7行：车辆归属平台
            row7 = ['', '', '', '', '', '']
            for vehicle in vehicles_data:
                row7.append(vehicle['vehicle_platform'])
            writer.writerow(row7)

            # 从第8行开始：测试数据
            for item in test_items:
                item_id = item['项目ID']
                data_row = [
                    item_id,
                    item['序号'],
                    item['一级目录'],
                    item['二级目录'],
                    item['测试项目'],
                    item['单位']
                ]

                for vehicle in vehicles_data:
                    cursor.execute('''
                        SELECT value FROM test_results 
                        WHERE vehicle_id = %s AND test_item_id = %s
                    ''', (vehicle['vehicle_id'], item_id))
                    result = cursor.fetchone()
                    test_value = result['value'] if result else ''
                    data_row.append(test_value)

                writer.writerow(data_row)

            csv_content = output.getvalue()
            output.close()
            return csv_content.encode('utf-8-sig')

    except Exception as e:
        logger.error(f"导出选中车辆全部性能数据失败: {e}")
        return None


def export_performance_basic_data_csv():
    """导出性能基础数据维护表"""
    try:
        with connection_pool.get_connection() as conn:
            cursor = conn.cursor(dictionary=True)
            cursor.execute('''
                SELECT v.id, v.vehicle_platform, v.energy_type, v.created_by
                FROM vehicles v
                ORDER BY v.created_at DESC
            ''')
            vehicles = cursor.fetchall()
            report_numbers = {}
            cursor.execute("""
                SELECT vehicle_id, config_value FROM report_configs
                WHERE config_type = 'header' AND config_key = '编号'
            """)
            for row in cursor.fetchall():
                report_numbers[row['vehicle_id']] = row['config_value'] or ''

            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow(['车辆ID', '试验报告号', '编制人员工编码', '车辆归属平台', '能源类型'])
            for v in vehicles:
                writer.writerow([
                    v['id'],
                    report_numbers.get(v['id'], ''),
                    v.get('created_by') or '',
                    v.get('vehicle_platform') or '',
                    v.get('energy_type') or '',
                ])
            return output.getvalue().encode('utf-8-sig')
    except Exception as e:
        logger.error(f"导出性能基础数据失败: {e}")
        return None