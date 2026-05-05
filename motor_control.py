"""
motor_control.py - 电机 / 舵机 / 超声波 / LED / 蜂鸣器 综合控制模块

适用: 树莓派5 + Freenove FNK0043B Smart Car Board (PCA9685 I2C 驱动)

功能:
  - 4 路麦克纳姆轮电机控制 (前进/后退/左转/右转/横移/斜移)
  - 2 路舵机云台控制 (水平/垂直)
  - HC-SR04 超声波测距
  - 8 颗 WS2812B RGB LED
  - 有源蜂鸣器

依赖: Freenove 官方库 (Motor.py, servo.py, Led.py, Buzzer.py, Ultrasonic.py, PCA9685.py)
      未安装时自动回退 Mock 模式 (适合开发调试)
"""

import logging
import time
import numpy as np

logger = logging.getLogger(__name__)

# ============================================================================
# Freenove 官方库导入 (优雅降级)
# ============================================================================

# --- 电机 ---
try:
    from Motor import Motor as _FreenoveMotor
    _HAS_MOTOR = True
except ImportError:
    logger.warning("Freenove Motor 库未安装, 电机控制进入 Mock 模式")
    _HAS_MOTOR = False

# --- 舵机 ---
try:
    from servo import Servo as _FreenoveServo
    _HAS_SERVO = True
except ImportError:
    logger.warning("Freenove servo 库未安装, 舵机进入 Mock 模式")
    _HAS_SERVO = False

# --- LED ---
try:
    from Led import Led as _FreenoveLed
    _HAS_LED = True
except ImportError:
    logger.warning("Freenove Led 库未安装, LED 进入 Mock 模式")
    _HAS_LED = False

# --- 蜂鸣器 ---
try:
    from Buzzer import Buzzer as _FreenoveBuzzer
    _HAS_BUZZER = True
except ImportError:
    logger.warning("Freenove Buzzer 库未安装, 蜂鸣器进入 Mock 模式")
    _HAS_BUZZER = False

# --- 超声波 ---
try:
    from Ultrasonic import Ultrasonic as _FreenoveUltrasonic
    _HAS_ULTRASONIC = True
except ImportError:
    logger.warning("Freenove Ultrasonic 库未安装, 超声波进入 Mock 模式")
    _HAS_ULTRASONIC = False


class MotorControl:
    """Freenove FNK0043B 小车综合控制

    封装 Freenove 官方库, 提供一致的 API。
    未安装官方库时自动进入 Mock 模式 (所有操作日志记录但不执行硬件动作)。
    """

    # 移动方向常量
    FORWARD = "forward"
    BACKWARD = "backward"
    LEFT = "left"
    RIGHT = "right"
    STOP = "stop"

    # 麦克纳姆轮特有方向
    STRAFE_LEFT = "strafe_left"    # 左横移
    STRAFE_RIGHT = "strafe_right"  # 右横移
    DIAGONAL_FL = "diag_fl"        # 左前斜移
    DIAGONAL_FR = "diag_fr"        # 右前斜移
    DIAGONAL_BL = "diag_bl"        # 左后斜移
    DIAGONAL_BR = "diag_br"        # 右后斜移
    ROTATE_LEFT = "rotate_left"    # 原地左旋
    ROTATE_RIGHT = "rotate_right"  # 原地右旋

    def __init__(self, config):
        self.config = config

        # 电机速度参数
        self.duty_base = config.MOTOR_DUTY_BASE
        self.duty_turn = config.MOTOR_DUTY_TURN
        self.duty_slow = config.MOTOR_DUTY_SLOW
        self.duty_max = config.MOTOR_DUTY_MAX
        self.duty_min = config.MOTOR_DUTY_MIN

        # 初始化 Freenove 实例 (或 Mock)
        self._motor = None
        self._servo = None
        self._led = None
        self._buzzer = None
        self._ultrasonic = None

        self._current_command = self.STOP
        self._initialized = False

    # ========================================================================
    # 初始化与清理
    # ========================================================================

    def setup(self) -> bool:
        """初始化所有硬件模块。返回 True 表示至少 Mock 可用。"""
        logger.info("正在初始化 Freenove FNK0043B 硬件模块...")

        # 电机 (PCA9685)
        if _HAS_MOTOR:
            try:
                self._motor = _FreenoveMotor()
                logger.info("  ✓ 电机模块 (PCA9685)")
            except Exception as e:
                logger.error("  ✗ 电机初始化失败: %s", e)

        # 舵机
        if _HAS_SERVO:
            try:
                self._servo = _FreenoveServo()
                logger.info("  ✓ 舵机模块")
            except Exception as e:
                logger.error("  ✗ 舵机初始化失败: %s", e)

        # LED
        if _HAS_LED:
            try:
                self._led = _FreenoveLed()
                logger.info("  ✓ LED 模块")
            except Exception as e:
                logger.error("  ✗ LED 初始化失败: %s", e)

        # 蜂鸣器
        if _HAS_BUZZER:
            try:
                self._buzzer = _FreenoveBuzzer()
                logger.info("  ✓ 蜂鸣器模块")
            except Exception as e:
                logger.error("  ✗ 蜂鸣器初始化失败: %s", e)

        # 超声波
        if _HAS_ULTRASONIC:
            try:
                self._ultrasonic = _FreenoveUltrasonic()
                logger.info("  ✓ 超声波模块")
            except Exception as e:
                logger.error("  ✗ 超声波初始化失败: %s", e)

        self._initialized = True
        self.stop()
        return True

    def cleanup(self):
        """释放所有硬件资源"""
        self.stop()
        if self._motor is not None:
            try:
                self._motor.close()
            except Exception:
                pass
        self._initialized = False
        logger.info("硬件资源已释放")

    # ========================================================================
    # 高级运动指令
    # ========================================================================

    def move_forward(self, duty: int = None):
        """前进 (四轮同向正转)"""
        d = duty if duty is not None else self.duty_base
        d = max(0, min(self.duty_max, d))
        self._set_motor_raw(d, d, d, d)
        self._current_command = self.FORWARD
        logger.debug("前进: duty=%d", d)

    def move_backward(self, duty: int = None):
        """后退 (四轮同向反转)"""
        d = duty if duty is not None else self.duty_base
        d = max(0, min(self.duty_max, d))
        self._set_motor_raw(-d, -d, -d, -d)
        self._current_command = self.BACKWARD
        logger.debug("后退: duty=%d", d)

    def turn_left(self, duty: int = None):
        """原地左旋 (四轮差速: 左轮后转, 右轮前转)"""
        d = duty if duty is not None else self.duty_turn
        d = max(0, min(self.duty_max, d))
        self._set_motor_raw(-d, -d, d, d)
        self._current_command = self.LEFT
        logger.debug("左旋: duty=%d", d)

    def turn_right(self, duty: int = None):
        """原地右旋 (四轮差速: 左轮前转, 右轮后转)"""
        d = duty if duty is not None else self.duty_turn
        d = max(0, min(self.duty_max, d))
        self._set_motor_raw(d, d, -d, -d)
        self._current_command = self.RIGHT
        logger.debug("右旋: duty=%d", d)

    def strafe_left(self, duty: int = None):
        """麦克纳姆轮左横移 (左前+右后反转, 右前+左后正转)"""
        d = duty if duty is not None else self.duty_base
        d = max(0, min(self.duty_max, d))
        self._set_motor_raw(-d, d, d, -d)
        self._current_command = self.STRAFE_LEFT
        logger.debug("左横移: duty=%d", d)

    def strafe_right(self, duty: int = None):
        """麦克纳姆轮右横移 (左前+右后正转, 右前+左后反转)"""
        d = duty if duty is not None else self.duty_base
        d = max(0, min(self.duty_max, d))
        self._set_motor_raw(d, -d, -d, d)
        self._current_command = self.STRAFE_RIGHT
        logger.debug("右横移: duty=%d", d)

    def steer(self, direction: str, inner_duty: int, outer_duty: int):
        """差速转向 (比原地旋转更平滑)。

        Args:
            direction: 'left' 或 'right'
            inner_duty: 内侧轮速度
            outer_duty: 外侧轮速度
        """
        inner_duty = max(0, min(self.duty_max, inner_duty))
        outer_duty = max(0, min(self.duty_max, outer_duty))

        if direction == self.LEFT:
            # 左转: 左轮慢, 右轮快
            self._set_motor_raw(inner_duty, inner_duty, outer_duty, outer_duty)
        elif direction == self.RIGHT:
            # 右转: 左轮快, 右轮慢
            self._set_motor_raw(outer_duty, outer_duty, inner_duty, inner_duty)
        self._current_command = direction
        logger.debug("差速转向 %s: inner=%d outer=%d", direction, inner_duty, outer_duty)

    def set_velocity(self, vx: float, vy: float, omega: float, max_duty: int = None):
        """麦克纳姆轮速度分解 (全向移动)。

        Args:
            vx: X 轴速度分量 (-1.0 ~ 1.0)
            vy: Y 轴速度分量 (-1.0 ~ 1.0, 正=前进)
            omega: 旋转角速度 (-1.0 ~ 1.0, 正=右旋)
            max_duty: 最大 duty 值上限
        """
        if max_duty is None:
            max_duty = self.duty_base

        # 麦克纳姆轮运动学逆解:
        #  LF =  vy - vx - omega
        #  LR =  vy + vx - omega
        #  RF = -vy - vx - omega
        #  RR = -vy + vx - omega
        #
        # 注意: 具体符号可能因电机安装方向而异, 首次运行需验证

        lf = vy - vx - omega
        lr = vy + vx - omega
        rf = -vy - vx - omega
        rr = -vy + vx - omega

        # 归一化
        max_val = max(abs(lf), abs(lr), abs(rf), abs(rr), 1.0)
        scale = max_duty / max_val
        duty_lf = int(lf * scale)
        duty_lr = int(lr * scale)
        duty_rf = int(rf * scale)
        duty_rr = int(rr * scale)

        self._set_motor_raw(duty_lf, duty_lr, duty_rf, duty_rr)
        self._current_command = "omni"
        logger.debug("全向移动: vx=%.2f vy=%.2f omega=%.2f → [%d,%d,%d,%d]",
                     vx, vy, omega, duty_lf, duty_lr, duty_rf, duty_rr)

    def stop(self):
        """停车 (四轮停转)"""
        self._set_motor_raw(0, 0, 0, 0)
        self._current_command = self.STOP
        logger.debug("停车")

    # ========================================================================
    # 底层电机控制
    # ========================================================================

    def _set_motor_raw(self, duty_lf: int, duty_lr: int,
                       duty_rf: int, duty_rr: int):
        """直接设置四路电机 duty 值。

        Args:
            duty_lf: 左前轮 (-4096 ~ 4096)
            duty_lr: 左后轮
            duty_rf: 右前轮
            duty_rr: 右后轮
        """
        # 限幅
        duty_lf = max(-self.duty_max, min(self.duty_max, duty_lf))
        duty_lr = max(-self.duty_max, min(self.duty_max, duty_lr))
        duty_rf = max(-self.duty_max, min(self.duty_max, duty_rf))
        duty_rr = max(-self.duty_max, min(self.duty_max, duty_rr))

        if self._motor is not None:
            try:
                self._motor.setMotorModel(duty_lf, duty_lr, duty_rf, duty_rr)
            except Exception as e:
                logger.error("setMotorModel 调用失败: %s", e)

    # ========================================================================
    # 舵机控制 (云台)
    # ========================================================================

    def set_pan_angle(self, angle: float):
        """设置水平舵机角度。

        Args:
            angle: 0° ~ 180°, 90° 居中
        """
        angle = max(self.config.SERVO_PAN_MIN_ANGLE,
                    min(self.config.SERVO_PAN_MAX_ANGLE, angle))
        # 角度 → Freenove PWM 值
        pwm_val = self._angle_to_pwm(angle, self.config.SERVO0_PWM_MIN,
                                     self.config.SERVO0_PWM_MAX)
        if self._servo is not None:
            try:
                self._servo.setServoPwm('0', int(pwm_val))
            except Exception as e:
                logger.error("舵机 0 控制失败: %s", e)
        logger.debug("云台水平: %.0f° (PWM=%d)", angle, int(pwm_val))

    def set_tilt_angle(self, angle: float):
        """设置垂直舵机角度。

        Args:
            angle: 80° ~ 150° (受限于云台机械结构)
        """
        angle = max(self.config.SERVO_TILT_MIN_ANGLE,
                    min(self.config.SERVO_TILT_MAX_ANGLE, angle))
        pwm_val = self._angle_to_pwm(angle, self.config.SERVO1_PWM_MIN,
                                     self.config.SERVO1_PWM_MAX)
        if self._servo is not None:
            try:
                self._servo.setServoPwm('1', int(pwm_val))
            except Exception as e:
                logger.error("舵机 1 控制失败: %s", e)
        logger.debug("云台垂直: %.0f° (PWM=%d)", angle, int(pwm_val))

    def center_servos(self):
        """双舵机回中"""
        self.set_pan_angle(self.config.SERVO_PAN_DEFAULT)
        self.set_tilt_angle(self.config.SERVO_TILT_DEFAULT)

    @staticmethod
    def _angle_to_pwm(angle: float, pwm_min: int, pwm_max: int) -> float:
        """将角度 (0~180) 转换为 Freenove 舵机 PWM 值"""
        # 注意: Freenove setServoPwm 的参数范围因舵机而异
        #   Servo 0: 50 (~0°) ~ 110 (~180°)
        #   Servo 1: 80 (~0°) ~ 150 (~180°)
        return pwm_min + (angle / 180.0) * (pwm_max - pwm_min)

    # ========================================================================
    # 超声波测距
    # ========================================================================

    def get_distance_cm(self) -> float:
        """获取前方障碍物距离。

        Returns:
            float: 距离 (cm), -1 表示测量失败, 999 表示 Mock 模式
        """
        if self._ultrasonic is not None:
            try:
                dist = self._ultrasonic.get_distance()
                return dist if dist is not None else -1
            except Exception as e:
                logger.error("超声波测距失败: %s", e)
                return -1
        return 999.0  # Mock 模式: 返回极大值

    # ========================================================================
    # LED 控制
    # ========================================================================

    def set_led(self, index: int, r: int, g: int, b: int):
        """设置指定 LED 颜色。

        Args:
            index: LED 编号 (0~7)
            r, g, b: 颜色值 (0~255)
        """
        if not 0 <= index <= 7:
            return
        bitmask = 1 << index  # 0x01, 0x02, 0x04, ...
        if self._led is not None:
            try:
                self._led.ledIndex(bitmask, r, g, b)
            except Exception as e:
                logger.error("LED 控制失败: %s", e)

    def clear_leds(self):
        """关闭所有 LED"""
        if self._led is not None:
            try:
                self._led.colorWipe(self._led.strip,
                                    self._led.Color(0, 0, 0))
            except Exception:
                pass

    def led_indicator(self, state: str):
        """根据导航状态显示不同 LED 颜色。

        Args:
            state: 'search' / 'track' / 'approach' / 'stop'
        """
        colors = {
            "SEARCH":   (0, 0, 255),    # 蓝色: 搜索
            "TRACK":    (255, 255, 0),  # 黄色: 追踪
            "APPROACH": (0, 255, 0),    # 绿色: 接近
            "STOP":     (255, 0, 0),    # 红色: 停止
        }
        r, g, b = colors.get(state, (0, 0, 0))
        for i in range(8):
            self.set_led(i, r, g, b)

    # ========================================================================
    # 蜂鸣器
    # ========================================================================

    def buzzer_on(self):
        """蜂鸣器开"""
        if self._buzzer is not None:
            try:
                self._buzzer.run('1')
            except Exception as e:
                logger.error("蜂鸣器控制失败: %s", e)

    def buzzer_off(self):
        """蜂鸣器关"""
        if self._buzzer is not None:
            try:
                self._buzzer.run('0')
            except Exception as e:
                logger.error("蜂鸣器控制失败: %s", e)

    def buzzer_beep(self, duration_ms: int = 200):
        """短鸣一声"""
        self.buzzer_on()
        time.sleep(duration_ms / 1000.0)
        self.buzzer_off()

    # ========================================================================
    # 属性
    # ========================================================================

    @property
    def is_initialized(self) -> bool:
        return self._initialized

    @property
    def current_command(self) -> str:
        return self._current_command
