import csv
import threading
from pathlib import Path
from dataclasses import dataclass
import time
from typing import Callable

import numpy as np
import nidaqmx
from nidaqmx.constants import TerminalConfiguration, AcquisitionType


@dataclass(frozen=True)
class ChannelConfig:

    """
	Configuration for a single analog input channel.
    Attributes:
    - ch: Channel name (e.g., "ai0")
    - terminal_config: Terminal configuration (e.g., TerminalConfiguration.DIFF, TerminalConfiguration.RSE)
    - voltage_range: Tuple of (min_voltage, max_voltage) for the channel
    - ch_label: Optional label for the channel, default is an empty string
	"""
    ch: str
    terminal_config: TerminalConfiguration
    voltage_range: tuple[float, float] = (-5.0, 5.0)
    ch_label: str = ""


class NIADC:
	
    def __init__(
            self,
            device_name: str,
            sampling_rate: float,
            buffer_size: int,
            samples_per_read: int,
            channel_configs: list[ChannelConfig]
            ):
        if samples_per_read > buffer_size:
            raise ValueError("samples_per_read must be less than or equal to buffer_size.")
        self.device_name = device_name
        self.sampling_rate = sampling_rate
        self.buffer_size = buffer_size
        self.samples_per_read = samples_per_read
        self.ch_configs = channel_configs

    def stream_to_csv(
            self,
            csv_path: Path,
            stop_event: threading.Event,
            preview_listener: Callable[[dict], None] | None = None,
            ):
        
        csv_path.parent.mkdir(parents=True, exist_ok=True)

        with nidaqmx.Task() as task, csv_path.open("w", newline="", encoding="utf-8") as f:

            # Add channels to the task
            for ch_config in self.ch_configs:
                channel_string = f"{self.device_name}/{ch_config.ch}"
                task.ai_channels.add_ai_voltage_chan(
                    channel_string,
                    name_to_assign_to_channel=ch_config.ch_label,
                    terminal_config=ch_config.terminal_config,
                    min_val=ch_config.voltage_range[0],
                    max_val=ch_config.voltage_range[1]
                )

            # Configure sampling timing
            task.timing.cfg_samp_clk_timing(
				rate=self.sampling_rate,
				sample_mode=AcquisitionType.CONTINUOUS,
				samps_per_chan=self.buffer_size,
			)

            writer = csv.writer(f)
            # Write header row
            header = [
                "Sample Index",
                "DAQ Time [s]",
                "Wall Clock [s]",
                "Perf Counter [ns]",
            ] + task.channel_names
            writer.writerow(header)

            sample_idx = 0
            expected_block_sec = self.samples_per_read / self.sampling_rate

            task.start()
            print(f"Started streaming data with NI DAQ.")
            print(f"    Writing to {csv_path}")

            try:
                while not stop_event.is_set():
                    data = task.read(
                        number_of_samples_per_channel=self.samples_per_read,
                        timeout=max(10.0, expected_block_sec * 5),
                    )
                    received_time_ns = time.time_ns()
                    received_perf_counter_ns = time.perf_counter_ns()

                    data_arr = np.atleast_2d(np.asarray(data, dtype=float)).T

                    if preview_listener is not None and data_arr.size > 0:
                        preview_listener(
                            {
                                "sample_idx": sample_idx,
                                "channel_names": list(task.channel_names),
                                "values": data_arr[-1].tolist(),
                            }
                        )

                    for i in range(data_arr.shape[0]):
                        daq_time = sample_idx / self.sampling_rate
                        row = [
                            sample_idx,
                            f"{daq_time:.6f}",
                            received_time_ns / 1e9,
                            received_perf_counter_ns,
                        ] + data_arr[i].tolist()
                        writer.writerow(row)
                        sample_idx += 1
            finally:
                print("Stopped NI data streaming.")


if __name__ == "__main__":

    channel_configs = [
        ChannelConfig(ch="ai0", ch_label="EMG LE", terminal_config=TerminalConfiguration.RSE, voltage_range=(-5.0, 5.0)),
        ChannelConfig(ch="ai1", ch_label="EMG LF", terminal_config=TerminalConfiguration.RSE, voltage_range=(-5.0, 5.0)),
        ChannelConfig(ch="ai2", ch_label="EMG RE", terminal_config=TerminalConfiguration.RSE, voltage_range=(-5.0, 5.0)),
        ChannelConfig(ch="ai3", ch_label="EMG RF", terminal_config=TerminalConfiguration.RSE, voltage_range=(-5.0, 5.0)),
        ChannelConfig(ch="ai8", ch_label="Tactile LI", terminal_config=TerminalConfiguration.RSE, voltage_range=(-2.0, 2.0)),
        ChannelConfig(ch="ai9", ch_label="Tactile LT", terminal_config=TerminalConfiguration.RSE, voltage_range=(-2.0, 2.0)),
        ChannelConfig(ch="ai10", ch_label="Tactile RI", terminal_config=TerminalConfiguration.RSE, voltage_range=(-2.0, 2.0)),
        ChannelConfig(ch="ai11", ch_label="Tactile RT", terminal_config=TerminalConfiguration.RSE, voltage_range=(-2.0, 2.0)),
        ChannelConfig(ch="ai12", ch_label="Sync Signal", terminal_config=TerminalConfiguration.RSE, voltage_range=(-0.5, 5.0))
    ]

    adc = NIADC(
        device_name="Dev1",
        sampling_rate=16000.0,
        buffer_size=2048,
        samples_per_read=2048,
        channel_configs=channel_configs
    )

    stop_event = threading.Event()
    thread = threading.Thread(
        target=adc.stream_to_csv,
        args=(Path("output") / "test" / "ni_data.csv", stop_event),
    )

    thread.start()

    try:
        input("Press Enter to stop streaming...\n")
    finally:
        stop_event.set()
        thread.join()
