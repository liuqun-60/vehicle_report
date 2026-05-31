# pages/image.py
"""
图片管理页面 - 修改版
改为使用一级目录名称关联
"""
import streamlit as st
from pathlib import Path
from PIL import Image

from database import (
    get_vehicles, get_main_categories,
    get_report_images_by_category,  # 新函数
    delete_report_images_by_category,  # 新函数
    save_report_image_by_category,  # 新函数
    get_sample_car_images, delete_sample_car_images,
    save_sample_car_image
)
from report_generator import resize_image


def show_image_management():
    """显示图片管理页面"""
    st.title("图片管理")

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
        selected_str = st.session_state.get("image_management_vehicle_select")
        if selected_str and "(ID:" in selected_str:
            vehicle_id = selected_str.split("(ID:")[1].rstrip(")").strip()
            st.session_state['global_selected_vehicle_id'] = vehicle_id

    selected_vehicle_str = st.selectbox(
        "选择车辆",
        vehicle_options,
        index=default_index,
        key="image_management_vehicle_select",
        on_change=update_global_selection
    )

    if 'global_selected_vehicle_id' not in st.session_state and vehicles:
        st.session_state['global_selected_vehicle_id'] = vehicles[0][0]

    if not selected_vehicle_str:
        return

    # 提取车辆ID
    vehicle_id = selected_vehicle_str.split("(ID:")[1].rstrip(")").strip()

    tab1, tab2 = st.tabs(["🖼️ 测试图片", "🚗 样车照片"])

    with tab1:
        st.markdown('<div class="image-upload-box">', unsafe_allow_html=True)
        st.subheader("测试图片上传")
        st.info("💡 为每个测试大类上传相关图片，图片将自动显示在报告中")

        main_categories = get_main_categories()

        # 获取一级目录名称列表
        main_cat_options = [mc[1] for mc in main_categories]
        selected_main_cat = st.selectbox(
            "选择测试大类",
            main_cat_options,
            key="select_main_cat_for_images"
        )

        if selected_main_cat:
            # 使用新函数获取图片（通过一级目录名称）
            existing_images = get_report_images_by_category(vehicle_id, selected_main_cat)

            if existing_images:
                st.write("已上传的图片：")

                cols = st.columns(3)
                for idx, (img_name, img_path) in enumerate(existing_images):
                    with cols[idx % 3]:
                        if Path(img_path).exists():
                            try:
                                with Image.open(img_path) as img:
                                    img.thumbnail((150, 100))
                                    st.image(img, caption=img_name)
                            except:
                                st.write(f"📷 {img_name}")

                        if st.button(
                            f"删除",
                            key=f"delete_{selected_main_cat}_{img_name}",
                            use_container_width=True
                        ):
                            if Path(img_path).exists():
                                Path(img_path).unlink()
                            # 使用新函数删除（通过一级目录名称）
                            delete_report_images_by_category(vehicle_id, selected_main_cat)
                            st.success(f"已删除图片: {img_name}")
                            st.rerun()

            st.markdown("---")

            uploaded_files = st.file_uploader(
                f"为【{selected_main_cat}】上传图片（可多选）",
                type=['jpg', 'jpeg', 'png', 'gif', 'bmp'],
                accept_multiple_files=True,
                key=f"upload_images_{selected_main_cat}"
            )

            if uploaded_files:
                st.info(f"已选择 {len(uploaded_files)} 张照片")

                for uploaded_file in uploaded_files:
                    col1, col2 = st.columns([1, 4])
                    with col1:
                        st.image(uploaded_file, width=80)
                    with col2:
                        st.write(f"文件名: {uploaded_file.name}")
                        st.write(f"大小: {uploaded_file.size / 1024:.1f} KB")

                if st.button(f"📤 上传到【{selected_main_cat}】", key=f"upload_btn_{selected_main_cat}"):
                    # 先删除该分类下的旧图片
                    delete_report_images_by_category(vehicle_id, selected_main_cat)

                    for uploaded_file in uploaded_files:
                        # 创建目录（使用一级目录名称）
                        image_dir = Path(f"uploads/{vehicle_id}/{selected_main_cat}")
                        image_dir.mkdir(parents=True, exist_ok=True)

                        image_path = image_dir / uploaded_file.name
                        with open(image_path, "wb") as f:
                            f.write(uploaded_file.getbuffer())

                        # 调整图片尺寸
                        resized_path = resize_image(str(image_path))

                        # 使用新函数保存（通过一级目录名称）
                        save_report_image_by_category(vehicle_id, selected_main_cat, uploaded_file.name, resized_path)

                    st.success(f"✅ 图片上传成功！已保存到【{selected_main_cat}】")
                    st.rerun()

        st.markdown('</div>', unsafe_allow_html=True)

    with tab2:
        st.markdown('<div class="image-upload-box">', unsafe_allow_html=True)
        st.subheader("样车照片上传")
        st.info("💡 样车照片不区分测试大类，直接上传")

        existing_sample_images = get_sample_car_images(vehicle_id)

        if existing_sample_images:
            st.write("已上传的样车照片：")

            cols = st.columns(3)
            for idx, (img_name, img_path) in enumerate(existing_sample_images):
                with cols[idx % 3]:
                    if Path(img_path).exists():
                        try:
                            with Image.open(img_path) as img:
                                img.thumbnail((150, 100))
                                st.image(img, caption=img_name)
                        except:
                            st.write(f"📷 {img_name}")

                    if st.button(
                        f"删除 {img_name}",
                        key=f"delete_sample_{img_name}",
                        use_container_width=True
                    ):
                        if Path(img_path).exists():
                            Path(img_path).unlink()
                        delete_sample_car_images(vehicle_id)
                        st.success(f"已删除照片: {img_name}")
                        st.rerun()

        uploaded_sample_images = st.file_uploader(
            "上传样车照片（可多选）",
            type=['jpg', 'jpeg', 'png', 'gif', 'bmp'],
            accept_multiple_files=True,
            key="upload_sample_car_images"
        )

        if uploaded_sample_images:
            st.info(f"已选择 {len(uploaded_sample_images)} 张照片")

            cols = st.columns(3)
            for idx, uploaded_file in enumerate(uploaded_sample_images):
                with cols[idx % 3]:
                    st.image(uploaded_file, caption=uploaded_file.name, width=120)

            if st.button("📤 上传样车照片", key="upload_sample_images_btn"):
                delete_sample_car_images(vehicle_id)

                for uploaded_file in uploaded_sample_images:
                    image_dir = Path(f"uploads/{vehicle_id}/sample_car")
                    image_dir.mkdir(parents=True, exist_ok=True)

                    image_path = image_dir / uploaded_file.name
                    with open(image_path, "wb") as f:
                        f.write(uploaded_file.getbuffer())

                    resized_path = resize_image(str(image_path))

                    save_sample_car_image(vehicle_id, uploaded_file.name, resized_path)

                st.success("✅ 样车照片上传成功！")
                st.rerun()

        st.markdown('</div>', unsafe_allow_html=True)