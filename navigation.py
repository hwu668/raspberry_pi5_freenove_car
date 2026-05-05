"""
navigation.py - 导航与路径规划模块

适用: Freenove FNK0043B (4WD 普通车轮)

功能:
  1. 接收图像识别结果 (TargetInfo), 计算运动指令
  2. PID 控制器 - 平滑转向, 避免震荡
  3. 差速转向 - 两侧车轮速度差实现前进中转向
  4. 状态机 - SEARCH / TRACK / APPROACH / STOP 四种状态
  5. 距离管理 - 超声波测距 + 目标面积估算
"""

import logging
import time
from enum import Enum, auto

logger = logging.getLogger(__name__)


class NavState(Enum):
    """导航状态枚举"""
    SEARCH = auto()    # 搜索模式: 原地旋转寻找目标
    TRACK = auto()     # 追踪模式: 目标在视野内, 调整方向
    APPROACH = auto()  # 接近模式: 目标在中心, 缓慢靠近
    STOP = auto()      # 停止: 已到达目标位置或遇障


class PIDController:
    """增量式 PID 控制器, 用于转向平滑控制"""

    def __init__(self, kp: float, ki: float, kd: float, output_limit: float = 100.0):
        self.kp = kp
        self.ki = ki
        self.kd = kd
        self.output_limit = output_limit

        self._integral = 0.0
        self._prev_error = 0.0
        self._last_time = time.time()

    def update(self, error: float) -> float:
        """给定误差, 计算控制输出 (正值=目标在右, 需右转)。

        Returns:
            float: 控制输出, 范围 [-output_limit, output_limit]
        """
        now = time.time()
        dt = now - self._last_time

        if dt <= 0.0 or dt > 0.5:
            dt = 0.05

        p_term = self.kp * error

        self._integral += error * dt
        self._integral = max(-50.0, min(50.0, self._integral))
        i_term = self.ki * self._integral

        d_term = self.kd * (error - self._prev_error) / dt

        self._prev_error = error
        self._last_time = now

        output = p_term + i_term + d_term
        return max(-self.output_limit, min(self.output_limit, output))

    def reset(self):
        """重置 PID 内部状态"""
        self._integral = 0.0
        self._prev_error = 0.0
        self._last_time = time.time()


class Navigation:
    """FNK0043B 导航引擎: 视觉引导 + 差速转向"""

    def __init__(self, config, motor_control):
        """
        Args:
            config: 项目配置模块
            motor_control: MotorControl 实例
        """
        self.config = config
        self.motor = motor_control

        # 参数
        self.frame_center_x = config.FRAME_CENTER_X
        self.turn_threshold = config.TURN_THRESHOLD
        self.approach_dist = config.APPROACH_DISTANCE_CM
        self.stop_dist = config.STOP_DISTANCE_CM
        self.base_duty = config.MOTOR_DUTY_BASE
        self.slow_duty = config.MOTOR_DUTY_SLOW

        # PID
        self.pid = PIDController(
            kp=config.PID_KP,
            ki=config.PID_KI,
            kd=config.PID_KD,
        )

        # 状态
        self.state = NavState.SEARCH
        self._target_lost_count = 0
        self._max_lost_frames = config.MAX_LOST_FRAMES

    # ========================================================================
    # 主更新入口
    # ========================================================================

    def update(self, target) -> str:
        """根据目标信息更新导航状态并执行运动指令。

        Args:
            target: TargetInfo 实例 (来自 ImageRecognition.detect())

        Returns:
            str: 当前导航状态名称
        """
        # 距离检查 (超声波优先)
        distance = self.motor.get_distance_cm()
        if 0 < distance < self.stop_dist:
            if self.state != NavState.STOP:
                logger.info("超声波测距 %.1f cm < 停车距离 %d cm, 停止",
                            distance, self.stop_dist)
            self.state = NavState.STOP
            self.motor.stop()
            self.motor.led_indicator(self.state.name)
            return self.state.name

        # 状态机
        if not target.found:
            self._handle_lost_target()
        else:
            self._handle_target_found(target, distance)

        # LED 状态指示
        self.motor.led_indicator(self.state.name)

        return self.state.name

    # ========================================================================
    # 状态处理
    # ========================================================================

    def _handle_lost_target(self):
        """目标丢失处理"""
        self._target_lost_count += 1

        if self._target_lost_count < self._max_lost_frames:
            # 短暂丢失: 保持最后指令
            if self.state == NavState.APPROACH:
                self.motor.move_forward(self.slow_duty)
            return

        # 持续丢失: 进入搜索模式
        if self.state != NavState.SEARCH:
            logger.info("目标丢失 >%.1fs, 进入搜索模式",
                        self._max_lost_frames * self.config.MAIN_LOOP_DELAY)
        self.state = NavState.SEARCH
        self.pid.reset()
        self.motor.turn_right(duty=1200)  # 慢速原地旋转寻找目标

    def _handle_target_found(self, target, distance: float):
        """目标在视野内的处理"""
        self._target_lost_count = 0
        offset = target.offset_from_center(self.frame_center_x)

        # 判断状态
        if abs(offset) <= self.turn_threshold:
            if 0 < distance < self.approach_dist:
                self.state = NavState.APPROACH
            else:
                self.state = NavState.TRACK
        else:
            self.state = NavState.TRACK

        # 执行运动
        if self.state == NavState.APPROACH:
            self._do_approach(offset, distance)
        elif self.state == NavState.TRACK:
            self._do_track(offset)
        else:
            self._do_track(offset)

    # ========================================================================
    # 运动执行
    # ========================================================================

    def _do_track(self, offset: int):
        """追踪模式: 用 PID 调整方向使目标居中

        PID 输出 → 差速转向:
          - 目标在右 (offset>0): 右转 (左快右慢)
          - 目标在左 (offset<0): 左转 (左慢右快)
        """
        turn_amount = self.pid.update(offset)

        if abs(offset) <= self.turn_threshold:
            # 目标接近中心, 直行
            self.motor.move_forward(self.base_duty)
        else:
            # 差速转向
            inner_duty = max(self.config.MOTOR_DUTY_MIN,
                             self.base_duty - int(abs(turn_amount) * 20))
            outer_duty = min(self.config.MOTOR_DUTY_MAX,
                             self.base_duty + int(abs(turn_amount) * 20))

            if turn_amount > 0:
                self.motor.steer(self.motor.RIGHT, inner_duty, outer_duty)
            else:
                self.motor.steer(self.motor.LEFT, inner_duty, outer_duty)

            logger.debug("追踪: offset=%+d PID=%.1f inner=%d outer=%d",
                         offset, turn_amount, inner_duty, outer_duty)

    def _do_approach(self, offset: int, distance: float):
        """接近模式: 缓慢靠近目标, 到达后停车"""
        if 0 < distance < self.stop_dist:
            logger.info("已到达目标! 距离 %.1f cm", distance)
            self.state = NavState.STOP
            self.motor.stop()
            self.motor.buzzer_beep(100)
            return

        # 微调方向 + 慢速前进
        if abs(offset) > self.turn_threshold // 2:
            self._do_track(offset)
        else:
            self.motor.move_forward(self.slow_duty)

    # ========================================================================
    # 辅助方法
    # ========================================================================

    def reset(self):
        """重置导航状态"""
        self.state = NavState.SEARCH
        self._target_lost_count = 0
        self.pid.reset()
        self.motor.clear_leds()
        logger.info("导航状态已重置 - SEARCH")

    def emergency_stop(self):
        """紧急停车"""
        self.state = NavState.STOP
        self.motor.stop()
        self.motor.buzzer_on()
        logger.warning("紧急停车!")

    @property
    def is_stopped(self) -> bool:
        return self.state == NavState.STOP
