"""Tests for config module values."""

import config


class TestConfig:
    def test_motor_duty_base_exists(self):
        assert hasattr(config, "MOTOR_DUTY_BASE")

    def test_motor_duty_base_in_range(self):
        assert 0 <= config.MOTOR_DUTY_BASE <= 4096

    def test_stop_distance_cm_exists(self):
        assert hasattr(config, "STOP_DISTANCE_CM")
        assert config.STOP_DISTANCE_CM > 0

    def test_pid_params_exist_and_numeric(self):
        assert isinstance(config.PID_KP, (int, float))
        assert isinstance(config.PID_KI, (int, float))
        assert isinstance(config.PID_KD, (int, float))

    def test_color_presets_exists(self):
        assert hasattr(config, "COLOR_PRESETS")
        assert isinstance(config.COLOR_PRESETS, dict)

    def test_color_presets_has_required_colors(self):
        presets = config.COLOR_PRESETS
        for color in ["red", "blue", "green", "yellow"]:
            assert color in presets, f"Missing color preset: {color}"

    def test_color_presets_have_valid_hsv_ranges(self):
        presets = config.COLOR_PRESETS
        for color_name, preset in presets.items():
            # Each preset must have lower1/upper1
            assert "lower1" in preset
            assert "upper1" in preset
            lower1 = preset["lower1"]
            upper1 = preset["upper1"]
            assert len(lower1) == 3, f"{color_name} lower1 length != 3"
            assert len(upper1) == 3, f"{color_name} upper1 length != 3"
            # HSV values must be in valid range
            # H: 0-180, S: 0-255, V: 0-255
            assert 0 <= lower1[0] <= 180
            assert 0 <= upper1[0] <= 180

    def test_motor_duty_max_exists(self):
        assert hasattr(config, "MOTOR_DUTY_MAX")
        assert config.MOTOR_DUTY_MAX > 0

    def test_frame_center_x_is_numeric(self):
        assert isinstance(config.FRAME_CENTER_X, int)
        assert config.FRAME_CENTER_X > 0

    def test_product_name_exists(self):
        assert hasattr(config, "PRODUCT_NAME")
        assert len(config.PRODUCT_NAME) > 0
