# MG400 手机视觉自动标定可行性

## 棋盘、机械臂与演出范围

越疆四轴 Python SDK 支持控制器 V1.5.6.0 及以上版本的 MG400。程序可以用 MovL 移到采样位置，用 Sync 等待运动完成，再用 GetPose 读取工具坐标 X、Y、Z、R。这些接口足以让电脑自动采点。实际部署需要从已知安全高位开始，在事先确认空旷的范围内采样。[越疆 SDK 适用条件](https://github.com/Dobot-Arm/TCP-IP-4Axis-Python/blob/b5f95647cfc44a60f92babf5a464d38dd1e4f72c/README.md) · [越疆四轴 TCP/IP 协议](https://github.com/Dobot-Arm/TCP-IP-Protocol-4AXis)

项目可在棋盘四角印四个唯一 ID 的标记，在吸盘轴线上方刚性安装第五个标记。手机固定、镜头参数已标定、标记尺寸及码面到吸盘底面的距离已知时，程序可在同一帧中分别估计棋盘和末端标记的空间位姿。机械臂自动走几个分散且不共线的高位采样点，程序将视觉结果与控制器坐标配对，在独立位置验证误差。此设计允许手机斜拍，部署精度需要用实际镜头、印品和机械臂测量。[OpenCV 标记位姿估计](https://docs.opencv.org/3.4.12/d5/dae/tutorial_aruco_detection.html)

控制器的 InverseSolution 可求给定 X、Y、Z、R 和用户、工具坐标系的关节解。预检可覆盖剧本起点、途经点、终点及高低位，并沿运动段采样检查。单点有解不能证明整段运动无碰撞，现场还要考虑气管、手机支架和道具。项目已接入自动采点和运动学采样预检，仍需实机验证。[越疆四轴 TCP/IP 协议](https://github.com/Dobot-Arm/TCP-IP-Protocol-4AXis) · [项目现有接入说明](dobot.md)

## 接触高度和吸取反馈

**只有取得吸盘处的真空反馈，程序才能用吸盘密封作为探测事件。** 越疆将 MG400 真空吸盘列为气动配件，Mini Air Pump Box 的规格列出了手动控制、I/O 控制以及 −70 至 +110 kPa 的气压范围。公开规格没有列出真空到位输出或可读取的压力值。机器人开启抽气的数字输出（DO）只记录了控制命令，吸盘悬空时这个输出也可以保持开启。[越疆吸盘套件规格](https://de.dobot-robots.com/products/accessories/vacuum-suction-cup-kit.html) · [越疆 Mini Air Pump Box 规格](https://www.dobot-robots.com/ecosystem/accessories/692.html)

**现场可从吸盘气路查起。** 若真空发生器或电动真空工具有独立的真空到位信号，先按具体型号核对端子、输出类型及有效电平。若现场只有泵的控制线，可在靠近吸盘的气路加装真空开关，将兼容的开关输出接入空闲的底座数字输入（DI）。MG400 的底座有 16 路 DI，硬件手册给出了开关触点和 PNP 输出的接线示例。实际输入编号取决于接线。[越疆《MG400 User Guide》V1.5，第 6.1.2 节，图 6.3–6.5](https://dobot.com.mx/assets/download/mg400/user%20guide/Dobot%20MG400%20Hardware%20User%20Guide.pdf)

**用实物验证信号后再用于标定。** 让机械臂静止，保持抽气，依次让吸盘悬空、与平整样板密封、再解除密封。在 I/O 监视器中确认同一路 DI 依次显示未到位、到位、未到位。标定时记录的是吸盘达到密封阈值的位置，杯唇压缩、台面透气性和输入延迟都会影响高度。可用已知高度的样板测量偏差和重复性。只有泵控制线时，应使用示教台面高度，或先补充独立传感器。

**区分底座与末端输入。** 项目固定的官方 Python SDK 版本中，`DI(1)` 会发送完整的 `DI(1)`，而 `ToolDI(1)` 也会发送同一条底座查询命令。若真空开关接在末端，应按四轴协议修正末端查询，并用实际开关变化验证读到的通道；接在底座则使用对应的 `DI` 通道。[固定版本 SDK 第 485–491 行](https://github.com/Dobot-Arm/TCP-IP-4Axis-Python/blob/b5f95647cfc44a60f92babf5a464d38dd1e4f72c/dobot_api.py#L485-L491) · [越疆四轴 TCP/IP 协议](https://github.com/Dobot-Arm/TCP-IP-Protocol-4AXis)
