"""Tests for ImageRecognition color detection using synthetic numpy images."""

import numpy as np

from image_recognition import ImageRecognition


class MockConfig:
    """Minimal config for ImageRecognition tests."""

    GAUSSIAN_BLUR_KERNEL = (5, 5)
    MORPH_KERNEL_SIZE = (5, 5)
    MIN_CONTOUR_AREA = 500
    FRAME_CENTER_X = 320
    FRAME_CENTER_Y = 240
    USE_DNN_MODEL = False
    COLOR_TARGET_LOWER = [0, 100, 100]
    COLOR_TARGET_UPPER = [10, 255, 255]
    COLOR_TARGET_LOWER2 = [160, 100, 100]
    COLOR_TARGET_UPPER2 = [180, 255, 255]


def make_blank_frame(width=640, height=480) -> np.ndarray:
    """Create a black frame."""
    return np.zeros((height, width, 3), dtype=np.uint8)


def make_red_rect_frame(width=640, height=480) -> np.ndarray:
    """Create a black frame with a red rectangle in the center."""
    frame = np.zeros((height, width, 3), dtype=np.uint8)
    # Red in BGR is (0, 0, 255)
    cx, cy = width // 2, height // 2
    half_w, half_h = 40, 40
    frame[cy - half_h:cy + half_h, cx - half_w:cx + half_w] = (0, 0, 255)
    return frame


def make_red_circle_frame(width=640, height=480) -> np.ndarray:
    """Create a black frame with a red circle in the center."""
    import cv2

    frame = np.zeros((height, width, 3), dtype=np.uint8)
    cv2.circle(frame, (width // 2, height // 2), 40, (0, 0, 255), -1)
    return frame


class TestImageRecognition:
    def make_recognizer(self):
        config = MockConfig()
        return ImageRecognition(config)

    def test_blank_frame_no_target(self):
        rec = self.make_recognizer()
        frame = make_blank_frame()
        target = rec.detect(frame)
        assert not target.found

    def test_red_rect_detected(self):
        rec = self.make_recognizer()
        frame = make_red_rect_frame()
        target = rec.detect(frame)
        assert target.found
        assert target.label == "color_target"

    def test_red_rect_center_near_middle(self):
        rec = self.make_recognizer()
        frame = make_red_rect_frame()
        target = rec.detect(frame)
        assert target.found
        # Center should be within 10% of frame center
        assert abs(target.center_x - 320) < 64
        assert abs(target.center_y - 240) < 48

    def test_red_circle_detected(self):
        rec = self.make_recognizer()
        frame = make_red_circle_frame()
        target = rec.detect(frame)
        assert target.found

    def test_target_has_valid_area(self):
        rec = self.make_recognizer()
        frame = make_red_rect_frame()
        target = rec.detect(frame)
        assert target.found
        assert target.area > 0

    def test_target_has_distance_estimate(self):
        rec = self.make_recognizer()
        frame = make_red_rect_frame()
        target = rec.detect(frame)
        assert target.found
        assert target.distance_estimate > 0

    def test_offset_from_center(self):
        rec = self.make_recognizer()
        frame = make_red_rect_frame()
        target = rec.detect(frame)
        assert target.found
        offset = target.offset_from_center(320)
        # Should be near zero for centered target
        assert abs(offset) < 80

    def test_small_frame_no_crash(self):
        rec = self.make_recognizer()
        frame = np.zeros((100, 100, 3), dtype=np.uint8)
        target = rec.detect(frame)
        assert not target.found  # no red object in blank
