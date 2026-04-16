from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
import csv
import time

from src.natnet_stream import NatNetConfig, run_natnet_stream


Vector3 = tuple[float, float, float]
Quaternion = tuple[float, float, float, float]


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
    skeleton_id: int
    bones_data: dict[int, tuple[Vector3, Quaternion]]  # bone_id -> (position, rotation)


class SkeletonReceiver:
    def __init__(self, config: NatNetConfig):
        self.config = config

    @staticmethod
    def _normalize_name(raw_name: object) -> str:
        if isinstance(raw_name, bytes):
            return raw_name.decode("utf-8", errors="replace")
        return str(raw_name) if raw_name else ""

    @classmethod
    def get_skeleton_structure(cls, frame: dict) -> dict[int, list[BoneDefinition]]:
        data_descriptions = frame.get("data_descriptions")
        skeleton_list = getattr(data_descriptions, "skeleton_list", None)
        if skeleton_list is None:
            return {}

        structure_by_skeleton_id = {}
        for skeleton_desc in skeleton_list:
            skeleton_id = getattr(skeleton_desc, "id_num", None)
            if not isinstance(skeleton_id, int):
                continue

            bones = []
            rb_list = getattr(skeleton_desc, "rigid_body_description_list", None) or []
            for rb_desc in rb_list:
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
                structure_by_skeleton_id[skeleton_id] = bones

        return structure_by_skeleton_id

    @classmethod
    def get_skeleton_names(cls, frame: dict) -> dict[int, str]:
        data_descriptions = frame.get("data_descriptions")
        skeleton_list = getattr(data_descriptions, "skeleton_list", None)
        if skeleton_list is None:
            return {}

        names_by_id = {}
        for skeleton_desc in skeleton_list:
            skeleton_id = getattr(skeleton_desc, "id_num", None)
            if not isinstance(skeleton_id, int):
                continue

            skeleton_name = cls._normalize_name(getattr(skeleton_desc, "name", None))
            if skeleton_name:
                names_by_id[skeleton_id] = skeleton_name

        return names_by_id

    @staticmethod
    def get_timestamps(frame: dict) -> tuple[float, Optional[float]]:
        received_time_ns = frame.get("received_time_ns")
        wallclock = (
            received_time_ns / 1_000_000_000.0
            if isinstance(received_time_ns, int) and received_time_ns >= 0
            else time.time()
        )

        timestamp = frame.get("timestamp")
        motive = float(timestamp) if isinstance(timestamp, (int, float)) and timestamp >= 0 else None
        return wallclock, motive

    @staticmethod
    def create_structure_csv(path: Path, bones: list[BoneDefinition]) -> None:
        with path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["skeleton_id", "bone_name", "bone_id", "parent_id"])
            for bone in bones:
                writer.writerow([bone.skeleton_id, bone.bone_name, bone.bone_id, bone.parent_id])

    @staticmethod
    def create_data_csv(path: Path, bones: list[BoneDefinition]) -> None:
        with path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            
            # Build header: wallclock_timestamp, motive_timestamp, bone1_pos_x, bone1_pos_y, ...
            header = ["wallclock_timestamp", "motive_timestamp"]
            for bone in bones:
                header.extend([
                    f"bone_{bone.bone_id}_pos_x",
                    f"bone_{bone.bone_id}_pos_y",
                    f"bone_{bone.bone_id}_pos_z",
                    f"bone_{bone.bone_id}_qx",
                    f"bone_{bone.bone_id}_qy",
                    f"bone_{bone.bone_id}_qz",
                    f"bone_{bone.bone_id}_qw",
                ])
            writer.writerow(header)

    @staticmethod
    def append_frame_sample(path: Path, sample: SkeletonSample, bones: list[BoneDefinition]) -> None:
        with path.open("a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            row = [sample.wallclock_timestamp, sample.motive_timestamp]
            
            for bone in bones:
                position, rotation = sample.bones_data.get(bone.bone_id, ((0, 0, 0), (0, 0, 0, 1)))
                row.extend([
                    position[0],
                    position[1],
                    position[2],
                    rotation[0],  # qx
                    rotation[1],  # qy
                    rotation[2],  # qz
                    rotation[3],  # qw
                ])
            writer.writerow(row)

    @staticmethod
    def parse_frame(frame: dict) -> list[SkeletonFrame]:
        mocap_data = frame.get("mocap_data")
        if mocap_data is None or mocap_data.skeleton_data is None:
            return []

        skeletons = []
        for skeleton in mocap_data.skeleton_data.skeleton_list:
            rigid_bodies = [
                SkeletonRigidBody(
                    rigid_body_id=rigid_body.id_num,
                    position=tuple(rigid_body.pos),
                    rotation=tuple(rigid_body.rot),
                )
                for rigid_body in skeleton.rigid_body_list
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
                print(
                    f"  rb_id={rigid_body.rigid_body_id} "
                    f"pos=({rigid_body.position[0]:.3f}, {rigid_body.position[1]:.3f}, {rigid_body.position[2]:.3f})"
                )

    def stream(
            self,
            print_enabled: bool = True,
            csv_folder_path: Optional[Path] = None,
            csv_batch_frames: int = 30,
            ) -> None:

        if csv_folder_path is not None:
            csv_folder_path.mkdir(parents=True, exist_ok=True)

        csv_paths_by_skeleton_id: dict[int, Path] = {}
        skeleton_structure_by_id: dict[int, list[BoneDefinition]] = {}
        skeleton_names_by_id: dict[int, str] = {}
        pending_samples: dict[int, list[SkeletonSample]] = defaultdict(list)
        pending_frame_count = 0
        structure_initialized = False

        def flush_pending() -> None:
            nonlocal pending_frame_count
            if csv_folder_path is None:
                return

            for skeleton_id, samples in pending_samples.items():
                if not samples:
                    continue
                for sample in samples:
                    self.append_frame_sample(
                        csv_paths_by_skeleton_id[skeleton_id],
                        sample,
                        skeleton_structure_by_id[skeleton_id],
                    )

            pending_samples.clear()
            pending_frame_count = 0

        def handle_frame(frame: dict) -> None:
            nonlocal pending_frame_count, structure_initialized

            skeletons = self.parse_frame(frame)
            if not skeletons:
                return

            if print_enabled:
                self.print_skeletons(skeletons)

            if csv_folder_path is None:
                return

            # Initialize skeleton structure once
            if not structure_initialized:
                structure_by_skeleton_id = self.get_skeleton_structure(frame)
                skeleton_structure_by_id.update(structure_by_skeleton_id)
                
                skeleton_names = self.get_skeleton_names(frame)
                skeleton_names_by_id.update(skeleton_names)
                
                for skeleton_id, bones in structure_by_skeleton_id.items():
                    # Create structure CSV
                    skeleton_name = skeleton_names_by_id.get(skeleton_id, f"skeleton_{skeleton_id}")
                    structure_csv_path = csv_folder_path / f"{skeleton_name}_structure.csv"
                    self.create_structure_csv(structure_csv_path, bones)
                    print(f"Created skeleton structure file: {structure_csv_path}")
                
                structure_initialized = True

            wallclock, motive = self.get_timestamps(frame)
            for skeleton in skeletons:
                skeleton_id = skeleton.skeleton_id
                
                # Initialize data CSV if needed
                if skeleton_id not in csv_paths_by_skeleton_id:
                    if skeleton_id not in skeleton_structure_by_id:
                        print(f"Warning: No structure definition for skeleton {skeleton_id}")
                        continue
                    
                    skeleton_name = skeleton_names_by_id.get(skeleton_id, f"skeleton_{skeleton_id}")
                    csv_path = csv_folder_path / f"{skeleton_name}_data.csv"
                    self.create_data_csv(csv_path, skeleton_structure_by_id[skeleton_id])
                    csv_paths_by_skeleton_id[skeleton_id] = csv_path
                    print(f"Started streaming skeleton {skeleton_id} ({skeleton_name}).")
                    print(f"    Writing to {csv_path}")

                # Build bones_data dict
                bones_data = {}
                for rigid_body in skeleton.rigid_bodies:
                    bones_data[rigid_body.rigid_body_id] = (rigid_body.position, rigid_body.rotation)

                pending_samples[skeleton_id].append(
                    SkeletonSample(
                        wallclock_timestamp=wallclock,
                        motive_timestamp=motive,
                        skeleton_id=skeleton_id,
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
        print_enabled=True,
        csv_folder_path=Path("output") / "skeletons",
    )