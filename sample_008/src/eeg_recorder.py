import threading
from pathlib import Path
import csv

import numpy as np

from src import OrbViewAPI_py313 as orb


class EEGRecorder:
    
    def __init__(self, com_port: str):
        self.com_port = com_port

        self.oif = orb.OIF()
        self.start_connection()

    def start_connection(self):
        self.oif.set_ch_all()
        self.oif.change_buffer_length(5000)
        self.oif.connect(self.com_port)

    def check_impedance(self, stop_event: threading.Event):
        self.oif.imp_check_start()
        print("Checking impedance...")

        try:
            while not stop_event.is_set():
                imp_res = self.oif.imp_check()
                print(
                    "Ref:", imp_res[0],
                    "F3:", imp_res[1],
                    "Fz:", imp_res[2],
                    "F4:", imp_res[3],
                    "C3:", imp_res[4],
                    "Cz:", imp_res[5],
                    "C4:", imp_res[6],
                    "O1:", imp_res[7],
                    "O2:", imp_res[8],
                    "X1:", imp_res[9],
                    "X2:", imp_res[10],
                    "A1:", imp_res[11],
                )
                if stop_event.wait(1.0):
                    break
        finally:
            self.oif.imp_check_stop()

    def stream_to_csv(self, csv_path: Path, stop_event: threading.Event):
        csv_path.parent.mkdir(parents=True, exist_ok=True)
        
        self.oif.start()
        self.oif.inst_on(5000)
        print("Started EEG streaming...")
        print(f"    Writing to {csv_path}")

        header = ["POINT", "F3", "Fz", "F4", "C3", "Cz", "C4", "O1", "O2", "X1", "X2", "A1", "EXT"]

        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(header)

        self.oif.orbtobuffer_interval(1000)

        clock_long = 0
        clock_short = 0

        try:
            while not stop_event.is_set():
                res = self.oif.getfrombuffer(1000)
                data = [self.oif.get_orbdata(i) for i in range(12)]
                with open(csv_path, "a", newline="", encoding="utf-8") as f:
                    writer = csv.writer(f)
                    writer.writerow(data)

                    for i in range(len(res)):
                        row =[clock_long + i, res[i][1], res[i][2], res[i][3], res[i][4], res[i][5], res[i][6], res[i][7], res[i][8], res[i][9], res[i][10], res[i][11], res[i][12]] 
                        writer.writerow(row)
                        clock_short += 1
                    clock_long += clock_short
                    clock_short = 0
        finally:
            self.oif.orbtobuffer_stopinterval()
            self.oif.end()
            self.oif.disconnect()
            del self.oif
            print("Stopped EEG streaming.")


if __name__ == "__main__":
    recorder = EEGRecorder(com_port="COM1")

    stop_imp = threading.Event()
    imp_thread = threading.Thread(target=recorder.check_impedance, args=(stop_imp,))
    imp_thread.start()

    input("Press Enter to stop impedance check and start recording...\n")
    stop_imp.set()
    imp_thread.join()

    csv_path = Path("data/eeg.csv")
    stop_stream = threading.Event()
    stream_thread = threading.Thread(
        target=recorder.stream_to_csv,
        args=(csv_path, stop_stream)
    )
    stream_thread.start()

    input("Press Enter to stop recording...\n")
    stop_stream.set()
    stream_thread.join()
    