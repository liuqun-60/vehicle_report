# pages/admin_perf_basic.py
"""管理员 - 性能基础数据维护"""
import streamlit as st
from datetime import datetime

from database.exports import export_performance_basic_data_csv
from database.imports import import_performance_basic_data_csv


def show_performance_basic_data_maintenance():
    st.title("性能基础数据维护")
    st.info("导出 CSV 编辑后导入，按 **车辆ID** 批量更新试验报告号、编制人员工编码、车辆归属平台、能源类型。")

    csv_data = export_performance_basic_data_csv()
    if csv_data:
        st.download_button(
            "📥 导出性能基础数据 CSV",
            data=csv_data,
            file_name=f"性能基础数据_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv",
            use_container_width=True,
        )
    else:
        st.error("导出失败")

    st.markdown("---")
    uploaded = st.file_uploader("上传 CSV", type=['csv'], key="perf_basic_upload")
    if uploaded and st.button("🚀 导入更新", type="primary", key="perf_basic_import"):
        uploaded.seek(0)
        success, message = import_performance_basic_data_csv(uploaded.read())
        if success:
            st.success(message)
            st.cache_data.clear()
        else:
            st.error(message)
