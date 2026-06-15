from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
import threading
import time

from src.measurement.adio.adio_adc import ADioADC, ADioADCConfig
from src.measurement.adio.adio_transport import ADioTransport
from src.measurement.sound import sound_player
from src.plot.live_plot_processor import (
    send_latest_to_plot,
    start_live_plot_process,
    stop_live_plot_process,
)


@dataclass(frozen=True)
class MeasurementResult:
    raw_csv_path: Path
    trial_end_times: tuple[float, ...]
    sampling_rate: int


class FingerMeasurement:
    def __init__(
        self,
        transport: ADioTransport,
        finger: str,
        channels: dict[int, str],
        raw_csv_path: Path,
        sound_path: Path,
        force_converter: Callable[[float], float],
        sampling_rate: int,
        chunk_rate_hz: int,
        request_chunks_per_command: int,
        input_range: float,
        trial_count: int,
        live_plot_enabled: bool = True,
        live_plot_window_seconds: float = 3.0,
        live_plot_y_limits: tuple[float, float] | None = (0.0, 1.5),
        live_plot_y_band: tuple[float, float] | None = (0.9, 1.1),
        input_func: Callable[[str], str] = input,
        play_sound: Callable[[Path], None] = sound_player.play_sound,
    ) -> None:
        self.transport = transport
        self.finger = finger
        self.channels = channels
        self.raw_csv_path = raw_csv_path
        self.sound_path = sound_path
        self.trial_count = trial_count
        self.live_plot_enabled = live_plot_enabled
        self.live_plot_window_seconds = live_plot_window_seconds
        self.live_plot_y_limits = live_plot_y_limits
        self.live_plot_y_band = live_plot_y_band
        self.input_func = input_func
        self.play_sound = play_sound

        finger_channel = self._find_channel(f"Tactile {finger} Output")
        input_channel = self._find_channel("Tactile Finger Input")
        force_channel = self._find_channel("Force")
        selected_channels = {
            channel: channels[channel]
            for channel in (finger_channel, input_channel, force_channel)
        }

        self.force_channel = force_channel
        self.adc_config = ADioADCConfig(
            fs=sampling_rate,
            chunk_rate_hz=chunk_rate_hz,
            request_chunks_per_command=request_chunks_per_command,
            channels=selected_channels,
            input_range=input_range,
            force_channel=force_channel,
            force_converter=force_converter,
        )
        self.adc = ADioADC(transport=transport, config=self.adc_config)

    def _find_channel(self, label: str) -> int:
        for channel, channel_label in self.channels.items():
            if channel_label == label:
                return channel
        raise ValueError(f"Required channel is not configured: {label}")

    def _plot_callback(self, channel: int, index: int, values: list[float]) -> None:
        if channel != self.force_channel:
            return

        sample_index_start = index * self.adc_config.chunk_size
        times = [
            (sample_index_start + sample_offset) / self.adc_config.fs
            for sample_offset in range(len(values))
        ]
        send_latest_to_plot(
            self.plot_queue,
            self.plot_start_event,
            (times, [[value] for value in values]),
        )

    def run(self) -> MeasurementResult:
        self.transport.reset_all()

        stop_event = threading.Event()
        started_event = threading.Event()

        self.plot_queue, self.plot_start_event, plot_stop_event, plot_process = start_live_plot_process(
            enabled=self.live_plot_enabled,
            channel_labels=[self.channels[self.force_channel]],
            plot_groups=[("Force", [0])],
            title=f"{self.finger} Force Live Plot",
            window_seconds=self.live_plot_window_seconds,
            y_limits=self.live_plot_y_limits,
            y_band=self.live_plot_y_band,
        )

        stream_thread = threading.Thread(
            target=self.adc.stream_to_csv,
            kwargs={
                "csv_path": self.raw_csv_path,
                "stop_event": stop_event,
                "started_event": started_event,
                "plot_callback": self._plot_callback,
            },
            name=f"{self.finger}MeasurementStream",
        )

        trial_end_times: list[float] = []
        try:
            stream_thread.start()
            started_event.wait()
            started_time = time.perf_counter()
            if self.plot_start_event is not None:
                self.plot_start_event.set()

            for trial_number in range(1, self.trial_count + 1):
                ordinal = {
                    1: "First",
                    2: "Second",
                    3: "Third",
                }.get(trial_number, f"Trial {trial_number}")
                self.input_func(
                    f"{ordinal} trial - Press Enter to start playing white noise.\n"
                )
                self.play_sound(self.sound_path)
                trial_end_times.append(time.perf_counter() - started_time)
        finally:
            stop_event.set()
            stream_thread.join()
            stop_live_plot_process(
                self.plot_queue,
                plot_stop_event,
                plot_process,
            )

        return MeasurementResult(
            raw_csv_path=self.raw_csv_path,
            trial_end_times=tuple(trial_end_times),
            sampling_rate=self.adc_config.fs,
        )
