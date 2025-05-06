import streamlit as st
import openrouteservice
from openrouteservice import convert
import folium
from streamlit_folium import st_folium

# 设置页面标题
st.set_page_config(page_title="智能交通路径规划系统")

st.title(" 智能交通路径规划系统")
st.markdown("输入起点、终点和可选途经点，选择偏好，生成推荐路线并展示在地图上。")

# 输入坐标
start = st.text_input("起点坐标（格式：经度,纬度）", "116.39139,39.9075")
end = st.text_input("终点坐标（格式：经度,纬度）", "116.3975,39.9087")
waypoint = st.text_input("（可选）途经点坐标（格式：经度,纬度）", "")

# 决策分支 1：选择交通方式
mode = st.selectbox("选择交通方式", ["driving-car", "cycling-regular", "foot-walking"])

# 决策分支 2：是否避开高速
avoid_highways = st.checkbox("避开高速公路")

# OpenRouteService API Key
api_key = "5b3ce3597851110001cf6248eae3d44b9bfb4894aec1bf589f109308"

if st.button("生成路线"):
    try:
        # 构建坐标列表
        coords = [list(map(float, start.split(",")))]
        if waypoint.strip():
            coords.append(list(map(float, waypoint.split(","))))
        coords.append(list(map(float, end.split(","))))

        client = openrouteservice.Client(key=api_key)

        # 请求参数构建
        request_params = {
            "coordinates": coords,
            "profile": mode,
            "format_out": "geojson",
        }

        if avoid_highways:
            request_params["options"] = {"avoid_features": ["highways"]}

        # 获取路径
        route = client.directions(**request_params)

        geometry = route['features'][0]['geometry']
        coords_line = geometry['coordinates']

        # 创建地图
        center_latlon = coords[0][::-1]  # 经纬度顺序调换
        m = folium.Map(location=center_latlon, zoom_start=13)

        # 起点终点和途经点标记
        folium.Marker(location=coords[0][::-1], tooltip="起点", icon=folium.Icon(color='green')).add_to(m)
        if len(coords) == 3:
            folium.Marker(location=coords[1][::-1], tooltip="途经点", icon=folium.Icon(color='orange')).add_to(m)
        folium.Marker(location=coords[-1][::-1], tooltip="终点", icon=folium.Icon(color='red')).add_to(m)

        # 路径绘制
        folium.PolyLine(locations=[(pt[1], pt[0]) for pt in coords_line], color="blue", weight=5).add_to(m)

        # 展示地图
        st_folium(m, width=700, height=500)

    except Exception as e:
        st.error(f"发生错误：{e}")
