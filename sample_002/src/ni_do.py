from dataclasses import dataclass
import threading
import time

import nidaqmx
from nidaqmx.constants import LineGrouping

@dataclass(frozen=True)
class LineConfig:
    line: str
    freq: float = 1.0
    duty_cycle: float = 0.4
    idle_state: bool = False

class NIDigitalOutput:
    def __init__(
            self,
            device_name: str,
            ):
        self.device_name = device_name

    def output_sync_signal(
            self,
            line_configs: list[LineConfig],
            stop_event: threading.Event,
            duration_s: float | None = None
            ):

        base_freq = line_configs[0].freq
        base_duty = line_configs[0].duty_cycle

        if any(
            config.freq != base_freq or config.duty_cycle != base_duty
            for config in line_configs
        ):
            raise ValueError("All line configs must have the same freq and duty_cycle")
        
        period_s = 1.0 / base_freq
        high_s = period_s * base_duty
        low_s = period_s - high_s

        lines = ",".join(
            f"{self.device_name}/{config.line}" for config in line_configs
        )
        
        with nidaqmx.Task() as task:
            task.do_channels.add_do_chan(
                line=lines,
                line_grouping=LineGrouping.CHAN_PER_LINE
            )

            values = [config.idle_state for config in line_configs]
            task.write(values)
            
            start_time = time.perf_counter()
            
            while not stop_event.is_set():
                elapsed_time = time.perf_counter() - start_time

                if duration_s is not None and elapsed_time >= duration_s:
                    break

                task.write([True] * len(line_configs))
                if stop_event.wait(timeout=high_s):
                    break

                task.write([False] * len(line_configs))
                if stop_event.wait(timeout=low_s):
                    break

            task.write(values)

if __name__ == "__main__":
    stop_event = threading.Event()
    ni_do = NIDigitalOutput(device_name="Dev1")

    line_configs = [
        LineConfig(line="port0/line0", freq=1.0, duty_cycle = 0.2, idle_state=False),
    ]

    ni_do.output_sync_signal(line_configs=line_configs, stop_event=stop_event, duration_s=5.0)

    line_configs = [
        LineConfig(line="port0/line0", freq=1.0, duty_cycle = 0.4, idle_state=False),
    ]
    
    thread = threading.Thread(
        target=ni_do.output_sync_signal,
        args=(line_configs, stop_event)
    )
    thread.start()

    input("Press Enter to stop sync signal...\n")

    stop_event.set()
    thread.join()
