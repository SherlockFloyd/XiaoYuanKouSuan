# XIaoYuanKouSuan

本项目最低耗时 0.1s

- 基本原理： 通过MitM拦截指定响应请求，修改其中题目答案全部为"1"并重放，通过 adb 模拟滑动操作解题
- 本代码对答案绘制及开始答题时间进行优化，无需修改具体坐标，由adb命令自动获取，可通过可调参数修改具体选项

## 前期准备
1. Windows电脑，安装任意一款安卓模拟器并获取root权限，教程可百度(很简单)
2. 安装python3环境
3. 安装adb工具[下载链接](https://dl.google.com/android/repository/platform-tools-latest-windows.zip)
4. 代码有详细注释，可根据需求自行更改

## 使用

1. 安装依赖

```shell
pip install -r requirements.txt
```

2. 配置 安卓虚拟机 设备

```shell
# 采用 trust me already 禁用 app ssl

# 打开开发者选项中的 usb 调试
adb devices

```

3. 配置安卓代理

WIFI 设置代理为电脑 ip 和端口(8080)

4. 运行脚本

```shell
python main.py -H <host> -P <port>
```


## 感谢

感谢以[大佬](https://github.com/cr4n5)的基础代码


