from pathlib import Path
import threading
import time

from src.adio_adc import ADioADC, ADioADCConfig
from src.adio_pwm import ADioPWM, ADioPWMConfig
from src.adio_transport import ADioTransport

def main():
    adio_pwm_config = ADioPWMConfig(
        bit=0,
        freq_hz=0,
        duty=0.40,
        idle_state=0
    )

    adio_adc_config = ADioADCConfig(
        fs=16000,
        chunk_rate_hz=200,
        request_chunks_per_command=50,
        channels={
            0: "Tactile LI",
            1: "Tactile LT",
            2: "Tactile RI",
            3: "Tactile RT",
            5: "EMG LE",
            6: "EMG LF",
            7: "EMG RE",
            8: "EMG RF",
            10: "Sync Signal"
        },
        input_range=5.0,
    )


    io = ADioTransport(serial="FT9IK4VX")
    io.open()

    sync_start_event = threading.Event()
    sync_stop_event = threading.Event()

    adc_stop_event = threading.Event()

    pwm = ADioPWM(io, adio_pwm_config)
    adc = ADioADC(transport=io, config=adio_adc_config)

    sync_thread = threading.Thread(
        target=pwm.output_sync_signal,
        kwargs={
            "start_event": sync_start_event,
            "stop_event": sync_stop_event,
            "duration_s": None
        },
        daemon=False,
    )

    sync_thread.start()

    adc_thread = threading.Thread(
        target=adc.stream_to_csv,
        kwargs={
            "csv_path": Path("output") / "adio_data.csv",
            "stop_event": adc_stop_event,
        },
        daemon=False,
    )

    adc_thread.start()

    input("Press Enter to start sync signal...\n")
    sync_start_event.set()

    input("Press Enter to stop sync signal...\n")
    sync_stop_event.set()

    time.sleep(3.0)
    adc_stop_event.set()

    sync_thread.join()
    adc_thread.join()
    io.close()

if __name__ == "__main__":
    main()
