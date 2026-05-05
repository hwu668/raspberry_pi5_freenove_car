"""
main.py - 树莓派5 + Freenove FNK0043B (普通车轮版) 视觉导航主程序

功能流程:
  1. 初始化摄像头、图像识别、电机控制、导航模块
  2. 主循环: 采集帧 → 检测目标 → 导航决策 → 执行运动
  3. 显示实时画面 (含 HUD 叠加) 与调试信息
  4. 键盘快捷键控制, Ctrl+C 安全退出

用法:
  python main.py                     # 追踪红色目标 (默认)
  python main.py --color blue        # 追踪蓝色目标
  python main.py --no-display        # 无头模式 (不显示 GUI, 可 SSH 运行)
  python main.py --duty 1500         # 自定义基础速度 (duty 值)
"""

import cv2
import sys
import time
import signal
import logging
import argparse
from pathlib import Path

# 确保日志目录存在
Path("logs").mkdir(parents=True, exist_ok=True)

# ---- 日志配置 ----
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("logs/car.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger("main")

import config
from camera import Camera
from image_recognition import ImageRecognition
from motor_control import MotorControl
from navigation import Navigation, NavState


class CarController:
    """FNK0043B 视觉导航总控制器"""

    def __init__(self, no_display: bool = False, target_color: str = "red",
                 base_duty: int = None):
        self.no_display = no_display

        if no_display:
            config.ENABLE_DISPLAY = False

        if base_duty is not None:
            config.MOTOR_DUTY_BASE = base_duty
            logger.info("自定义基础速度: duty=%d", base_duty)

        self._apply_color_preset(target_color)

        logger.info("=" * 55)
        logger.info("Freenove FNK0043B - 4WD 普通车轮 视觉导航系统")
        logger.info("=" * 55)

        self.camera = Camera(config)
        self.recognition = ImageRecognition(config)
        self.motor = MotorControl(config)
        self.navigation = Navigation(config, self.motor)

        self._running = False
        self._fps_counter = 0
        self._fps_timer = time.time()
        self._fps_current = 0.0

    # ========================================================================
    # 颜色预置
    # ========================================================================

    def _apply_color_preset(self, color_name: str):
        presets = config.COLOR_PRESETS
        if color_name in presets:
            preset = presets[color_name]
            config.COLOR_TARGET_LOWER = preset["lower1"]
            config.COLOR_TARGET_UPPER = preset["upper1"]
            if preset["lower2"] is not None:
                config.COLOR_TARGET_LOWER2 = preset["lower2"]
                config.COLOR_TARGET_UPPER2 = preset["upper2"]
            else:
                config.COLOR_TARGET_LOWER2 = None
                config.COLOR_TARGET_UPPER2 = None
            logger.info("目标颜色: %s", color_name)
        else:
            logger.warning("未知颜色 '%s', 使用默认红色", color_name)

    # ========================================================================
    # 启动 / 关闭
    # ========================================================================

    def start(self):
        """启动所有模块并进入主循环"""
        if not self.camera.start():
            logger.error("摄像头初始化失败, 退出")
            sys.exit(1)

        self.motor.setup()
        self.motor.center_servos()

        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

        self._running = True
        logger.info("主循环启动 (按 Ctrl+C 或 'q' 退出)...")

        try:
            self._main_loop()
        except KeyboardInterrupt:
            logger.info("收到键盘中断信号")
        except Exception as e:
            logger.exception("主循环异常: %s", e)
        finally:
            self.shutdown()

    def shutdown(self):
        """安全关闭所有模块"""
        logger.info("正在关闭系统...")
        self._running = False

        self.motor.stop()
        self.motor.clear_leds()

        self.camera.release()
        self.motor.cleanup()

        if config.ENABLE_DISPLAY:
            cv2.destroyAllWindows()

        logger.info("Freenove FNK0043B 已安全关闭")

    # ========================================================================
    # 主循环
    # ========================================================================

    def _main_loop(self):
        while self._running:
            loop_start = time.time()

            # 1. 采集帧
            frame = self.camera.capture()
            if frame is None:
                logger.warning("采集帧失败, 等待重试...")
                time.sleep(0.5)
                continue

            # 2. 图像识别
            target = self.recognition.detect(frame)

            # 3. 导航决策
            nav_state = self.navigation.update(target)

            # 4. 显示
            if config.ENABLE_DISPLAY:
                display_frame = self.recognition.draw_debug(frame, target)
                self._draw_hud(display_frame, nav_state)
                cv2.imshow(config.DISPLAY_WINDOW_NAME, display_frame)

                key = cv2.waitKey(1) & 0xFF
                self._handle_key(key)

            # 5. FPS
            self._fps_counter += 1
            elapsed = time.time() - self._fps_timer
            if elapsed >= 1.0:
                self._fps_current = self._fps_counter / elapsed
                self._fps_counter = 0
                self._fps_timer = time.time()

            # 6. 速率控制
            loop_time = time.time() - loop_start
            sleep_time = config.MAIN_LOOP_DELAY - loop_time
            if sleep_time > 0:
                time.sleep(sleep_time)

    # ========================================================================
    # 键盘控制
    # ========================================================================

    def _handle_key(self, key: int):
        """处理键盘快捷键"""
        if key == ord('q'):
            logger.info("用户按下 'q', 退出")
            self._running = False
        elif key == ord('r'):
            self.navigation.reset()
        elif key == ord('s'):
            self.navigation.emergency_stop()
        elif key == ord('f'):
            if not self.navigation.is_stopped:
                self.navigation.emergency_stop()
            else:
                self.motor.move_forward()
        elif key == ord('w'):
            self.motor.move_forward()
        elif key == ord('a'):
            self.motor.turn_left()
        elif key == ord('d'):
            self.motor.turn_right()
        elif key == ord('x'):
            self.motor.move_backward()
        elif key == ord('m'):
            self.motor.led_indicator("SEARCH")
            self.motor.buzzer_beep(50)
        elif key == ord('1'):
            self.motor.set_pan_angle(30)
        elif key == ord('2'):
            self.motor.set_pan_angle(90)
        elif key == ord('3'):
            self.motor.set_pan_angle(150)
        elif key == ord('i'):
            distance = self.motor.get_distance_cm()
            logger.info("超声波距离: %.1f cm", distance)

    # ========================================================================
    # HUD
    # ========================================================================

    def _draw_hud(self, frame, nav_state: str):
        """绘制半透明 HUD"""
        h, w = frame.shape[:2]
        overlay = frame.copy()
        cv2.rectangle(overlay, (0, h - 65), (w, h), (20, 20, 20), -1)
        frame[:] = cv2.addWeighted(frame, 0.75, overlay, 0.25, 0)

        lines = [
            f"State: {nav_state:10s}  Command: {self.motor.current_command:12s}",
            f"FPS: {self._fps_current:5.1f}   Duty: {self.motor.duty_base}",
            "[Q]uit [R]eset [S]top [F]wd [WASD] Move",
        ]
        for i, line in enumerate(lines):
            cv2.putText(frame, line, (10, h - 48 + i * 18),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 255), 1)

    def _signal_handler(self, signum, frame):
        logger.info("收到信号 %d, 正在退出...", signum)
        self._running = False


# ============================================================================
# CLI
# ============================================================================

def parse_args():
    parser = argparse.ArgumentParser(
        description="Freenove FNK0043B 4WD 普通车轮 视觉导航系统",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python main.py                          # 追踪红色目标
  python main.py --color blue              # 追踪蓝色目标
  python main.py --no-display              # 无头模式 (SSH)
  python main.py --duty 1500 --color green # 低速追踪绿色
        """,
    )
    parser.add_argument("--no-display", action="store_true",
                        help="无头模式, 不显示 OpenCV GUI")
    parser.add_argument("--color", type=str, default="red",
                        choices=list(config.COLOR_PRESETS.keys()),
                        help="追踪的目标颜色 (默认: red)")
    parser.add_argument("--duty", type=int, default=None,
                        help=f"电机基础 duty 值 0-{config.MOTOR_DUTY_MAX} (默认: {config.MOTOR_DUTY_BASE})")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    controller = CarController(no_display=args.no_display,
                               target_color=args.color,
                               base_duty=args.duty)
    controller.start()
