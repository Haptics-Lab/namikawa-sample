from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
import threading
import csv
import time

from src.motive.natnet_stream import NatNetConfig, run_natnet_stream


Vector3 = tuple[float, float, float]


@dataclass(frozen=True)
class MarkerSample:
    wallclock_timestamp: float
    perf_timestamp: int
    motive_timestamp: Optional[float]
    positions: list[Vector3]


@dataclass
class MarkerSetInfo:
    csv_path: Path
    marker_count: int
    column_order: list[int]


class MarkerSetReceiver:
    def __init__(self, config: NatNetConfig):
        self.config = config

    @staticmethod
    def _normalize_name(raw_name: object) -> str:
        if isinstance(raw_name, bytes):
            return raw_name.decode("utf-8", errors="replace")
        return str(raw_name) if raw_name else ""

    @classmethod
    def parse_frame(cls, frame: dict) -> list[tuple[str, list[Vector3]]]:
        mocap_data = frame.get("mocap_data")
        if mocap_data is None or mocap_data.marker_set_data is None:
            return []

        result = []
        for marker_set in mocap_data.marker_set_data.marker_data_list:
            name = cls._normalize_name(marker_set.model_name)
            if name == "all":
                continue
            positions = [tuple(pos) for pos in marker_set.marker_pos_list]
            result.append((name, positions))
        return result

    @classmethod
    def get_marker_set_labels(cls, frame: dict) -> dict[str, list[str]]:
        data_descriptions = frame.get("data_descriptions")
        marker_set_list = getattr(data_descriptions, "marker_set_list", None)
        if marker_set_list is None:
            return {}

        labels_by_set = {}
        for desc in marker_set_list:
            set_name = cls._normalize_name(getattr(desc, "marker_set_name", None))
            if not set_name or set_name == "all":
                continue

            raw_labels = getattr(desc, "marker_names_list", None) or []
            labels_by_set[set_name] = [cls._normalize_name(x) for x in raw_labels]

        return labels_by_set

    @staticmethod
    def _build_column_prefixes(
            marker_count: int,
            marker_labels: Optional[list[str]] = None,
            ) -> list[str]:
        
        labels = marker_labels or []
        counts: dict[str, int] = defaultdict(int)
        prefixes = []

        for i in range(marker_count):
            name = labels[i].strip() if i < len(labels) else ""
            if not name:
                name = str(i)

            counts[name] += 1
            if counts[name] > 1:
                name = f"{name}_{counts[name]}"

            prefixes.append(name)

        return prefixes

    @classmethod
    def _build_column_order(
            cls,
            marker_count: int,
            marker_labels: Optional[list[str]] = None,
            ) -> list[int]:
        
        prefixes = cls._build_column_prefixes(marker_count, marker_labels)
        return sorted(range(marker_count), key=lambda i: prefixes[i])

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
    def print_marker_sets(marker_sets: list[tuple[str, list[Vector3]]]) -> None:
        for name, positions in marker_sets:
            print(f"set={name} count={len(positions)}")
            for i, (x, y, z) in enumerate(positions):
                print(f"  idx={i} pos=({x:.3f}, {y:.3f}, {z:.3f})")

    @classmethod
    def create_csv(
            cls,
            path: Path,
            marker_count: int,
            column_order: list[int],
            marker_labels: Optional[list[str]] = None,
            ) -> None:
        
        prefixes = cls._build_column_prefixes(marker_count, marker_labels)

        header = ["Motive Time", "Wall Clock [s]", "Perf Counter [ns]"]
        for idx in column_order:
            p = prefixes[idx]
            header.extend([f"{p}_x", f"{p}_y", f"{p}_z"])

        with path.open("w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow(header)

    @staticmethod
    def append_samples(
            path: Path,
            samples: list[MarkerSample],
            marker_count: int,
            column_order: list[int],
            ) -> None:
        
        with path.open("a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)

            for sample in samples:
                if len(sample.positions) > marker_count:
                    raise ValueError(
                        f"Marker count increased from {marker_count} to {len(sample.positions)}"
                    )

                row = [sample.motive_timestamp, sample.wallclock_timestamp, sample.perf_timestamp]
                for idx in column_order:
                    if idx < len(sample.positions):
                        row.extend(sample.positions[idx])
                    else:
                        row.extend(["", "", ""])

                writer.writerow(row)

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

        marker_infos: dict[str, MarkerSetInfo] = {}
        pending_samples: dict[str, list[MarkerSample]] = defaultdict(list)
        pending_frame_count = 0

        def flush_pending() -> None:
            nonlocal pending_frame_count
            if csv_folder_path is None:
                return

            for name, samples in pending_samples.items():
                if not samples:
                    continue
                info = marker_infos[name]
                self.append_samples(
                    info.csv_path,
                    samples,
                    info.marker_count,
                    info.column_order,
                )

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

            labels_by_set = self.get_marker_set_labels(frame)
            wallclock, perf, motive = self._get_timestamps(frame)

            for name, positions in marker_sets:
                count = len(positions)

                if name not in marker_infos:
                    labels = labels_by_set.get(name)
                    column_order = self._build_column_order(count, labels)
                    csv_path = csv_folder_path / f"{name}.csv"

                    self.create_csv(
                        csv_path,
                        count,
                        column_order,
                        marker_labels=labels,
                    )

                    marker_infos[name] = MarkerSetInfo(
                        csv_path=csv_path,
                        marker_count=count,
                        column_order=column_order,
                    )

                    print(f"Started streaming data with Motive marker set '{name}'.")
                    print(f"    Writing to {csv_path}")

                elif count > marker_infos[name].marker_count:
                    raise ValueError(
                        f"Marker count increased for '{name}' "
                        f"from {marker_infos[name].marker_count} to {count}"
                    )

                pending_samples[name].append(
                    MarkerSample(
                        wallclock_timestamp=wallclock,
                        perf_timestamp=perf,
                        motive_timestamp=motive,
                        positions=positions,
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

    marker_set_receiver = MarkerSetReceiver(config=natnet_config)
    
    started_event = threading.Event()
    stop_event = threading.Event()
    thread = threading.Thread(
        target=marker_set_receiver.stream,
        kwargs={
            "print_enabled": False,
            "csv_folder_path": Path("output") / "test" / "motive" / "marker_sets",
            "stop_event": stop_event,
            "started_event": started_event,
        },
    )
    
    thread.start()
    started_event.wait()

    try:
        input("Press Enter to stop streaming...\n")
    finally:
        stop_event.set()
        thread.join()
