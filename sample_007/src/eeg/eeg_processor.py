import argparse
from pathlib import Path
import threading
import multiprocessing as mp
import sys
import queue
import json

from src.eeg.eeg_recorder import EEGConfig, EEGRecorder, EEG_CHANNELS
from src.plot.live_plotter import run_live_plot


def start_live_plot_process(enabled: bool, plot_groups):
    if not enabled:
        return None, None, None, None

    plot_queue = mp.Queue(maxsize=1)
    plot_queue.cancel_join_thread()
    plot_start_event = mp.Event()
    plot_stop_event = mp.Event()

    plot_process = mp.Process(
        target=run_live_plot,
        kwargs={
            "plot_queue": plot_queue,
            "start_event": plot_start_event,
            "stop_event": plot_stop_event,
            "channel_labels": EEG_CHANNELS + ["Sync Signal"],
            "plot_groups": plot_groups,
            "window_seconds": 5.0,
            "title": "EEG",
        },
        name="EEG Live Plot Process",
    )
    plot_process.start()

    return plot_queue, plot_start_event, plot_stop_event, plot_process


def send_latest_to_plot(plot_queue, plot_start_event, data):
    if plot_queue is None or plot_start_event is None or not plot_start_event.is_set():
        return

    try:
        plot_queue.put_nowait(data)
    except queue.Full:
        try:
            plot_queue.get_nowait()
        except queue.Empty:
            pass

        try:
            plot_queue.put_nowait(data)
        except queue.Full:
            pass


def stop_live_plot_process(plot_queue, plot_stop_event, plot_process):
    if plot_stop_event is not None:
        plot_stop_event.set()

    if plot_process is not None:
        plot_process.join(timeout=5.0)
        if plot_process.is_alive():
            plot_process.terminate()
            plot_process.join()

    if plot_queue is not None:
        plot_queue.close()
        plot_queue.cancel_join_thread()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--com-port", type=str, required=True)
    parser.add_argument("--csv-path", type=Path, required=True)
    parser.add_argument("--live-plot-enabled", action="store_true")
    parser.add_argument("--plot-groups", type=str, required=True)
    args = parser.parse_args()

    eeg_config = EEGConfig(com_port=args.com_port)
    eeg_recorder = EEGRecorder(com_port=eeg_config.com_port)

    stop_imp = threading.Event()
    stop_event = threading.Event()
    started_event = threading.Event()

    imp_thread = None
    record_thread = None

    eeg_plot_groups = [
        (group_name, channel_indices)
        for group_name, channel_indices in json.loads(args.plot_groups)
    ]

    plot_queue, plot_start_event, plot_stop_event, plot_process = start_live_plot_process(
        enabled=args.live_plot_enabled,
        plot_groups=eeg_plot_groups
    )

    def send_to_plot(data):
        send_latest_to_plot(plot_queue, plot_start_event, data)

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
                        "plot_callback": send_to_plot if args.live_plot_enabled else None,
                    },
                    name="EEG Recording",
                )

                record_thread.start()
                started_event.wait()
                if plot_start_event is not None:
                    plot_start_event.set()
                print("EEG_RECORDING_STARTED", flush=True)

        elif cmd == "STOP_RECORD":
            if record_thread is not None:

                stop_event.set()
                record_thread.join()
                record_thread = None

                stop_live_plot_process(plot_queue, plot_stop_event, plot_process)
                plot_queue = None
                plot_start_event = None
                plot_stop_event = None
                plot_process = None

        elif cmd == "EXIT":
            stop_imp.set()
            stop_event.set()

            if imp_thread is not None and imp_thread.is_alive():
                imp_thread.join()

            if record_thread is not None and record_thread.is_alive():
                record_thread.join()

            stop_live_plot_process(plot_queue, plot_stop_event, plot_process)

            break


if __name__ == "__main__":
    main()
