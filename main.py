"""
Author: fengshao
Date: 2024/10/10 12:27
Description: 小猿口算脚本
"""

import re
import sys
import threading
import argparse
import io
import time
import subprocess

import adbutils
from PIL import Image
from functools import lru_cache
from mitmproxy import http
from mitmproxy.tools.main import mitmdump

'''
基本原理
拦截Http响应并筛选，提取其中的答案，并修改所有答案为"1"，通过adb命令在屏幕上绘制响应答案
'''

# 可调参数
# 是否开启自动答题
auto_jump = False
# 每道题的滑动基准次数
base_swipe_count = 1
# 通过颜色变化判断是否进入答题界面阈值(0-255)
white_pixel_threshold = 240
# 答题区域占屏幕的比例
BOTTOM_PERCENTAGE = 0.5
# 绘制答案大小占绘制区域比例
LINE_HEIGHT_PERCENTAGE = 0.5


def request(flow: http.HTTPFlow) -> None:
    """拦截并打印 HTTP 请求"""
    print(f"Request: {flow.request.method} {flow.request.url}")


def response(flow: http.HTTPFlow):
    """拦截 HTTP 响应，检查 URL 并逐个字段替换"""
    print(f"Response: {flow.response.status_code} {flow.request.url}")
    # 匹配目标 URL
    url_pattern = re.compile(r"https://xyks.yuanfudao.com/leo-math/android/exams.+")

    # 如果 URL 匹配
    if url_pattern.match(flow.request.url):
        print("响应匹配成功！")
        # 如果响应类型是 JSON
        if "application/json" in flow.response.headers.get("Content-Type", ""):
            response_text = flow.response.text

            # 使用正则表达式逐个替换字段
            response_text = re.sub(r'"answer":"[^"]+"', '"answer":"1"', response_text)
            response_text = re.sub(r'"answers":\[[^\]]+\]', '"answers":["1"]', response_text)

            # 更新修改后的响应体
            flow.response.text = response_text

        # 动态计算题目数量并启动答题逻辑
        answer_count = len(re.findall(r'answers', flow.response.text))  # 根据答案数量统计题目数量
        threading.Thread(target=wait_until_ready_and_start_answering, args=(answer_count,)).start()
        if auto_jump:
            threading.Thread(target=jump_to_next).start()


def is_screen_ready_for_answer():
    """判断是否进入答题界面"""
    # 截图
    device = adbutils.adb.device()
    img_bytes = device.screencap()  # 获取截图的字节流

    # 使用 PIL 打开图片
    img = Image.open(io.BytesIO(img_bytes))
    width, height = img.size

    # 截取图片的下半部分
    lower_half = img.crop((0, height // 2, width, height))

    # 判断该部分是否为纯白色
    # 获取图像数据
    pixels = list(lower_half.getdata())

    # 判断像素是否接近白色
    def is_white(pixel):
        return all(p >= white_pixel_threshold for p in pixel)

    # 计算下半部分白色像素的比例
    white_pixel_count = sum(1 for pixel in pixels if is_white(pixel))
    total_pixel_count = len(pixels)
    # 如果白色像素占比超过一定比例，则判断为纯白色区域
    white_pixel_ratio = white_pixel_count / total_pixel_count
    # 当白色像素占比超过 95% 时，认为屏幕下半部分变成了纯白色答题区域
    return white_pixel_ratio > 0.95


def wait_until_ready_and_start_answering(answer_count):
    """判断是否进入答题界面"""
    print("等待进入答题界面...")
    while True:
        if is_screen_ready_for_answer():
            print(f"开始答题，总题目数：{answer_count}")
            answer_write(answer_count)
            break
        time.sleep(0.1)


@lru_cache()
def get_device_resolution():
    """获取设备的实际分辨率"""
    device = adbutils.adb.device()
    size_output = device.shell("wm size")
    if "Physical size" in size_output:
        resolution_str = size_output.split(":")[-1].strip()
        width, height = map(int, resolution_str.split("x"))
        return width, height
    else:
        raise Exception("无法获取设备分辨率")


def calculate_line_coordinates():
    """计算竖线的起始和结束坐标，封装成数据结构返回。"""
    screen_width, screen_height = get_device_resolution()

    # 计算绘制区域
    draw_area_top = int(screen_height * (1 - BOTTOM_PERCENTAGE))  # 下半屏开始位置
    draw_area_height = int(screen_height * BOTTOM_PERCENTAGE)  # 下半屏的高度
    line_height = int(draw_area_height * LINE_HEIGHT_PERCENTAGE)  # 线条高度占绘制区域的60%

    # 计算竖线的起始和结束坐标，线条位于屏幕正中间
    line_x = screen_width // 2  # 屏幕宽度的中间
    line_start_y = draw_area_top + (draw_area_height - line_height) // 2  # 竖线顶部位置
    line_end_y = line_start_y + line_height  # 竖线底部位置

    # 返回坐标封装成字典
    return {
        "x": line_x,
        "start_y": line_start_y,
        "end_y": line_end_y
    }


# 自动进入下一题
def jump_to_next():
    # 结束，自动进下一局
    device = adbutils.adb.device()
    time.sleep(3)
    command = "input tap 540 1520"
    device.shell(command)  # “开心收下”按钮的坐标
    time.sleep(0.3)
    command = "input tap 780 1820"
    device.shell(command)  # “继续”按钮的坐标
    time.sleep(0.3)
    command = "input tap 510 1700"
    device.shell(command)  # “继续PK”按钮的坐标


def swipe_screen(coordinates):
    """根据传入的坐标数据结构在屏幕上绘制竖线。"""
    line_x = coordinates['x']
    line_start_y = coordinates['start_y']
    line_end_y = coordinates['end_y']

    # 使用 ADB 指令绘制竖线
    command = f"input swipe {line_x} {line_start_y} {line_x} {line_end_y} 0"
    subprocess.run(["adb", "shell", command], stdout=subprocess.PIPE, stderr=subprocess.PIPE)



def answer_write(answer_count):
    start_time = time.time()
    """根据题目数量滑动屏幕"""
    total_swipe_count = answer_count * base_swipe_count  # 总滑动次数根据题目数量计算

    print(f"预计滑动次数：{total_swipe_count}")
    # 获取计算好的竖线坐标
    coordinates = calculate_line_coordinates()

    for i in range(total_swipe_count):
        swipe_screen(coordinates)
        time.sleep(0.01)  # 滑动之间的等待时间

    end_time = time.time()  # 记录结束时间
    elapsed_time = end_time - start_time  # 计算耗时
    print(f"答题完成，耗时：{elapsed_time:.3f} 秒")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Mitmproxy script")
    parser.add_argument("-P", "--port", type=int, default=8080, help="Port to listen on")
    parser.add_argument("-H", "--host", type=str, default="192.168.190.1", help="Host to listen on")
    args = parser.parse_args()

    sys.argv = ["mitmdump", "-s", __file__, "--listen-host", args.host, "--listen-port", str(args.port)]
    mitmdump()
