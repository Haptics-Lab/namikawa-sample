from pathlib import Path

from src.camera_recorder import CameraConfig, record_multiple_cameras


def main():

    configs = [
        CameraConfig(device=1, output_path=Path("output\\cam1.mp4")),
        CameraConfig(device=2, output_path=Path("output\\cam2.mp4")),
    ]

    record_multiple_cameras(configs)
