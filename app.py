# 智能交通管理系统 - 《人工智能通识基础》课程设计
# 功能：基于 OSRM（路径规划）和 Open-Meteo（天气）提供免费路径规划和个性化建议
# 决策分支：
# 1. 雨雪天气（天气代码 ≥51）：建议推迟或用公共交通
# 2. 温度高/低（>30°C 或 <5°C）：穿衣建议
# 3. 交通繁忙（高峰时段或长距离）：推荐非高峰出行
# 作者：基于 Streamlit 实现，适配课程作业提交
# 优化：
# 1. 去掉多余表情，保持界面简洁
# 2. 保留核心功能，确保健壮性

import streamlit as st
import streamlit.components.v1 as components
import requests
import folium
from datetime import datetime
import os
import uuid

# 检查 retrying 模块（可选）
try:
    from retrying import retry
    RETRY_AVAILABLE = True
except ImportError:
    RETRY_AVAILABLE = False
    def retry(*args, **kwargs):
        """伪装饰器，跳过重试"""
        def decorator(func):
            return func
        return decorator

# 页面设置
st.set_page_config(page_title="智能交通管理系统", layout="wide")

# 标题
st.title("智能交通管理系统")
st.markdown("""
本系统为《人工智能通识基础》课程设计，基于免费 OSRM 和 Open-Meteo API 实现智能交通管理。
功能：输入起点/终点坐标和出行方式，生成推荐路线，并根据实时天气和交通状况提供个性化建议。
**决策分支**：
1. 雨雪天气 → 是否推荐出行  
2. 温度过高/过低 → 穿衣建议  
3. 交通繁忙 → 推荐非高峰时段出行
""")

# 坐标验证函数
def validate_coords(coord_str):
    """验证坐标格式和范围"""
    try:
        lon, lat = map(float, coord_str.split(","))
        if not (-180 <= lon <= 180 and -90 <= lat <= 90):
            raise ValueError("坐标超出有效范围（经度 -180~180，纬度 -90~90）")
        return lon, lat
    except:
        raise ValueError("坐标格式错误，需为：经度,纬度（如 116.39139,39.9075）")

# API 调用函数
@retry(stop_max_attempt_number=3, wait_fixed=2000) if RETRY_AVAILABLE else lambda x: x
def fetch_url(url):
    """调用 API，带超时，兼容无 retrying"""
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        raise Exception(f"API 请求失败：{e}")

# 输入界面
st.subheader("输入出行信息")
col1, col2 = st.columns(2)
with col1:
    start = st.text_input("起点坐标（经度,纬度）", "116.39139,39.9075", help="格式：经度,纬度，例如 116.39139,39.9075")
with col2:
    end = st.text_input("终点坐标（经度,纬度）", "116.3975,39.9087", help="格式：经度,纬度，例如 116.3975,39.9087")
travel_mode = st.selectbox(
    "请选择出行方式",
    ["driving", "cycling", "walking"],
    format_func=lambda x: {"driving": "驾车", "cycling": "骑行", "walking": "步行"}[x]
)

# 按钮触发
if st.button("生成路线并分析", use_container_width=True, help="点击生成推荐路线和出行建议"):
    with st.spinner("正在生成路线和智能建议，请稍候..."):
        # 初始化变量
        map_html = None
        distance = None
        duration = None
        start_coords = None
        end_coords = None
        map_file = None

        # 1. 生成地图（独立逻辑）
        try:
            # 验证坐标
            start_coords = validate_coords(start)
            end_coords = validate_coords(end)

            # 调用 OSRM API 获取路径
            osrm_url = f"http://router.project-osrm.org/route/v1/{travel_mode}/{start_coords[0]},{start_coords[1]};{end_coords[0]},{end_coords[1]}?overview=full&geometries=geojson"
            data = fetch_url(osrm_url)

            if data.get("code") != "Ok":
                st.error("无法生成路线，请检查坐标或网络连接。")
                st.stop()

            # 提取路径信息
            route = data["routes"][0]
            distance = route["distance"] / 1000  # 公里
            duration = route["duration"] / 60  # 分钟
            coordinates = route["geometry"]["coordinates"]  # [[lon, lat], ...]

            # 生成地图
            m = folium.Map(location=[start_coords[1], start_coords[0]], zoom_start=14)
            folium.Marker(location=[start_coords[1], start_coords[0]], tooltip="起点", icon=folium.Icon(color='green')).add_to(m)
            folium.Marker(location=[end_coords[1], end_coords[0]], tooltip="终点", icon=folium.Icon(color='red')).add_to(m)
            folium.PolyLine(locations=[[p[1], p[0]] for p in coordinates], color="blue", weight=5).add_to(m)

            # 保存地图为 HTML
            map_file = f"map_{uuid.uuid4()}.html"
            m.save(map_file)

            # 读取 HTML 内容
            with open(map_file, "r", encoding="utf-8") as f:
                map_html = f.read()

        except ValueError as e:
            st.error(f"输入错误：{e}")
            st.stop()
        except Exception as e:
            st.error(f"路线生成失败：{e}")
            if "network" in str(e).lower() or "timeout" in str(e).lower():
                st.info("提示：请检查网络连接，或稍后重试。")
            st.stop()

        # 显示地图
        st.subheader("推荐路线地图")
        components.html(map_html, height=500, scrolling=True)

        # 显示路径信息
        st.success(f"推荐路线：距离 {distance:.2f} 公里，预计耗时 {duration:.1f} 分钟")

        # 2. 获取天气和生成建议（独立逻辑）
        suggestions = []
        try:
            # 获取天气（Open-Meteo）
            weather_url = f"https://api.open-meteo.com/v1/forecast?latitude={start_coords[1]}&longitude={start_coords[0]}&hourly=weathercode,temperature_2m&current_weather=true"
            weather_data = fetch_url(weather_url)
            weather_code = weather_data["current_weather"]["weathercode"]
            temperature = weather_data["current_weather"]["temperature"]
            weather_desc = {
                0: "晴", 1: "少云", 2: "多云", 3: "阴",
                51: "小雨", 61: "中雨", 63: "大雨",
                71: "小雪", 73: "中雪", 75: "大雪"
            }.get(weather_code, "未知")
            st.markdown(f"当前天气：{weather_desc}，温度：{temperature}°C")

            # 决策分支和建议（表格展示）
            st.subheader("智能出行建议")
            suggestion_table = "| 决策分支 | 条件 | 建议 |\n|---|---|---|\n"

            # 决策分支 1：是否下雨
            if weather_code >= 51:  # 雨雪天气
                suggestion = "雨雪天气，建议推迟出行或选择公共交通。"
                st.warning(f"决策 1：雨雪天气 - {suggestion}")
                suggestion_table += f"| 雨雪天气 | 天气代码 ≥51 | {suggestion} |\n"
            else:
                suggestion = "天气适合出行。"
                st.info(f"决策 1：天气适宜 - {suggestion}")
                suggestion_table += f"| 雨雪天气 | 无雨雪 | {suggestion} |\n"
            suggestions.append(suggestion)

            # 决策分支 2：温度高/低
            if temperature > 30:
                suggestion = "高温，穿轻薄衣物，携带防晒用品。"
                st.warning(f"决策 2：高温 - {suggestion}")
                suggestion_table += f"| 温度高/低 | 温度 >30°C | {suggestion} |\n"
            elif temperature < 5:
                suggestion = "低温，穿厚实保暖衣物。"
                st.warning(f"决策 2：低温 - {suggestion}")
                suggestion_table += f"| 温度高/低 | 温度 <5°C | {suggestion} |\n"
            else:
                suggestion = "温度适宜，穿日常衣物。"
                st.info(f"决策 2：温度适宜 - {suggestion}")
                suggestion_table += f"| 温度高/低 | 5°C ≤ 温度 ≤ 30°C | {suggestion} |\n"
            suggestions.append(suggestion)

            # 决策分支 3：交通繁忙
            current_hour = datetime.now().hour
            is_peak_hour = current_hour in [7, 8, 9, 17, 18, 19]  # 高峰时段
            is_long_distance = distance > 10  # 长距离
            if is_peak_hour or is_long_distance:
                suggestion = "高峰时段或长距离，建议非高峰时段（如10:00-16:00）出行。"
                st.warning(f"决策 3：交通繁忙 - {suggestion}")
                suggestion_table += f"| 交通繁忙 | 高峰时段或距离 >10km | {suggestion} |\n"
            else:
                suggestion = "交通状况良好，适合出行。"
                st.info(f"决策 3：交通顺畅 - {suggestion}")
                suggestion_table += f"| 交通繁忙 | 非高峰且距离 ≤10km | {suggestion} |\n"
            suggestions.append(suggestion)

            # 显示建议表格
            st.markdown(suggestion_table)

        except Exception as e:
            st.error(f"天气数据获取失败：{e}")
            st.info("天气数据不可用，将跳过智能建议。")
            suggestions = ["天气数据不可用，无法生成智能建议。"]

        # 3. 保存建议和路线信息
        result = "智能交通管理系统 - 《人工智能通识基础》课程设计\n\n"
        result += f"起点：{start}\n终点：{end}\n出行方式：{travel_mode}\n"
        result += f"距离：{distance:.2f} 公里\n耗时：{duration:.1f} 分钟\n"
        if len(suggestions) > 1:  # 天气数据成功时
            result += f"天气：{weather_desc}，温度：{temperature}°C\n\n"
        result += "智能建议（决策分支）：\n" + "\n".join(f"- {s}" for s in suggestions)
        st.download_button(
            "下载建议和路线信息",
            result,
            file_name="smart_traffic_report.txt",
            use_container_width=True,
            help="下载路线和建议报告"
        )

        # 4. 清理临时文件
        if map_file and os.path.exists(map_file):
            os.remove(map_file)

# 提示未安装 retrying
if not RETRY_AVAILABLE:
    st.warning("未安装 retrying 模块，建议运行 `pip install retrying` 以增强 API 稳定性。")

# 自定义 CSS 移除非法 ARIA 属性
st.markdown("""
<style>
[aria-expanded="false"] {
    aria-expanded: none !important;
}
</style>
""", unsafe_allow_html=True)