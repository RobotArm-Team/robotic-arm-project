# 视觉采集准备

本目录供 B 在 200DK 上补采彩色方块图片。采集程序只访问 USB 摄像头，不导入 `Arm_Lib`，也不发送舵机指令。相机标定仍按课程 `camera.ipynb` 在 C 配合下完成。

## 当前可离线完成的准备

1. 继续在 Model Adapter 中复核课程 206 张图片的实色面候选框。
2. 使用固定标签：`0=recyclable`、`1=hazardous`、`2=kitchen`、`3=other`。
3. 保留每批采集的会话目录和 `session.json`，后续按会话划分训练、验证、测试集。

## 连接 200DK 后

课程示例使用 200DK 的 eth1 地址 `192.168.137.100`。电脑有线网口应配置到同一网段，例如 `192.168.137.101/24`。实际连接成功后先执行只读检查：

```bash
cd /home/HwHiAiUser/RobotArm
python3 vision/check_200dk.py
python3 vision/check_200dk.py --probe-camera
```

第一条命令不打开摄像头；第二条仅读取一帧，不初始化机械臂。

采集程序使用 OpenCV 预览窗口。通过 MobaXterm 登录时保持右上角 X server 开启，并确认 `echo $DISPLAY` 有输出；否则预览窗口不会显示。

在课程相机标定完成并生成 `Camera_Cal/config/dp.bin` 后，按类别采集：

```bash
python3 vision/capture_blocks.py \
  --label recyclable \
  --session 20261113-s01 \
  --output /home/HwHiAiUser/RobotArm/data/raw/captures \
  --warp /home/HwHiAiUser/RobotArm/Camera_Cal/config/dp.bin
```

按空格或 `S` 保存当前图像，按 `Q` 或 `Esc` 退出。其他类别将 `--label` 改为 `hazardous`、`kitchen` 或 `other`。

程序把图片存入“会话/类别”目录，并连续编号，已有文件不会被覆盖。`session.json` 记录类别、相机编号、标定文件和保存数量。原始图片属于运行数据，应下载到本机备份，不提交到 Git；仓库 `.gitignore` 已忽略 `data/raw/`。

## 上传方式

连接恢复后，可在 MobaXterm 左侧 SFTP 面板将整个 `src/vision` 文件夹上传为：

```text
/home/HwHiAiUser/RobotArm/vision
```

上传后先运行 `check_200dk.py`。看到摄像头和依赖检查结果后，再决定是否开始标定或采集。

## 数据要求

标注框和采集目标以[彩色方块数据集标注规范](../../docs/vision/DATASET_ANNOTATION_GUIDE.md)为准。每次保存前改变方块的位置、角度或朝向，避免连续近重复帧。当前项目目标为四类各至少 300 张有效图片；先完成已有标注统计，再按差额补采。

