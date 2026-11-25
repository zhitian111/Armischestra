# Armischestra · 艾露猫大战黑龙

当前剧目是[《修雷德的最后一串团子》演出本](docs/修雷德的最后一串团子.md)。一个垂直吸盘操演十二张纸卡。七回合约 3 分 40 秒，呆猫与黑龙从 2:3 打到 1:0。棋盘上沿有双方的实体血槽及弃血区，下沿有吐息、换偶、刀光和甩尾的候场位。[开场摆位图](examples/score.synthetic.png)可供布景时对照。直接打开[离线回放](rehearsal.html)，或将[完整工程](examples/schrade.armischestra.json)导入编辑器改戏。剧本使用棋盘 XY 毫米坐标，升降只有 `high` 和 `low` 两档。现在可以用 Python 3.10 或更高版本在电脑上排练，离线排练只依赖标准库。

## 用可视化编辑器编排

在项目目录运行 `python3 -m armischestra editor`，打开 **http://127.0.0.1:8765/**。编辑器随本地 Python 服务运行，自带一场可以修改的示例剧。

1. **摆角色和道具**。在“候场区”设置预置区域；纸卡可标为角色或道具。在棋盘上拖动角色，或输入起点的毫米坐标。在角色设置中上传自己的画，设置卡片的印刷宽高、标记编号，以及标记中心到吸取点的偏移。坐标表示吸取点。示意立绘可换成你的彩印原图。
   在血条设置中可为角色划定血区，自动生成指定格数的红方块，也可绑定已做好的纸卡。开场把它们摆在本方槽内，用普通吸移将一块送进弃血区即可扣一格；最后一块离开后显示零血。
2. **排戏**。针对单张卡选择吸移或直线平推。添加、编辑或调整移动、字幕、等待动作的顺序。移动可经过多个途经点。点击播放或拖动进度条，查看 Python 模拟机械臂依次抓取、移动、释放角色的过程。
3. **准备场地**。示例剧已附 [A3 横向印品（3 页）](examples/print/theater-A3.pdf)和 [A4 横向印品（6 页）](examples/print/theater-A4.pdf)。在“打印素材”选择 A2、A3、A4 或 A5，横向或纵向，以及棋盘、角色或两者。打印预览提供逐页 SVG 下载，也可以打印或从浏览器保存 PDF。选择实际大小/100%，关闭浏览器页眉页脚，印好先用尺子核对页面上的校尺。棋盘超出单页时按拼接标记组合；角色页含 ArUco 标记，可在印品预览中切换为角色图与标记分开打印。角色设置中的两组偏移分别表示画面中心到标记中心、标记中心到吸取点，单位为毫米，向右和向上为正。分开打印时按标注位置、朝向贴标。按工程取向摆正棋盘，从左下角量 XY。
4. **保存演出**。“导出剧本”下载一份带版本号的 JSON，里面同时包含舞台、剧本和内嵌 PNG。之后可重新导入编辑。用下面的命令将同一文件交给 Python：

```sh
python3 -m armischestra rehearse --project 我的剧场.json --replay 我的预演.html
.venv/bin/python -m armischestra locate 艾露猫 --project 我的剧场.json --calibration hardware.local.json --image stage.jpg
```

设备接好后，使用相同的工程文件启动实机演出：

```sh
.venv/bin/python -m armischestra perform 我的剧场.json --calibration hardware.local.json --device dobot.local.json --sdk-dir /path/to/TCP-IP-4Axis-Python
```

使用固定手机自动对齐 XY 时，在前端「部署与标定」打印四个棋盘码和一个吸盘码，按图安装。首次建立镜头档案，手动测定高低 Z；之后每次开场自动采点并预检路线。两场之间挪动手机可以复用同一镜头档案。命令和现场配置见 [自动 XY 部署说明](docs/dobot.md#自动-xy-标定与演前预检) 和 [自动标定配置模板](examples/hardware.auto.template.json)。

[Dobot 接入说明](docs/dobot.md)列出适配型号、官方 SDK 版本、坐标系、气阀接线配置、相机来源和首次测试步骤。[标定模板](examples/hardware.template.json)和[设备模板](examples/dobot.template.json)分别记录场地测量值和设备设置。网页预演只使用本地模拟器。舞台尺寸与卡片尺寸均为毫米，虚拟时长由模拟速度估算。

## 排练和改戏

在项目目录执行：

```sh
python3 -m armischestra rehearse
```

打开生成的 [rehearsal.html](rehearsal.html)，点击播放或拖动进度条。画面显示演员、道具和候场区，十字圆环是吸盘。横移速度、升降耗时和吸放等待都是模拟值。排练按点位计算，纸片尺寸、碰撞、真空密封和机械臂可达范围需要在实体舞台上确认。

旧版两角色示例的[舞台](examples/stage.json)规定尺寸、格距、观察时的备用退让位置、允许的落点误差，以及各角色的标记编号和排练初始位置。示例棋盘为 300 × 200 mm，每格 25 mm，原点在左下角，X 向右、Y 向上。坐标可以落在格子之间。真机起点由相机读取。

旧版[剧本](examples/show.json)按顺序编排字幕、等待和移动。下面这一段让艾露猫沿两段路径绕到黑龙身侧：

```json
[
  {"op": "cue", "text": "喵！艾露猫侧身一跃。"},
  {"op": "move", "actor": "艾露猫", "via_mm": [[125, 50], [175, 50]], "to_mm": [200, 75]},
  {"op": "wait", "seconds": 0.5}
]
```

把这些动作放进剧本的 `steps` 数组。`via_mm` 可以省略；有途经点时，吸盘一路保持吸住，直到终点才放下。`cue` 显示字幕，实机也可以接音效回调。`wait` 等待指定秒数。换剧本、指定回放文件或导出逐步状态可运行：

```sh
python3 -m armischestra rehearse --stage examples/stage.json --show examples/show.json --replay output/show.html --trace output/moves.json
```

每个 `move` 都从上一步结束的位置接续，相机在动手前和放下后就地读标记。目标被遮挡时只高位侧让再试；开场吸盘位置未知且遮挡时才可能使用 `park_mm`。普通移动吸起卡片经过途经点，低位平推用 `method: "push"`，从推耳接触处沿直线推到目标。反复无法定位或落点超过容差会报告对应步骤并中止。详见[场务与平推参数](docs/修雷德的最后一串团子.md)。

## 从照片读出双方血量

可以用现成的合成摆台图测试完整的印品识别流程。其图像由本剧 PDF 中的棋盘和纸卡排成。下面的命令应读出艾露猫 2/2、黑龙 3/3，打印上场后换用实拍照片和实测标定文件即可：

```sh
.venv/bin/python -m armischestra score --project examples/schrade.armischestra.json --calibration examples/score.synthetic.json --image examples/score.synthetic.png
```

## 只有照片也可以测试定位

[打印页](examples/markers.svg)包含艾露猫（ID 1）和黑龙（ID 2）的 ArUco 标记。按 100% 打印，黑框为 24 mm，沿虚线剪下保留白边。将标记贴在画的正面。如果吸盘不能吸在标记中心，就量中心到吸取点的偏移，填进该角色的 `pickup_offset_mm`。将印刷标记按打印页方向摆正时，向右、向上为正。角色在棋盘上转向后，程序会随标记旋转这个偏移。

没有图片时，先用附带的角点记录走一遍定位，结果为艾露猫 (50, 75) mm：

```sh
python3 -m armischestra locate 艾露猫 --calibration examples/camera.synthetic.json --markers examples/markers.synthetic.json
```

当前工作区的 `.venv` 已安装 OpenCV。在新环境中可用以下命令安装：

```sh
python3 -m venv .venv
.venv/bin/python -m pip install 'opencv-contrib-python-headless>=4.7,<5'
```

仓库附有一张[合成棋盘照片](examples/stage.synthetic.png)。可以用它跑完整的图像识别流程；黑龙的吸取点应为 (250, 150) mm。

```sh
.venv/bin/python -m armischestra locate 黑龙 --calibration examples/camera.synthetic.json --image examples/stage.synthetic.png
```

测试手机照片时，复制 [硬件模板](examples/hardware.template.json) 为 `hardware.local.json`，此时只需填写 `camera`。保持镜头、分辨率和支架固定，在与纸片表面同高的平面选取四个分散的点，沿四边依次记录像素坐标 `corners_px`，以相同顺序记录棋盘毫米坐标 `corners_mm`。选好对应点后，运行：

```sh
.venv/bin/python -m armischestra locate 艾露猫 --calibration hardware.local.json --image stage.jpg
```

## 接入机械臂

1. 按实物更新舞台尺寸、格距和 `park_mm`。停臂后镜头应能看见各角色；整段路线都应在机械臂可达范围内。
2. 在 `arm.pairs` 填至少三组不共线的对应点。用吸盘中心对准棋盘上的已知点，分别记录棋盘毫米坐标 `board_mm` 与机械臂毫米坐标 `arm_mm`。另选点检查换算误差。
3. 填 `high_z_mm`（能越过场景的运输高度）、`low_z_mm`（吸盘轻贴卡片时的高度）、`grip_seconds` 和 `release_seconds`。两档 Z 都沿用机械臂自己的坐标方向。所有卡片共用接触高度。若释放需要吹气，填入实测的 `blow_seconds`，零表示直接释放。
4. 将设备驱动接入下列 Python 入口。所有运动回调应在**实际到位**后返回，首次升高依赖当前吸盘的实际 XY。读帧回调应取得停臂后的新图，沿用标定时的视角和分辨率。

```python
from armischestra.hardware import run_hardware
from armischestra.show import load_json, load_show, load_stage

stage = load_stage("examples/stage.json")
show = load_show("examples/show.json", stage)
# read_xy、move_xyz、set_pump、read_frame 由设备端提供
run_hardware(
    stage, show, load_json("hardware.local.json"),
    read_xy=read_xy,        # () -> armischestra.motion.Point，机械臂坐标系的毫米位置
    move_xyz=move_xyz,      # (x_mm, y_mm, z_mm) -> 同步完成直线运动
    set_pump=set_pump,      # 接受 suck / release / blow
    read_frame=read_frame,  # () -> OpenCV 图像
    cue=print,
)
```

底层还可单独使用 `Motion.park(Point(x, y))` 高位移到棋盘上的一点，或 `Motion.carry(source, target, via=...)` 按已知吸取点搬运。实机入口与离线排练共用同一套搬运和剧本逻辑。

运行全部测试：

```sh
python3 -m unittest discover -s tests -v
```

未安装 OpenCV 时，合成图像识别测试会跳过；安装后用虚拟环境的 Python 执行同一条测试命令即可。
