# Troubleshooting

## Camera cannot open

检查：

- 摄像头排线是否连接正确（蓝色标签朝向网口方向）
- Raspberry Pi 是否识别摄像头: `libcamera-hello --list-cameras`
- 是否有其他进程占用摄像头: `ps aux | grep libcamera`
- 是否在 headless 环境误用了 display 模式 (使用 `--no-display`)
- CSI 接口是否在 `/boot/firmware/config.txt` 中启用: `camera_auto_detect=1`

## Car does not move

检查：

- 是否运行在 mock 模式 (`--mode mock` 不会驱动真实电机)
- 是否缺少 Freenove 硬件库 (运行 `--mode hardware` 查看具体错误)
- 电池电压是否足够 (建议 ≥7V)
- 电机线连接是否正确
- duty 是否太低 (建议至少 800，首次测试用 `--duty 1200`)
- hardware 模式是否初始化成功 (查看日志中的 ✓/✗ 标记)

## Color target not detected

检查：

- 目标颜色是否在 HSV 范围内 (参考 `docs/calibration.md`)
- 光照是否过暗或过曝
- saturation / value 下限是否过高
- min area 是否过大 (`MIN_CONTOUR_AREA` in config.py)
- 摄像头画面是否正常 (先确认摄像头能打开)
- 尝试用 `--color` 切换颜色预设

## Car moves in wrong direction

检查：

- 电机接线方向 (可能需要交换某路电机的正负极)
- motor mapping: `_set_motor_raw()` 中的四路 duty 对应关系
- left / right duty 符号是否反了
- navigation steering sign 是否反了 (PID 输出方向)

## Ultrasonic stop does not work

检查：

- TRIG (BCM 23) / ECHO (BCM 24) 接线是否正确
- 读数是否稳定 (按 `i` 键查看实时距离)
- `STOP_DISTANCE_CM` 是否合理 (默认 10 cm)
- 是否在 navigation 中优先处理了 stop condition (超声波检查在状态机最前面)

## Program exits but car keeps moving

检查：

- `finally` 中是否调用了 `motor.stop()`
- `KeyboardInterrupt` 是否被正确处理
- `cleanup` 是否执行
- 硬件库 `stop` 方法是否真的停止所有电机 (可能需要额外调用硬件级停止)

## Import errors on PC

如果你在普通 PC 上遇到导入错误：

- 运行 `--mode mock` 跳过硬件库需求
- 确保安装了跨平台依赖: `pip install -r requirements.txt`
- 不要安装 `requirements-rpi.txt` (那是树莓派专属依赖)
- 如果 `picamera2` 导入失败，确认使用了 `--mode mock`
