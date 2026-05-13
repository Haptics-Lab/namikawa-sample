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
            start_event: threading.Event,
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

            start_event.wait()  # Wait until the start event is set

            task.start()

            if duration_s is None:
                stop_event.wait()
            else:
                stop_event.wait(timeout=duration_s)

if __name__ == "__main__":
    ch="ctr0"
    freq=1.0
    duty_cycle=0.4
    idle_state=Level.LOW

    start_event = threading.Event()
    stop_event = threading.Event()
    ni_counter = NICounter(device_name="Dev1")

    def output_sync_sequence():
        # First marker period: 1 Hz, duty 20%, for 5 seconds
        ni_counter.output_sync_signal(
            ch_configs=[
                ChannelConfig(ch=ch, freq=freq, duty_cycle=duty_cycle*0.5, idle_state=idle_state),
            ],
            start_event=start_event,
            stop_event=stop_event,
            duration_s=5.0,
        )

        if stop_event.is_set():
            return
        
        # Main sync period: 1 Hz, duty 40%, until stop_event is set
        ni_counter.output_sync_signal(
            ch_configs=[
                ChannelConfig(ch=ch, freq=freq, duty_cycle=duty_cycle, idle_state=idle_state),
            ],
            start_event=start_event,
            stop_event=stop_event,
        )

    thread = threading.Thread(target=output_sync_sequence)

    thread.start()
    
    input("Press Enter to start sync signal...\n")
    start_event.set()
        
    input("Press Enter to stop sync signal...\n")
    stop_event.set()
    thread.join()
