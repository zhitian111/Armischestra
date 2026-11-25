# Dobot 四轴机械臂接入

`perform` 读取编辑器导出的剧场 JSON，并使用实测标定、现场气泵接线和实时相机执行同一份剧本。适配器对照 Dobot 官方 SDK 提交 `b5f95647` 实现，厂家列出的机型为 MG400 和 M1Pro，控制器版本要求 V1.5.6.0 或以上。拿到机械臂后先核对铭牌与控制器版本。[厂家 SDK 说明](https://github.com/Dobot-Arm/TCP-IP-4Axis-Python/blob/b5f95647cfc44a60f92babf5a464d38dd1e4f72c/README.md)

1. 下载厂家 SDK 到本机。适配器从指定目录导入 `dobot_api.py`。Python 环境需要 OpenCV（含 ArUco）、NumPy 及 Tk。可以用 `.venv/bin/python -c 'import cv2.aruco, numpy, tkinter'` 检查依赖。厂家模块会导入 Tk，即使演出不使用厂家的图形界面。
2. 把 [hardware.template.json](../examples/hardware.template.json) 复制为 `hardware.local.json`。填写与实际打印舞台对应的相机四点标定、棋盘至机械臂的标定点、高低位和吸放等待时间。标定机械臂时使用吸盘中心的 TCP（工具中心点）。确保球头或吸盘与试演时朝向一致。
3. 把 [dobot.template.json](../examples/dobot.template.json) 复制为 `dobot.local.json`，按下表填写。电脑须能连接控制端口 29999 和运动端口 30003，两者使用同一个控制器地址。
4. 用厂家软件设置 TCP/IP 控制模式、负载等参数。将控制器置于已使能、空闲状态，初始吸盘空载，气阀置于释放状态。程序保持开始演出时的吸盘朝向。
5. 先以实物检查棋盘范围、吸放电平和高低位，然后在项目目录运行下面的命令。运行 `perform` 会向控制器发送实际动作。

```sh
git clone https://github.com/Dobot-Arm/TCP-IP-4Axis-Python.git /path/to/TCP-IP-4Axis-Python
git -C /path/to/TCP-IP-4Axis-Python checkout b5f95647cfc44a60f92babf5a464d38dd1e4f72c
.venv/bin/python -m armischestra perform show.json \
    --calibration hardware.local.json --device dobot.local.json \
    --sdk-dir /path/to/TCP-IP-4Axis-Python
```

| 设备字段 | 要填写的内容 |
| --- | --- |
| `host` | 机械臂控制器实际 IP 或可解析的主机名。 |
| `camera_source` | OpenCV 可读的 USB 摄像头编号（JSON 整数，例如 `0`），或手机提供的 RTSP/HTTP/HTTPS 实时视频流地址。每次拍摄时在当前位置停止运动，随后重新打开相机、丢弃首帧再取图，避免复用上次运动前缓存的帧。标定和演出应使用相同的视频源、分辨率、裁剪与镜头。 |
| `camera_size_px` | 填入标定图像的像素尺寸 `[宽, 高]`。对 USB 相机会请求此分辨率，所有视频源在尺寸不符时会提示错误。留空使用设备默认设置。 |
| `user_index`、`tool_index` | 与实测 XYZ 时相同的用户坐标系和吸盘工具坐标系编号。程序设置全局 User、Tool 后同步一次，再读取 TCP 的 XYZ 和朝向 R。 |
| `speed_l_percent` | 每段直线的速度百分比（1～100），实际速度还受控制器全局设置影响。 |
| `command_timeout_s` | 单次 SDK 应答的超时秒数，应覆盖最长单段动作及到位等待。 |
| `suction`、`blow` | 阀门的 `bank` 取 `controller`（控制柜 DO）或 `tool`（末端 DO）。`index` 是实际端口编号，`active_level` 取 0 或 1，由接线决定。单独吸气、断电释放时令 `blow` 为 `null` 且 `arm.blow_seconds` 为 0。有独立吹气阀时，填入该阀及实测吹气时间。 |

本适配器控制独立的吸气阀和可选的吹气阀。切换时先关闭对侧阀门，再打开所需阀门。若现场泵有单独的串口协议或不同的电气控制方式，可通过 `run_hardware` 的 `set_pump(mode)` 回调接入。

适配器使用 `GetPose` 读取当前位置，`MovL` 执行直线运动，`Sync` 等待当前队列执行完成。吸放使用 `DOExecute` 或 `ToolDOExecute` 即时设置数字输出。控制器拒绝命令、应答不完整或超时会中断演出；移动过程中若失去确认，程序会通过控制口尝试 `ResetRobot` 停止运动并清除队列。网络中断时仍应通过现场设备确认状态。[官方 SDK 源码](https://github.com/Dobot-Arm/TCP-IP-4Axis-Python/blob/b5f95647cfc44a60f92babf5a464d38dd1e4f72c/dobot_api.py) · [四轴 TCP/IP 命令手册](https://github.com/Dobot-Arm/TCP-IP-Protocol-4AXis)

### 连续走位和接触推移

每次移动在当前位置先取新帧，吸盘高位直达实际观测到的角色或道具；放下后原地升高、取新帧核对落点，下一次移动从这里直接出发。只有本帧缺少目标标记时才重试一次。若吸盘在棋盘的位置已知，会沿剩余空间较大的坐标轴在高位侧让；`camera.occlusion_clearance_mm` 为侧让距离（默认一个棋格，0 表示不侧让）。开场位置未知且目标不可见时使用一次已标定的 `park_mm`。第二帧仍看不到目标或落点超差，会停止演出。

剧本中的 `method: "push"` 表示用垂直末端接触纸道具后缘的推耳，关闭吸吹，保持低位直线推进，再原地升高。给道具准备能接触吸盘侧面的推耳，初始朝向应使推耳位于推向的反侧；用同厚材料验证吸取低位也适合轻触推耳，且沿路与周围卡片有间隙。`push_back_mm` 是顺着推向从末端接触中心量到可定位吸取点的距离，两个点都用棋盘 XY 表示。请勿将气泵的吹气当成可控的侧推。若仅能吸、放、吹或推耳尚未试过，把编辑器中对应移动方式选为“吸移”即可保留相同目标位置。用空白纸片实际验证低位推进后，才将 `hardware.local.json` 中的 `arm.contact_push_enabled` 改为 `true`。模拟器默认可演示接触推移。

### 自动 XY 标定与演前预检

编辑器的「部署与标定 → 打印标定码」生成五张白底方片。以 100% 打印，检查黑框 18 mm、白底 24 mm。按前端示意将 45–48 紧贴棋盘左右外侧，保持朝向，上下端分别齐边；棋盘高须超过 48 mm。让棋盘标记与纸卡码面等高。49 水平朝上装在吸盘轴线上。自动模式给纸卡使用 0–44，已有工程若占用 45–49，请更换并重印相应纸卡。照明应避免铜版纸反光。

首次用同一视频流保存至少六张不同倾角、不同画面位置的清晰画面（全部可见四个码）。校准期间可以移动手机。使用与实物尺寸一致的编辑器工程。把设备模板和自动标定模板分别复制为本机配置，填写设备连接、手动测得的两个 Z、低位时 49 号码面到棋盘码面的高度、吸放时长。坐标系的 Z 轴须垂直棋盘且朝上。每次开场让空载吸盘从设定高位、四码和吸盘码均可见的位置开始。从此处沿机械臂用户坐标系 +X、+Y 展开的整个正方形都应空旷，按现场可用边长填写 sample_span_mm。尽量用较大边长以降低测量噪声。复核后吸盘回到本次采样起点，请让起点避开纸卡以供读取开场布局。

```sh
.venv/bin/python -m armischestra lens --project show.json --output lens.local.json photos/*.png
.venv/bin/python -m armischestra perform show.json --device dobot.local.json \
  --calibration hardware.auto.local.json --lens lens.local.json \
  --sdk-dir /path/to/TCP-IP-4Axis-Python --preflight-only
```

第一条也可将照片列表换成 --device dobot.local.json，从手机视频流逐张取景，不需要连接机械臂。第二条会实际移动吸盘采点，随后只查询逆解。去掉最后的 --preflight-only 可在预检成功后直接演出。程序从实测纸卡位置开始，用相同的吸移、途经和推移逻辑，以至多 10 mm 间隔采样高低位路线，报告失败的步骤。逆解采样不检测支架、道具或气管碰撞。演出中实时修正和遮挡避让路线也在下发前采样检查。手机或棋盘在取图时发生明显位移、四码缺失会中止；运动过程中没有连续视频监控。

两场之间移动手机后重新运行 perform 即可。固定镜头、焦距、输出尺寸、方向和裁剪时可以复用镜头档案；改变其中任一项后重建档案。改变底座与台面的相对高度或更换末端后重新测量 Z 和码面高度。保留原有手工标定模式时可省略 --lens。
