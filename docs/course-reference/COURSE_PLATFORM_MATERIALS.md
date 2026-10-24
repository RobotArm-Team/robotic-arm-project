# 课程平台资料盘点与导入

盘点日期：2026-10-24。来源：[课程“资料”页](http://10.126.59.136:30080/course/course/1f9e240953f345e09d3df3778352a3fe/ShareFilePage?userRole=)，目录“基于计算机视觉的智能机械臂应用实践”。访问需课程账号；本文不保存登录凭据或会话票据。

## 已取回并整理

组长 B 于 2026-10-24 回复，已获得老师公开发布课程资料的许可。精选文件现放在仓库的 [`materials/`](materials/) 下；此前用于筛选的 `local/course-materials/` 是被 Git 忽略的本地副本。公开发布许可**不等于**课程文件可按本项目 Apache-2.0 许可证再许可；课程 ROS2 包的 `package.xml` 仍写着 `TODO: License declaration`。使用和进一步分发时保留课程来源，许可范围如有疑问再向老师确认。

| 课程文件 | 本地保留内容 | 用途与边界 |
| --- | --- | --- |
| `任务3_相机校准与数据采集.zip`（13.313 MB） | [`camera-calibration/`](materials/camera-calibration/) 下 2 个 Jupyter notebook、3 个配置样例 | 供 B/C 对照相机标定、640×480 透视变换和图片采集。notebook 会打开摄像头并直接驱动机械臂，**不可在真实设备上直接顺序运行**；样例 `XYT_config.txt` 和 `dp.bin` 不是本机标定结果。 |
| `images.zip`（13.27 MB） | [`block-sample-images.zip`](materials/block-sample-images.zip)，206 张 JPG | 仅用于理解课程采集画面或离线试验。抽查图像是带有图案的积木道具，压缩包没有标注文件；不能计入本项目“四类垃圾、每类至少 300 张”的正式数据集。任务 3 包内的 206 张图片与该包逐张 SHA-256 相同，故不重复提取。 |
| `任务2_ROS2服务与机械臂仿真.zip`（42.066 MB） | [`ros2-dofbot/src/`](materials/ros2-dofbot/src/) 下 17 个源文件，包括 ROS2 服务定义、C++ 服务、launch、URDF、RViz 配置、6 个 STL 网格、头文件和 `.so` | 供 C 研究 ROS2/机械臂仿真。未复制原压缩包中的 `build/`、`install/`、`log/` 等生成物。源文件是课程示例，不是项目已验证实现。 |

本地提取后的文件共 23 个，约 76.6 MB。原压缩包的 SHA-256（用于核对来源，不代表 HTTP 下载具备防篡改保证）：

导入核对：23 个文件与筛选副本逐个 SHA-256 一致；206 张 JPG 全部可解码，未发现 GPS EXIF 标签；2 个 notebook 可解析为 JSON。未执行任何课程代码或二进制文件。

| 文件 | SHA-256 |
| --- | --- |
| `images.zip` | `4614AB6FE3277FD212EF6DFCC1981FCA6F5BA7BDC6416AAE9A9A2FB06F81B40E` |
| `任务3_相机校准与数据采集.zip` | `F425492D754976E895D2C1C22527CF2BE83C2BA255E11EB253E51929CAA94EE4` |
| `任务2_ROS2服务与机械臂仿真.zip` | `F82AC00B875CF816B44CA28E00D257F28C1B9222965285DC21C1EB940F96D3D0` |

## 已核对但未重复保存

| 课程文件 | 处理原因 |
| --- | --- |
| `三维结构文件.zip`（20.416 MB） | 只有 `base_link.STL`、`link1.STL` 至 `link5.STL` 六个网格；与任务 2 的 `meshes/` 对应文件逐个 SHA-256 相同。 |
| `libdofbot_kinemarics.so`、`dofbot_kinemarics.h` | 任务 2 的 `src/dofbot_moveit/lib/` 和 `include/` 已包含对应文件，不再单独下载。`.so` 是平台相关二进制，未经架构、来源与安全验证，不得当作本项目构建产物直接部署。 |
| `Anaconda3安装包.zip`（617.786 MB）、`MobaXterm_Portable_v22.2.zip`（28.262 MB） | 通用工具安装包，团队成员应从可信官方渠道获取，不占用 Git 历史。 |
| `模型适配迁移工具安装包.zip`（316.805 MB） | 对应课程 Ascend/YOLOv5s-OM 示例路径；本项目当前计划 YOLOv8。若目标设备实测要求改走课程工具，再单独核对版本、来源与部署方案。 |

## 使用前检查

- B：先固定四类垃圾标签和数据来源，再把课程 notebook 的采集、透视处理逻辑迁移到本项目的数据流程；不要把道具照片当成项目验收样本。
- C：先审查 ROS2 示例的硬编码 `/home/HwHiAiUser/...` 路径、`CMakeLists.txt` 中未定义的 `library_name`、服务接口及舵机安全边界；不要直接接入真实机械臂。课程示例的许可声明也需向老师确认。
- 当前公开仓库中此前已有 `course-code-2.docx` 及提取文本；这些也属于课程资料，不应自动视为 Apache-2.0 许可。

下一步：B/C 分别审查采集流程与 ROS2 接口，按项目安全边界改写和验证；正式 F1 数据集仍需重新采集、标注、划分并验证。
