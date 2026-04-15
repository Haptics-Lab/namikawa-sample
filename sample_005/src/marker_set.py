from dataclasses import dataclass

from src.natnet_stream import NatNetConfig, run_natnet_stream


Vector3 = tuple[float, float, float]


@dataclass(frozen=True)
class MarkerSetFrame:
    name: str
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

    def stream(self) -> None:
        def handle_frame(frame: dict) -> None:
            marker_sets = self.parse_frame(frame)
            if marker_sets:
                self.print_marker_sets(marker_sets)

        run_natnet_stream(self.config, frame_listener=handle_frame)


if __name__ == "__main__":
    MarkerSetReceiver(config=NatNetConfig()).stream()