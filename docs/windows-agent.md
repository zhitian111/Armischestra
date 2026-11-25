# Windows agent 交接提示词

请接手当前目录的 Armischestra 机械臂纸片剧场，协助我从 Windows 完成离线验收、手机视觉标定、MG400 实机预检和演出。我会负责摆台、固定手机、用 DobotStudio 手操测量 Z，并在设备旁配合。请直接做当前条件允许的工作，缺少现场读数时告诉我具体去哪里读。在我明确确认现场可以运动前，只执行离线或相机侧操作；自动标定和带 --preflight-only 的命令都会让实机移动。

## 项目状态

默认工程在 examples/schrade.armischestra.json，是《修雷德的最后一串团子 · 七合交锋》。380 × 296 mm 棋盘、12 张纸卡，模拟时长约 3 分 40 秒。前端编辑和打印用本地 Python 服务，演出执行读取前端导出的 JSON。已有连续走位、实体血条、自动 XY 配准、人工高低 Z、运动学预检。请先读 README.md 和 docs/dobot.md。实机精度和气路仍待现场验证。

## 先完成离线验收

在项目根目录用 PowerShell 工作。使用带 Tk 的 64 位 Python 3.10 或以上版本。下面以 3.12 为例，可按本机可用版本选择。虚拟环境只需创建一次，直接调用其 Python 就无需修改 PowerShell 执行策略。

```powershell
py -3.12 -m venv .venv
$python = ".\.venv\Scripts\python.exe"
& $python -m pip install numpy "opencv-contrib-python-headless>=4.7,<5"
& $python -c "import tkinter, numpy, cv2; print(cv2.__version__, cv2.aruco.ArucoDetector)"
& $python -m unittest discover -s tests -v
& $python -m armischestra rehearse --project examples/schrade.armischestra.json --replay "$env:TEMP\armischestra-rehearsal.html"
& $python -m armischestra editor --port 8765
```

服务在 http://127.0.0.1:8765/ 。把它留在独立终端。若已装近期 Node.js，可用 node --test tests/test_health.mjs tests/test_print.mjs 运行前端逻辑测试。已有的 rehearsal.html 双击即可预览。打印时分别选「棋盘与全部纸片」和「部署与标定 → 打印标定码」，按 100% 核对校尺。

## 再接手机和机械臂

1. 在新 PowerShell 终端重新设置下面的变量。若我提供了新版导出剧本，把 $show 改为那份文件。保留已有本地配置。
   
   ```powershell
   $python = ".\.venv\Scripts\python.exe"
   $show = "examples/schrade.armischestra.json"
   if (!(Test-Path dobot.local.json)) { Copy-Item examples/dobot.template.json dobot.local.json }
   if (!(Test-Path hardware.auto.local.json)) { Copy-Item examples/hardware.auto.template.json hardware.auto.local.json }
   ```

2. 手机通过局域网直接提供 RTSP/HTTP 视频流。将实际地址和画面分辨率填入 dobot.local.json。45、46、47、48 依次是左下、右下、右上、左上外侧的棋盘码，49 在吸盘轴线上方。首次建立镜头档案时按程序提示从不同角度取景；机械臂可以尚未连接。正式演出时固定手机。两场之间只挪手机可复用档案，改变镜头、焦距、分辨率、方向或裁剪后重新建立。

   ```powershell
   & $python -m armischestra lens --project $show --output lens.local.json --device dobot.local.json
   ```

3. 厂商 SDK 使用以下固定提交，另存到项目旁边。下载 Git SDK 和安装依赖需要联网。DobotStudio 客户端需使用现场设备对应的厂家版本。核对 MG400 控制器版本、TCP/IP 控制模式、用户及工具坐标系、气阀接线与极性，确认电脑可达控制器的 29999、30003 端口。

   ```powershell
   $sdk = "..\TCP-IP-4Axis-Python"
   if (!(Test-Path $sdk)) { git clone https://github.com/Dobot-Arm/TCP-IP-4Axis-Python.git $sdk }
   git -C $sdk checkout b5f95647cfc44a60f92babf5a464d38dd1e4f72c
   ```

4. 由我手操测量高低 Z，测量低位时 49 号码面距棋盘码面的高度，确认吸放等待时间和沿用户坐标 +X、+Y 的空旷采样边长。填写 hardware.auto.local.json。自动模式不需要手点 XY。样例有一次低位推团子，只有现场验证推耳和低位侧推后才启用 contact_push_enabled；否则用编辑器把这一步改成吸移并导出，用导出文件更新 $show。

5. 在现场确认可运动、吸盘空载且已经处于指定高位、纸卡摆好后，先执行以下命令。预检会实走高位采样方形，再查询剧本路线的逆解。现场仍需检查气管、支架和道具间隙。记录失败步骤或控制器应答，处理后再继续。预检通过并确认可以开演后，去掉末尾的 --preflight-only 执行同一命令。每个新 PowerShell 会话都需要重设 $python、$show 和 $sdk。

   ```powershell
   & $python -m armischestra perform $show --device dobot.local.json --calibration hardware.auto.local.json --lens lens.local.json --sdk-dir $sdk --preflight-only
   ```

交付时请说明实际完成到了哪一步，分别记录模拟结果、相机实测与实机结果。把现场配置保存在本机的 *.local.json 中。
