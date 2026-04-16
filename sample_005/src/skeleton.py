from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
import csv
import time

from src.natnet_stream import NatNetConfig, run_natnet_stream


Vector3 = tuple[float, float, float]
Quaternion = tuple[float, float, float, float]
DEFAULT_BONE_STATE = ((0.0, 0.0, 0.0), (0.0, 0.0, 0.0, 1.0))


@dataclass(frozen=True)
class SkeletonRigidBody:
    rigid_body_id: int
    position: Vector3
    rotation: Quaternion


@dataclass(frozen=True)
class SkeletonFrame:
    skeleton_id: int
    rigid_bodies: list[SkeletonRigidBody]


@dataclass(frozen=True)
class BoneDefinition:
    skeleton_id: int
    bone_name: str
    bone_id: int
    parent_id: int


@dataclass(frozen=True)
class SkeletonSample:
    wallclock_timestamp: float
    motive_timestamp: Optional[float]
    bones_data: dict[int, tuple[Vector3, Quaternion]]


@dataclass
class SkeletonInfo:
    name: str
    bones: list[BoneDefinition]
    data_csv_path: Path


class SkeletonReceiver:
    def __init__(self, config: NatNetConfig):
        self.config = config

    @staticmethod
    def _normalize_name(raw_name: object) -> str:
        if isinstance(raw_name, bytes):
            return raw_name.decode("utf-8", errors="replace")
        return str(raw_name) if raw_name else ""

    @staticmethod
    def _get_timestamps(frame: dict) -> tuple[float, Optional[float]]:
        received_time_ns = frame.get("received_time_ns")
        wallclock = (
            received_time_ns / 1_000_000_000.0
            if isinstance(received_time_ns, int) and received_time_ns >= 0
            else time.time()
        )

        timestamp = frame.get("timestamp")
        motive = float(timestamp) if isinstance(timestamp, (int, float)) and timestamp >= 0 else None
        return wallclock, motive

    @classmethod
    def _get_skeleton_descriptions(cls, frame: dict) -> dict[int, tuple[str, list[BoneDefinition]]]:
        data_descriptions = frame.get("data_descriptions")
        skeleton_list = getattr(data_descriptions, "skeleton_list", None)
        if skeleton_list is None:
            return {}

        result = {}
        for skeleton_desc in skeleton_list:
            skeleton_id = getattr(skeleton_desc, "id_num", None)
            if not isinstance(skeleton_id, int):
                continue

            name = cls._normalize_name(getattr(skeleton_desc, "name", None))
            bones = []
            for rb_desc in getattr(skeleton_desc, "rigid_body_description_list", None) or []:
                bone_id = getattr(rb_desc, "id_num", None)
                parent_id = getattr(rb_desc, "parent_id", None)
                bone_name = cls._normalize_name(getattr(rb_desc, "sz_name", None))

                if isinstance(bone_id, int) and isinstance(parent_id, int):
                    bones.append(
                        BoneDefinition(
                            skeleton_id=skeleton_id,
                            bone_name=bone_name,
                            bone_id=bone_id,
                            parent_id=parent_id,
                        )
                    )

            if bones:
                result[skeleton_id] = (name or f"skeleton_{skeleton_id}", bones)

        return result

    @staticmethod
    def parse_frame(frame: dict) -> list[SkeletonFrame]:
        mocap_data = frame.get("mocap_data")
        if mocap_data is None or mocap_data.skeleton_data is None:
            return []

        skeletons = []
        for skeleton in mocap_data.skeleton_data.skeleton_list:
            rigid_bodies = [
                SkeletonRigidBody(
                    rigid_body_id=rb.id_num,
                    position=tuple(rb.pos),
                    rotation=tuple(rb.rot),
                )
                for rb in skeleton.rigid_body_list
            ]
            skeletons.append(
                SkeletonFrame(
                    skeleton_id=skeleton.id_num,
                    rigid_bodies=rigid_bodies,
                )
            )
        return skeletons

    @staticmethod
    def print_skeletons(skeletons: list[SkeletonFrame]) -> None:
        for skeleton in skeletons:
            print(
                f"skeleton_id={skeleton.skeleton_id} "
                f"rigid_body_count={len(skeleton.rigid_bodies)}"
            )
            for rigid_body in skeleton.rigid_bodies:
                x, y, z = rigid_body.position
                print(
                    f"  rb_id={rigid_body.rigid_body_id} "
                    f"pos=({x:.3f}, {y:.3f}, {z:.3f})"
                )

    @staticmethod
    def create_structure_csv(path: Path, bones: list[BoneDefinition]) -> None:
        with path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["skeleton_id", "bone_name", "bone_id", "parent_id"])
            for bone in bones:
                writer.writerow([bone.skeleton_id, bone.bone_name, bone.bone_id, bone.parent_id])

    @staticmethod
    def create_data_csv(path: Path, bones: list[BoneDefinition]) -> None:
        header = ["wallclock_timestamp", "motive_timestamp"]
        for bone in bones:
            header.extend(
                [
                    f"bone_{bone.bone_id}_pos_x",
                    f"bone_{bone.bone_id}_pos_y",
                    f"bone_{bone.bone_id}_pos_z",
                    f"bone_{bone.bone_id}_qx",
                    f"bone_{bone.bone_id}_qy",
                    f"bone_{bone.bone_id}_qz",
                    f"bone_{bone.bone_id}_qw",
                ]
            )

        with path.open("w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow(header)

    @staticmethod
    def append_samples(
        path: Path,
        samples: list[SkeletonSample],
        bones: list[BoneDefinition],
    ) -> None:
        with path.open("a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            for sample in samples:
                row = [sample.wallclock_timestamp, sample.motive_timestamp]
                for bone in bones:
                    position, rotation = sample.bones_data.get(bone.bone_id, DEFAULT_BONE_STATE)
                    row.extend([*position, *rotation])
                writer.writerow(row)

    def stream(
            self,
            print_enabled: bool = False,
            csv_folder_path: Optional[Path] = None,
            csv_batch_frames: int = 30,
            ) -> None:
        if csv_folder_path is not None:
            csv_folder_path.mkdir(parents=True, exist_ok=True)

        skeleton_infos: dict[int, SkeletonInfo] = {}
        pending_samples: dict[int, list[SkeletonSample]] = defaultdict(list)
        pending_frame_count = 0

        def flush_pending() -> None:
            nonlocal pending_frame_count
            if csv_folder_path is None:
                return

            for skeleton_id, samples in pending_samples.items():
                if not samples:
                    continue
                info = skeleton_infos.get(skeleton_id)
                if info is None:
                    continue
                self.append_samples(info.data_csv_path, samples, info.bones)

            pending_samples.clear()
            pending_frame_count = 0

        def initialize_structure(frame: dict) -> None:
            descriptions = self._get_skeleton_descriptions(frame)
            for skeleton_id, (name, bones) in descriptions.items():
                if skeleton_id in skeleton_infos:
                    continue  # Already initialized
                
                structure_csv_path = csv_folder_path / f"{name}_structure.csv"
                data_csv_path = csv_folder_path / f"{name}_data.csv"

                self.create_structure_csv(structure_csv_path, bones)
                self.create_data_csv(data_csv_path, bones)
                
                skeleton_infos[skeleton_id] = SkeletonInfo(
                    name=name,
                    bones=bones,
                    data_csv_path=data_csv_path,
                )

                print(f"Started streaming data with Motive skeleton '{name}'. Ctrl+C to stop.")
                print(f"    Writing to {data_csv_path}")

        def handle_frame(frame: dict) -> None:
            nonlocal pending_frame_count

            skeletons = self.parse_frame(frame)
            if not skeletons:
                return

            if print_enabled:
                self.print_skeletons(skeletons)

            if csv_folder_path is None:
                return

            # Initialize structure only when data_descriptions is present
            if frame.get("data_descriptions") is not None:
                initialize_structure(frame)

            wallclock, motive = self._get_timestamps(frame)

            for skeleton in skeletons:
                info = skeleton_infos.get(skeleton.skeleton_id)

                bones_data = {
                    rb.rigid_body_id & 0xFFFF: (rb.position, rb.rotation)
                    for rb in skeleton.rigid_bodies
                }

                pending_samples[skeleton.skeleton_id].append(
                    SkeletonSample(
                        wallclock_timestamp=wallclock,
                        motive_timestamp=motive,
                        bones_data=bones_data,
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
    SkeletonReceiver(config=NatNetConfig()).stream(
        print_enabled=False,
        csv_folder_path=Path("output") / "skeletons",
    )