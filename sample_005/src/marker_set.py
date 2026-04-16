from pathlib import Path
from typing import Optional
from dataclasses import dataclass
from collections import defaultdict
import time

from src.natnet_stream import NatNetConfig, run_natnet_stream


Vector3 = tuple[float, float, float]


# from NatNet mocap data, representing a single marker set in a single frame
@dataclass(frozen=True)
class MarkerSetFrame:
    name: str
    positions: list[Vector3]


# representing a single marker set sample, used for CSV output
@dataclass(frozen=True)
class MarkerSetSample:
    timestamp: float
    positions: list[Vector3]


class MarkerSetReceiver:
    def __init__(self, config: NatNetConfig):
        self.config = config

    @staticmethod
    def parse_frame(frame: dict) -> list[MarkerSetFrame]:

        def _normalize_name(raw_name: object) -> str:
            if isinstance(raw_name, bytes):
                return raw_name.decode("utf-8", errors="replace")
            if raw_name:
                return str(raw_name)
            return "(no-name)"
        
        mocap_data = frame.get("mocap_data")
        if mocap_data is None or mocap_data.marker_set_data is None:
            return []

        marker_sets = []
        for marker_set in mocap_data.marker_set_data.marker_data_list:
            positions = [tuple(position) for position in marker_set.marker_pos_list]
            marker_sets.append(
                MarkerSetFrame(
                    name=_normalize_name(marker_set.model_name),
                    positions=positions,
                )
            )
        return marker_sets

    @staticmethod
    def print_marker_sets(marker_sets: list[MarkerSetFrame]) -> None:
        for marker_set in marker_sets:
            print(f"set={marker_set.name} count={len(marker_set.positions)}")
            for index, position in enumerate(marker_set.positions):
                print(
                    f"  idx={index} "
                    f"pos=({position[0]:.3f}, {position[1]:.3f}, {position[2]:.3f})"
                )

    @staticmethod
    def get_frame_timestamp(frame: dict) -> float:
        frame_timestamp = frame.get("timestamp")
        if isinstance(frame_timestamp, (int, float)) and frame_timestamp >= 0:
            return float(frame_timestamp)

        mocap_data = frame.get("mocap_data")
        if mocap_data is not None and mocap_data.suffix_data is not None:
            suffix_timestamp = mocap_data.suffix_data.timestamp
            if isinstance(suffix_timestamp, (int, float)) and suffix_timestamp >= 0:
                return float(suffix_timestamp)

        return time.time()

    @staticmethod
    def save_marker_sets_to_csv(
        marker_sets_by_name: dict[str, list[MarkerSetSample]],
        folder_path: Path,
        marker_column_counts: dict[str, int],
    ) -> None:
        for marker_set_name, samples in marker_sets_by_name.items():
            csv_file = folder_path / f"{marker_set_name}.csv"
            file_exists = csv_file.exists()
            marker_count = marker_column_counts[marker_set_name]

            with csv_file.open("a") as f:
                if not file_exists:
                    header = ["timestamp"]
                    for marker_index in range(marker_count):
                        header.extend(
                            [
                                f"{marker_index}_x",
                                f"{marker_index}_y",
                                f"{marker_index}_z",
                            ]
                        )
                    f.write(",".join(header) + "\n")

                for sample in samples:
                    if len(sample.positions) > marker_count:
                        raise ValueError(
                            f"Marker count increased for '{marker_set_name}' from {marker_count} to {len(sample.positions)}"
                        )

                    row = [str(sample.timestamp)]
                    for position in sample.positions:
                        row.extend([str(position[0]), str(position[1]), str(position[2])])

                    missing_marker_count = marker_count - len(sample.positions)
                    row.extend([""] * (missing_marker_count * 3))
                    f.write(",".join(row) + "\n")


    def stream(
            self,
            print_enabled: bool = False,
            csv_folder_path: Optional[Path] = None,
            csv_batch_frames: int = 30,
            ) -> None:

        if csv_folder_path is not None:
            csv_folder_path.mkdir(parents=True, exist_ok=True)

        pending_samples: dict[str, list[MarkerSetSample]] = defaultdict(list)
        marker_column_counts: dict[str, int] = {}
        pending_frame_count = 0

        def flush_pending() -> None:
            nonlocal pending_frame_count
            if csv_folder_path is None or not pending_samples:
                return

            self.save_marker_sets_to_csv(
                pending_samples,
                csv_folder_path,
                marker_column_counts,
            )
            pending_samples.clear()
            pending_frame_count = 0

        def handle_frame(frame: dict) -> None:
            nonlocal pending_frame_count
            marker_sets = self.parse_frame(frame)
            if marker_sets:
                if print_enabled:
                    self.print_marker_sets(marker_sets)
                if csv_folder_path is not None:
                    frame_timestamp = self.get_frame_timestamp(frame)
                    for marker_set in marker_sets:
                        marker_count = len(marker_set.positions)
                        existing_marker_count = marker_column_counts.get(marker_set.name)
                        if existing_marker_count is None:
                            marker_column_counts[marker_set.name] = marker_count
                        elif marker_count > existing_marker_count:
                            raise ValueError(
                                f"Marker count increased for '{marker_set.name}' from {existing_marker_count} to {marker_count}"
                            )

                        pending_samples[marker_set.name].append(
                            MarkerSetSample(
                                timestamp=frame_timestamp,
                                positions=list(marker_set.positions),
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
    MarkerSetReceiver(config=NatNetConfig()).stream(print_enabled=False, csv_folder_path=Path("output") / "marker_sets")