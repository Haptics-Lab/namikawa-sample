from pathlib import Path
import random
import threading
import time

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

from src.adio.adio_adc import ADioADC, ADioADCConfig
from src.adio.adio_transport import ADioTransport
from src.plot.live_plot_processor import (
    send_latest_to_plot,
    start_live_plot_process,
    stop_live_plot_process,
)
from src.sound import sound_player

FINGERS = ("LI", "LT", "RI", "RT")

CHANNELS = {
    0: "Tactile LI Output",
    1: "Tactile LT Output",
    2: "Tactile RI Output",
    3: "Tactile RT Output",
    5: "Tactile Finger Input",
    6: "Force",
}

def force_converter(raw_value: float) -> float:
    return 1.1251 * raw_value + 0.0049

def one_finger(io: ADioTransport, finger: str):
    if finger not in FINGERS:
        raise ValueError("Invalid finger. Must be one of LI, LT, RI, RT.")
    
    finger_index = FINGERS.index(finger)
    filtered_channels = {k: CHANNELS[k] for k in [finger_index, 3, 6]}
        
    adio_adc_config = ADioADCConfig(
        fs=16000,
        chunk_rate_hz=200,
        request_chunks_per_command=50,
        channels=filtered_channels,
        input_range=5.0,
        force_channel=6,
        force_converter=force_converter,
    )

    adio_adc = ADioADC(transport=io, config=adio_adc_config)
    
    io.reset_all()

    stop_event = threading.Event()
    started_event = threading.Event()

    plot_queue, plot_start_event, plot_stop_event, plot_process = start_live_plot_process(
        enabled=True,
        channel_labels=[CHANNELS[6]],
        plot_groups=[("Force", [0])],
        title=f"{finger} Force Live Plot",
        window_seconds=5.0,
        y_limits=(0.0, 1.5),
        y_band=(0.9, 1.1),
    )

    def plot_callback(ch: int, idx: int, values: list[float]) -> None:
        if ch != 6:
            return

        sample_index_start = idx * adio_adc_config.chunk_size
        times = [
            (sample_index_start + sample_offset) / adio_adc_config.fs
            for sample_offset in range(len(values))
        ]
        send_latest_to_plot(
            plot_queue,
            plot_start_event,
            (times, [[value] for value in values]),
        )

    stream_thread = threading.Thread(
        target=adio_adc.stream_to_csv,
        kwargs={
            "csv_path": Path("output") / "raw" / f"{finger}.csv",
            "stop_event": stop_event,
            "started_event": started_event,
            "plot_callback": plot_callback,
        }
    )

    try:
        stream_thread.start()
        started_event.wait()
        started_time = time.perf_counter()
        if plot_start_event is not None:
            plot_start_event.set()

        input("First trial - Press Enter to start playing white noise.\n")
        sound_player.play_sound(Path("src") / "sound" / "whitenoise_sample.wav")
        first_trial_end_time = time.perf_counter() - started_time

        input("Second trial - Press Enter to start playing white noise.\n")
        sound_player.play_sound(Path("src") / "sound" / "whitenoise_sample.wav")
        second_trial_end_time = time.perf_counter() - started_time

        input("Third trial - Press Enter to start playing white noise.\n")
        sound_player.play_sound(Path("src") / "sound" / "whitenoise_sample.wav")
        third_trial_end_time = time.perf_counter() - started_time

    finally:
        stop_event.set()
        stream_thread.join()
        stop_live_plot_process(plot_queue, plot_stop_event, plot_process)
        io.close()


    processed_dir = Path("output") / "processed"
    processed_dir.mkdir(parents=True, exist_ok=True)

    df: pd.DataFrame = pd.read_csv(Path("output") / "raw" / f"{finger}.csv")
    df = df.dropna()

    selected_windows_path = processed_dir / f"{finger}_selected_windows.txt"
    selected_windows_path.write_text("", encoding="utf-8")

    def trial_transfer_functions(
        df: pd.DataFrame,
        last_time: float,
        excel_writer: pd.ExcelWriter,
        sheet_name: str,
        ) -> tuple[list[np.ndarray], np.ndarray]:

        df = df[(df["Time [sec]"] <= last_time - 1.0) & (df["Time [sec]"] >= last_time - 9.0)]
        df = df.reset_index(drop=True)

        window_sec = 0.4
        window_count = 15

        fs = adio_adc_config.fs
        samples_per_window = int(round(window_sec * fs))

        max_non_overlapping_windows = len(df) // samples_per_window

        if max_non_overlapping_windows < window_count:
            raise ValueError(
                f"Not enough samples to extract {window_count} non-overlapping windows "
                f"of {window_sec} sec ({samples_per_window} samples each)."
            )

        df["window_id"] = np.arange(len(df)) // samples_per_window

        candidate_window_ids = list(range(max_non_overlapping_windows))

        df.to_excel(excel_writer, sheet_name=sheet_name, index=False)

        selected_window_ids = sorted(random.sample(candidate_window_ids, window_count))

        with selected_windows_path.open("a", encoding="utf-8") as o:
            print(*selected_window_ids, file=o)

        selected_dfs: list[pd.DataFrame] = []
        transfer_functions = []
        frequency_bin = np.fft.rfftfreq(samples_per_window, d=1 / fs)

        for window_id in selected_window_ids:
            start = window_id * samples_per_window
            end = start + samples_per_window

            window_df = df.iloc[start:end].copy()
            selected_dfs.append(window_df)

            input_signal = window_df["Tactile Finger Input"].values
            output_signal = window_df[f"Tactile {finger} Output"].values

            input_fft = np.fft.rfft(input_signal)
            output_fft = np.fft.rfft(output_signal)

            transfer_function = np.abs(output_fft) / np.abs(input_fft)
            
            transfer_functions.append(transfer_function)

        return transfer_functions, frequency_bin
    
    transfer_functions = []
    frequency_bins = []


    trial_end_times = [first_trial_end_time, second_trial_end_time, third_trial_end_time]
    excel_path = processed_dir / f"{finger}.xlsx"
    with pd.ExcelWriter(excel_path, engine="openpyxl") as excel_writer:
        for trial_number, trial_end_time in enumerate(trial_end_times, start=1):
            _transfer_functions, _frequency_bin = trial_transfer_functions(
                df,
                trial_end_time,
                excel_writer,
                sheet_name=f"Trial {trial_number}",
            )
            transfer_functions.extend(_transfer_functions)
            frequency_bins.append(_frequency_bin)

    if len(set(tuple(fb) for fb in frequency_bins)) != 1:
        raise ValueError("Frequency bins are not the same across trials.")
    else:
        frequency_bin = frequency_bins[0]

    mean_transfer_function = np.mean(transfer_functions, axis=0)
    std_transfer_function = np.std(transfer_functions, axis=0)
    transfer_function_df = pd.DataFrame({
        "Frequency [Hz]": frequency_bin,
        "Mean Transfer Function": mean_transfer_function,
        "Std Transfer Function": std_transfer_function,
    })
    transfer_function_df.to_csv(processed_dir / f"{finger}_transfer_function.csv", index=False)

    plt.figure(figsize=(10, 6))
    plt.plot(frequency_bin, mean_transfer_function, label="Mean Transfer Function")
    plt.fill_between(
        frequency_bin,
        mean_transfer_function - std_transfer_function,
        mean_transfer_function + std_transfer_function,
        color="lightblue",
        alpha=0.5,
    )
    plt.xlabel("Frequency [Hz]")
    plt.ylabel("Transfer Function Magnitude")
    plt.xlim(0, 1500)
    plt.ylim(0, 2.0)
    plt.legend()
    plt.show()

    return

def main():
    io = ADioTransport(serial="FT9IK4VX")
    io.open()

    one_finger(io, "LT")

    io.close()


if __name__ == "__main__":
    main()
