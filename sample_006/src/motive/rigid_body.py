from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
import threading
import csv
import time

from src.motive.natnet_stream import NatNetConfig, run_natnet_stream


Vector3 = tuple[float, float, float]
Quaternion = tuple[float, float, float, float]


@dataclass(frozen=True)
class RigidBodyFrame:
    rigid_body_id: int
    position: Vector3
    rotation: Quaternion


@dataclass(frozen=True)
class RigidBodySample:
    wallclock_timestamp: float
    perf_timestamp: int
    motive_timestamp: Optional[float]
    position: Vector3
    rotation: Quaternion


class RigidBodyReceiver:
    def __init__(self, config: NatNetConfig):
        self.config = config

    @staticmethod
    def _normalize_name(raw_name: object) -> str:
        if isinstance(raw_name, bytes):
            return raw_name.decode("utf-8", errors="replace")
        return str(raw_name) if raw_name else ""

    @classmethod
    def get_rigid_body_names(cls, frame: dict) -> dict[int, str]:
        data_descriptions = frame.get("data_descriptions")
        rigid_body_list = getattr(data_descriptions, "rigid_body_list", None)
        if rigid_body_list is None:
            return {}

        names_by_id = {}
        for desc in rigid_body_list:
            rigid_body_id = getattr(desc, "id_num", None)
            if not isinstance(rigid_body_id, int):
                continue

            name = cls._normalize_name(getattr(desc, "sz_name", None))
            if name:
                names_by_id[rigid_body_id] = name

        return names_by_id

    @staticmethod
    def build_frame(
            rigid_body_id: int,
            position: tuple[float, float, float],
            rotation: tuple[float, float, float, float],
            ) -> RigidBodyFrame:
        return RigidBodyFrame(
            rigid_body_id=rigid_body_id,
            position=tuple(position),
            rotation=tuple(rotation),
        )

    @staticmethod
    def print_rigid_bodies(rigid_bodies: list[RigidBodyFrame]) -> None:
        for rigid_body in rigid_bodies:
            print(
                f"id={rigid_body.rigid_body_id} "
                f"pos=({rigid_body.position[0]:.3f}, {rigid_body.position[1]:.3f}, {rigid_body.position[2]:.3f}) "
                f"rot=({rigid_body.rotation[0]:.3f}, {rigid_body.rotation[1]:.3f}, {rigid_body.rotation[2]:.3f}, {rigid_body.rotation[3]:.3f})"
            )

    @classmethod
    def parse_frame(cls, frame: dict) -> list[RigidBodyFrame]:
        mocap_data = frame.get("mocap_data")
        rigid_body_data = getattr(mocap_data, "rigid_body_data", None)
        rigid_body_list = getattr(rigid_body_data, "rigid_body_list", None)
        if rigid_body_list is None:
            return []

        rigid_bodies = []
        for rigid_body in rigid_body_list:
            rigid_bodies.append(
                cls.build_frame(
                    rigid_body_id=int(rigid_body.id_num),
                    position=tuple(rigid_body.pos),
                    rotation=tuple(rigid_body.rot),
                )
            )
        return rigid_bodies

    @staticmethod
    def _get_timestamps(frame: dict) -> tuple[float, int, Optional[float]]:
        received_time_ns = frame.get("received_time_ns")
        received_perf_counter_ns = frame.get("received_perf_counter_ns")
        wallclock = (
            received_time_ns / 1e9
            if isinstance(received_time_ns, int) and received_time_ns >= 0
            else time.time()
        )
        perf = (
            received_perf_counter_ns
            if isinstance(received_perf_counter_ns, int) and received_perf_counter_ns >= 0
            else time.perf_counter_ns()
        )

        timestamp = frame.get("timestamp")
        motive = float(timestamp) if isinstance(timestamp, (int, float)) and timestamp >= 0 else None
        return wallclock, perf, motive

    @staticmethod
    def create_csv(path: Path) -> None:
        with path.open("w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow(
                [
                    "Motive Time",
                    "Wall Clock [s]",
                    "Perf Counter [ns]",
                    "x",
                    "y",
                    "z",
                    "qx",
                    "qy",
                    "qz",
                    "qw",
                ]
            )

    @staticmethod
    def append_samples(path: Path, samples: list[RigidBodySample]) -> None:
        with path.open("a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            for sample in samples:
                writer.writerow(
                    [
                        sample.motive_timestamp,
                        sample.wallclock_timestamp,
                        sample.perf_timestamp,
                        sample.position[0],
                        sample.position[1],
                        sample.position[2],
                        sample.rotation[0],
                        sample.rotation[1],
                        sample.rotation[2],
                        sample.rotation[3],
                    ]
                )

    def stream(
            self,
            stop_event: threading.Event,
            started_event: threading.Event,
            print_enabled: bool = False,
            csv_folder_path: Optional[Path] = None,
            csv_batch_frames: int = 30,
            ) -> None:

        if csv_folder_path is not None:
            csv_folder_path.mkdir(parents=True, exist_ok=True)

        csv_paths_by_id: dict[int, Path] = {}
        rigid_body_names_by_id: dict[int, str] = {}
        pending_samples: dict[int, list[RigidBodySample]] = defaultdict(list)
        pending_frame_count = 0

        def flush_pending() -> None:
            nonlocal pending_frame_count
            if csv_folder_path is None:
                return

            for rigid_body_id, samples in pending_samples.items():
                if not samples:
                    continue
                self.append_samples(csv_paths_by_id[rigid_body_id], samples)

            pending_samples.clear()
            pending_frame_count = 0

        def handle_frame(frame: dict) -> None:
            nonlocal pending_frame_count

            rigid_bodies = self.parse_frame(frame)
            if not rigid_bodies:
                return

            if print_enabled:
                self.print_rigid_bodies(rigid_bodies)

            if csv_folder_path is None:
                return

            rigid_body_names_by_id.update(self.get_rigid_body_names(frame))
            wallclock, perf_timestamp, motive = self._get_timestamps(frame)
            for rigid_body in rigid_bodies:
                rigid_body_id = rigid_body.rigid_body_id
                if rigid_body_id not in csv_paths_by_id:
                    rigid_body_name = rigid_body_names_by_id.get(rigid_body_id)
                    if rigid_body_name:
                        csv_path = csv_folder_path / f"{rigid_body_name}.csv"
                        if csv_path in csv_paths_by_id.values():
                            csv_path = csv_folder_path / f"{rigid_body_name}_{rigid_body_id}.csv"
                    else:
                        csv_path = csv_folder_path / f"rigid_body_{rigid_body_id}.csv"

                    self.create_csv(csv_path)
                    csv_paths_by_id[rigid_body_id] = csv_path

                    display_name = rigid_body_names_by_id.get(rigid_body_id, f"id={rigid_body_id}")
                    print(f"Started streaming data with Motive rigid body '{display_name}'.")
                    print(f"    Writing to {csv_path}")

                pending_samples[rigid_body_id].append(
                    RigidBodySample(
                        wallclock_timestamp=wallclock,
                        perf_timestamp=perf_timestamp,
                        motive_timestamp=motive,
                        position=rigid_body.position,
                        rotation=rigid_body.rotation,
                    )
                )

            pending_frame_count += 1
            if pending_frame_count >= csv_batch_frames:
                flush_pending()

        try:
            run_natnet_stream(
                self.config,
                frame_listener=handle_frame,
                stop_event=stop_event,
                started_event=started_event
            )
        finally:
            flush_pending()


if __name__ == "__main__":

    natnet_config = NatNetConfig(
        client_ip="127.0.0.1",
        server_ip="127.0.0.1",
        use_multicast=False,
    )

    rigid_body_receiver = RigidBodyReceiver(config=natnet_config)

    started_event = threading.Event()
    stop_event = threading.Event()
    thread = threading.Thread(
        target=rigid_body_receiver.stream,
        kwargs={
            "stop_event": stop_event,
            "started_event": started_event,
            "print_enabled": True,
            "csv_folder_path": Path("output") / "test" / "motive" / "rigid_bodies",
            "csv_batch_frames": 30,
        },
    )

    thread.start()
    started_event.wait()

    try:
        input("Press Enter to stop streaming...\n")
    finally:
        stop_event.set()
        thread.join()
