# Freenove FNK0043B - 4WD 普通车轮 视觉导航系统

基于 **Raspberry Pi 5** + **Freenove FNK0043B** (4WD Standard Wheel Smart Car Kit) 的视觉导航系统。

摄像头实时采集图像 → 识别目标 (颜色追踪 / 深度学习) → 小车自动驶向目标位置。

> **共同作者**: Hwu & DeepSeek  
> **开发工具**: 本项目使用 [DeepSeek-TUI](https://github.com/deepseek-ai/deepseek-tui) 完成开发

## 硬件

| 组件 | 说明 |
|------|------|
| 主控 | Raspberry Pi 5 |
| 底盘 | Freenove FNK0043B (4WD 普通车轮) |
| 驱动板 | Freenove Smart Car Board (PCA9685 I2C 电机驱动) |
| 摄像头 | CSI 摄像头 (推荐) 或 USB 摄像头 |
| 舵机 | 2 × SG90 (云台 Pan/Tilt) |
| 超声波 | HC-SR04 |
| LED | 8 × WS2812B RGB (板载 SPI) |
| 蜂鸣器 | 有源蜂鸣器 (板载) |
| 可选 | 红外循迹模块、光敏电阻 (ADC) |

## 项目结构

```
raspberry_pi5_freenove_car/
├── main.py               # 主入口, 主循环 + CLI
├── config.py             # 全局配置 (PCA9685/舵机/HSV/PID 等)
├── camera.py             # 摄像头 (PiCamera2 CSI / USB)
├── image_recognition.py  # 图像识别 (HSV 颜色追踪 / DNN)
├── motor_control.py      # 电机 + 舵机 + LED + 超声波 + 蜂鸣器
├── navigation.py         # 导航引擎 (PID + 状态机 + 差速转向)
├── requirements.txt      # Python 依赖
├── README.md
├── models/               # DNN 模型文件 (可选)
└── logs/                 # 运行日志
```

**数据流**:
```
camera.py → image_recognition.py → navigation.py → motor_control.py
  (帧)         (TargetInfo)            (指令)        (PCA9685/GPIO)
```

## 前置安装

### 1. Freenove 官方库

此项目依赖 Freenove FNK0043 官方库。请在树莓派上先安装：

```bash
# 下载 Freenove 完整代码包
# 链接: https://freenove.com/tutorial → 搜索 FNK0043 → Download ZIP

# 解压并安装
cd ~/Freenove_4WD_Smart_Car_Kit_for_Raspberry_Pi/Code/
python3 setup.py

# 启用 I2C 和 SPI
sudo raspi-config
# Interface Options → I2C → Enable
# Interface Options → SPI → Enable
# 然后重启
```

### 2. 本项目依赖

```bash
cd raspberry_pi5_freenove_car
pip install -r requirements.txt
```

### 3. 摄像头 (Pi5)

编辑 `/boot/firmware/config.txt`:
```
camera_auto_detect=1
```

## 配置

编辑 `config.py` 修改关键参数：

- **电机速度**: `MOTOR_DUTY_BASE` (默认 2000, 范围 0-4096)
- **追踪颜色**: `COLOR_TARGET_LOWER/UPPER` HSV 阈值，或命令行 `--color`
- **PID 参数**: `PID_KP/KI/KD`
- **停车距离**: `STOP_DISTANCE_CM` (默认 10cm)

## 运行

```bash
# 追踪红色目标 (默认)
python main.py

# 追踪其他颜色
python main.py --color blue
python main.py --color green
python main.py --color yellow

# 自定义速度 (更慢/更稳)
python main.py --duty 1200

# 无头模式 (SSH, 不显示 GUI)
python main.py --no-display

# 组合使用
python main.py --color blue --duty 1500 --no-display
```

### 键盘快捷键

| 按键 | 功能 |
|------|------|
| `q` | 退出 |
| `r` | 重置导航 (重新搜索) |
| `s` | 紧急停车 |
| `f` | 手动前进/停止切换 |
| `w/a/d/x` | 前进 / 左转 / 右转 / 后退 (手动模式) |
| `1/2/3` | 舵机云台 左/中/右 |
| `i` | 打印超声波距离 |

## 导航状态机

```
SEARCH ──(发现目标)──▶ TRACK ──(目标居中)──▶ APPROACH ──(到达)──▶ STOP
   ▲                      │                      │
   └──(丢失 >2s)──────────┘                      │
                                       (超声波 < STOP_DISTANCE_CM)
                                                 │
                                                 ▼
                                               STOP
```

- **SEARCH**: 原地慢速旋转, LED 蓝色
- **TRACK**: PID 差速转向追踪, LED 黄色
- **APPROACH**: 慢速靠近, LED 绿色
- **STOP**: 停车 + 蜂鸣, LED 红色

## 运动控制

FNK0043B 普通车轮版采用差速转向:

- `move_forward/backward`: 前进/后退 (四轮同向)
- `turn_left/right`: 原地转向 (两侧反向)
- `steer(direction, inner, outer)`: 差速转向 (前进中微调, 内侧轮慢外侧轮快)

## 自定义目标

### 颜色追踪

修改 `config.py` → `COLOR_PRESETS` 字典, 或命令行 `--color`

### DNN 目标检测

1. 下载模型放入 `models/`
2. 修改 `config.py`:
```python
USE_DNN_MODEL = True
DNN_MODEL_PATH = "models/your_model.pbtxt"
DNN_WEIGHTS_PATH = "models/your_weights.pb"
TARGET_CLASS_IDS = [1]  # COCO 类别
```

## 故障排查

| 问题 | 可能原因 | 解决 |
|------|---------|------|
| 摄像头无法打开 | 未连接 / 配置错误 | `libcamera-hello` 测试 |
| 电机不转 | S1/S2 开关未按 / 电池亏电 | 检查电池 ≥7V |
| 方向反了 | 电机线序 | 在 `_set_motor_raw()` 中反转 duty 符号 |
| 转向震荡 | PID 过大 | 减小 `PID_KP`, 增大 `PID_KD` |
| LED 不亮 | SPI 未启用 | `sudo raspi-config` 启用 SPI |
| 超声波读数为 -1 | 接线错误 | 确认 TRIG→23, ECHO→24 |

## 开发

非树莓派环境开发调试: 项目所有模块均有 Mock 降级机制 — 未检测到 Freenove 库 / GPIO 时自动进入日志模式, 可在 PC 上运行和调试图像识别逻辑。

## License

MIT
