from pathlib import Path

import matplotlib.pyplot as plt

from src.analysis.transfer_function_analyzer import TransferFunctionAnalyzer
from src.measurement.adio.adio_transport import ADioTransport
from src.measurement.finger_measurement import FingerMeasurement


plt.rcParams['font.family'] = 'Times New Roman'
plt.rcParams['font.size'] = 12
plt.rcParams['xtick.direction'] = 'in'
plt.rcParams['ytick.direction'] = 'in'


# Measurement target and device
DEVICE_SERIAL = "FT9I7HE7"

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
    return 1.1332 * raw_value


def one_finger(io: ADioTransport, finger: str) -> None:
    if finger not in FINGERS:
        raise ValueError("Invalid finger. Must be one of LI, LT, RI, RT.")

    measurement = FingerMeasurement(
        transport = io,
        finger = finger,
        channels = CHANNELS,
        raw_csv_path = Path("output") / "raw" / f"{finger}.csv",
        sound_path = Path("src") / "measurement" / "sound" / "whitenoise_sample.wav",
        force_converter = force_converter,
        sampling_rate = 16000,
        chunk_rate_hz = 200,
        request_chunks_per_command = 50,
        input_range = 5.0,
        trial_count = 3, # Trial count per finger
    ).run()

    TransferFunctionAnalyzer(
        finger=finger,
        selected_windows_path = Path("output") / "processed" / f"{finger}_selected_windows.txt",
        processed_data_excel_path = Path("output") / "processed" / f"{finger}_processed_data.xlsx",
        transfer_function_excel_path = Path("output") / "processed" / f"{finger}_transfer_function.xlsx",
        window_sec = 0.4,
        window_count = 15,
        plot_save_dir = Path("output") / "processed",
    ).analyze(measurement)


def main() -> None:
    io = ADioTransport(serial=DEVICE_SERIAL)
    io.open()

    try:
        one_finger(io, finger="LI")
        one_finger(io, finger="LT")
        one_finger(io, finger="RI")
        one_finger(io, finger="RT")

    finally:
        io.close()


if __name__ == "__main__":
    main()
