from pathlib import Path
import threading

from nidaqmx.constants import Level

from src.ni_adc import ChannelConfig, NIADC, TerminalConfiguration
from src.ni_counter import ChannelConfig, NICounter
from src.ni_do import LineConfig, NIDigitalOutput


def main_adc():
    channel_configs = [
        ChannelConfig(ch="ai0", ch_label="Tactile LI", terminal_config=TerminalConfiguration.RSE, voltage_range=(-2.0, 2.0)),
        ChannelConfig(ch="ai1", ch_label="Tactile LT", terminal_config=TerminalConfiguration.RSE, voltage_range=(-2.0, 2.0)),
        ChannelConfig(ch="ai2", ch_label="Tactile RI", terminal_config=TerminalConfiguration.RSE, voltage_range=(-2.0, 2.0)),
        ChannelConfig(ch="ai3", ch_label="Tactile RT", terminal_config=TerminalConfiguration.RSE, voltage_range=(-2.0, 2.0)),
        ChannelConfig(ch="ai12", ch_label="Sync Signal", terminal_config=TerminalConfiguration.RSE, voltage_range=(-0.5, 5.0)),
    ]

    adc = NIADC(
        device_name="Dev1",
        sampling_rate=16000.0,
        buffer_size=2048,
        samples_per_read=2048,
        channel_configs=channel_configs
    )

    adc.stream_to_csv(Path("output\\ni_data.csv"))


def main_counter():
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


def main_do():
    stop_event = threading.Event()
    ni_do = NIDigitalOutput(device_name="Dev1")

    line_configs = [
        LineConfig(line="port1/line0", freq=1.0, duty_cycle = 0.2, idle_state=False),
    ]

    ni_do.output_sync_signal(line_configs=line_configs, stop_event=stop_event, duration_s=5.0)

    line_configs = [
        LineConfig(line="port1/line0", freq=1.0, duty_cycle = 0.4, idle_state=False),
    ]
    
    thread = threading.Thread(
        target=ni_do.output_sync_signal,
        args=(line_configs, stop_event)
    )
    thread.start()

    input("Press Enter to stop sync signal...\n")

    stop_event.set()
    thread.join()


if __name__ == "__main__":
    main_adc()
    # main_counter()
    # main_do()
