"""
motor_control.py - 电机 / 舵机 / 超声波 / LED / 蜂鸣器 综合控制模块

适用: 树莓派5 + Freenove FNK0043B Smart Car Board (PCA9685 I2C 驱动)

功能:
  - 4 路直流电机控制 (前进/后退/左转/右转/差速转向)
  - 2 路舵机云台控制 (水平/垂直)
  - HC-SR04 超声波测距
  - 8 颗 WS2812B RGB LED
  - 有源蜂鸣器

运行模式:
  - auto:     优先使用硬件，初始化失败时降级为 Mock
  - mock:     强制 Mock 模式，不依赖真实硬件
  - hardware: 强制硬件模式，缺少硬件库或初始化失败时直接报错

依赖: Freenove 官方库 (Motor.py, servo.py, Led.py, Buzzer.py, Ultrasonic.py, PCA9685.py)
      未安装时按模式决定是否回退 Mock。
"""

import logging
import time

logger = logging.getLogger(__name__)

# ============================================================================
# Freenove 官方库导入 (优雅降级)
# ============================================================================

# --- 电机 ---
try:
    from Motor import Motor as _FreenoveMotor

    _HAS_MOTOR = True
except ImportError:
    _HAS_MOTOR = False

# --- 舵机 ---
try:
    from servo import Servo as _FreenoveServo

    _HAS_SERVO = True
except ImportError:
    _HAS_SERVO = False

# --- LED ---
try:
    from Led import Led as _FreenoveLed

    _HAS_LED = True
except ImportError:
    _HAS_LED = False

# --- 蜂鸣器 ---
try:
    from Buzzer import Buzzer as _FreenoveBuzzer

    _HAS_BUZZER = True
except ImportError:
    _HAS_BUZZER = False

# --- 超声波 ---
try:
    from Ultrasonic import Ultrasonic as _FreenoveUltrasonic

    _HAS_ULTRASONIC = True
except ImportError:
    _HAS_ULTRASONIC = False


class MotorControl:
    """Freenove FNK0043B 小车综合控制

    封装 Freenove 官方库, 提供一致的 API。
    根据运行模式决定是否使用真实硬件或 Mock。
    """

    # 运行模式常量
    MODE_AUTO = "auto"
    MODE_MOCK = "mock"
    MODE_HARDWARE = "hardware"

    # 移动方向常量
    FORWARD = "forward"
    BACKWARD = "backward"
    LEFT = "left"
    RIGHT = "right"
    STOP = "stop"

    def __init__(self, config, mode: str = "auto"):
        self.config = config
        self._mode = mode

        # 运行状态字段
        self.hardware_available = False
        self.mock_active = False
        self.initialization_errors: list[str] = []

        # 电机速度参数
        self.duty_base = config.MOTOR_DUTY_BASE
        self.duty_turn = config.MOTOR_DUTY_TURN
        self.duty_slow = config.MOTOR_DUTY_SLOW
        self.duty_max = config.MOTOR_DUTY_MAX
        self.duty_min = config.MOTOR_DUTY_MIN

        # 硬件实例 (初始化前为 None)
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
        """初始化所有硬件模块。

        根据 self.mode 决定初始化策略:
          - mock:     跳过所有硬件初始化, 直接进入 Mock 模式
          - auto:     尝试初始化硬件, 失败则降级 Mock
          - hardware: 尝试初始化硬件, 失败则报错返回 False

        Returns:
            bool: True 表示初始化成功 (Mock 或硬件均可), False 表示失败
        """
        logger.info("正在初始化 Freenove FNK0043B 硬件模块... (mode=%s)", self._mode)

        # --- Mock 模式: 跳过硬件 ---
        if self._mode == self.MODE_MOCK:
            logger.info("Mock mode active - 跳过硬件初始化")
            self.mock_active = True
            self.hardware_available = False
            self._initialized = True
            self.stop()
            return True

        # --- Auto / Hardware 模式: 尝试初始化硬件 ---
        any_hardware_ok = False
        self.initialization_errors = []

        # 检查是否有任何硬件库可用
        if not any([_HAS_MOTOR, _HAS_SERVO, _HAS_LED, _HAS_BUZZER, _HAS_ULTRASONIC]):
            msg = "未检测到任何 Freenove 硬件库 (Motor/servo/Led/Buzzer/Ultrasonic)"
            logger.error(msg)
            self.initialization_errors.append(msg)
            if self._mode == self.MODE_HARDWARE:
                self._initialized = False
                return False
            # Auto 模式降级
            logger.info("Auto 模式降级为 Mock: %s", msg)
            self.mock_active = True
            self.hardware_available = False
            self._initialized = True
            self.stop()
            return True

        # 电机 (PCA9685)
        if _HAS_MOTOR:
            try:
                self._motor = _FreenoveMotor()
                logger.info("  ✓ 电机模块 (PCA9685)")
                any_hardware_ok = True
            except Exception as e:
                err = f"电机初始化失败: {e}"
                logger.error("  ✗ %s", err)
                self.initialization_errors.append(err)

        # 舵机
        if _HAS_SERVO:
            try:
                self._servo = _FreenoveServo()
                logger.info("  ✓ 舵机模块")
                any_hardware_ok = True
            except Exception as e:
                err = f"舵机初始化失败: {e}"
                logger.error("  ✗ %s", err)
                self.initialization_errors.append(err)

        # LED
        if _HAS_LED:
            try:
                self._led = _FreenoveLed()
                logger.info("  ✓ LED 模块")
                any_hardware_ok = True
            except Exception as e:
                err = f"LED 初始化失败: {e}"
                logger.error("  ✗ %s", err)
                self.initialization_errors.append(err)

        # 蜂鸣器
        if _HAS_BUZZER:
            try:
                self._buzzer = _FreenoveBuzzer()
                logger.info("  ✓ 蜂鸣器模块")
                any_hardware_ok = True
            except Exception as e:
                err = f"蜂鸣器初始化失败: {e}"
                logger.error("  ✗ %s", err)
                self.initialization_errors.append(err)

        # 超声波
        if _HAS_ULTRASONIC:
            try:
                self._ultrasonic = _FreenoveUltrasonic()
                logger.info("  ✓ 超声波模块")
                any_hardware_ok = True
            except Exception as e:
                err = f"超声波初始化失败: {e}"
                logger.error("  ✗ %s", err)
                self.initialization_errors.append(err)

        if any_hardware_ok:
            self.hardware_available = True
            self.mock_active = False
            self._initialized = True
            self.stop()
            logger.info("硬件初始化完成 (hardware mode)")
            return True

        # 硬件库存在但全部初始化失败
        if self._mode == self.MODE_HARDWARE:
            logger.error("Hardware 模式: 所有硬件模块初始化失败, 退出")
            self._initialized = False
            return False

        # Auto 模式降级
        logger.warning("Auto 模式降级为 Mock: 硬件初始化全部失败")
        self.mock_active = True
        self.hardware_available = False
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
        if not self.mock_active:
            logger.info("硬件资源已释放")
        self._initialized = False

    # ========================================================================
    # 运动指令 (普通车轮: 前进/后退/差速转向)
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
        """原地左转 (四轮差速: 左轮后转, 右轮前转)"""
        d = duty if duty is not None else self.duty_turn
        d = max(0, min(self.duty_max, d))
        self._set_motor_raw(-d, -d, d, d)
        self._current_command = self.LEFT
        logger.debug("左转: duty=%d", d)

    def turn_right(self, duty: int = None):
        """原地右转 (四轮差速: 左轮前转, 右轮后转)"""
        d = duty if duty is not None else self.duty_turn
        d = max(0, min(self.duty_max, d))
        self._set_motor_raw(d, d, -d, -d)
        self._current_command = self.RIGHT
        logger.debug("右转: duty=%d", d)

    def steer(self, direction: str, inner_duty: int, outer_duty: int):
        """差速转向 (比原地旋转更平滑, 前进中微调方向)。

        Args:
            direction: 'left' 或 'right'
            inner_duty: 内侧轮速度 (较慢)
            outer_duty: 外侧轮速度 (较快)
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
        bitmask = 1 << index
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
            state: 'SEARCH' / 'TRACK' / 'APPROACH' / 'STOP'
        """
        colors = {
            "SEARCH": (0, 0, 255),
            "TRACK": (255, 255, 0),
            "APPROACH": (0, 255, 0),
            "STOP": (255, 0, 0),
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
    def mode(self) -> str:
        return self._mode

    @property
    def is_initialized(self) -> bool:
        return self._initialized

    @property
    def current_command(self) -> str:
        return self._current_command
