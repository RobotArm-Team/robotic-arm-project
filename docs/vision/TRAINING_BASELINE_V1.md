# YOLOv8 彩色方块阶段性基线训练报告

## 结论

2026-11-13 已使用课程现有 206 张人工复核图片完成 YOLOv8n 阶段性基线训练。最佳模型在独立测试集上的 `mAP50=0.9950`、`mAP50-95=0.9700`，可用于继续开发推理接口和验证项目流水线。

该结果不是最终验收结果：现有数据仍未满足每类至少 300 张、总计至少 1200 张的需求，而且训练、验证、测试图片均来自同一课程拍摄环境。补采条件恢复后必须扩充数据并重新训练。

## 数据与划分

- 来源：`E:\RobotArmData\prelabel-color-faces-206\images` 中已由 B 全量复核的 LabelMe 标注。
- 总量：206 张图片，469 个大面积实色面框。
- 类别：`0=recyclable`、`1=hazardous`、`2=kitchen`、`3=other`。
- 划分方法：用感知哈希距离与缩略图平均绝对差建立近似图片组，再以固定种子 `20261113` 搜索组级 7:2:1 划分；同一相似组不会跨集合。
- 相似组：160 组，最大组 9 张。

| 集合 | 图片数 | 可回收框 | 有害框 | 厨余框 | 其他框 |
| --- | ---: | ---: | ---: | ---: | ---: |
| 训练 | 145 | 80 | 89 | 77 | 80 |
| 验证 | 40 | 24 | 24 | 24 | 22 |
| 测试 | 21 | 12 | 14 | 12 | 11 |

本地生成数据位于 `data/processed/block-baseline-v1/`，属于 Git 忽略的运行数据。`summary.json` 和 `split_manifest.csv` 记录了划分结果。

## 训练配置

| 项目 | 值 |
| --- | --- |
| 模型 | YOLOv8n，使用官方预训练权重 |
| 输入尺寸 | 640×640 |
| Batch | 16 |
| 最大轮次 | 100 |
| 早停耐心 | 20 |
| 实际轮次 | 71 |
| 最佳轮次 | 51 |
| 随机种子 | 20261113 |
| GPU | NVIDIA GeForce RTX 4060 Laptop GPU 8GB |
| Python | 3.10.20 |
| PyTorch | 2.6.0+cu124 |
| Ultralytics | 8.4.211 |

最佳轮次的验证集指标为 `Precision=0.9964`、`Recall=1.0000`、`mAP50=0.9950`、`mAP50-95=0.9789`。

## 独立测试集结果

| 指标 | 结果 |
| --- | ---: |
| Precision | 0.9951 |
| Recall | 1.0000 |
| mAP50 | 0.9950 |
| mAP50-95 | 0.9700 |

| 类别 | mAP50-95 |
| --- | ---: |
| recyclable | 0.9843 |
| hazardous | 0.9524 |
| kitchen | 0.9598 |
| other | 0.9835 |

测试时每张图片平均耗时：预处理 4.1 ms、GPU 推理 28.0 ms、后处理 2.2 ms。混淆矩阵中四个真实类别均落在正确对角线；仍存在少量背景候选框，因此 Precision 未达到 1.0。

## 交付物

- 最佳权重（本地）：`models/block-baseline-v1-best.pt`
- 权重 SHA-256：`14318D72DA09C8416F66A6557E9062DE0933835330827185BE1F97E85E74B2C8`
- 完整训练输出（本地）：`artifacts/training/baseline-v1/`
- 测试输出（本地）：`artifacts/training/baseline-v1-test/`
- 训练清单：`artifacts/training/baseline-v1/run_manifest.json`
- 数据准备脚本：`tools/prepare_yolo_dataset.py`
- 训练与测试脚本：`tools/train_yolov8_baseline.py`

仓库通过 `.gitignore` 排除 `.pt` 权重、处理后数据和训练图表。需要组内分发权重时，应上传到 GitHub Release 或课程允许的文件存储，并核对上述 SHA-256，不直接提交到 Git 历史。

## 复现命令

安装训练依赖后，在仓库根目录执行：

```powershell
.\.venv\Scripts\python.exe tools\prepare_yolo_dataset.py `
  "E:\RobotArmData\prelabel-color-faces-206\images" `
  data\processed\block-baseline-v1

.\.venv\Scripts\python.exe tools\train_yolov8_baseline.py `
  --data data\processed\block-baseline-v1\data.yaml `
  --model models\yolov8n.pt `
  --project artifacts\training `
  --name baseline-v1 `
  --epochs 100 --patience 20 --imgsz 640 --batch 16 --workers 4 --device 0
```

## 已知限制与后续

1. 测试集只有 21 张图片、49 个目标，高指标的置信区间有限。
2. 虽已进行相似组隔离，所有图片仍来自同一课程场景，不能证明对新相机、光照、背景和遮挡的泛化能力。
3. 当前模型识别的是蓝、红、绿、黄大面积实色面，不代表能够识别任意图文面或真实垃圾。
4. 补采恢复后按缺口扩充四类数据，重新冻结测试集、训练正式模型并在 200DK 上测量端到端时延。
