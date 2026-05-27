import threading
from dataclasses import dataclass
from typing import Any, Callable

from src.motive.fromSDK.NatNetClient import NatNetClient


@dataclass(frozen=True)
class NatNetConfig:
    client_ip: str = "127.0.0.1"
    server_ip: str = "127.0.0.1"
    use_multicast: bool = False
    print_level: int = 0
    run_mode: str = "d"


RigidBodyListener = Callable[[int, tuple[float, float, float], tuple[float, float, float, float]], None]
FrameListener = Callable[[dict[str, Any]], None]


def run_natnet_stream(
        config: NatNetConfig,
        stop_event: threading.Event,
        started_event: threading.Event,
        *,
        rigid_body_listener: RigidBodyListener | None = None,
        frame_listener: FrameListener | None = None,
        ) -> None:
    client = NatNetClient()
    client.set_client_address(config.client_ip)
    client.set_server_address(config.server_ip)
    client.set_use_multicast(config.use_multicast)
    client.set_print_level(config.print_level)
    client.rigid_body_listener = rigid_body_listener
    client.new_frame_with_data_listener = frame_listener

    if not client.run(config.run_mode):
        raise RuntimeError("Failed to start NatNet client")
    
    started_event.set()

    try:
        stop_event.wait()
    finally:
        client.shutdown()
        print("Stopped Motive NatNet streaming.")
