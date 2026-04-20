from pathlib import Path
import threading
import time

from src.ni.ni_adc import NIADC, ChannelConfig, TerminalConfiguration
from src.audio.audio_recorder import AudioRecorder
from src.mfa.camera_recorder import CameraConfig, MultiCameraRecorder
from src.motive.natnet_stream import NatNetConfig
from src.motive.marker_set import MarkerSetReceiver
from src.motive.rigid_body import RigidBodyReceiver


def main():

    # === Config ===
    # folder for raw data (CSV, WAV, etc.)
    raw_data_folder = Path("output") / "raw_data" / "test01" / "trial01"

    # NI DAQ
    channel_configs = [
        ChannelConfig(ch="ai0", ch_label="Tactile LI", terminal_config=TerminalConfiguration.RSE, voltage_range=(-2.0, 2.0)),
        ChannelConfig(ch="ai1", ch_label="Tactile LT", terminal_config=TerminalConfiguration.RSE, voltage_range=(-2.0, 2.0)),
        ChannelConfig(ch="ai2", ch_label="Tactile RI", terminal_config=TerminalConfiguration.RSE, voltage_range=(-2.0, 2.0)),
        ChannelConfig(ch="ai3", ch_label="Tactile RT", terminal_config=TerminalConfiguration.RSE, voltage_range=(-2.0, 2.0)),
        ChannelConfig(ch="ai8", ch_label="EMG LE", terminal_config=TerminalConfiguration.RSE, voltage_range=(-5.0, 5.0)),
        ChannelConfig(ch="ai9", ch_label="EMG LF", terminal_config=TerminalConfiguration.RSE, voltage_range=(-5.0, 5.0)),
        ChannelConfig(ch="ai10", ch_label="EMG RE", terminal_config=TerminalConfiguration.RSE, voltage_range=(-5.0, 5.0)),
        ChannelConfig(ch="ai11", ch_label="EMG RF", terminal_config=TerminalConfiguration.RSE, voltage_range=(-5.0, 5.0)),
        ChannelConfig(ch="ai12", ch_label="Sync Signal", terminal_config=TerminalConfiguration.RSE, voltage_range=(-0.5, 5.0))
    ]

    ni_adc = NIADC(
        device_name="Dev1",
        sampling_rate=16000.0,
        buffer_size=2048,
        samples_per_read=2048,
        channel_configs=channel_configs
    )

    # Audio Recorder
    audio_recorder = AudioRecorder(device=2, sample_rate=44100, channels=2, blocksize=1024)

    # Mocap For All Camera Recorder
    multi_camera_recorder = MultiCameraRecorder(configs=[
        CameraConfig(device=0, width=640, height=480, fps=30),
        CameraConfig(device=2, width=640, height=480, fps=30),
        CameraConfig(device=3, width=640, height=480, fps=30),
    ])

    # Motive
    natnet_config = NatNetConfig(
        client_ip="127.0.0.1",
        server_ip="127.0.0.1",
        use_multicast=False,
    )

    marker_receiver = MarkerSetReceiver(config=natnet_config)
    rigid_body_receiver = RigidBodyReceiver(config=natnet_config)


    # === Run Workers ===
    stop_event = threading.Event()
    worker_errors: list[tuple[str, Exception]] = []
    error_lock = threading.Lock()

    def run_worker(name: str, target):
        try:
            target()
        except Exception as exc:
            with error_lock:
                worker_errors.append((name, exc))
            stop_event.set()

    workers = [
        (
            "NI DAQ",
            lambda: ni_adc.stream_to_csv(
                csv_path=raw_data_folder / "ni_data.csv",
                stop_event=stop_event,
            ),
        ),
        (
            "Audio",
            lambda: audio_recorder.record(
                audio_path=raw_data_folder / "audio_data.wav",
                stop_event=stop_event,
            ),
        ),
        (
            "MocapForAll Cameras",
            lambda: multi_camera_recorder.record(
                output_folder=raw_data_folder,
                stop_event=stop_event,
            ),
        ),
        (
            "Motive MarkerSets",
            lambda: marker_receiver.stream(
                print_enabled=False,
                csv_folder_path=raw_data_folder / "motive" / "marker_sets",
                stop_event=stop_event,
            ),
        ),
        (
            "Motive RigidBodies",
            lambda: rigid_body_receiver.stream(
                print_enabled=False,
                csv_folder_path=raw_data_folder / "motive" / "rigid_bodies",
                stop_event=stop_event,
            ),
        ),
    ]

    threads: list[threading.Thread] = []
    for worker_name, worker_func in workers:
        thread = threading.Thread(
            target=run_worker,
            args=(worker_name, worker_func),
            name=worker_name,
        )
        thread.start()
        threads.append(thread)

    print("All recorders started. Press Ctrl+C once to stop all.")

    try:
        while any(thread.is_alive() for thread in threads):
            if stop_event.is_set():
                break
            time.sleep(0.2)
    except KeyboardInterrupt:
        print("\nKeyboardInterrupt received. Stopping all recordings...")
    finally:
        stop_event.set()
        for thread in threads:
            thread.join()

    if worker_errors:
        for worker_name, error in worker_errors:
            print(f"[ERROR] {worker_name}: {error}")
        raise RuntimeError("One or more recorder workers failed.")


if __name__ == "__main__":
    main()
