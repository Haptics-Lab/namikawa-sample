import argparse
from pathlib import Path
import threading
import sys

from src.eeg.eeg_recorder import EEGConfig, EEGRecorder


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--com-port", type=str, required=True)
    parser.add_argument("--csv-path", type=Path, required=True)
    args = parser.parse_args()

    eeg_config = EEGConfig(com_port=args.com_port)
    eeg_recorder = EEGRecorder(com_port=eeg_config.com_port)

    stop_imp = threading.Event()
    stop_event = threading.Event()
    started_event = threading.Event()

    imp_thread = None
    record_thread = None

    for cmd in sys.stdin:
        cmd = cmd.strip()

        if cmd == "START_IMPEDANCE_CHECK":
            if imp_thread is None or not imp_thread.is_alive():

                stop_imp.clear()

                imp_thread = threading.Thread(
                    target=eeg_recorder.check_impedance,
                    args=(stop_imp,),
                    name="EEG Impedance Check",
                )
                imp_thread.start()

        elif cmd == "STOP_IMPEDANCE_CHECK":
            if imp_thread is not None:

                stop_imp.set()
                imp_thread.join()
                imp_thread = None

        elif cmd == "START_RECORD":
            if record_thread is None or not record_thread.is_alive():

                stop_event.clear()
                started_event.clear()

                record_thread = threading.Thread(
                    target=eeg_recorder.stream_to_csv,
                    kwargs={
                        "csv_path": Path(args.csv_path),
                        "stop_event": stop_event,
                        "started_event": started_event,
                    },
                    name="EEG Recording",
                )

                record_thread.start()
                started_event.wait()
                print("EEG_RECORDING_STARTED", flush=True)

        elif cmd == "STOP_RECORD":
            if record_thread is not None:

                stop_event.set()
                record_thread.join()
                record_thread = None

        elif cmd == "EXIT":
            stop_imp.set()
            stop_event.set()

            if imp_thread is not None and imp_thread.is_alive():
                imp_thread.join()

            if record_thread is not None and record_thread.is_alive():
                record_thread.join()

            break


if __name__ == "__main__":
    main()
