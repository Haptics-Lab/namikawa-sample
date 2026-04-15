from src.natnet_stream import NatNetConfig
from src.marker_set import MarkerSetReceiver
from src.rigid_body import RigidBodyReceiver
from src.skeleton import SkeletonReceiver


def stream_marker_sets(config: NatNetConfig) -> None:
    MarkerSetReceiver(config=config).stream()

def stream_rigid_bodies(config: NatNetConfig) -> None:
    RigidBodyReceiver(config=config).stream()

def stream_skeletons(config: NatNetConfig) -> None:
    SkeletonReceiver(config=config).stream()


def main():
    natnet_config = NatNetConfig(
        client_ip="127.0.0.1",
        server_ip="127.0.0.1",
        use_multicast=False,
    )

    # === You can choose which data to stream ===
    # stream_rigid_bodies(config=natnet_config)
    # stream_skeletons(config=natnet_config)
    stream_marker_sets(config=natnet_config)


if __name__ == "__main__":
    main()
