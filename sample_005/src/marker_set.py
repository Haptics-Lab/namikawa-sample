from pathlib import Path
from typing import Optional
from dataclasses import dataclass
from collections import defaultdict
import csv
import time

from src.natnet_stream import NatNetConfig, run_natnet_stream


Vector3 = tuple[float, float, float]


@dataclass(frozen=True)
class MarkerSample:
    wallclock_timestamp: float
    motive_timestamp: Optional[float]
    positions: list[Vector3]


class MarkerSetReceiver:
    def __init__(self, config: NatNetConfig):
        self.config = config

    @staticmethod
    def _normalize_name(raw_name: object) -> str:
        if isinstance(raw_name, bytes):
            return raw_name.decode("utf-8", errors="replace")
        return str(raw_name) if raw_name else "(no-name)"

    @staticmethod
    def parse_frame(frame: dict) -> list[tuple[str, list[Vector3]]]:
        mocap_data = frame.get("mocap_data")
        if mocap_data is None or mocap_data.marker_set_data is None:
            return []

        marker_sets = []
        for marker_set in mocap_data.marker_set_data.marker_data_list:
            positions = [tuple(pos) for pos in marker_set.marker_pos_list]
            marker_sets.append(
                (MarkerSetReceiver._normalize_name(marker_set.model_name), positions)
            )
        return marker_sets

    @staticmethod
    def print_marker_sets(marker_sets: list[tuple[str, list[Vector3]]]) -> None:
        for name, positions in marker_sets:
            print(f"set={name} count={len(positions)}")
            for i, (x, y, z) in enumerate(positions):
                print(f"  idx={i} pos=({x:.3f}, {y:.3f}, {z:.3f})")

    @staticmethod
    def get_wallclock_timestamp(frame: dict) -> float:
        received_time_ns = frame.get("received_time_ns")
        if isinstance(received_time_ns, int) and received_time_ns >= 0:
            return received_time_ns / 1_000_000_000.0
        return time.time()

    @staticmethod
    def get_motive_timestamp(frame: dict) -> Optional[float]:
        timestamp = frame.get("timestamp")
        if isinstance(timestamp, (int, float)) and timestamp >= 0:
            return float(timestamp)
        return None

    @staticmethod
    def create_csv(path: Path, marker_count: int) -> None:
        header = ["wallclock_timestamp", "motive_timestamp"]
        for i in range(marker_count):
            header += [f"{i}_x", f"{i}_y", f"{i}_z"]

        with path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(header)

    @staticmethod
    def append_samples(path: Path, samples: list[MarkerSample], marker_count: int) -> None:
        with path.open("a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)

            for sample in samples:
                if len(sample.positions) > marker_count:
                    raise ValueError(
                        f"Marker count increased from {marker_count} to {len(sample.positions)}"
                    )

                row = [sample.wallclock_timestamp, sample.motive_timestamp]

                for x, y, z in sample.positions:
                    row += [x, y, z]

                missing = marker_count - len(sample.positions)
                row += [""] * (missing * 3)

                writer.writerow(row)

    def stream(
            self,
            print_enabled: bool = False,
            csv_folder_path: Optional[Path] = None,
            csv_batch_frames: int = 30,
            ) -> None:
        
        if csv_folder_path is not None:
            csv_folder_path.mkdir(parents=True, exist_ok=True)

        marker_counts: dict[str, int] = {}
        pending_samples: dict[str, list[MarkerSample]] = defaultdict(list)
        pending_frame_count = 0

        def flush_pending() -> None:
            nonlocal pending_frame_count
            if csv_folder_path is None:
                return

            for name, samples in pending_samples.items():
                if samples:
                    csv_path = csv_folder_path / f"{name}.csv"
                    self.append_samples(csv_path, samples, marker_counts[name])

            pending_samples.clear()
            pending_frame_count = 0

        def handle_frame(frame: dict) -> None:
            nonlocal pending_frame_count

            marker_sets = self.parse_frame(frame)
            if not marker_sets:
                return

            if print_enabled:
                self.print_marker_sets(marker_sets)

            if csv_folder_path is None:
                return

            wallclock = self.get_wallclock_timestamp(frame)
            motive = self.get_motive_timestamp(frame)

            for name, positions in marker_sets:
                count = len(positions)

                if name not in marker_counts:
                    marker_counts[name] = count
                    csv_path = csv_folder_path / f"{name}.csv"
                    self.create_csv(csv_path, count)

                elif count > marker_counts[name]:
                    raise ValueError(
                        f"Marker count increased for '{name}' "
                        f"from {marker_counts[name]} to {count}"
                    )

                pending_samples[name].append(
                    MarkerSample(
                        wallclock_timestamp=wallclock,
                        motive_timestamp=motive,
                        positions=positions,
                    )
                )

            pending_frame_count += 1
            if pending_frame_count >= csv_batch_frames:
                flush_pending()

        try:
            run_natnet_stream(self.config, frame_listener=handle_frame)
        finally:
            flush_pending()


if __name__ == "__main__":
    MarkerSetReceiver(NatNetConfig()).stream(
        print_enabled=True,
        csv_folder_path=Path("output") / "marker_sets",
    )