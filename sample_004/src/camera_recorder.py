from dataclasses import dataclass
from pathlib import Path

import cv2


@dataclass
class CameraConfig:
    device: int
    output_path: Path
    width: int = 640
    height: int = 480
    fps: float = 30.0
    codec: str = "mp4v"


class CameraRecorder:
    def __init__(self, config: CameraConfig):
        self.config = config
        self.cap = None
        self.writer = None

    def open(self):
        self.config.output_path.parent.mkdir(parents=True, exist_ok=True)

        self.cap = cv2.VideoCapture(self.config.device)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.config.width)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.config.height)
        self.cap.set(cv2.CAP_PROP_FPS, self.config.fps)

        if not self.cap.isOpened():
            self.close()
            raise RuntimeError(f"Could not open camera {self.config.device}")

        fourcc = cv2.VideoWriter_fourcc(*self.config.codec)
        self.writer = cv2.VideoWriter(
            str(self.config.output_path),
            fourcc,
            self.config.fps,
            (self.config.width, self.config.height),
        )

        if not self.writer.isOpened():
            self.close()
            raise RuntimeError(f"Could not open video writer: {self.config.output_path}")

    def write_one_frame(self) -> bool:
        if self.cap is None or self.writer is None:
            raise RuntimeError("Camera is not opened.")

        ret, frame = self.cap.read()
        if not ret:
            return False

        self.writer.write(frame)
        return True

    def close(self):
        if self.cap is not None:
            self.cap.release()
            self.cap = None

        if self.writer is not None:
            self.writer.release()
            self.writer = None

    @staticmethod
    def check_device(max_devices: int = 10):
        for i in range(max_devices):
            cap = cv2.VideoCapture(i)
            if cap.isOpened():
                print(f"Camera {i}: available")
                cap.release()


def record_multiple_cameras(configs: list[CameraConfig]):
    recorders = [CameraRecorder(config) for config in configs]

    try:
        for recorder in recorders:
            recorder.open()

        print("Started recording video. Ctrl+C to stop.")
        for recorder in recorders:
            print(f"    Camera {recorder.config.device} -> {recorder.config.output_path}")

        while True:
            for recorder in recorders:
                if not recorder.write_one_frame():
                    print(f"Failed to read frame from camera {recorder.config.device}.")
                    return

    except KeyboardInterrupt:
        print("\nKeyboardInterrupt received. Stopping video recording...")

    finally:
        for recorder in recorders:
            recorder.close()


if __name__ == "__main__":
    
    CameraRecorder.check_device(max_devices=5)

    configs = [
        CameraConfig(device=1, output_path=Path("output\\cam1.mp4")),
        CameraConfig(device=2, output_path=Path("output\\cam2.mp4")),
    ]

    record_multiple_cameras(configs)
