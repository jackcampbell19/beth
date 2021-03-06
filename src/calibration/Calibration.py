import cv2
import numpy as np
import os
import pathlib
import time
import json

from sys import argv, path
src = pathlib.Path(__file__).parent.absolute().parent.absolute()
path.append(str(src.parent.absolute()))

from src.misc.Helpers import draw_markers
from src.misc.Log import log
from src.tracking.Marker import Marker


CALIBRATION_DIR = pathlib.Path(__file__)\
    .parent.absolute()\
    .parent.absolute()\
    .parent.joinpath('runtime')\
    .joinpath('calibration').absolute()

def calibrate_distortion_correction_k_d(image_dir, checkerboard_dimensions=(6, 9)):
    sub_pix_criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.1)
    calibration_flags = \
        cv2.fisheye.CALIB_RECOMPUTE_EXTRINSIC + cv2.fisheye.CALIB_CHECK_COND + cv2.fisheye.CALIB_FIX_SKEW
    obj_p = np.zeros((1, checkerboard_dimensions[0] * checkerboard_dimensions[1], 3), np.float32)
    obj_p[0, :, :2] = np.mgrid[0:checkerboard_dimensions[0], 0:checkerboard_dimensions[1]].T.reshape(-1, 2)
    img_shape = None
    obj_points = []  # 3d point in real world space
    img_points = []  # 2d points in image plane.
    images = os.listdir(image_dir)
    images = list(filter(lambda x: 'cam-dis' in x, images))
    images = list(map(lambda x: str(CALIBRATION_DIR.joinpath(x).absolute()), images))
    prop_sh = None
    for f_name in images:
        img = cv2.imread(f_name)
        if img_shape is None:
            img_shape = img.shape[:2]
        else:
            assert img_shape == img.shape[:2], "All images must share the same size."
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        prop_sh = gray.shape[::-1]
        # Find the chess board corners
        ret, corners = cv2.findChessboardCorners(
            gray,
            checkerboard_dimensions,
            cv2.CALIB_CB_ADAPTIVE_THRESH + cv2.CALIB_CB_FAST_CHECK + cv2.CALIB_CB_NORMALIZE_IMAGE
        )
        # If found, add object points, image points (after refining them)
        if ret:
            obj_points.append(obj_p)
            cv2.cornerSubPix(gray, corners, (3, 3), (-1, -1), sub_pix_criteria)
            img_points.append(corners)
    if prop_sh is None:
        print('No images read.')
        return
    n_ok = len(obj_points)
    k = np.zeros((3, 3))
    d = np.zeros((4, 1))
    r_vecs = [np.zeros((1, 1, 3), dtype=np.float64) for i in range(n_ok)]
    t_vecs = [np.zeros((1, 1, 3), dtype=np.float64) for i in range(n_ok)]
    rms, _, _, _, _ = \
        cv2.fisheye.calibrate(
            obj_points,
            img_points,
            prop_sh,
            k,
            d,
            r_vecs,
            t_vecs,
            calibration_flags,
            (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 1e-6)
        )
    print("Found " + str(n_ok) + " valid images for calibration")
    print("k=" + str(k.tolist()))
    print("d=" + str(d.tolist()))


def calculate_fid_correction_coefficients(frame_center):
    top_img = CALIBRATION_DIR.joinpath('fcc-top.jpg')
    base_img = CALIBRATION_DIR.joinpath('fcc-base.jpg')
    if not top_img.exists() or not base_img.exists():
        log.error('Missing calibration images.')
        return
    top_frame = cv2.imread(str(top_img.absolute()))
    base_frame = cv2.imread(str(base_img.absolute()))
    top_markers = Marker.extract_markers(top_frame, marker_family=Marker.FAMILY_tag16h5, scan_for_inverted_markers=True)
    valid_markers = ['0', '1', '2', '3', '4', '6', '14', '15', '16', '17', '19', '24']
    top_markers = list(filter(lambda m: np.linalg.norm(frame_center - m.center) < 600 and m.id in valid_markers, top_markers))
    base_markers = Marker.extract_markers(base_frame, marker_family=Marker.FAMILY_tag16h5, scan_for_inverted_markers=True)
    base_markers = list(filter(lambda m: np.linalg.norm(frame_center - m.center) < 600 and m.id in valid_markers, base_markers))
    draw_markers(top_frame, top_markers)
    draw_markers(base_frame, base_markers)
    cv2.imshow('top', top_frame)
    cv2.imshow('base', base_frame)
    cv2.waitKey()
    present_top_marker_ids = [m.id for m in top_markers]
    present_base_marker_ids = [m.id for m in base_markers]
    if len(present_top_marker_ids) == 0 \
            or len(set(present_top_marker_ids)) != len(present_top_marker_ids)\
            or set(present_base_marker_ids) != set(present_top_marker_ids):
        log.error('Marker images are not valid or do not appear consistent.')
        return
    fcc = {}
    for tm in top_markers:
        bm = [m for m in base_markers if m.id == tm.id][0]
        bv = bm.center - frame_center
        tv = tm.center - frame_center
        x = bv[0] / tv[0]
        y = bv[1] / tv[1]
        fcc[tm.id] = (x + y) / 2
    log.info(f"FCC:\n{json.dumps(fcc)}")


if __name__ == '__main__':
    if '--camera-distortion' in argv:
        calibrate_distortion_correction_k_d(str(CALIBRATION_DIR.absolute()))
