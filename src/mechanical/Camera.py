import cv2
import numpy as np
from src.misc.Exceptions import *
from src.misc.Helpers import save_frame_to_runtime_dir

from src.misc.Log import log


class Camera:
    """
    The {Camera} class is a wrapper for the {VideoCapture} camera from cv2. This
    class does additional computation when reading frames and initializing.
    """

    def __init__(self, camera_index, frame_size, k, d, frame_center=None):
        """
        Initializes the {Camera} object.
        :param camera_index: The index of the camera to read from.
        :param frame_size: [width, height]
        :param k: Distortion correction k variable.
        :param d: Distortion correction d variable.
        """
        self.frame_size = tuple(frame_size)
        self.index = camera_index
        self.k = np.array(k)
        self.d = np.array(d)
        self.mock_frame_path = None
        self.latest_frame = None
        if frame_center is None:
            self.frame_center = np.array([self.frame_size[0] / 2, self.frame_size[1] / 2])
        else:
            self.frame_center = np.array(frame_center)
        self.exposure = None

    def generate_camera(self, exposure=None):
        """
        Generates and returns a new camera instance.
        :return:
        """
        camera = cv2.VideoCapture(self.index)
        camera.set(cv2.CAP_PROP_FRAME_WIDTH, self.frame_size[0])
        camera.set(cv2.CAP_PROP_FRAME_HEIGHT, self.frame_size[1])
        camera.set(cv2.CAP_PROP_BUFFERSIZE, 3)
        e = camera.get(cv2.CAP_PROP_EXPOSURE)
        if exposure is not None:
            camera.set(cv2.CAP_PROP_AUTO_EXPOSURE, 0.25)
            camera.set(cv2.CAP_PROP_EXPOSURE, exposure)
        self.exposure = camera.get(cv2.CAP_PROP_EXPOSURE)
        for _ in range(25):
            _, _ = camera.read()
        return camera

    def correct_distortion(self, frame):
        """
        Corrects distortion due to curved lenses using the distortion variables 'k' and 'd'.
        :param frame: The frame to correct.
        :return: The corrected frame.
        """
        log.info('Correcting camera distortion on frame.')
        new_k = cv2.fisheye.estimateNewCameraMatrixForUndistortRectify(self.k,
                                                                       self.d,
                                                                       self.
                                                                       frame_size,
                                                                       np.eye(3),
                                                                       balance=1)
        m1, m2 = cv2.fisheye.initUndistortRectifyMap(self.k,
                                                     self.d,
                                                     np.eye(3),
                                                     new_k,
                                                     self.frame_size,
                                                     cv2.CV_32FC1)
        undistorted_img = cv2.remap(frame, m1, m2, interpolation=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT)
        return undistorted_img

    def capture_frame(self, correct_distortion=True, exposure=None):
        """
        Captures a raw RGB color frame from the camera. Corrects distortion if necessary.
        :param correct_distortion: Tell the function if it should correct for distortion.
        :param exposure: Exposure to capture.
        :return: np array of pixel data
        """
        if self.mock_frame_path is not None:
            log.debug('Camera returning a mock frame in place of the captured image.')
            frame = cv2.imread(self.mock_frame_path)
            self.latest_frame = frame
            return frame
        log.info('Warming camera up.')
        camera = self.generate_camera(exposure)
        log.info(f"Capturing frame from camera with"
                 f"{'' if correct_distortion else ' no'} distortion correction.")
        ret, frame = camera.read()
        if not ret:
            raise CameraError('Failed to read from from camera.')
        camera.release()
        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        if correct_distortion:
            frame = self.correct_distortion(frame)
        self.latest_frame = frame
        return frame

    @staticmethod
    def adjust_frame_contrast_and_brightness(frame, contrast=1, brightness=0):
        if not 1 <= contrast <= 3:
            log.error(f"Contrast must be between 1 and 3. Provided {contrast}")
        return cv2.convertScaleAbs(frame, alpha=contrast, beta=brightness)

    @staticmethod
    def blur_frame(frame, amount):
        return cv2.blur(frame, (amount, amount))

    @staticmethod
    def invert_colors(frame):
        return cv2.bitwise_not(frame)
