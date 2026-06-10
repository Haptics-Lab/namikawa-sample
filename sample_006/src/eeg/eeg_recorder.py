import sys
import threading
from pathlib import Path
import csv
import time
from dataclasses import dataclass


EEG_CHANNELS = ["Fp1", "Fz", "Fp2", "C3", "Cz", "C4", "O1", "O2", "T8", "T7", "Pz"]


@dataclass(frozen=True)
class EEGConfig:
    com_port: str

    def to_subprocess_args(self, csv_path: Path) -> list[str]:
        return [
            sys.executable,
            "-m",
            "src.eeg.eeg_processor",
            "--com-port", self.com_port,
            "--csv-path", str(csv_path),
        ]


class EEGRecorder:
    def __init__(self, com_port: str):
        from src.eeg import OrbViewAPI_py313 as orb

        self.com_port = com_port
        self.fs = 1000
        self.oif = orb.OIF()
        self.connected: bool = False

    def connect(self):
        self.oif.set_ch_all()
        self.oif.change_buffer_length(5000)
        self.oif.connect(self.com_port)
        self.connected = True

    def check_impedance(self, stop_event: threading.Event):
        if not self.connected:
            self.connect()
        self.oif.imp_check_start()
        print("    Checking impedance...", flush=True)

        labels = ["Ref"] + EEG_CHANNELS

        try:
            while not stop_event.is_set():
                imp_res = self.oif.imp_check()
                print("    ", "  ".join(f"{label}: {value}" for label, value in zip(labels, imp_res)), flush=True)

                if stop_event.wait(1.0):
                    break
        finally:
            self.oif.imp_check_stop()

    def stream_to_csv(
            self,
            csv_path: Path,
            stop_event: threading.Event,
            started_event: threading.Event
            ):
        if not self.connected:
            self.connect()

        csv_path.parent.mkdir(parents=True, exist_ok=True)

        header = ["Sample Index", "EEG Time [s]", "Estimated Wall Clock [s]"] + EEG_CHANNELS + ["Sync Signal"]

        self.oif.start()
        self.oif.inst_on(5000)
        time.sleep(5.0)
        self.oif.orbtobuffer_interval(1000)
        self.oif.clear_memory()

        print("Started EEG streaming.", flush=True)
        print(f"    Writing to {csv_path}", flush=True)

        started_event.set()

        sample_index = 0
        prev_received_time_ns = None

        try:
            with open(csv_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(header)

                while not stop_event.is_set():
                    res = self.oif.getfrombuffer(1000)

                    received_time_ns = time.time_ns()
                    if prev_received_time_ns is None:
                        prev_received_time_ns = received_time_ns - len(res) * 1e9 / self.fs
                    interval_sec = (received_time_ns - prev_received_time_ns) / len(res)

                    rows = [
                        [sample_index + i, (sample_index + i)/self.fs, (prev_received_time_ns + interval_sec * (i + 1))/1e9] + list(row[1:13])
                        for i, row in enumerate(res)
                    ]

                    writer.writerows(rows)
                    sample_index += len(rows)
                    prev_received_time_ns = received_time_ns

        finally:
            self.oif.orbtobuffer_stopinterval()
            self.oif.end()
            self.oif.disconnect()
            print("Stopped EEG streaming.", flush=True)


if __name__ == "__main__":
    recorder = EEGRecorder(com_port="COM3")

    stop_imp = threading.Event()
    imp_thread = threading.Thread(
        target=recorder.check_impedance,
        args=(stop_imp,)
    )
    imp_thread.start()

    input("Press Enter to stop impedance check and start recording...\n")
    stop_imp.set()
    imp_thread.join()

    csv_path = Path("output") / "test" / "eeg_data.csv"

    started_event = threading.Event()
    stop_stream = threading.Event()
    stream_thread = threading.Thread(
        target=recorder.stream_to_csv,
        kwargs={
            "csv_path": csv_path,
            "stop_event": stop_stream,
            "started_event": started_event,
        },
    )
    stream_thread.start()
    started_event.wait()

    input("Press Enter to stop recording...\n")
    stop_stream.set()
    stream_thread.join()
