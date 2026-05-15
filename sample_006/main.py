from pathlib import Path
import threading
from functools import partial
import time
import subprocess

from src.ni.ni_adc import NIADC, ChannelConfig as ADCChannelConfig, TerminalConfiguration
from src.ni.ni_do import NIDigitalOutput, LineConfig as DOLineConfig
from src.audio.audio_recorder import AudioRecorder
from src.mfa.camera_recorder import CameraConfig, MultiCameraRecorder
from src.motive.natnet_stream import NatNetConfig
from src.motive.marker_set import MarkerSetReceiver
from src.motive.rigid_body import RigidBodyReceiver
from src.eeg.eeg_recorder import EEGConfig


def main():

    # === Config ===

    # folder for raw data (CSV, WAV, etc.)
    raw_data_folder = Path("output") / "20260515" / "trial01"

    recording_bool = {
        "NI DAQ": True,
        "Audio": True,
        "MocapForAll Cameras": False,
        "Motive MarkerSets": False,
        "Motive RigidBodies": False,
        "EEG": True,
    }

    # NI DAQ
    adc_channel_configs = [
        ADCChannelConfig(ch="ai0", ch_label="Tactile LI", terminal_config=TerminalConfiguration.RSE, voltage_range=(-2.0, 2.0)),
        ADCChannelConfig(ch="ai1", ch_label="Tactile LT", terminal_config=TerminalConfiguration.RSE, voltage_range=(-2.0, 2.0)),
        ADCChannelConfig(ch="ai2", ch_label="Tactile RI", terminal_config=TerminalConfiguration.RSE, voltage_range=(-2.0, 2.0)),
        ADCChannelConfig(ch="ai3", ch_label="Tactile RT", terminal_config=TerminalConfiguration.RSE, voltage_range=(-2.0, 2.0)),
        ADCChannelConfig(ch="ai8", ch_label="EMG LE", terminal_config=TerminalConfiguration.RSE, voltage_range=(-5.0, 5.0)),
        ADCChannelConfig(ch="ai9", ch_label="EMG LF", terminal_config=TerminalConfiguration.RSE, voltage_range=(-5.0, 5.0)),
        ADCChannelConfig(ch="ai10", ch_label="EMG RE", terminal_config=TerminalConfiguration.RSE, voltage_range=(-5.0, 5.0)),
        ADCChannelConfig(ch="ai11", ch_label="EMG RF", terminal_config=TerminalConfiguration.RSE, voltage_range=(-5.0, 5.0)),
        ADCChannelConfig(ch="ai12", ch_label="Sync Signal", terminal_config=TerminalConfiguration.RSE, voltage_range=(-0.5, 5.0))
    ]

    ni_adc = NIADC(
        device_name="Dev1",
        sampling_rate=16000.0,
        buffer_size=2048,
        samples_per_read=2048,
        channel_configs=adc_channel_configs
    )

    # Audio Recorder
    audio_recorder = AudioRecorder(device=5, sample_rate=44100, channels=2, blocksize=1024)

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

    # EEG
    eeg_config = EEGConfig(com_port="COM3")


    # === Sync Signal ===
    ni_do = NIDigitalOutput(device_name="Dev1")
    sync_start_event = threading.Event()
    sync_stop_event = threading.Event()
    sync_thread_error: list[Exception] = []

    def output_sync_sequence():
        try:
            ni_do.output_sync_signal(
                line_configs=[
                    DOLineConfig(line="port1/line0", freq=1.0, duty_cycle=0.2),
                ],
                start_event=sync_start_event,
                stop_event=sync_stop_event,
                duration_s=3.5,
            )

            if sync_stop_event.is_set():
                return

            # Continue the sync signal until sync_stop_event is set.
            ni_do.output_sync_signal(
                line_configs=[
                    DOLineConfig(line="port1/line0", freq=1.0, duty_cycle=0.4),
                ],
                start_event=sync_start_event,
                stop_event=sync_stop_event,
            )
        except Exception as exc:
            sync_thread_error.append(exc)
            sync_stop_event.set()


    # === Run Workers ===

    # prepare NI DO thread and start it
    sync_thread = threading.Thread(
        target=output_sync_sequence,
        name="NI DO Sync Signal",
    )
    sync_thread.start()

    # EEG subprocess
    eeg_started_event = threading.Event()
    eeg_output_errors: list[Exception] = []

    def forward_eeg_stdout(stream):
        try:
            for line in stream:
                text = line.rstrip("\n")
                if text == "EEG_RECORDING_STARTED":
                    eeg_started_event.set()
                    continue
                print(text, flush=True)
        except Exception as exc:
            eeg_output_errors.append(exc)
            eeg_started_event.set()

    eeg_process = None
    if recording_bool.get("EEG", True):
        eeg_process = subprocess.Popen(
            eeg_config.to_subprocess_args(
                csv_path=raw_data_folder / "eeg_data.csv"
            ),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            text=True,
            bufsize=1,
        )

        eeg_stdout_thread = threading.Thread(
            target=forward_eeg_stdout,
            args=(eeg_process.stdout,),
            name="EEG Stdout Forwarder",
            daemon=True,
        )
        eeg_stdout_thread.start()

        # start impedance check
        input("Press Enter to start impedance check...\n")
        eeg_process.stdin.write("START_IMPEDANCE_CHECK\n")
        eeg_process.stdin.flush()

        input("Press Enter to stop impedance check and start recording...\n")
        eeg_process.stdin.write("STOP_IMPEDANCE_CHECK\n")
        eeg_process.stdin.flush()

        eeg_process.stdin.write("START_RECORD\n")
        eeg_process.stdin.flush()

        while not eeg_started_event.wait(timeout=0.1):
            if eeg_process.poll() is not None:
                raise RuntimeError("EEG subprocess exited before recording started.")

        if eeg_output_errors:
            raise RuntimeError("Failed to read EEG subprocess output.") from eeg_output_errors[0]
    else:
        input("Press Enter to start recordings...\n")

    # recording workers
    stop_event = threading.Event()
    worker_errors: list[tuple[str, Exception]] = []
    error_lock = threading.Lock()

    def run_worker(name: str, target, worker_started_event: threading.Event):
        try:
            target()
        except Exception as exc:
            with error_lock:
                print(f"[ERROR immediately] {name}: {repr(exc)}")
                worker_errors.append((name, exc))
            worker_started_event.set()
            stop_event.set()

    workers = [
        (
            "NI DAQ",
            lambda started_event: ni_adc.stream_to_csv(
                csv_path=raw_data_folder / "ni_data.csv",
                stop_event=stop_event,
                started_event=started_event,
            ),
        ),
        (
            "Audio",
            lambda started_event: audio_recorder.record(
                wav_path=raw_data_folder / "audio_data.wav",
                stop_event=stop_event,
                started_event=started_event,
            ),
        ),
        (
            "MocapForAll Cameras",
            lambda started_event: multi_camera_recorder.record(
                output_folder=raw_data_folder / "mfa",
                stop_event=stop_event,
                started_event=started_event,
            ),
        ),
        (
            "Motive MarkerSets",
            lambda started_event: marker_receiver.stream(
                print_enabled=False,
                csv_folder_path=raw_data_folder / "motive" / "marker_sets",
                stop_event=stop_event,
                started_event=started_event,
            ),
        ),
        (
            "Motive RigidBodies",
            lambda started_event: rigid_body_receiver.stream(
                print_enabled=False,
                csv_folder_path=raw_data_folder / "motive" / "rigid_bodies",
                stop_event=stop_event,
                started_event=started_event,
            ),
        ),
    ]

    worker_started_events: dict[str, threading.Event] = {}
    threads: list[threading.Thread] = []
    for worker_name, worker_func in workers:
        if not recording_bool.get(worker_name, False):
            print(f"Skipping {worker_name} recording as per configuration.\n")
            continue

        worker_started_event = threading.Event()
        worker_started_events[worker_name] = worker_started_event
        thread = threading.Thread(
            target=run_worker,
            kwargs={
                "name": worker_name,
                "target": partial(worker_func, worker_started_event),
                "worker_started_event": worker_started_event,
            },
            name=worker_name,
        )
        thread.start()
        threads.append(thread)

    try:
        for event in worker_started_events.values():
            if stop_event.is_set():
                break
            event.wait()

        if not stop_event.is_set():
            print("All recorders started.\n")
            sync_start_event.set()
            input("Press Enter to stop sync signal and finish recordings...\n")
            sync_stop_event.set()
            sync_thread.join()
            time.sleep(3.0)
    except KeyboardInterrupt:
        print("\nKeyboardInterrupt received. Stopping all recordings...")
    finally:
        sync_stop_event.set()
        if sync_thread.is_alive():
            sync_thread.join()

        if eeg_process is not None and eeg_process.stdin is not None:
            eeg_process.stdin.write("STOP_RECORD\n")
            eeg_process.stdin.flush()
            eeg_process.stdin.write("EXIT\n")
            eeg_process.stdin.flush()
            eeg_process.wait()

        stop_event.set()
        for thread in threads:
            thread.join()

    if sync_thread_error:
        raise RuntimeError("NI DO Sync failed.") from sync_thread_error[0]

    if worker_errors:
        for worker_name, error in worker_errors:
            print(f"[ERROR] {worker_name}: {error}")
        raise RuntimeError("One or more recorder workers failed.")


if __name__ == "__main__":
    main()
