"""
image_recognition.py - 图像识别与目标检测模块

功能:
  1. 颜色追踪 (HSV 色彩空间) - 快速追踪特定颜色物体
  2. DNN 目标检测 (OpenCV DNN / TensorFlow Lite) - 深度学习识别

检测结果统一封装为 TargetInfo。
"""

import cv2
import numpy as np
import logging
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class TargetInfo:
    """目标检测结果"""
    found: bool = False
    center_x: int = 0
    center_y: int = 0
    width: int = 0
    height: int = 0
    area: float = 0.0
    distance_estimate: float = -1.0   # cm, -1 表示未知
    label: str = ""
    confidence: float = 0.0
    contour: Optional[np.ndarray] = None

    def offset_from_center(self, frame_center_x: int) -> int:
        """水平偏移量 (px), 正值 = 目标在右侧"""
        return self.center_x - frame_center_x


class ImageRecognition:
    """图像识别引擎"""

    def __init__(self, config):
        self.config = config
        self.frame_center_x = config.FRAME_CENTER_X
        self.frame_center_y = config.FRAME_CENTER_Y

        # HSV 阈值
        self.color_lower = np.array(config.COLOR_TARGET_LOWER)
        self.color_upper = np.array(config.COLOR_TARGET_UPPER)
        self.color_lower2 = (np.array(config.COLOR_TARGET_LOWER2)
                             if config.COLOR_TARGET_LOWER2 else None)
        self.color_upper2 = (np.array(config.COLOR_TARGET_UPPER2)
                             if config.COLOR_TARGET_UPPER2 else None)

        # 预处理
        self.blur_kernel = config.GAUSSIAN_BLUR_KERNEL
        self.morph_kernel = cv2.getStructuringElement(
            cv2.MORPH_ELLIPSE, config.MORPH_KERNEL_SIZE
        )
        self.min_contour_area = config.MIN_CONTOUR_AREA

        # DNN
        self.dnn_net = None
        if config.USE_DNN_MODEL:
            self._load_dnn_model()

    def _load_dnn_model(self):
        try:
            self.dnn_net = cv2.dnn_DetectionModel(
                self.config.DNN_WEIGHTS_PATH,
                self.config.DNN_MODEL_PATH,
            )
            self.dnn_net.setInputSize(320, 320)
            self.dnn_net.setInputScale(1.0 / 127.5)
            self.dnn_net.setInputMean((127.5, 127.5, 127.5))
            self.dnn_net.setInputSwapRB(True)
            logger.info("DNN 模型已加载")
        except Exception as e:
            logger.error("DNN 模型加载失败: %s", e)
            self.dnn_net = None

    def detect(self, frame: np.ndarray) -> TargetInfo:
        if self.dnn_net is not None:
            return self._detect_dnn(frame)
        return self._detect_color(frame)

    def _detect_color(self, frame: np.ndarray) -> TargetInfo:
        """HSV 颜色追踪"""
        blurred = cv2.GaussianBlur(frame, self.blur_kernel, 0)
        hsv = cv2.cvtColor(blurred, cv2.COLOR_BGR2HSV)

        if self.color_lower2 is not None and self.color_upper2 is not None:
            mask1 = cv2.inRange(hsv, self.color_lower, self.color_upper)
            mask2 = cv2.inRange(hsv, self.color_lower2, self.color_upper2)
            mask = cv2.bitwise_or(mask1, mask2)
        else:
            mask = cv2.inRange(hsv, self.color_lower, self.color_upper)

        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, self.morph_kernel)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, self.morph_kernel)

        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL,
                                       cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            return TargetInfo(found=False, label="color_target")

        best = max(contours, key=cv2.contourArea)
        if cv2.contourArea(best) < self.min_contour_area:
            return TargetInfo(found=False, label="color_target")

        x, y, w, h = cv2.boundingRect(best)
        cx, cy = x + w // 2, y + h // 2
        area = cv2.contourArea(best)
        distance = 5000.0 / (np.sqrt(area) + 1e-6) if area > 0 else -1

        return TargetInfo(
            found=True, center_x=cx, center_y=cy,
            width=w, height=h, area=area,
            distance_estimate=distance,
            label="color_target", contour=best,
        )

    def _detect_dnn(self, frame: np.ndarray) -> TargetInfo:
        """OpenCV DNN 目标检测"""
        class_ids, confidences, boxes = self.dnn_net.detect(
            frame, confThreshold=self.config.DNN_CONFIDENCE_THRESHOLD
        )
        if len(class_ids) == 0:
            return TargetInfo(found=False)

        best_conf, best_box, best_class = 0, None, None
        for cls, conf, box in zip(class_ids, confidences, boxes):
            if cls in self.config.TARGET_CLASS_IDS and conf > best_conf:
                best_conf, best_box, best_class = conf, box, cls

        if best_box is None:
            return TargetInfo(found=False)

        x, y, w, h = best_box
        coco_names = {1: "person", 2: "bicycle", 3: "car", 4: "motorcycle"}

        return TargetInfo(
            found=True, center_x=x + w // 2, center_y=y + h // 2,
            width=w, height=h, area=w * h,
            label=coco_names.get(best_class, f"class_{best_class}"),
            confidence=best_conf,
        )

    def draw_debug(self, frame: np.ndarray, target: TargetInfo) -> np.ndarray:
        """绘制调试叠加层"""
        display = frame.copy()

        # 画面中心十字
        cv2.drawMarker(display, (self.frame_center_x, self.frame_center_y),
                       (255, 255, 255), cv2.MARKER_CROSS, 20, 2)

        if not target.found:
            cv2.putText(display, "No Target", (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
            return display

        x = target.center_x - target.width // 2
        y = target.center_y - target.height // 2
        cv2.rectangle(display, (x, y), (x + target.width, y + target.height),
                      (0, 255, 0), 2)
        cv2.circle(display, (target.center_x, target.center_y), 5,
                   (0, 0, 255), -1)
        cv2.line(display,
                 (self.frame_center_x, self.frame_center_y),
                 (target.center_x, target.center_y), (255, 255, 0), 2)

        offset = target.offset_from_center(self.frame_center_x)
        for i, line in enumerate([
            f"Target: {target.label}  Offset: {offset:+d}px",
            f"Area: {target.area:.0f}  Dist: {target.distance_estimate:.1f}cm",
        ]):
            cv2.putText(display, line, (10, 30 + i * 25),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
        return display
