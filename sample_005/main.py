from pathlib import Path

from src.natnet_stream import NatNetConfig
from src.marker_set import MarkerSetReceiver
from src.rigid_body import RigidBodyReceiver
from src.skeleton import SkeletonReceiver


def stream_marker_sets(config: NatNetConfig) -> None:
    '''
    Streams marker set data from the NatNet server.
    '''
    MarkerSetReceiver(config=config).stream(
        print_enabled=False,
        csv_folder_path=Path("output") / "marker_sets",
    )

def stream_rigid_bodies(config: NatNetConfig) -> None:
    '''
    Streams rigid body data from the NatNet server.
    '''
    RigidBodyReceiver(config=config).stream(
        print_enabled=False,
        csv_folder_path=Path("output") / "rigid_bodies",
    )

def stream_skeletons(config: NatNetConfig) -> None:
    '''
    Streams skeleton data from the NatNet server.
    '''
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
