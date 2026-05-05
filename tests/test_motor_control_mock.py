"""Tests for MotorControl mock mode."""


class MockConfig:
    """Minimal config for MotorControl mock tests."""

    MOTOR_DUTY_BASE = 2000
    MOTOR_DUTY_TURN = 2000
    MOTOR_DUTY_SLOW = 1200
    MOTOR_DUTY_MAX = 4096
    MOTOR_DUTY_MIN = 800
    SERVO_PAN_MIN_ANGLE = 0
    SERVO_PAN_MAX_ANGLE = 180
    SERVO_PAN_DEFAULT = 90
    SERVO_TILT_MIN_ANGLE = 80
    SERVO_TILT_MAX_ANGLE = 150
    SERVO_TILT_DEFAULT = 115
    SERVO0_PWM_MIN = 50
    SERVO0_PWM_MAX = 110
    SERVO1_PWM_MIN = 80
    SERVO1_PWM_MAX = 150
    ULTRASONIC_TRIG_PIN = 23
    ULTRASONIC_ECHO_PIN = 24
    BUZZER_PIN = 8
    LED_COUNT = 8
    LED_SPI_DEVICE = "/dev/spidev0.0"
    LED_SPI_SPEED_HZ = 800000


class TestMotorControlMock:
    def make_motor(self, mode="mock"):
        from motor_control import MotorControl

        config = MockConfig()
        return MotorControl(config, mode=mode)

    def test_mock_init_no_crash(self):
        motor = self.make_motor("mock")
        assert motor is not None

    def test_mock_setup_succeeds(self):
        motor = self.make_motor("mock")
        result = motor.setup()
        assert result is True
        assert motor.mock_active is True
        assert motor.mode == "mock"

    def test_mock_move_forward_no_crash(self):
        motor = self.make_motor("mock")
        motor.setup()
        motor.move_forward()
        assert motor.current_command == "forward"

    def test_mock_move_backward_no_crash(self):
        motor = self.make_motor("mock")
        motor.setup()
        motor.move_backward()
        assert motor.current_command == "backward"

    def test_mock_turn_left_no_crash(self):
        motor = self.make_motor("mock")
        motor.setup()
        motor.turn_left()
        assert motor.current_command == "left"

    def test_mock_turn_right_no_crash(self):
        motor = self.make_motor("mock")
        motor.setup()
        motor.turn_right()
        assert motor.current_command == "right"

    def test_mock_stop_no_crash(self):
        motor = self.make_motor("mock")
        motor.setup()
        motor.stop()
        assert motor.current_command == "stop"

    def test_mock_steer_no_crash(self):
        motor = self.make_motor("mock")
        motor.setup()
        motor.steer(motor.LEFT, 1000, 2000)
        assert motor.current_command == "left"

    def test_mock_servo_no_crash(self):
        motor = self.make_motor("mock")
        motor.setup()
        motor.set_pan_angle(90)
        motor.set_tilt_angle(115)
        motor.center_servos()

    def test_mock_cleanup_no_crash(self):
        motor = self.make_motor("mock")
        motor.setup()
        motor.cleanup()

    def test_mock_get_distance(self):
        motor = self.make_motor("mock")
        motor.setup()
        dist = motor.get_distance_cm()
        assert dist == 999.0  # Mock always returns 999

    def test_mock_led_no_crash(self):
        motor = self.make_motor("mock")
        motor.setup()
        motor.set_led(0, 255, 0, 0)
        motor.led_indicator("SEARCH")
        motor.clear_leds()

    def test_mock_buzzer_no_crash(self):
        motor = self.make_motor("mock")
        motor.setup()
        motor.buzzer_on()
        motor.buzzer_off()
        motor.buzzer_beep(50)

    def test_hardware_mode_missing_libs_fails(self):
        motor = self.make_motor("hardware")
        result = motor.setup()
        assert result is False
        assert len(motor.initialization_errors) > 0

    def test_auto_mode_falls_back_to_mock(self):
        motor = self.make_motor("auto")
        result = motor.setup()
        assert result is True
        assert motor.mock_active is True

    def test_initialization_errors_list(self):
        motor = self.make_motor("hardware")
        motor.setup()
        assert isinstance(motor.initialization_errors, list)

    def test_mode_property(self):
        motor = self.make_motor("mock")
        assert motor.mode == "mock"
