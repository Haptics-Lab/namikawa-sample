import threading
from pathlib import Path

from src.eeg_recorder import EEGRecorder


def main():
    recorder = EEGRecorder(com_port="COM3")

    # Inpedance check
    stop_imp = threading.Event()
    imp_thread = threading.Thread(
        target=recorder.check_impedance,
        args=(stop_imp,)
    )
    imp_thread.start()

    input("Press Enter to stop impedance check and start recording...\n")
    stop_imp.set()
    imp_thread.join()

    # Start EEG recording
    csv_path = Path("output/eeg.csv")

    started_event = threading.Event()
    stop_stream = threading.Event()
    stream_thread = threading.Thread(
        target=recorder.stream_to_csv,
        args=(csv_path, stop_stream, started_event)
    )
    stream_thread.start()
    started_event.wait()

    input("Press Enter to stop recording...\n")
    stop_stream.set()
    stream_thread.join()


if __name__ == "__main__":
    main()
