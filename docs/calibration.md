# HSV 颜色阈值校准

## 为什么需要校准

HSV 颜色追踪的效果高度依赖光照条件、摄像头白平衡和目标物体本身的颜色特性。同一颜色在不同环境下可能需要不同的 HSV 阈值范围。

本项目默认提供了 red / blue / green / yellow 四种颜色预置，但这些值可能需要根据你的实际环境微调。

## 校准流程

### 1. 打开摄像头预览

```bash
python main.py --mode mock --no-display --log-level DEBUG
```

或将 `--no-display` 去掉以查看实时画面（需要桌面环境）。

### 2. 使用 OpenCV trackbar 辅助校准

可以编写临时脚本或使用 OpenCV 的 `cv2.createTrackbar()` 动态调节 HSV 阈值。基本思路：

```python
import cv2
import numpy as np

cv2.namedWindow("Calibration")

def nothing(x):
    pass

cv2.createTrackbar("H Low", "Calibration", 0, 180, nothing)
cv2.createTrackbar("H High", "Calibration", 180, 180, nothing)
cv2.createTrackbar("S Low", "Calibration", 0, 255, nothing)
cv2.createTrackbar("S High", "Calibration", 255, 255, nothing)
cv2.createTrackbar("V Low", "Calibration", 0, 255, nothing)
cv2.createTrackbar("V High", "Calibration", 255, 255, nothing)

cap = cv2.VideoCapture(0)

while True:
    ret, frame = cap.read()
    if not ret:
        break

    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

    h_low = cv2.getTrackbarPos("H Low", "Calibration")
    h_high = cv2.getTrackbarPos("H High", "Calibration")
    s_low = cv2.getTrackbarPos("S Low", "Calibration")
    s_high = cv2.getTrackbarPos("S High", "Calibration")
    v_low = cv2.getTrackbarPos("V Low", "Calibration")
    v_high = cv2.getTrackbarPos("V High", "Calibration")

    lower = np.array([h_low, s_low, v_low])
    upper = np.array([h_high, s_high, v_high])

    mask = cv2.inRange(hsv, lower, upper)
    result = cv2.bitwise_and(frame, frame, mask=mask)

    cv2.imshow("Calibration", np.hstack([frame, result]))

    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()
```

### 3. 将校准结果写入 config.py

调节到满意的 mask 效果后，记录当前的 lower 和 upper 值，更新 `config.py` 中的 `COLOR_PRESETS`：

```python
COLOR_PRESETS = {
    "red": {
        "lower1": [0, 100, 100],   # 修改为你的校准值
        "upper1": [10, 255, 255],
        "lower2": [160, 100, 100], # 红色需要两段 (跨越 0 度)
        "upper2": [180, 255, 255],
    },
    "blue": {
        "lower1": [100, 100, 50],  # 修改为你的校准值
        "upper1": [130, 255, 255],
        "lower2": None,
        "upper2": None,
    },
    # ... 其他颜色同理
}
```

## 光照影响

- **环境光变化**: 室内外、白天晚上的 HSV 阈值可能不同。
- **摄像头白平衡**: PiCamera2 有自动白平衡，前几帧可能偏色。
- **目标材质**: 高饱和度物体比低饱和度物体更容易检测。

## 推荐测试顺序

1. 使用高饱和度红色物体（如红色球、红色纸板）。
2. 在目标使用环境的光照条件下进行校准。
3. 先调整 Hue 范围（确定颜色种类）。
4. 再降低 Saturation 下限（提高对颜色纯度的包容度）。
5. 最后降低 Value 下限（提高对暗光条件的包容度）。

## 如果检测不到目标

检查以下参数：

| 参数 | 位置 | 说明 |
|------|------|------|
| Hue 范围 | `COLOR_TARGET_LOWER/UPPER[0]` | 颜色种类，范围 0-180 |
| Saturation 下限 | `COLOR_TARGET_LOWER[1]` | 颜色纯度，过低容易误检 |
| Value 下限 | `COLOR_TARGET_LOWER[2]` | 亮度，过低容易噪声 |
| min area | `MIN_CONTOUR_AREA` | 过滤小面积噪声，过大可能漏检 |
| camera exposure | 摄像头自动曝光 | 过暗或过曝都会影响 HSV |
| lighting condition | 环境光照 | 强光或阴影会影响颜色识别 |
