from dataclasses import dataclass

from src.natnet_stream import NatNetConfig, run_natnet_stream


Vector3 = tuple[float, float, float]
Quaternion = tuple[float, float, float, float]


@dataclass(frozen=True)
class RigidBodyFrame:
    rigid_body_id: int
    position: Vector3
    rotation: Quaternion


class RigidBodyReceiver:
    def __init__(self, config: NatNetConfig):
        self.config = config

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
    def print_rigid_body(rigid_body: RigidBodyFrame) -> None:
        print(
            f"id={rigid_body.rigid_body_id} "
            f"pos=({rigid_body.position[0]:.3f}, {rigid_body.position[1]:.3f}, {rigid_body.position[2]:.3f}) "
            f"rot=({rigid_body.rotation[0]:.3f}, {rigid_body.rotation[1]:.3f}, {rigid_body.rotation[2]:.3f}, {rigid_body.rotation[3]:.3f})"
        )

    def stream(self) -> None:
        def handle_rigid_body(
            rigid_body_id: int,
            position: tuple[float, float, float],
            rotation: tuple[float, float, float, float],
        ) -> None:
            rigid_body = self.build_frame(rigid_body_id, position, rotation)
            self.print_rigid_body(rigid_body)

        run_natnet_stream(self.config, rigid_body_listener=handle_rigid_body)


if __name__ == "__main__":
    RigidBodyReceiver(config=NatNetConfig()).stream()