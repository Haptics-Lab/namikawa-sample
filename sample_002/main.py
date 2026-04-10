from pathlib import Path

from src.ni_adc import ChannelConfig, NIADC, TerminalConfiguration

def main():
    channel_configs = [
        ChannelConfig(ch="ai0", ch_label="Channel 0", terminal_config=TerminalConfiguration.RSE, voltage_range=(-1.0, 1.0)),
        ChannelConfig(ch="ai1", ch_label="Channel 1", terminal_config=TerminalConfiguration.RSE, voltage_range=(-1.0, 1.0)),
        ChannelConfig(ch="ai2", ch_label="Channel 2", terminal_config=TerminalConfiguration.RSE, voltage_range=(-1.0, 1.0)),
        ChannelConfig(ch="ai3", ch_label="Channel 3", terminal_config=TerminalConfiguration.RSE, voltage_range=(-1.0, 1.0)),
    ]

    adc = NIADC(
        device_name="Dev1",
        sampling_rate=16000.0,
        buffer_size=2048,
        samples_per_read=2048,
        channel_configs=channel_configs
    )

    adc.stream_to_csv(Path("output\\ni_data.csv"))


if __name__ == "__main__":
    main()
