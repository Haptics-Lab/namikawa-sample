from pathlib import Path
import random

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from src.measurement.finger_measurement import MeasurementResult


class TransferFunctionAnalyzer:
    def __init__(
            self,
            finger: str,
            selected_windows_path: Path,
            processed_data_excel_path: Path,
            transfer_function_excel_path: Path,
            window_sec: float,
            window_count: int,
            analysis_start_offset_sec: float = 9.0,
            analysis_end_offset_sec: float = 1.0,
            plot_x_limits: tuple[float, float] = (0.0, 1500.0),
            plot_save_dir: Path | None = None,
            ) -> None:
        self.finger = finger
        self.selected_windows_path = selected_windows_path
        self.processed_data_excel_path = processed_data_excel_path
        self.transfer_function_excel_path = transfer_function_excel_path
        self.window_sec = window_sec
        self.window_count = window_count
        self.analysis_start_offset_sec = analysis_start_offset_sec
        self.analysis_end_offset_sec = analysis_end_offset_sec
        self.plot_x_limits = plot_x_limits
        self.plot_save_dir = plot_save_dir

    def analyze(self, measurement: MeasurementResult) -> pd.DataFrame:
        for path in (self.selected_windows_path, self.processed_data_excel_path, self.transfer_function_excel_path, self.plot_save_dir):
            if path:
                path.parent.mkdir(parents=True, exist_ok=True)

        data = pd.read_csv(measurement.raw_csv_path).dropna()
        self.selected_windows_path.write_text("", encoding="utf-8")

        linear_transfer_functions: list[np.ndarray] = []
        db_transfer_functions: list[np.ndarray] = []
        frequency_bins: list[np.ndarray] = []
        random_generator = random.Random()

        with pd.ExcelWriter(self.processed_data_excel_path, engine="openpyxl") as excel_writer:
            for trial_number, trial_end_time in enumerate(measurement.trial_end_times, start=1):
                trial_functions, trial_db_functions, frequency_bin = self._analyze_trial(
                    data=data,
                    trial_end_time=trial_end_time,
                    sampling_rate=measurement.sampling_rate,
                    excel_writer=excel_writer,
                    sheet_name=f"Trial {trial_number}",
                    random_generator=random_generator,
                )
                linear_transfer_functions.extend(trial_functions)
                db_transfer_functions.extend(trial_db_functions)
                frequency_bins.append(frequency_bin)

        frequency_bin = self._common_frequency_bin(frequency_bins)
        mean_linear_transfer_function = np.mean(linear_transfer_functions, axis=0)
        std_linear_transfer_function = np.std(linear_transfer_functions, axis=0)
        mean_db_transfer_function = np.mean(db_transfer_functions, axis=0)
        std_db_transfer_function = np.std(db_transfer_functions, axis=0)
        linear_result = pd.DataFrame(
            {
                "Frequency [Hz]": frequency_bin,
                "Mean Transfer Function": mean_linear_transfer_function,
                "Std Transfer Function": std_linear_transfer_function,
            }
        )
        db_result = pd.DataFrame(
            {
                "Frequency [Hz]": frequency_bin,
                "Mean Transfer Function [dB]": mean_db_transfer_function,
                "Std Transfer Function [dB]": std_db_transfer_function,
            }
        )
        linear_result.to_excel(self.transfer_function_excel_path, sheet_name="linear", index=False)
        db_result.to_excel(self.transfer_function_excel_path, sheet_name="dB", index=False)

        self._show_plot(frequency_bin, mean_linear_transfer_function, std_linear_transfer_function, self.plot_x_limits, (0, 2.0), save_path=self.plot_save_dir / f"{self.finger}_linear_transfer_function.png" if self.plot_save_dir else None)
        self._show_plot(frequency_bin, mean_db_transfer_function, std_db_transfer_function, self.plot_x_limits, (-40, 5), save_path=self.plot_save_dir / f"{self.finger}_db_transfer_function.png" if self.plot_save_dir else None)

        return

    def _analyze_trial(
            self,
            data: pd.DataFrame,
            trial_end_time: float,
            sampling_rate: int,
            excel_writer: pd.ExcelWriter,
            sheet_name: str,
            random_generator: random.Random,
            ) -> tuple[list[np.ndarray], list[np.ndarray], np.ndarray]:
        trial_data = data[
            (
                data["Time [sec]"]
                <= trial_end_time - self.analysis_end_offset_sec
            )
            & (
                data["Time [sec]"]
                >= trial_end_time - self.analysis_start_offset_sec
            )
        ].reset_index(drop=True)

        samples_per_window = int(round(self.window_sec * sampling_rate))
        max_non_overlapping_windows = len(trial_data) // samples_per_window
        if max_non_overlapping_windows < self.window_count:
            raise ValueError(
                f"Not enough samples to extract {self.window_count} "
                f"non-overlapping windows of {self.window_sec} sec "
                f"({samples_per_window} samples each)."
            )

        trial_data["window_id"] = np.arange(len(trial_data)) // samples_per_window
        trial_data.to_excel(excel_writer, sheet_name=sheet_name, index=False)

        selected_window_ids = sorted(
            random_generator.sample(
                range(max_non_overlapping_windows),
                self.window_count,
            )
        )

        with self.selected_windows_path.open("a", encoding="utf-8") as output:
            print(*selected_window_ids, file=output)

        frequency_bin = np.fft.rfftfreq(samples_per_window, d = 1 / sampling_rate)
        linear_transfer_functions: list[np.ndarray] = []
        db_transfer_functions: list[np.ndarray] = []
        for window_id in selected_window_ids:
            start = window_id * samples_per_window
            end = start + samples_per_window
            window_data = trial_data.iloc[start:end]

            input_fft = np.fft.rfft(
                window_data["Tactile Finger Input"].to_numpy()
            )
            output_fft = np.fft.rfft(
                window_data[f"Tactile {self.finger} Output"].to_numpy()
            )
            linear_transfer_functions.append(np.abs(output_fft) / np.abs(input_fft))
            db_transfer_functions.append(20 * np.log10(np.abs(output_fft) / np.abs(input_fft)))

        return linear_transfer_functions, db_transfer_functions, frequency_bin

    @staticmethod
    def _common_frequency_bin(frequency_bins: list[np.ndarray]) -> np.ndarray:
        if not frequency_bins:
            raise ValueError("No trial data was analyzed.")

        first = frequency_bins[0]
        if not all(np.array_equal(first, values) for values in frequency_bins[1:]):
            raise ValueError("Frequency bins are not the same across trials.")
        return first

    @staticmethod
    def _show_plot(
            frequency_bin: np.ndarray,
            mean_transfer_function: np.ndarray,
            std_transfer_function: np.ndarray,
            x_limits: tuple[float, float],
            y_limits: tuple[float, float],
            save_path: Path | None = None,
            ) -> None:        
        plt.figure(figsize=(6, 3.5))
        plt.fill_between(frequency_bin, mean_transfer_function - std_transfer_function, mean_transfer_function + std_transfer_function, color="lightsteelblue")
        plt.plot(frequency_bin, mean_transfer_function, color="darkblue",label="Mean Transfer Function")
        plt.xlabel("Frequency [Hz]")
        plt.ylabel("Transfer Function Magnitude")
        plt.xlim(*x_limits)
        plt.ylim(*y_limits)
        plt.tight_layout()
        plt.legend(loc="lower right", bbox_to_anchor=(1.03, 0.98), frameon=False)
        plt.subplots_adjust(top=0.88)
        if save_path is not None:
            plt.savefig(save_path, dpi=300)
        plt.show()
        plt.close()
