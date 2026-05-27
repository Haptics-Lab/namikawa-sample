from dataclasses import dataclass
from pathlib import Path
import threading
import csv
import time

import cv2


@dataclass
class CameraConfig:
    device: int
    width: int = 640
    height: int = 480
    fps: float = 30.0
    codec: str = "mp4v"


class CameraRecorder:
    def __init__(self, config: CameraConfig):
        self.config = config
        self.cap = None
        self.writer = None
        self.timestamp_file = None
        self.timestamp_writer = None
        self.frame_index = 0

    def open(self, output_path: Path):
        self.output_path = output_path
        output_path.parent.mkdir(parents=True, exist_ok=True)

        self.cap = cv2.VideoCapture(self.config.device)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.config.width)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.config.height)
        self.cap.set(cv2.CAP_PROP_FPS, self.config.fps)

        if not self.cap.isOpened():
            self.close()
            raise RuntimeError(f"Could not open camera {self.config.device}")

        fourcc = cv2.VideoWriter_fourcc(*self.config.codec)
        self.writer = cv2.VideoWriter(
            str(output_path),
            fourcc,
            self.config.fps,
            (self.config.width, self.config.height),
        )

        if not self.writer.isOpened():
            self.close()
            raise RuntimeError(f"Could not open video writer: {output_path}")

        timestamp_path = output_path.with_name(f"{output_path.stem}_timestamps.csv")
        self.timestamp_file = timestamp_path.open("w", newline="", encoding="utf-8")
        self.timestamp_writer = csv.writer(self.timestamp_file)
        self.timestamp_writer.writerow(["Frame Index", "Wall Clock [s]", "Perf Counter [ns]"])
        self.frame_index = 0

    def write_one_frame(self) -> bool:
        if self.cap is None or self.writer is None or self.timestamp_writer is None:
            raise RuntimeError("Camera is not opened.")

        ret, frame = self.cap.read()
        if not ret:
            return False

        wallclock_ns = time.time_ns()
        wallclock = wallclock_ns / 1e9
        perf_counter = time.perf_counter_ns()

        self.writer.write(frame)
        self.timestamp_writer.writerow([self.frame_index, wallclock, perf_counter])
        self.frame_index += 1
        return True

    def close(self):
        if self.cap is not None:
            self.cap.release()
            self.cap = None

        if self.writer is not None:
            self.writer.release()
            self.writer = None

        if self.timestamp_file is not None:
            self.timestamp_file.close()
            self.timestamp_file = None
            self.timestamp_writer = None

    @staticmethod
    def check_device(max_devices: int = 10):
        for i in range(max_devices):
            cap = cv2.VideoCapture(i)
            if cap.isOpened():
                print(f"Camera {i}: available")
                cap.release()


class MultiCameraRecorder:

    def __init__(self, configs: list[CameraConfig]):
        self.configs = configs

    def record(
            self,
            output_folder: Path,
            stop_event: threading.Event,
            started_event: threading.Event
            ):
        
        recorders = [CameraRecorder(config) for config in self.configs]

        try:
            for recorder in recorders:
                output_path = output_folder / f"cam{recorder.config.device}.mp4"
                recorder.open(output_path)

            print("Started recording mfa video.")
            for recorder in recorders:
                print(f"    Camera {recorder.config.device} -> {recorder.output_path}")
                print(
                    f"    Camera {recorder.config.device} timestamps -> "
                    f"{recorder.output_path.with_name(f'{recorder.output_path.stem}_timestamps.csv')}"
                )

            started_event.set()

            while not stop_event.is_set():
                for recorder in recorders:
                    if not recorder.write_one_frame():
                        print(f"Failed to read frame from camera {recorder.config.device}.")
                        stop_event.set()
                        break

        finally:
            for recorder in recorders:
                recorder.close()
            print("Stopped mfa video recording.")


if __name__ == "__main__":
    
    CameraRecorder.check_device(max_devices=5)

    multi_camera_recorder = MultiCameraRecorder(configs=[
        CameraConfig(device=0, width=640, height=480, fps=30),
        CameraConfig(device=2, width=640, height=480, fps=30),
        CameraConfig(device=3, width=640, height=480, fps=30),
    ])

    started_event = threading.Event()
    stop_event = threading.Event()
    thread = threading.Thread(
        target=multi_camera_recorder.record,
        kwargs={
            "output_folder": Path("output") / "test" / "mfa",
            "stop_event": stop_event,
            "started_event": started_event,
        },
    )

    thread.start()
    started_event.wait()

    try:
        input("Press Enter to stop recording...\n")
    finally:
        stop_event.set()
        thread.join()
