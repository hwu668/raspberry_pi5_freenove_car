"""Tests for PIDController and Navigation state machine."""



from navigation import Navigation, NavState, PIDController


class MockMotor:
    """Mock MotorControl for testing Navigation without hardware."""

    FORWARD = "forward"
    BACKWARD = "backward"
    LEFT = "left"
    RIGHT = "right"
    STOP = "stop"

    def __init__(self):
        self.commands: list[str] = []
        self.mock_distance = 999.0
        self.duty_base = 2000
        self.current_command = "stop"
        self.mock_active = True

    def get_distance_cm(self) -> float:
        return self.mock_distance

    def stop(self):
        self.commands.append("stop")
        self.current_command = "stop"

    def move_forward(self, duty=None):
        self.commands.append(f"forward({duty})")
        self.current_command = "forward"

    def turn_left(self, duty=None):
        self.commands.append(f"turn_left({duty})")
        self.current_command = "left"

    def turn_right(self, duty=None):
        self.commands.append(f"turn_right({duty})")
        self.current_command = "right"

    def steer(self, direction, inner_duty, outer_duty):
        self.commands.append(f"steer({direction},{inner_duty},{outer_duty})")
        self.current_command = direction

    def led_indicator(self, state: str):
        self.commands.append(f"led({state})")

    def clear_leds(self):
        self.commands.append("clear_leds")

    def buzzer_on(self):
        self.commands.append("buzzer_on")

    def buzzer_beep(self, ms=200):
        self.commands.append(f"buzzer_beep({ms})")

    def get_last_command(self) -> str:
        return self.commands[-1] if self.commands else ""


class MockConfig:
    """Minimal config for Navigation tests."""

    FRAME_CENTER_X = 320
    TURN_THRESHOLD = 50
    APPROACH_DISTANCE_CM = 20
    STOP_DISTANCE_CM = 10
    MAIN_LOOP_DELAY = 0.05
    MAX_LOST_FRAMES = 30
    MOTOR_DUTY_BASE = 2000
    MOTOR_DUTY_SLOW = 1200
    MOTOR_DUTY_MIN = 800
    MOTOR_DUTY_MAX = 4096
    PID_KP = 0.08
    PID_KI = 0.005
    PID_KD = 0.02


class MockTarget:
    """Mock TargetInfo for testing Navigation."""

    def __init__(self, found=True, center_x=320, distance_estimate=50.0):
        self.found = found
        self.center_x = center_x
        self.center_y = 240
        self.width = 80
        self.height = 80
        self.area = 6400.0
        self.distance_estimate = distance_estimate
        self.label = "test_target"
        self.confidence = 0.9
        self.contour = None

    def offset_from_center(self, frame_center_x: int) -> int:
        return self.center_x - frame_center_x


# ========================================================================
# PIDController tests
# ========================================================================


class TestPIDController:
    def test_pid_output_is_numeric(self):
        pid = PIDController(kp=1.0, ki=0.0, kd=0.0)
        output = pid.update(error=10)
        assert isinstance(output, (int, float))

    def test_pid_positive_error_positive_output(self):
        pid = PIDController(kp=1.0, ki=0.0, kd=0.0)
        assert pid.update(error=10) > 0

    def test_pid_negative_error_negative_output(self):
        pid = PIDController(kp=1.0, ki=0.0, kd=0.0)
        assert pid.update(error=-10) < 0

    def test_pid_zero_error_near_zero_output(self):
        pid = PIDController(kp=1.0, ki=0.0, kd=0.0)
        # With no integral/differential, zero error => zero output
        output = pid.update(error=0)
        assert abs(output) < 1e-6

    def test_pid_integral_does_not_explode(self):
        pid = PIDController(kp=0.5, ki=0.1, kd=0.01)
        for _ in range(100):
            output = pid.update(error=100)
            assert -100.0 <= output <= 100.0

    def test_pid_reset_clears_state(self):
        pid = PIDController(kp=1.0, ki=0.1, kd=0.0)
        pid.update(error=50)
        pid.update(error=50)
        pid.reset()
        # After reset, output should be small for zero error
        output = pid.update(error=0)
        assert abs(output) < 10.0

    def test_pid_output_clamped(self):
        pid = PIDController(kp=10.0, ki=0.0, kd=0.0, output_limit=50.0)
        output = pid.update(error=100)
        assert output <= 50.0

    def test_pid_very_small_dt_does_not_crash(self):
        pid = PIDController(kp=1.0, ki=0.1, kd=0.01)
        # Rapid calls should not crash
        for _ in range(10):
            pid.update(error=5)
        assert True  # no crash


# ========================================================================
# Navigation state machine tests
# ========================================================================


class TestNavigationStateMachine:
    def make_nav(self, mock_distance=999.0):
        config = MockConfig()
        motor = MockMotor()
        motor.mock_distance = mock_distance
        nav = Navigation(config, motor)
        return nav, motor

    def test_no_target_enters_search(self):
        nav, motor = self.make_nav()
        target = MockTarget(found=False)
        # Need enough frames to exceed MAX_LOST_FRAMES
        for _ in range(31):
            state = nav.update(target)
        assert state == NavState.SEARCH.name

    def test_target_found_enters_track(self):
        nav, motor = self.make_nav()
        target = MockTarget(found=True, center_x=320, distance_estimate=50.0)
        state = nav.update(target)
        assert state in (NavState.TRACK.name, NavState.APPROACH.name)

    def test_ultrasonic_below_stop_dist_stops(self):
        nav, motor = self.make_nav(mock_distance=5.0)
        target = MockTarget(found=True, center_x=320)
        state = nav.update(target)
        assert state == NavState.STOP.name
        assert "stop" in motor.commands

    def test_target_lost_returns_to_search(self):
        nav, motor = self.make_nav()
        # First find target
        target = MockTarget(found=True, center_x=320)
        nav.update(target)
        # Then lose it for many frames
        target.found = False
        for _ in range(35):
            nav.update(target)
        assert nav.state == NavState.SEARCH

    def test_reset_goes_to_search(self):
        nav, motor = self.make_nav()
        target = MockTarget(found=True, center_x=320)
        nav.update(target)
        nav.reset()
        assert nav.state == NavState.SEARCH
        assert "clear_leds" in motor.commands

    def test_emergency_stop(self):
        nav, motor = self.make_nav()
        nav.emergency_stop()
        assert nav.state == NavState.STOP
        assert nav.is_stopped
        assert "stop" in motor.commands

    def test_approach_when_centered_and_close(self):
        nav, motor = self.make_nav(mock_distance=15.0)
        target = MockTarget(found=True, center_x=320, distance_estimate=15.0)
        state = nav.update(target)
        # Distance 15 < APPROACH_DISTANCE_CM (20) and centered => APPROACH
        assert state == NavState.APPROACH.name
