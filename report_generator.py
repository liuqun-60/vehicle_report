# report_generator.py (PDF版本 - 优化版)
import os
import io
from datetime import datetime
from pathlib import Path
from PIL import Image
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm, mm, inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image as ReportLabImage, \
    PageBreak, KeepTogether, PageTemplate, Frame, NextPageTemplate, FrameBreak
from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT, TA_JUSTIFY
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus.doctemplate import PageTemplate, BaseDocTemplate
from reportlab.platypus.flowables import Spacer, PageBreak, KeepTogether
import base64
from io import BytesIO

from database import (
    get_main_categories, get_vehicle_test_data_for_report,
    get_test_info_config, get_report_images, get_sample_car_images,
    get_test_projects, get_test_equipment, get_all_signature_images,
    get_vehicle_details
)


class NumberedCanvas(canvas.Canvas):
    """添加页码的画布"""

    def __init__(self, *args, **kwargs):
        canvas.Canvas.__init__(self, *args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        """添加页码"""
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_number(num_pages)
            self.draw_header()  # 添加页眉绘制
            canvas.Canvas.showPage(self)
        canvas.Canvas.save(self)

    # report_generator.py - 修改 NumberedCanvas 类的 draw_page_number 方法

    def draw_page_number(self, page_count):
        """绘制页码"""
        page_width, page_height = A4

        # 封面页（第一页）和声明页（第二页）不显示页码
        if self._pageNumber == 1 or self._pageNumber == 2:
            return

        # 设置字体
        self.setFont("ChineseFont", 9)

        # 页码文本
        page_text = f"第 {self._pageNumber - 2} 页  共 {page_count - 2} 页"

        # 计算位置（页面底部居中）
        text_width = self.stringWidth(page_text, "ChineseFont", 9)
        x = (page_width - text_width) / 2
        y = 15 * mm

        # 绘制页码
        self.setFillColor(colors.gray)
        self.drawString(x, y, page_text)
        self.setFillColor(colors.black)

    # report_generator.py - 修改 NumberedCanvas 类的 draw_header 方法

    def draw_header(self):
        """绘制页眉 - 封面页和声明页不绘制"""
        if self._pageNumber == 1 or self._pageNumber == 2:  # 封面页和声明页不绘制页眉
            return

        page_width, page_height = A4

        # 获取表格的实际宽度（左右边距之间的区域）
        left_margin = 20 * mm
        right_margin = 20 * mm
        content_width = page_width - left_margin - right_margin

        # 计算居中位置
        center_x = left_margin + content_width / 2

        # 设置字体
        self.setFont("ChineseFont", 12)

        # 中文页眉
        chinese_text = "XXX"
        y_chinese = page_height - 15 * mm
        self.drawCentredString(center_x, y_chinese, chinese_text)

        # 英文页眉
        english_text = "XXX"
        y_english = page_height - 22 * mm
        self.drawCentredString(center_x, y_english, english_text)

        # 绘制分隔线 - 与表格同宽
        self.setStrokeColor(colors.black)
        self.setLineWidth(0.5)
        line_y = page_height - 25 * mm
        self.line(left_margin, line_y, left_margin + content_width, line_y)


class PageWithHeaderFooter(BaseDocTemplate):
    """自定义文档模板，添加页眉"""

    def __init__(self, filename, **kw):
        BaseDocTemplate.__init__(self, filename, **kw)
        self.allowSplitting = 0  # 禁止在Flowable中间分页


class PDFReportGenerator:
    """PDF报告生成器 - 优化版"""

    def __init__(self):
        # 页面尺寸设置
        self.page_width, self.page_height = A4
        self.left_margin = 20 * mm
        self.right_margin = 20 * mm
        self.top_margin = 25 * mm  # 增加上边距，为页眉留出空间
        self.bottom_margin = 25 * mm

        # 内容区域尺寸
        self.content_width = self.page_width - self.left_margin - self.right_margin

        # 统一的表格样式设置
        self.table_font_size = 10
        self.table_header_font_size = 10
        self.table_padding = 4
        self.table_line_height = 14

        # 图片统一高度 - 固定5cm
        self.image_height = 5 * cm

        # 初始化样式
        self._init_styles()

        # 注册中文字体
        self._register_chinese_font()

    def _init_styles(self):
        """初始化所有样式 - 所有字体颜色改为黑色"""
        # 公司名称样式
        self.company_style = ParagraphStyle(
            name='CompanyStyle',
            fontName='ChineseFont',
            fontSize=18,
            alignment=TA_CENTER,
            spaceAfter=8,
            textColor=colors.black,
            leading=22
        )

        # 报告标题样式
        self.title_style = ParagraphStyle(
            name='TitleStyle',
            fontName='ChineseFont-Bold',
            fontSize=24,
            alignment=TA_CENTER,
            spaceBefore=10,
            spaceAfter=10,
            textColor=colors.black,
            leading=28
        )

        # 密级样式
        self.secret_style = ParagraphStyle(
            name='SecretStyle',
            fontName='ChineseFont',
            fontSize=12,
            alignment=TA_CENTER,
            spaceAfter=15,
            textColor=colors.black,
            leading=16
        )

        # 章节标题样式
        self.section_style = ParagraphStyle(
            name='SectionStyle',
            fontName='ChineseFont-Bold',
            fontSize=16,
            alignment=TA_LEFT,
            spaceBefore=10,
            spaceAfter=8,
            textColor=colors.black,
            leftIndent=0,
            leading=20
        )

        # 子章节标题样式
        self.sub_section_style = ParagraphStyle(
            name='SubSectionStyle',
            fontName='ChineseFont-Bold',
            fontSize=14,
            alignment=TA_LEFT,
            spaceBefore=8,
            spaceAfter=6,
            textColor=colors.black,
            leftIndent=0,
            leading=18
        )

        # 描述文本样式
        self.desc_style = ParagraphStyle(
            name='DescStyle',
            fontName='ChineseFont',
            fontSize=10,
            alignment=TA_LEFT,
            spaceAfter=8,
            leading=14
        )

        # 试验总结样式
        self.conclusion_style = ParagraphStyle(
            name='ConclusionStyle',
            fontName='ChineseFont',
            fontSize=11,
            alignment=TA_LEFT,
            leftIndent=5,
            rightIndent=5,
            spaceBefore=5,
            spaceAfter=10,
            backColor=colors.white,
            borderWidth=1,
            borderColor=colors.black,
            borderPadding=8,
            borderRadius=2,
            leading=16
        )

        # 图片标题样式
        self.image_caption_style = ParagraphStyle(
            name='ImageCaption',
            fontName='ChineseFont',
            fontSize=9,
            alignment=TA_CENTER,
            textColor=colors.black,
            leading=12
        )

        # 图片文本样式
        self.image_text_style = ParagraphStyle(
            name='ImageText',
            fontName='ChineseFont',
            fontSize=9,
            alignment=TA_LEFT,
            textColor=colors.black,
            leading=12
        )

        # 表格内容样式 - 左对齐
        self.table_content_style = ParagraphStyle(
            name='TableContent',
            fontName='ChineseFont',
            fontSize=self.table_font_size,
            alignment=TA_LEFT,
            leading=self.table_line_height,
            textColor=colors.black,
            wordWrap='CJK'
        )

        # 表格标题样式 - 左对齐
        self.table_header_style = ParagraphStyle(
            name='TableHeader',
            fontName='ChineseFont-Bold',
            fontSize=self.table_header_font_size,
            alignment=TA_LEFT,
            leading=self.table_line_height,
            textColor=colors.black,
            wordWrap='CJK'
        )

        # 页眉样式 - 中文
        self.header_chinese_style = ParagraphStyle(
            name='HeaderChinese',
            fontName='ChineseFont',
            fontSize=10,
            alignment=TA_CENTER,
            textColor=colors.black,
            leading=14,
            spaceAfter=2
        )

        # 页眉样式 - 英文
        self.header_english_style = ParagraphStyle(
            name='HeaderEnglish',
            fontName='ChineseFont',
            fontSize=9,
            alignment=TA_CENTER,
            textColor=colors.black,
            leading=12,
            spaceAfter=4
        )

    def _register_chinese_font(self):
        """注册中文字体"""
        try:
            project_fonts_dir = Path("fonts")
            font_path = project_fonts_dir / "wqy-microhei.ttc"

            if not font_path.exists():
                font_paths = [
                    project_fonts_dir / "wqy-microhei.ttc",
                    Path("fonts/wqy-microhei.ttc"),
                    Path("./fonts/wqy-microhei.ttc"),
                    Path("../fonts/wqy-microhei.ttc")
                ]

                for fp in font_paths:
                    if fp.exists():
                        font_path = fp
                        break

            if not font_path.exists():
                raise Exception(f"找不到字体文件: {font_path}")

            pdfmetrics.registerFont(TTFont('ChineseFont', str(font_path), subfontIndex=0))
            pdfmetrics.registerFont(TTFont('ChineseFont-Bold', str(font_path), subfontIndex=0))

            print(f"✅ 成功加载中文字体: {font_path}")

        except Exception as e:
            print(f"❌ 中文字体加载失败: {str(e)}")
            raise Exception(f"中文字体加载失败：{str(e)}。请确保项目目录下有 fonts/wqy-microhei.ttc 字体文件。")

    def _create_paragraph(self, text, style, max_width=None):
        """创建自动换行的段落对象"""
        if not text:
            text = ""
        return Paragraph(str(text), style)

    def _create_header(self):
        """创建页眉内容 - 返回空列表，因为页眉通过画布绘制"""
        return []  # 不添加任何内容到story中

    def generate_pdf_report(self, vehicle_id, config_data=None, test_info_data=None):
        """生成PDF格式报告 - 完整实现"""
        try:
            print(f"开始生成PDF报告，车辆ID: {vehicle_id}")

            # 获取车辆信息
            vehicle_info = get_vehicle_details(vehicle_id)
            if not vehicle_info:
                error_msg = "未找到车辆信息，请确认车辆ID是否正确"
                print(f"❌ {error_msg}")
                return {"success": False, "error": error_msg, "path": None}

            print(f"获取到车辆信息: {vehicle_info['model']} - {vehicle_info['chassis_number']}")

            # 获取测试数据（自动重新编号）
            report_data = get_vehicle_test_data_for_report(vehicle_id)
            if not report_data:
                error_msg = "该车辆暂无测试数据，请先在【测试数据录入】中上传测试数据"
                print(f"❌ {error_msg}")
                return {"success": False, "error": error_msg, "path": None}

            # 检查是否有有效测试数据
            total_test_items = 0
            for category, items in report_data.items():
                total_test_items += len(items)

            if total_test_items == 0:
                error_msg = "该车辆没有有效的测试数据（所有测试值均为空），请先在【测试数据录入】中填写测试数据"
                print(f"❌ {error_msg}")
                return {"success": False, "error": error_msg, "path": None}

            print(f"获取到测试数据，共{len(report_data)}个分类，{total_test_items}个测试项")

            # 获取所有主分类
            main_categories = get_main_categories()
            print(f"获取到{len(main_categories)}个主分类")

            # 获取图片数据
            image_data = {}
            image_data = {}
            for main_cat_id, main_cat_name in main_categories:
                # 使用新函数，通过一级目录名称获取图片
                from database.core import get_report_images_by_category
                images = get_report_images_by_category(vehicle_id, main_cat_name)
                image_data[main_cat_name] = images
                if images:
                    print(f"分类[{main_cat_name}]有{len(images)}张图片")

            # 获取样车照片
            sample_car_images = get_sample_car_images(vehicle_id)
            if sample_car_images:
                print(f"获取到{len(sample_car_images)}张样车照片")
            else:
                print("⚠️ 警告：未上传样车照片，报告中将不显示样车图片")

            # 获取试验项目
            test_projects = get_test_projects(vehicle_id)
            if test_projects:
                print(f"获取到{len(test_projects)}个试验项目")
            else:
                print("⚠️ 警告：未配置试验项目，将使用默认项目")

            # 获取试验设备
            test_equipment = get_test_equipment(vehicle_id)
            if test_equipment:
                print(f"获取到{len(test_equipment)}个试验设备")
            else:
                print("⚠️ 警告：未配置试验设备，将使用默认设备")

            # 获取测试信息配置
            if test_info_data is None:
                test_info_data = {}
                for main_cat_id, main_cat_name in main_categories:
                    config = get_test_info_config(vehicle_id, main_cat_id)
                    test_info_data[main_cat_name] = config
                    if config and any(config.values()):
                        print(f"分类[{main_cat_name}]有测试信息配置")
                    else:
                        print(f"⚠️ 分类[{main_cat_name}]测试信息为空")

            # 获取签名图片路径
            signature_images_paths = get_all_signature_images(vehicle_id)
            if signature_images_paths:
                print(f"获取到{len(signature_images_paths)}个签名")
            else:
                print("⚠️ 警告：未上传签名图片，报告中将显示'(签名)'占位符")

            # 合并默认配置
            if config_data is None:
                config_data = {}

            default_config = {
                'header': {
                    '编号': config_data.get('header', {}).get('编号', 'SY-GCYZ-ZC-2025-147'),
                    '名称': config_data.get('header', {}).get('名称', 'T17轻量化项目性能试验'),
                    '编制日期': config_data.get('header', {}).get('编制日期', ''),
                    '校对日期': config_data.get('header', {}).get('校对日期', ''),
                    '审核日期': config_data.get('header', {}).get('审核日期', ''),
                    '批准日期': config_data.get('header', {}).get('批准日期', '')
                },
                'overview': {
                    '试验目的': config_data.get('overview', {}).get('试验目的', ''),
                    '任务来源': config_data.get('overview', {}).get('任务来源', ''),
                    '项目费用': config_data.get('overview', {}).get('项目费用', ''),
                    '车型号': vehicle_info['model'],
                    '发动机型号': config_data.get('overview', {}).get('发动机型号', ''),
                    '底盘号': vehicle_info['chassis_number'],
                    '车厢类型': config_data.get('overview', {}).get('车厢类型', ''),
                    'GVW（kg）': config_data.get('overview', {}).get('GVW（kg）', ''),
                    '胎压（Kpa）': config_data.get('overview', {}).get('胎压（Kpa）', ''),
                    '磨合行驶里程（km）': config_data.get('overview', {}).get('磨合行驶里程（km）', ''),
                    '接车时间': config_data.get('overview', {}).get('接车时间', ''),
                    '完成时间': config_data.get('overview', {}).get('完成时间', ''),
                    '试验结论': config_data.get('overview', {}).get('试验结论', '')
                },
                'signatures': config_data.get('signatures', {})
            }

            # 创建PDF文件保存目录
            reports_dir = Path("reports/pdf")
            reports_dir.mkdir(exist_ok=True, parents=True)

            # 获取报告编号和名称（从config_data中获取）
            report_number = config_data.get('header', {}).get('编号', '')
            report_name = config_data.get('header', {}).get('名称', '')

            # 清理文件名中的非法字符
            def clean_filename(text):
                # 只保留字母、数字、下划线、横线和中文字符
                import re
                # 匹配中文字符、字母、数字、下划线、横线
                cleaned = re.sub(r'[^\u4e00-\u9fa5a-zA-Z0-9_-]', '', text)
                return cleaned or '未命名'

            # 生成文件名
            if report_number and report_name:
                # 使用 "编号_名称" 格式
                safe_report_number = clean_filename(report_number)
                safe_report_name = clean_filename(report_name)
                pdf_filename = f"{safe_report_number}_{safe_report_name}.pdf"
            else:
                # 如果没有编号或名称，使用原有的命名方式
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                safe_model = "".join(c for c in vehicle_info['model'] if c.isalnum() or c in (' ', '-', '_'))
                safe_chassis = "".join(c for c in vehicle_info['chassis_number'] if c.isalnum() or c in (' ', '-', '_'))
                pdf_filename = f"报告_{safe_model}_{safe_chassis}_{timestamp}.pdf"

            pdf_path = reports_dir / pdf_filename

            print(f"开始创建PDF文档: {pdf_path}")

            # 生成PDF文档
            self._create_pdf_document(
                pdf_path=pdf_path,
                vehicle_info=vehicle_info,
                report_data=report_data,
                config_data=default_config,
                test_info_data=test_info_data,
                image_data=image_data,
                sample_car_images=sample_car_images,
                test_projects=test_projects,
                test_equipment=test_equipment,
                signature_images_paths=signature_images_paths
            )

            # 验证PDF文件是否成功生成
            if not pdf_path.exists():
                error_msg = "PDF文件生成失败，文件未创建"
                print(f"❌ {error_msg}")
                return {"success": False, "error": error_msg, "path": None}

            file_size = pdf_path.stat().st_size
            if file_size == 0:
                error_msg = "PDF文件生成失败，文件大小为0"
                print(f"❌ {error_msg}")
                return {"success": False, "error": error_msg, "path": None}

            print(f"✅ PDF报告生成成功: {pdf_filename} (大小: {file_size / 1024:.1f} KB)")
            return {"success": True, "error": None, "path": pdf_path}

        except Exception as e:
            error_msg = str(e)
            print(f"❌ PDF报告生成失败: {error_msg}")
            import traceback
            traceback.print_exc()

            # 返回包含错误信息的字典
            return {"success": False, "error": error_msg, "path": None}

    # report_generator.py - 修改 _create_pdf_document 方法

    def _create_pdf_document(self, pdf_path, vehicle_info, report_data, config_data,
                             test_info_data, image_data, sample_car_images,
                             test_projects, test_equipment, signature_images_paths):
        """创建PDF文档 - 完整实现"""
        print("开始构建PDF文档结构...")

        # 创建文档模板
        doc = SimpleDocTemplate(
            str(pdf_path),
            pagesize=A4,
            leftMargin=self.left_margin,
            rightMargin=self.right_margin,
            topMargin=self.top_margin,
            bottomMargin=self.bottom_margin,
            title=f"{vehicle_info['model']}性能试验报告",
            author="XXX",
            creator="汽车性能试验报告系统"
        )

        # 准备文档内容
        story = []

        print("创建封面页...")
        # 1. 封面页
        story.extend(self._create_cover_page(config_data, signature_images_paths))
        story.append(PageBreak())

        # 2. 声明页（新增）
        print("创建声明页...")
        story.extend(self._create_declaration_page())
        story.append(PageBreak())

        print("创建试验一览页...")
        # 3. 试验一览页
        story.extend(self._create_overview_page(
            config_data, test_equipment, test_projects,
            sample_car_images, test_info_data
        ))
        story.append(PageBreak())

        print("创建测试数据页...")
        # 4. 测试数据页
        story.extend(self._create_test_data_pages(
            report_data, test_info_data, image_data
        ))

        print("开始生成PDF文件...")
        doc.build(story, canvasmaker=NumberedCanvas)

        print(f"PDF文档生成完成，共{len(story)}个元素")

    def _create_cover_page(self, config_data, signature_images_paths):
        """创建封面页 - 最简版，直接绘制内容"""
        elements = []

        # 固定签名高度
        SIGNATURE_HEIGHT = 0.8 * cm

        # 1. 直接添加内容，不使用复杂的边框表格
        # 顶部空白
        elements.append(Spacer(1, 0.2 * cm))

        # 顶部行：核心商密和编号
        top_data = [
            [Paragraph("XXX", ParagraphStyle(
                name='TopLeft',
                fontName='ChineseFont-Bold',
                fontSize=12,
                alignment=TA_LEFT,
                textColor=colors.black,
                leading=16
            )),
             Paragraph(f"编号：{config_data['header']['编号']}", ParagraphStyle(
                 name='TopRight',
                 fontName='ChineseFont',
                 fontSize=12,
                 alignment=TA_RIGHT,
                 textColor=colors.black,
                 leading=16
             ))]
        ]

        top_table = Table(top_data, colWidths=[10 * cm, 7 * cm])  # 左边6cm，右边10cm

        top_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (0, 0), 'LEFT'),
            ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ]))
        elements.append(top_table)

        # 中间空白
        elements.append(Spacer(1, 3 * cm))

        # 公司名称
        company_style = ParagraphStyle(
            name='CoverCompany',
            fontName='ChineseFont-Bold',
            fontSize=20,
            alignment=TA_CENTER,
            textColor=colors.black,
            leading=26
        )
        elements.append(Paragraph("XXX", company_style))
        elements.append(Paragraph("XXX", company_style))

        # 报告标题
        elements.append(Spacer(1, 1.5 * cm))
        title_style = ParagraphStyle(
            name='CoverTitle',
            fontName='ChineseFont-Bold',
            fontSize=28,
            alignment=TA_CENTER,
            textColor=colors.black,
            leading=34
        )
        elements.append(Paragraph("试 验 报 告", title_style))

        # 名称行
        elements.append(Spacer(1, 1.5 * cm))
        name_style = ParagraphStyle(
            name='CoverName',
            fontName='ChineseFont',
            fontSize=14,
            alignment=TA_CENTER,
            textColor=colors.black,
            leading=20
        )
        elements.append(Paragraph(f"名称：{config_data['header']['名称']}", name_style))

        # 编制单位
        elements.append(Spacer(1, 0.5 * cm))
        dept_style = ParagraphStyle(
            name='CoverDept',
            fontName='ChineseFont',
            fontSize=14,
            alignment=TA_CENTER,
            textColor=colors.black,
            leading=20
        )
        elements.append(Paragraph("XXX", dept_style))

        # 签名区域
        elements.append(Spacer(1, 2 * cm))

        signature_items = [
            ('编制', '编制签名', config_data['header']['编制日期']),
            ('校对', '校对签名', config_data['header']['校对日期']),
            ('审核', '审核签名', config_data['header']['审核日期']),
            ('批准', '批准签名', config_data['header']['批准日期'])
        ]

        for sig_name, sig_key, sig_date in signature_items:
            # 创建签名行
            row_elements = []

            # 签名类型
            row_elements.append(Paragraph(f"{sig_name}：", ParagraphStyle(
                name='SigName',
                fontName='ChineseFont-Bold',
                fontSize=12,
                alignment=TA_CENTER,
                textColor=colors.black,
                leading=18
            )))

            # 签名图片
            if sig_key in signature_images_paths:
                sig_info = signature_images_paths[sig_key]
                img_path = sig_info.get('path', '')

                if img_path and os.path.exists(img_path):
                    try:
                        img = ReportLabImage(img_path)
                        original_width = img.imageWidth
                        original_height = img.imageHeight

                        scale = SIGNATURE_HEIGHT / original_height if original_height > 0 else 1
                        img.drawHeight = SIGNATURE_HEIGHT
                        img.drawWidth = original_width * scale
                        row_elements.append(img)
                    except Exception as e:
                        print(f"签名图片加载失败 [{sig_name}]: {str(e)}")
                        row_elements.append(Paragraph('(签名)', ParagraphStyle(
                            name='SigPlaceholder',
                            fontName='ChineseFont',
                            fontSize=11,
                            alignment=TA_CENTER,
                            textColor=colors.black,
                            leading=16
                        )))
                else:
                    row_elements.append(Paragraph('(签名)', ParagraphStyle(
                        name='SigPlaceholder',
                        fontName='ChineseFont',
                        fontSize=11,
                        alignment=TA_CENTER,
                        textColor=colors.black,
                        leading=16
                    )))
            else:
                row_elements.append(Paragraph('(签名)', ParagraphStyle(
                    name='SigPlaceholder',
                    fontName='ChineseFont',
                    fontSize=11,
                    alignment=TA_CENTER,
                    textColor=colors.black,
                    leading=16
                )))

            # 日期
            row_elements.append(Paragraph(f"日期：{sig_date}", ParagraphStyle(
                name='SigDate',
                fontName='ChineseFont',
                fontSize=12,
                alignment=TA_CENTER,
                textColor=colors.black,
                leading=18
            )))

            # 将三个元素放在一行 - 修改这里的列宽，让签名区域收窄
            row_data = [[row_elements[0], row_elements[1], row_elements[2]]]
            # 修改 colWidths 参数：第一列2cm，第二列2.5cm，第三列2.5cm
            row_table = Table(row_data, colWidths=[2 * cm, 2 * cm, 5 * cm])
            row_table.setStyle(TableStyle([
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('TOPPADDING', (0, 0), (-1, -1), 2),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
            ]))

            elements.append(row_table)
            elements.append(Spacer(1, 0.2 * cm))

        # 底部留白
        elements.append(Spacer(1, 2 * cm))

        return elements

    def _create_signature_section(self, config_data, signature_images_paths):
        """创建签名区域 - 统一行高"""
        elements = []

        # 签名表格数据
        signature_data = []
        signature_items = [
            ('编制', '编制签名', config_data['header']['编制日期']),
            ('校对', '校对签名', config_data['header']['校对日期']),
            ('审核', '审核签名', config_data['header']['审核日期']),
            ('批准', '批准签名', config_data['header']['批准日期'])
        ]

        for sig_name, sig_key, sig_date in signature_items:
            signature_cell = self._create_signature_cell(sig_name, sig_key, sig_date, signature_images_paths)
            signature_data.append(signature_cell)

        # 创建签名表格 - 统一行高
        sig_table = Table(signature_data, colWidths=[2 * cm, 5 * cm, 3 * cm], rowHeights=[1.5 * cm] * 4)
        sig_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, -1), 'ChineseFont'),
            ('FONTSIZE', (0, 0), (-1, -1), self.table_font_size),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('BACKGROUND', (0, 0), (-1, -1), colors.white),
            ('TOPPADDING', (0, 0), (-1, -1), self.table_padding),
            ('BOTTOMPADDING', (0, 0), (-1, -1), self.table_padding),
            ('LEFTPADDING', (0, 0), (-1, -1), 5),
            ('RIGHTPADDING', (0, 0), (-1, -1), 5),
        ]))

        elements.append(sig_table)

        return elements

    def _create_signature_cell(self, sig_name, sig_key, sig_date, signature_images_paths):
        """创建签名单元格 - 修复图片加载"""
        # 第一列：签名类型
        col1 = Paragraph(sig_name, self.table_content_style)

        # 第二列：签名图片或文字
        if sig_key in signature_images_paths:
            sig_info = signature_images_paths[sig_key]
            img_path = sig_info.get('path', '')

            if img_path and os.path.exists(img_path):
                try:
                    # 加载图片
                    img = ReportLabImage(img_path)
                    # 获取原始尺寸
                    original_width = img.imageWidth
                    original_height = img.imageHeight

                    # 设置最大高度为1.2cm，宽度按比例计算
                    max_height = 1.2 * cm
                    if original_height > max_height:
                        scale = max_height / original_height
                        img.drawHeight = max_height
                        img.drawWidth = original_width * scale
                    else:
                        img.drawHeight = original_height
                        img.drawWidth = original_width

                    col2 = img
                except Exception as e:
                    print(f"签名图片加载失败 [{sig_name}]: {str(e)}")
                    col2 = Paragraph('(签名)', self.table_content_style)
            else:
                col2 = Paragraph('(签名)', self.table_content_style)
        else:
            col2 = Paragraph('(签名)', self.table_content_style)

        # 第三列：日期
        col3 = Paragraph(sig_date, self.table_content_style)

        return [col1, col2, col3]


    def _create_overview_page(self, config_data, test_equipment, test_projects,
                              sample_car_images, test_info_data):
        """创建试验一览页 - 优化版"""
        elements = []

        # 添加页眉
        elements.extend(self._create_header())

        # 章节标题
        elements.append(Paragraph("一、试验一览", self.section_style))

        # 合并试验基本信息表格
        elements.extend(self._create_merged_overview_table(config_data))

        # 试验设备表格
        elements.append(Paragraph("二、试验设备及设备精度", self.sub_section_style))

        if test_equipment:
            equipment_data = [
                [Paragraph('序号', self.table_header_style),
                 Paragraph('设备名称', self.table_header_style),
                 Paragraph('设备精度', self.table_header_style)]
            ]
            for idx, equipment in enumerate(test_equipment, start=1):
                equipment_number = equipment.get('序号', idx)
                equipment_name = equipment.get('设备名称', '')
                equipment_accuracy = equipment.get('设备精度', '')

                equipment_data.append([
                    Paragraph(str(equipment_number), self.table_content_style),
                    Paragraph(equipment_name, self.table_content_style),
                    Paragraph(equipment_accuracy, self.table_content_style)
                ])

            equipment_table = Table(equipment_data,
                                    colWidths=[1.5 * cm, 6 * cm, 8.5 * cm],
                                    repeatRows=1)
            equipment_table.setStyle(TableStyle([
                ('FONTNAME', (0, 0), (-1, -1), 'ChineseFont'),
                ('FONTSIZE', (0, 0), (-1, -1), self.table_font_size),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
                ('BACKGROUND', (0, 0), (-1, -1), colors.white),
                ('TOPPADDING', (0, 0), (-1, -1), self.table_padding),
                ('BOTTOMPADDING', (0, 0), (-1, -1), self.table_padding),
                ('LEFTPADDING', (0, 0), (-1, -1), 3),
                ('RIGHTPADDING', (0, 0), (-1, -1), 3),
            ]))
            elements.append(equipment_table)
        else:
            elements.append(Paragraph("暂无试验设备信息", self.desc_style))

        elements.append(Spacer(1, 0.5 * cm))

        # 试验项目表格
        elements.append(Paragraph("三、试验项目", self.sub_section_style))

        if test_projects:
            projects_data = [
                [Paragraph('序号', self.table_header_style),
                 Paragraph('项目名称', self.table_header_style),
                 Paragraph('执行标准', self.table_header_style)]
            ]
            for project in test_projects:
                project_number = project.get('序号', '')
                project_name = project.get('项目名称', '')
                execution_standard = project.get('执行标准', '')

                projects_data.append([
                    Paragraph(str(project_number), self.table_content_style),
                    Paragraph(project_name, self.table_content_style),
                    Paragraph(execution_standard, self.table_content_style)
                ])

            projects_table = Table(projects_data,
                                   colWidths=[1.5 * cm, 6 * cm, 8.5 * cm],
                                   repeatRows=1)
            projects_table.setStyle(TableStyle([
                ('FONTNAME', (0, 0), (-1, -1), 'ChineseFont'),
                ('FONTSIZE', (0, 0), (-1, -1), self.table_font_size),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
                ('BACKGROUND', (0, 0), (-1, -1), colors.white),
                ('TOPPADDING', (0, 0), (-1, -1), self.table_padding),
                ('BOTTOMPADDING', (0, 0), (-1, -1), self.table_padding),
                ('LEFTPADDING', (0, 0), (-1, -1), 3),
                ('RIGHTPADDING', (0, 0), (-1, -1), 3),
            ]))
            elements.append(projects_table)
        else:
            elements.append(Paragraph("暂无试验项目信息", self.desc_style))

        elements.append(Spacer(1, 0.5 * cm))

        # 修改：四、样车检查及照片
        elements.append(Paragraph("四、样车检查及照片", self.sub_section_style))
        elements.append(Paragraph("对样车进行检查，确认样车试验前状态，排除样车试验前所存在的不良状况。", self.desc_style))

        # 样车图片 - 直接显示，不加额外标题
        if sample_car_images:
            elements.append(Spacer(1, 0.3 * cm))
            # 传入空标题，这样就不会显示"样车照片"子标题
            image_block = self._create_image_block(sample_car_images, "")
            elements.append(KeepTogether(image_block))

        elements.append(Spacer(1, 0.5 * cm))

        # 试验结论
        elements.append(Paragraph("五、试验总结", self.sub_section_style))

        conclusion_text = config_data['overview'].get('试验结论', '试验总结待填写')
        if not conclusion_text:
            conclusion_text = '试验总结待填写'

        conclusion_text_with_br = conclusion_text.replace('\n', '<br/>')
        elements.append(Paragraph(conclusion_text_with_br, self.desc_style))

        return elements

    def _create_merged_overview_table(self, config_data):
        """创建合并的试验基本信息表格"""
        elements = []

        # 准备所有数据行
        all_rows = [
            ['试验目的', config_data['overview']['试验目的'] or '', '车厢类型',
             config_data['overview']['车厢类型'] or ''],
            ['任务来源', config_data['overview']['任务来源'] or '', 'GVW（kg）',
             config_data['overview']['GVW（kg）'] or ''],
            ['项目费用', config_data['overview']['项目费用'] or '', '胎压（Kpa）',
             config_data['overview']['胎压（Kpa）'] or ''],
            ['车型号', config_data['overview']['车型号'] or '', '磨合行驶里程（km）',
             config_data['overview']['磨合行驶里程（km）'] or ''],
            ['发动机型号', config_data['overview']['发动机型号'] or '', '接车时间',
             config_data['overview']['接车时间'] or ''],
            ['底盘号', config_data['overview']['底盘号'] or '', '完成时间',
             config_data['overview']['完成时间'] or '']
        ]

        # 构建表格数据
        table_data = []
        for row in all_rows:
            table_row = [
                Paragraph(row[0], self.table_content_style),
                Paragraph(row[1], self.table_content_style),
                Paragraph(row[2], self.table_content_style),
                Paragraph(row[3], self.table_content_style)
            ]
            table_data.append(table_row)

        # 创建表格 - 使用最大宽度
        col_widths = [
            3 * cm,  # 第一列标签
            5.5 * cm,  # 第一列值
            3 * cm,  # 第二列标签
            4.5 * cm  # 第二列值
        ]

        overview_table = Table(table_data, colWidths=col_widths)
        overview_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, -1), 'ChineseFont'),
            ('FONTSIZE', (0, 0), (-1, -1), self.table_font_size),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('BACKGROUND', (0, 0), (-1, -1), colors.white),
            ('TOPPADDING', (0, 0), (-1, -1), self.table_padding),
            ('BOTTOMPADDING', (0, 0), (-1, -1), self.table_padding),
            ('LEFTPADDING', (0, 0), (-1, -1), 3),
            ('RIGHTPADDING', (0, 0), (-1, -1), 3),
        ]))

        elements.append(overview_table)
        elements.append(Spacer(1, 0.5 * cm))

        return elements

    def _create_test_data_pages(self, report_data, test_info_data, image_data):
        """创建测试数据页 - 简化表格宽度"""
        elements = []

        print(f"开始创建测试数据页，共{len(report_data)}个分类")

        # 主章节编号 - 从"六"开始
        main_chapter = "六"

        for category_idx, (category_name, category_data) in enumerate(report_data.items()):
            print(f"处理分类 [{category_idx + 1}/{len(report_data)}]: {category_name}")

            # 每个分类开始新页（除了第一个）
            if category_idx > 0:
                elements.append(PageBreak())

            # 添加页眉
            elements.extend(self._create_header())

            # 主章节标题
            elements.append(Paragraph(f"{main_chapter}、测试数据", self.section_style))

            # 子标题 - 直接使用 1、2、3...
            sub_number = category_idx + 1
            elements.append(
                Paragraph(f"{sub_number}、{category_name}", self.sub_section_style)
            )

            # 测试信息配置（如果有）
            if category_name in test_info_data and test_info_data[category_name]:
                elements.extend(self._create_test_info_table(test_info_data[category_name]))

            # 检查是否有数据
            if not category_data:
                elements.append(Paragraph("暂无测试数据", self.desc_style))
                elements.append(Spacer(1, 0.5 * cm))
                continue

            # 创建测试数据表格 - 固定列宽
            table_data = [
                [Paragraph('序号', self.table_header_style),
                 Paragraph('二级项目', self.table_header_style),
                 Paragraph('测试项目', self.table_header_style),
                 Paragraph('单位', self.table_header_style),
                 Paragraph('数据', self.table_header_style)]
            ]

            for item in category_data:
                table_data.append([
                    Paragraph(str(item.get('序号', '')), self.table_content_style),
                    Paragraph(item.get('二级项目', ''), self.table_content_style),
                    Paragraph(item.get('测试项目', ''), self.table_content_style),
                    Paragraph(item.get('测试项目单位', ''), self.table_content_style),
                    Paragraph(item.get('数据', ''), self.table_content_style)
                ])

            # 固定列宽（单位：cm）
            col_widths = [
                1.0 * cm,  # 序号
                3.5 * cm,  # 二级项目
                7.5 * cm,  # 测试项目
                2.0 * cm,  # 单位
                2.0 * cm  # 数据
            ]

            # 创建表格
            data_table = Table(table_data, colWidths=col_widths, repeatRows=1)
            data_table.setStyle(TableStyle([
                ('FONTNAME', (0, 0), (-1, -1), 'ChineseFont'),
                ('FONTSIZE', (0, 0), (-1, -1), self.table_font_size),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
                ('BACKGROUND', (0, 0), (-1, -1), colors.white),
                ('TOPPADDING', (0, 0), (-1, -1), self.table_padding),
                ('BOTTOMPADDING', (0, 0), (-1, -1), self.table_padding),
                ('LEFTPADDING', (0, 0), (-1, -1), 3),
                ('RIGHTPADDING', (0, 0), (-1, -1), 3),
            ]))

            elements.append(data_table)

            # 相关图片 - 使用KeepTogether确保标题和图片在同一页
            if category_name in image_data and image_data[category_name]:
                elements.append(Spacer(1, 0.5 * cm))
                # 注意：这里 image_data 的 key 已经是 category_name（一级目录名称）
                image_block = self._create_image_block(
                    image_data[category_name],
                    f"{sub_number}.1 相关图片"
                )
                elements.append(KeepTogether(image_block))

        return elements

    # report_generator.py - 修改 _create_image_block 方法

    def _create_image_block(self, images, title):
        """创建图片块 - 包含标题和所有图片，固定图片高度4.5cm，检测宽高比避免重叠"""
        elements = []

        if not images:
            return elements

        # 只有当标题不为空时才添加图片子标题
        if title and title.strip():
            elements.append(Paragraph(title, self.sub_section_style))
            elements.append(Spacer(1, 0.3 * cm))

        # 宽高比阈值
        MAX_ASPECT_RATIO = 1.6  # 超过此值需要调整

        # 目标高度固定为4.5cm
        TARGET_HEIGHT = 4.5 * cm

        valid_images = []
        for img_name, img_path in images:
            if os.path.exists(img_path):
                try:
                    # 加载图片
                    img = ReportLabImage(img_path)
                    # 获取原始尺寸
                    original_width = img.imageWidth
                    original_height = img.imageHeight

                    # 计算原始宽高比
                    aspect_ratio = original_width / original_height if original_height > 0 else 1

                    # 如果宽高比超过阈值，调整为阈值比例
                    if aspect_ratio > MAX_ASPECT_RATIO:
                        # 以MAX_ASPECT_RATIO为准，高度固定为5cm，计算宽度
                        target_width = MAX_ASPECT_RATIO * TARGET_HEIGHT
                        target_height = TARGET_HEIGHT
                        print(
                            f"图片 [{img_name}] 宽高比过大 ({aspect_ratio:.2f})，调整为 {target_width / 28.35:.1f}cm x {target_height / 28.35:.1f}cm")
                    else:
                        # 正常情况：高度固定5cm，宽度按比例计算
                        target_width = original_width * (TARGET_HEIGHT / original_height)
                        target_height = TARGET_HEIGHT

                    # 应用尺寸
                    img.drawHeight = target_height
                    img.drawWidth = target_width

                    # 添加图片标题
                    caption = Paragraph(img_name, self.image_caption_style)

                    # 组合：图片在上，标题在下
                    combined = Table([[img], [caption]],
                                     colWidths=[target_width],
                                     rowHeights=[target_height, 0.8 * cm])
                    combined.setStyle(TableStyle([
                        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                        ('TOPPADDING', (0, 0), (-1, -1), 2),
                        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
                    ]))

                    valid_images.append(combined)

                except Exception as e:
                    print(f"图片加载失败 [{img_name}]: {str(e)}")
                    valid_images.append(Paragraph(f"图片加载失败: {img_name}", self.image_text_style))
            else:
                valid_images.append(Paragraph(f"图片文件不存在: {img_name}", self.image_text_style))

        if not valid_images:
            return elements

        # 根据图片数量排列
        if len(valid_images) == 1:
            # 单张图片居中
            img_table = Table([[valid_images[0]]],
                              colWidths=[self.content_width],
                              hAlign='CENTER')
        else:
            # 多张图片，每行两张
            img_rows = []
            for i in range(0, len(valid_images), 2):
                row = valid_images[i:i + 2]
                if len(row) == 1:
                    row.append(Spacer(1, 0))
                img_rows.append(row)

            img_table = Table(img_rows,
                              colWidths=[self.content_width / 2, self.content_width / 2],
                              hAlign='CENTER')

        img_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('TOPPADDING', (0, 0), (-1, -1), 5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ]))

        elements.append(img_table)
        return elements

    def _create_test_info_table(self, test_info):
        """创建测试信息表格 - 固定列宽"""
        elements = []

        if not test_info:
            return elements

        # 按指定顺序排序
        order = ['试验日期', '试验地点', '里程（km）', '总质量（kg）', '天气', '备注']
        ordered_items = []

        for key in order:
            if key in test_info:
                value = test_info[key] or ''
                ordered_items.append((key, value))

        # 如果没有数据，返回空列表
        if not ordered_items:
            return elements

        # 创建2列3行的表格
        table_data = []
        for i in range(0, len(ordered_items), 2):
            row = []
            for j in range(2):
                if i + j < len(ordered_items):
                    key, value = ordered_items[i + j]
                    row.append(Paragraph(key, self.table_content_style))
                    row.append(Paragraph(value, self.table_content_style))
                else:
                    row.append(Paragraph('', self.table_content_style))
                    row.append(Paragraph('', self.table_content_style))
            table_data.append(row)

        # 固定列宽（单位：cm）
        col_widths = [
            3.0 * cm,  # 第一列标签
            5.0 * cm,  # 第一列值
            3.0 * cm,  # 第二列标签
            5.0 * cm  # 第二列值
        ]

        info_table = Table(table_data, colWidths=col_widths)
        info_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, -1), 'ChineseFont'),
            ('FONTSIZE', (0, 0), (-1, -1), self.table_font_size),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('BACKGROUND', (0, 0), (-1, -1), colors.white),
            ('TOPPADDING', (0, 0), (-1, -1), self.table_padding),
            ('BOTTOMPADDING', (0, 0), (-1, -1), self.table_padding),
            ('LEFTPADDING', (0, 0), (-1, -1), 3),
            ('RIGHTPADDING', (0, 0), (-1, -1), 3),
        ]))

        elements.append(info_table)
        elements.append(Spacer(1, 0.3 * cm))

        return elements


    def _create_declaration_page(self):
        """创建声明页 - 不参与页码计数"""
        elements = []

        # 声明标题样式
        title_style = ParagraphStyle(
            name='DeclarationTitle',
            fontName='ChineseFont-Bold',
            fontSize=18,
            alignment=TA_CENTER,
            spaceAfter=20,
            textColor=colors.black,
            leading=24
        )

        # 内容样式
        content_style = ParagraphStyle(
            name='DeclarationContent',
            fontName='ChineseFont',
            fontSize=11,
            alignment=TA_LEFT,
            spaceAfter=12,
            leading=18,
            leftIndent=0,
            rightIndent=0
        )

        # 标题样式（小标题）
        sub_title_style = ParagraphStyle(
            name='DeclarationSubTitle',
            fontName='ChineseFont-Bold',
            fontSize=12,
            alignment=TA_LEFT,
            spaceBefore=15,
            spaceAfter=5,
            textColor=colors.black,
            leading=18
        )

        # 底部信息样式
        footer_style = ParagraphStyle(
            name='DeclarationFooter',
            fontName='ChineseFont',
            fontSize=9,
            alignment=TA_LEFT,
            spaceBefore=20,
            leading=14,
            textColor=colors.gray
        )

        # 添加顶部空白
        elements.append(Spacer(1, 1 * cm))

        # 声明标题
        elements.append(Paragraph("声      明", title_style))
        elements.append(Spacer(1, 0.5 * cm))

        # 声明内容 - 使用编号列表
        declarations = [
            "1、本试验室对出具的检测结果负责。",
            "2、检测报告必须有检测单位报告专用章，否则该报告无效。",
            "3、报告无编制、校对、审核、批准人签字无效。",
            "4、报告涂改、缺页无效；复制报告未重新加盖检测单位报告专用章无效。",
            "5、对报告若有异议，请于报告签发之日起的20个工作日内以书面形式向本检测单位提出，逾期不予受理。",
            "6、结果仅与被检测样品有关。"
        ]

        for decl in declarations:
            elements.append(Paragraph(decl, content_style))

        elements.append(Spacer(1, 0.8 * cm))

        return elements




def generate_pdf_report(vehicle_id, config_data=None, test_info_data=None):
    """生成PDF报告（兼容接口）"""
    try:
        generator = PDFReportGenerator()
        result = generator.generate_pdf_report(vehicle_id, config_data, test_info_data)

        # 兼容旧接口：如果返回的是字典，提取path
        if isinstance(result, dict):
            if result["success"]:
                return result["path"]
            else:
                # 抛出异常，让上层捕获
                raise Exception(result["error"])
        return result
    except Exception as e:
        error_msg = str(e)
        if "中文字体" in error_msg or "字体" in error_msg:
            raise Exception(f"字体错误：{error_msg}")
        else:
            raise e


def resize_image(image_path, max_width=800, max_height=600):
    """调整图片尺寸（保持兼容性）"""
    try:
        with Image.open(image_path) as img:
            img.thumbnail((max_width, max_height), Image.Resampling.LANCZOS)
            resized_path = image_path.replace('.', '_resized.')
            img.save(resized_path)
            return resized_path
    except Exception as e:
        print(f"图片调整失败: {e}")
        return image_path


# 保持向后兼容的别名
generate_report = generate_pdf_report