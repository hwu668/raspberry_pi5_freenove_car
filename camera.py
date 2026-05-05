"""
camera.py - 摄像头管理模块

支持:
  - Raspberry Pi 5 CSI 摄像头 (PiCamera2 / libcamera)
  - USB 摄像头 (OpenCV VideoCapture)

统一接口，上层模块无需关心底层实现。
"""

import logging
import time

import cv2
import numpy as np

logger = logging.getLogger(__name__)


class Camera:
    """摄像头抽象类，封装 PiCamera2 和 USB 摄像头"""

    def __init__(self, config):
        self.config = config
        self.cap = None
        self.picam2 = None
        self.use_picamera2 = config.CAMERA_USE_PICAMERA2
        self.width = config.CAMERA_WIDTH
        self.height = config.CAMERA_HEIGHT
        self.fps = config.CAMERA_FPS
        self.flip_h = config.CAMERA_FLIP_HORIZONTAL
        self.flip_v = config.CAMERA_FLIP_VERTICAL

    def start(self) -> bool:
        """初始化摄像头，失败返回 False"""
        if self.use_picamera2:
            return self._start_picamera2()
        return self._start_usb()

    def _start_picamera2(self) -> bool:
        """PiCamera2 (CSI 摄像头) 初始化"""
        try:
            from picamera2 import Picamera2

            self.picam2 = Picamera2()
            video_config = self.picam2.create_video_configuration(
                main={"size": (self.width, self.height), "format": "RGB888"},
                controls={"FrameRate": self.fps},
            )
            self.picam2.configure(video_config)
            self.picam2.start()
            time.sleep(1.0)  # 等待 AGC/AWB 稳定
            logger.info("PiCamera2 已启动: %dx%d @ %d FPS",
                        self.width, self.height, self.fps)
            return True
        except ImportError:
            logger.warning("picamera2 未安装, 回退到 USB 摄像头")
            self.use_picamera2 = False
            return self._start_usb()
        except Exception as e:
            logger.error("PiCamera2 初始化失败: %s", e, exc_info=True)
            return False

    def _start_usb(self) -> bool:
        """OpenCV USB 摄像头初始化"""
        self.cap = cv2.VideoCapture(self.config.CAMERA_INDEX)
        if not self.cap.isOpened():
            logger.error("无法打开 USB 摄像头 (索引 %d)", self.config.CAMERA_INDEX)
            return False

        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
        self.cap.set(cv2.CAP_PROP_FPS, self.fps)

        actual_w = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        actual_h = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        logger.info("USB 摄像头已启动: %dx%d @ %d FPS",
                    actual_w, actual_h, self.fps)
        return True

    def capture(self) -> np.ndarray | None:
        """采集一帧 BGR 图像，失败返回 None"""
        if self.use_picamera2 and self.picam2 is not None:
            return self._capture_picamera2()
        if self.cap is not None:
            return self._capture_usb()
        logger.error("摄像头未初始化")
        return None

    def _capture_picamera2(self) -> np.ndarray | None:
        """PiCamera2 → RGB → BGR"""
        try:
            frame = self.picam2.capture_array()
            frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
            return self._apply_flips(frame)
        except Exception as e:
            logger.error("PiCamera2 采集失败: %s", e)
            return None

    def _capture_usb(self) -> np.ndarray | None:
        """USB 摄像头采集"""
        ret, frame = self.cap.read()
        if not ret:
            logger.error("USB 读取失败")
            return None
        return self._apply_flips(frame)

    def _apply_flips(self, frame: np.ndarray) -> np.ndarray:
        if self.flip_h:
            frame = cv2.flip(frame, 1)
        if self.flip_v:
            frame = cv2.flip(frame, 0)
        return frame

    def release(self):
        """释放摄像头资源"""
        if self.picam2 is not None:
            try:
                self.picam2.stop()
                self.picam2.close()
            except Exception:
                pass
            self.picam2 = None
        if self.cap is not None:
            self.cap.release()
            self.cap = None
        logger.info("摄像头资源已释放")

    def is_ready(self) -> bool:
        if self.use_picamera2:
            return self.picam2 is not None
        return self.cap is not None and self.cap.isOpened()

    @property
    def resolution(self) -> tuple:
        return (self.width, self.height)
