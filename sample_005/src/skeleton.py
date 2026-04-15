from dataclasses import dataclass

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


class SkeletonReceiver:
    def __init__(self, config: NatNetConfig):
        self.config = config

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

    def stream(self) -> None:
        def handle_frame(frame: dict) -> None:
            skeletons = self.parse_frame(frame)
            if skeletons:
                self.print_skeletons(skeletons)

        run_natnet_stream(self.config, frame_listener=handle_frame)


if __name__ == "__main__":
    SkeletonReceiver(config=NatNetConfig()).stream()