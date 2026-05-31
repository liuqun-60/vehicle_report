# database/imports.py
"""
数据导入功能 - 修改版，使用覆盖逻辑
"""
import io
import csv
import logging
from datetime import datetime
from db_config import connection_pool
from .core import save_test_result

logger = logging.getLogger(__name__)


def import_database_from_csv(csv_content):
    """从CSV文件导入并更新数据库结构（安全重建版）- 6列版本"""
    try:
        with connection_pool.get_connection() as conn:
            cursor = conn.cursor()

            # 开始事务
            cursor.execute("PRAGMA foreign_keys = OFF")

            try:
                # 步骤1：解析CSV数据
                try:
                    csv_str = csv_content.decode('utf-8-sig')
                except:
                    csv_str = csv_content.decode('gbk')

                lines = csv_str.strip().split('\n')
                if len(lines) < 2:
                    return False, "CSV文件内容过少"

                # 解析表头
                headers = [h.strip() for h in lines[0].split(',')]
                expected_headers = ['项目ID', '序号', '一级目录', '二级目录', '测试项目', '单位']

                # 验证表头
                if len(headers) != len(expected_headers):
                    return False, f"CSV表头格式不正确，期望有{len(expected_headers)}列，实际有{len(headers)}列"

                for i, expected in enumerate(expected_headers):
                    if headers[i] != expected:
                        return False, f"CSV表头第{i + 1}列应为'{expected}'，实际为'{headers[i]}'"

                # 步骤2：收集CSV中的所有项目
                csv_items = []
                all_main_categories = set()
                all_sub_categories = {}  # {一级目录: set(二级目录)}

                for line_num, line in enumerate(lines[1:], start=2):
                    if not line.strip():
                        continue

                    # 解析CSV行
                    values = []
                    reader = csv.reader([line])
                    for row in reader:
                        values = row

                    if len(values) < len(headers):
                        continue

                    # 创建项目字典
                    item_dict = {}
                    for i, header in enumerate(headers):
                        if i < len(values):
                            item_dict[header] = values[i].strip()

                    # 验证必要字段
                    required_fields = ['序号', '一级目录', '二级目录', '测试项目']
                    for field in required_fields:
                        if not item_dict.get(field):
                            return False, f"第{line_num}行：缺少'{field}'字段"

                    try:
                        display_order = int(item_dict['序号'])
                        if display_order <= 0:
                            return False, f"第{line_num}行：序号必须为正整数"
                    except:
                        return False, f"第{line_num}行：序号 '{item_dict['序号']}' 不是有效数字"

                    # 收集数据
                    item_data = {
                        '序号': display_order,
                        '一级目录': item_dict['一级目录'],
                        '二级目录': item_dict['二级目录'],
                        '测试项目': item_dict['测试项目'],
                        '单位': item_dict.get('单位', ''),
                        '项目ID': item_dict.get('项目ID', '').strip()  # 可能为空（新项目）
                    }

                    csv_items.append(item_data)

                    # 收集目录信息
                    all_main_categories.add(item_dict['一级目录'])
                    if item_dict['一级目录'] not in all_sub_categories:
                        all_sub_categories[item_dict['一级目录']] = set()
                    all_sub_categories[item_dict['一级目录']].add(item_dict['二级目录'])

                # 验证序号连续且唯一
                display_orders = [item['序号'] for item in csv_items]
                if len(set(display_orders)) != len(csv_items):
                    return False, "序号重复：请确保每个序号都是唯一的"

                if min(display_orders) != 1:
                    return False, f"序号必须从1开始，实际最小序号为{min(display_orders)}"

                if max(display_orders) != len(csv_items):
                    return False, f"序号必须连续：应有{len(csv_items)}个项目，序号1-{len(csv_items)}，实际最大序号为{max(display_orders)}"

                print(f"📊 CSV解析完成：{len(csv_items)} 个项目，序号1-{len(csv_items)}")

                # 步骤3：备份当前测试项目（仅用于参考）
                cursor.execute("SELECT COUNT(*) FROM test_items")
                old_item_count = cursor.fetchone()[0]

                # 获取数据库中现有的最大ID号
                cursor.execute("""
                    SELECT MAX(CAST(SUBSTRING(id, 3) AS UNSIGNED)) 
                    FROM test_items 
                    WHERE id LIKE 'TI%'
                """)
                result = cursor.fetchone()
                current_max_id = result[0] if result[0] else 0
                print(f"📋 数据库中当前最大ID号：TI{current_max_id:04d}")

                # 步骤4：分离处理现有项目和新项目
                existing_items = []  # 有ID的项目（更新信息）
                new_items = []  # 无ID的项目（新建）

                for item in csv_items:
                    if item['项目ID'] and item['项目ID'].startswith('TI'):
                        # 现有项目（可能有更新）
                        existing_items.append(item)
                    else:
                        # 新项目（需要分配ID）
                        new_items.append(item)

                print(f"🔍 项目分类：{len(existing_items)} 个现有项目，{len(new_items)} 个新项目")

                # 步骤5：为新项目分配ID（从当前最大ID+1开始，只增不减）
                for item in new_items:
                    current_max_id += 1
                    item['项目ID'] = f"TI{current_max_id:04d}"
                    print(f"  分配新ID：序号{item['序号']} -> {item['项目ID']}")

                print(f"🆔 ID分配完成：新最大ID为 TI{current_max_id:04d}")

                # 步骤6：临时禁用外键约束
                cursor.execute("PRAGMA foreign_keys = OFF")

                # 步骤7：重建目录结构
                print("🏗️  重建目录结构...")

                # 清空并重建目录表
                cursor.execute("DELETE FROM sub_categories")
                cursor.execute("DELETE FROM main_categories")

                # 插入一级目录（按CSV中的顺序）
                main_cat_id_map = {}
                main_cat_order_map = {}  # 记录一级目录的顺序

                # 先收集所有一级目录及其出现的顺序
                unique_main_categories = []
                for item in csv_items:
                    main_cat = item['一级目录']
                    if main_cat not in main_cat_order_map:
                        main_cat_order_map[main_cat] = len(unique_main_categories) + 1
                        unique_main_categories.append(main_cat)

                # 按出现顺序插入一级目录
                for order, main_cat_name in enumerate(unique_main_categories, start=1):
                    cursor.execute('''
                        INSERT INTO main_categories (name, display_order)
                        VALUES (%s, %s)
                    ''', (main_cat_name, order))
                    main_cat_id = cursor.lastrowid
                    main_cat_id_map[main_cat_name] = main_cat_id

                # 插入二级目录（按CSV中的顺序）
                sub_cat_id_map = {}  # (main_cat_name, sub_cat_name) -> sub_cat_id
                sub_cat_order_map = {}  # 记录二级目录的顺序

                # 先收集所有二级目录及其顺序
                for item in csv_items:
                    main_cat = item['一级目录']
                    sub_cat = item['二级目录']

                    key = (main_cat, sub_cat)
                    if key not in sub_cat_order_map:
                        # 获取该一级目录下的二级目录顺序
                        if main_cat not in sub_cat_order_map:
                            sub_cat_order_map[main_cat] = {}
                        sub_cat_order_map[main_cat][sub_cat] = len(sub_cat_order_map[main_cat]) + 1

                # 按顺序插入二级目录
                for main_cat_name, sub_cats in sub_cat_order_map.items():
                    main_cat_id = main_cat_id_map[main_cat_name]
                    for sub_cat_name, order in sub_cats.items():
                        cursor.execute('''
                            INSERT INTO sub_categories (main_category_id, name, display_order)
                            VALUES (%s, %s, %s)
                        ''', (main_cat_id, sub_cat_name, order))
                        sub_cat_id = cursor.lastrowid
                        sub_cat_id_map[(main_cat_name, sub_cat_name)] = sub_cat_id

                print(f"✅ 目录重建完成：{len(main_cat_id_map)} 个一级目录，{len(sub_cat_id_map)} 个二级目录")

                # 步骤8：重建测试项目
                print("📝 重建测试项目...")

                # 按序号排序
                csv_items.sort(key=lambda x: x['序号'])

                # 清空test_items表
                cursor.execute("DELETE FROM test_items")
                print("🗑️  已清空test_items表")

                # 插入所有测试项目
                inserted_count = 0
                for item in csv_items:
                    display_order = item['序号']
                    main_cat_name = item['一级目录']
                    sub_cat_name = item['二级目录']
                    item_id = item['项目ID']

                    # 获取目录ID
                    main_cat_id = main_cat_id_map[main_cat_name]
                    sub_cat_id = sub_cat_id_map[(main_cat_name, sub_cat_name)]

                    # 插入测试项目
                    cursor.execute('''
                        INSERT INTO test_items 
                        (id, display_order, name, unit, sub_category_id)
                        VALUES (%s, %s, %s, %s, %s)
                    ''', (
                        item_id,
                        display_order,
                        item['测试项目'],
                        item['单位'],
                        sub_cat_id
                    ))

                    inserted_count += 1
                    if inserted_count % 50 == 0:
                        print(f"  已插入 {inserted_count}/{len(csv_items)} 个项目...")

                # 步骤9：重新启用外键约束
                cursor.execute("PRAGMA foreign_keys = ON")

                # 步骤10：验证并提交
                cursor.execute("SELECT COUNT(*) FROM test_items")
                new_item_count = cursor.fetchone()[0]

                conn.commit()

                # 构建成功消息
                result_message = f"""
✅ 数据库结构更新成功！

📊 统计信息：
  • CSV项目总数：{len(csv_items)}个
  • 现有项目（更新）：{len(existing_items)}个
  • 新增项目：{len(new_items)}个
  • 原数据库项目数：{old_item_count}个
  • 新数据库项目数：{new_item_count}个
  • 变更：{new_item_count - old_item_count:+d}个项目

🆔 ID分配策略：
  • 现有项目ID：保持不变
  • 新增项目ID：从TI{current_max_id - len(new_items) + 1:04d}开始
  • 最大ID号：TI{current_max_id:04d}
  • 删除的ID：永久禁用（不重用）

📁 目录结构：
  • 一级目录：{len(main_cat_id_map)}个
  • 二级目录：{len(sub_cat_id_map)}个
  • 序号范围：1-{len(csv_items)}（连续无重复）

✅ 数据安全：
  • 车辆数据：✅ 完全保留
  • 测试结果：✅ 完全保留（关联到原项目ID）
  • 报告配置：✅ 完全保留
  • 图片文件：✅ 完全保留

⚠️ 注意事项：
  • 如果修改了现有项目的名称/单位，相关测试数据会显示新名称
  • 删除的项目ID不会被重用，测试数据会被保留但无法显示
  • 新增一级目录会自动创建
                """

                print(result_message)
                return True, result_message.strip()

            except Exception as e:
                conn.rollback()
                # 确保重新启用外键约束
                try:
                    cursor.execute("PRAGMA foreign_keys = ON")
                except:
                    pass
                raise e

    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        logger.error(f"导入数据库失败: {e}\n{error_details}")
        return False, f"导入失败：{str(e)}\n请检查CSV文件格式和数据完整性"


# database/imports.py

def import_test_data(vehicle_id, csv_content):
    """导入测试数据 - 使用ON DUPLICATE KEY UPDATE实现覆盖"""
    from database.core import check_vehicle_frozen

    # ========== 新增：先检查车辆是否冻结 ==========
    is_frozen, status = check_vehicle_frozen(vehicle_id)
    if is_frozen:
        return False, "🔒 车辆已冻结，如需修改请联系管理员！"
    # =========================================

    try:
        with connection_pool.get_connection() as conn:
            cursor = conn.cursor()

            try:
                csv_str = csv_content.decode('utf-8-sig')
            except:
                csv_str = csv_content.decode('gbk')

            lines = csv_str.strip().split('\n')
            if len(lines) < 2:
                return False, "CSV文件内容过少"

            headers = [h.strip() for h in lines[0].split(',')]
            required_headers = ['项目ID', '测试值']
            for header in required_headers:
                if header not in headers:
                    return False, f"缺少必要列：{header}"


            saved_count = 0
            for line_num, line in enumerate(lines[1:], start=2):
                if not line.strip():
                    continue

                values = []
                reader = csv.reader([line])
                for row in reader:
                    values = row

                if len(values) < len(headers):
                    continue

                row_dict = {}
                for i, header in enumerate(headers):
                    if i < len(values):
                        row_dict[header] = values[i].strip()

                item_id = row_dict.get('项目ID', '').strip()
                test_value = row_dict.get('测试值', '').strip()

                if not item_id:
                    continue

                cursor.execute("SELECT id FROM test_items WHERE id = %s", (item_id,))
                if not cursor.fetchone():
                    continue

                test_date = datetime.now().strftime("%Y%m%d")

                cursor.execute('''
                    INSERT INTO test_results (vehicle_id, test_item_id, value, test_date)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT(vehicle_id, test_item_id) DO UPDATE SET
                        value = excluded.value,
                        test_date = excluded.test_date
                ''', (vehicle_id, item_id, test_value, test_date))

                saved_count += 1

            conn.commit()

            # 更新统计表
            from database.core import update_vehicle_stats
            update_vehicle_stats(vehicle_id)

            return True, f"成功导入/更新 {saved_count} 条测试数据"
    except Exception as e:
        try:
            conn.rollback()
        except:
            pass
        logger.error(f"导入测试数据失败: {e}")
        return False, f"导入失败：{str(e)}"


# database/imports.py - 修改 import_multiple_vehicles_from_csv 函数

# database/imports.py

def import_multiple_vehicles_from_csv(csv_content):
    """
    从多车格式CSV批量导入车辆和测试数据
    支持新旧两种格式
    """
    from database.core import check_vehicle_frozen, update_vehicle_stats

    try:
        with connection_pool.get_connection() as conn:
            cursor = conn.cursor(dictionary=True)

            csv_file = io.StringIO(csv_content)
            reader = csv.reader(csv_file)
            rows = list(reader)

            if len(rows) < 7:
                return False, "CSV文件格式不正确，行数不足"

            headers = [h.strip() for h in rows[0]]
            base_column_count = 6
            vehicle_columns = headers[base_column_count:]

            if not vehicle_columns:
                return False, "未找到车辆数据列"

            # 判断文件格式
            is_new_format = False
            if len(rows) >= 2:
                row2_sample = rows[1] if len(rows) > 1 else []
                if row2_sample and len(row2_sample) > base_column_count:
                    sample_value = row2_sample[base_column_count] if len(row2_sample) > base_column_count else ''
                    if sample_value and sample_value.startswith('V') and not any(
                            '\u4e00' <= c <= '\u9fff' for c in sample_value):
                        is_new_format = True

            # 解析车辆信息行
            vehicle_ids = []
            models = []
            report_numbers = []
            report_names = []
            chassis_numbers = []
            curb_weights = []
            energy_types = []
            vehicle_platforms = []

            if is_new_format:
                row_ids = rows[1] if len(rows) > 1 else []
                row_report_nums = rows[2] if len(rows) > 2 else []
                row_report_names = rows[3] if len(rows) > 3 else []
                row_chassis = rows[4] if len(rows) > 4 else []
                row_weights = rows[5] if len(rows) > 5 else []
                row_energy = rows[6] if len(rows) > 6 else []
                row_platform = rows[7] if len(rows) > 7 else []
                # 扩展格式：第7、8行为能源类型与归属平台（第6行首列为空）
                first_cell_row6 = row_energy[0].strip() if row_energy and len(row_energy) > 0 else ''
                if len(rows) >= 8 and not first_cell_row6:
                    data_start_row = 8
                else:
                    data_start_row = 6
                    row_energy = []
                    row_platform = []
            else:
                row_ids = rows[2] if len(rows) > 2 else []
                row_report_nums = rows[3] if len(rows) > 3 else []
                row_chassis = rows[4] if len(rows) > 4 else []
                row_weights = rows[5] if len(rows) > 5 else []
                row_report_names = []
                data_start_row = 6
                row_energy = []
                row_platform = []

            for i in range(len(vehicle_columns)):
                model = vehicle_columns[i].strip() if i < len(vehicle_columns) else ''
                models.append(model)

                if i < len(row_ids):
                    vehicle_ids.append(
                        row_ids[base_column_count + i].strip() if base_column_count + i < len(row_ids) else '')
                else:
                    vehicle_ids.append('')

                if i < len(row_report_nums):
                    report_numbers.append(row_report_nums[base_column_count + i].strip() if base_column_count + i < len(
                        row_report_nums) else '')
                else:
                    report_numbers.append('')

                if is_new_format and i < len(row_report_names):
                    report_names.append(row_report_names[base_column_count + i].strip() if base_column_count + i < len(
                        row_report_names) else '')
                else:
                    report_names.append('')

                if i < len(row_chassis):
                    chassis_numbers.append(
                        row_chassis[base_column_count + i].strip() if base_column_count + i < len(row_chassis) else '')
                else:
                    chassis_numbers.append('')

                if i < len(row_weights):
                    curb_weights.append(
                        row_weights[base_column_count + i].strip() if base_column_count + i < len(row_weights) else '')
                else:
                    curb_weights.append('')

                if i < len(row_energy):
                    energy_types.append(
                        row_energy[base_column_count + i].strip() if base_column_count + i < len(row_energy) else '')
                else:
                    energy_types.append('')

                if i < len(row_platform):
                    vehicle_platforms.append(
                        row_platform[base_column_count + i].strip() if base_column_count + i < len(row_platform) else '')
                else:
                    vehicle_platforms.append('')

            # 处理车辆数据
            successful_vehicle_ids = set()
            imported_count = 0
            updated_count = 0
            failed_count = 0

            for i in range(len(vehicle_columns)):
                vehicle_id = vehicle_ids[i] if i < len(vehicle_ids) else ""
                model = models[i] if i < len(models) else ""
                chassis_number = chassis_numbers[i] if i < len(chassis_numbers) else ""
                curb_weight = curb_weights[i] if i < len(curb_weights) else ""
                energy_type = energy_types[i] if i < len(energy_types) else ""
                vehicle_platform = vehicle_platforms[i] if i < len(vehicle_platforms) else ""
                report_number = report_numbers[i] if i < len(report_numbers) else ""
                report_name = report_names[i] if i < len(report_names) else ""

                if not vehicle_id:
                    failed_count += 1
                    continue

                if not model:
                    model = vehicle_columns[i].strip() if i < len(vehicle_columns) else ''

                cursor.execute("SELECT id FROM vehicles WHERE id = %s", (vehicle_id,))
                existing = cursor.fetchone()

                try:
                    if existing:
                        cursor.execute('''
                            UPDATE vehicles 
                            SET model = %s, chassis_number = %s, curb_weight = %s,
                                energy_type = %s, vehicle_platform = %s
                            WHERE id = %s
                        ''', (model, chassis_number, curb_weight,
                              energy_type, vehicle_platform, vehicle_id))

                        if report_number:
                            cursor.execute('''
                                INSERT INTO report_configs (vehicle_id, config_type, config_key, config_value)
                                VALUES (%s, 'header', '编号', %s)
                                ON CONFLICT(vehicle_id, config_type, config_key) DO UPDATE SET
                                    config_value = excluded.config_value
                            ''', (vehicle_id, report_number))

                        if report_name:
                            cursor.execute('''
                                INSERT INTO report_configs (vehicle_id, config_type, config_key, config_value)
                                VALUES (%s, 'header', '名称', %s)
                                ON CONFLICT(vehicle_id, config_type, config_key) DO UPDATE SET
                                    config_value = excluded.config_value
                            ''', (vehicle_id, report_name))

                        successful_vehicle_ids.add(vehicle_id)
                        updated_count += 1
                    else:
                        try:
                            from auth import get_current_username
                            import_created_by = get_current_username()
                        except Exception:
                            import_created_by = ''

                        cursor.execute('''
                            INSERT INTO vehicles (id, model, chassis_number, curb_weight, notes,
                                                  energy_type, vehicle_platform, created_by)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                        ''', (vehicle_id, model, chassis_number, curb_weight,
                              f"批量导入 - {datetime.now().strftime('%Y-%m-%d')}",
                              energy_type, vehicle_platform, import_created_by))

                        if report_number:
                            cursor.execute('''
                                INSERT INTO report_configs (vehicle_id, config_type, config_key, config_value)
                                VALUES (%s, 'header', '编号', %s)
                                ON CONFLICT(vehicle_id, config_type, config_key) DO UPDATE SET
                                    config_value = excluded.config_value
                            ''', (vehicle_id, report_number))

                        if report_name:
                            cursor.execute('''
                                INSERT INTO report_configs (vehicle_id, config_type, config_key, config_value)
                                VALUES (%s, 'header', '名称', %s)
                                ON CONFLICT(vehicle_id, config_type, config_key) DO UPDATE SET
                                    config_value = excluded.config_value
                            ''', (vehicle_id, report_name))

                        successful_vehicle_ids.add(vehicle_id)
                        imported_count += 1
                except Exception as veh_error:
                    failed_count += 1

            # ========== 先检查所有车辆的冻结状态 ==========
            frozen_vehicles = set()
            active_vehicles = set()

            for vehicle_id in successful_vehicle_ids:
                is_frozen, _ = check_vehicle_frozen(vehicle_id)
                if is_frozen:
                    frozen_vehicles.add(vehicle_id)
                else:
                    active_vehicles.add(vehicle_id)

            print(f"冻结车辆: {frozen_vehicles}")
            print(f"激活车辆: {active_vehicles}")

            # ========== 处理测试数据（只更新激活车辆） ==========
            test_data_count = 0
            test_data_failed = 0

            for row_num in range(data_start_row, len(rows)):
                row = rows[row_num]
                if len(row) <= base_column_count:
                    continue

                test_item_id = row[0].strip() if len(row) > 0 else ""
                if not test_item_id:
                    continue

                cursor.execute("SELECT id FROM test_items WHERE id = %s", (test_item_id,))
                if not cursor.fetchone():
                    continue

                for i in range(len(vehicle_columns)):
                    if i >= len(vehicle_ids):
                        break

                    vehicle_id = vehicle_ids[i].strip()

                    # 跳过无效车辆和冻结车辆
                    if not vehicle_id or vehicle_id not in successful_vehicle_ids:
                        continue

                    if vehicle_id in frozen_vehicles:
                        continue  # 跳过冻结车辆

                    col_index = base_column_count + i
                    if col_index >= len(row):
                        continue

                    test_value = row[col_index].strip()

                    if test_value:
                        try:
                            test_date = datetime.now().strftime("%Y%m%d")
                            cursor.execute('''
                                INSERT INTO test_results (vehicle_id, test_item_id, value, test_date)
                                VALUES (%s, %s, %s, %s)
                                ON CONFLICT(vehicle_id, test_item_id) DO UPDATE SET
                                    value = excluded.value,
                                    test_date = excluded.test_date
                            ''', (vehicle_id, test_item_id, test_value, test_date))
                            test_data_count += 1
                        except Exception as data_error:
                            test_data_failed += 1

            # ========== 更新激活车辆的统计信息 ==========
            for vehicle_id in active_vehicles:
                try:
                    update_vehicle_stats(vehicle_id)
                except Exception as e:
                    print(f"更新车辆 {vehicle_id} 统计失败: {e}")

            conn.commit()

            # 构建提示信息
            frozen_warning = ""
            if frozen_vehicles:
                frozen_warning = f"\n• ⚠️ 跳过 {len(frozen_vehicles)} 辆已冻结车辆的测试数据更新，如需修改请联系管理员解冻！"

            summary = f"""
✅ 批量导入完成！
• 车辆处理: 新增 {imported_count} 辆, 更新 {updated_count} 辆, 失败 {failed_count} 辆
• 测试数据: 成功导入/更新 {test_data_count} 条, 失败 {test_data_failed} 条{frozen_warning}
• 激活车辆: {len(active_vehicles)} 辆, 冻结车辆: {len(frozen_vehicles)} 辆
• 文件格式: {'新格式（车辆ID在第2行）' if is_new_format else '旧格式'}
            """
            return True, summary

    except Exception as e:
        try:
            conn.rollback()
        except:
            pass
        import traceback
        error_details = traceback.format_exc()
        logger.error(f"批量导入失败: {e}\n{error_details}")
        return False, f"批量导入失败：{str(e)[:200]}"


def import_performance_basic_data_csv(csv_content):
    """
    批量更新性能基础数据（管理员）
    CSV：车辆ID, 试验报告号, 编制人员工编码, 车辆归属平台, 能源类型
    """
    try:
        if isinstance(csv_content, bytes):
            for enc in ('utf-8-sig', 'utf-8', 'gbk'):
                try:
                    csv_content = csv_content.decode(enc)
                    break
                except UnicodeDecodeError:
                    continue

        reader = csv.reader(io.StringIO(csv_content))
        rows = list(reader)
        if len(rows) < 2:
            return False, "CSV文件无数据行"

        header = [h.strip() for h in rows[0]]
        idx = {h: i for i, h in enumerate(header)}

        def col(row, name, aliases):
            for key in [name] + aliases:
                if key in idx and len(row) > idx[key]:
                    return row[idx[key]].strip()
            return ''

        updated = 0
        skipped = 0
        failed = 0

        with connection_pool.get_connection() as conn:
            cursor = conn.cursor()
            for row in rows[1:]:
                vehicle_id = col(row, '车辆ID', ['id'])
                if not vehicle_id:
                    skipped += 1
                    continue
                report_no = col(row, '试验报告号', ['报告编号', '编号'])
                staff_code = col(row, '编制人员工编码', ['编制人', '用户名', '创建人'])
                platform = col(row, '车辆归属平台', ['项目归属平台', '项目平台'])
                energy = col(row, '能源类型', [])

                cursor.execute("SELECT id FROM vehicles WHERE id = %s", (vehicle_id,))
                if not cursor.fetchone():
                    failed += 1
                    continue
                try:
                    cursor.execute('''
                        UPDATE vehicles
                        SET created_by = %s, vehicle_platform = %s, energy_type = %s
                        WHERE id = %s
                    ''', (staff_code, platform, energy, vehicle_id))
                    if report_no:
                        cursor.execute('''
                            INSERT INTO report_configs (vehicle_id, config_type, config_key, config_value)
                            VALUES (%s, 'header', '编号', %s)
                            ON CONFLICT(vehicle_id, config_type, config_key) DO UPDATE SET
                                config_value = excluded.config_value
                        ''', (vehicle_id, report_no))
                    updated += 1
                except Exception:
                    failed += 1
            conn.commit()

        return True, f"批量更新完成：成功 {updated} 辆，跳过 {skipped} 行，未找到 {failed} 辆"
    except Exception as e:
        logger.error(f"批量导入性能基础数据失败: {e}")
        return False, f"导入失败：{str(e)}"