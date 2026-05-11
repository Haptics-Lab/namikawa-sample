from dataclasses import dataclass
import threading

import nidaqmx
from nidaqmx.constants import AcquisitionType, Level


@dataclass(frozen=True)
class ChannelConfig:
    ch: str
    freq: float = 1.0
    duty_cycle: float = 0.4
    idle_state: Level = Level.LOW


class NICounter:
    def __init__(
            self,
            device_name: str,
            ):
        self.device_name = device_name

    def output_sync_signal(
            self,
            ch_configs: list[ChannelConfig],
            stop_event: threading.Event,
            duration_s: float | None = None
            ):
        with nidaqmx.Task() as task:
            for ch_config in ch_configs:
                channel_counter = f"{self.device_name}/{ch_config.ch}"
                task.co_channels.add_co_pulse_chan_freq(
                    counter=channel_counter,
                    freq=ch_config.freq,
                    duty_cycle=ch_config.duty_cycle,
                    idle_state=ch_config.idle_state
                )
            
            task.timing.cfg_implicit_timing(sample_mode=AcquisitionType.CONTINUOUS)

            task.start()

            if duration_s is None:
                stop_event.wait()
            else:
                stop_event.wait(timeout=duration_s)

if __name__ == "__main__":
    stop_event = threading.Event()
    ni_counter = NICounter(device_name="Dev1")

    ch_configs = [
        ChannelConfig(ch="ctr0", freq=1.0, duty_cycle=0.2, idle_state=Level.LOW),
    ]
    ni_counter.output_sync_signal(ch_configs=ch_configs, stop_event=stop_event, duration_s=5.0)

    ch_configs = [
        ChannelConfig(ch="ctr0", freq=1.0, duty_cycle=0.4, idle_state=Level.LOW),
    ]

    thread = threading.Thread(
        target=ni_counter.output_sync_signal,
        args=(ch_configs, stop_event)
    )
    thread.start()
    
    input("Press Enter to stop sync signal...\n")

    stop_event.set()
    thread.join()
