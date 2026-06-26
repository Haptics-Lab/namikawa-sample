import time
import threading
import os
import queue
import csv
from queue import Queue
from pathlib import Path
from typing import Callable, Optional
from collections import defaultdict
from dataclasses import dataclass

from src.measurement.adio.adio_transport import ADioTransport


INPUT_VOLTAGE_TO_RANGE_CODE = {
    10.0: 0x0000,   # ±10V
    5.0: 0x0001,    # ±5V
    1.25: 0x0002,   # ±1.25V
    0.3125: 0x0003, # ±0.3125V
    0.15625: 0x0004 # ±0.15625V
}


HZ_TO_SPEED_CODE = {
    1000: 0x0000,   # 1 kHz
    2000: 0x0001,   # 2 kHz
    4000: 0x0002,   # 4 kHz
    8000: 0x0003,   # 8 kHz
    16000: 0x0004,  # 16 kHz
    32000: 0x0005,  # 32 kHz
    64000: 0x0006,  # 64 kHz
    128000: 0x0007, # 128 kHz
    256000: 0x0008  # 256 kHz
}


@dataclass
class ADioADCConfig:
    fs: int
    chunk_rate_hz: int
    request_chunks_per_command: int
    channels: dict[int, str]
    input_range: float = 5.0
    force_channel: Optional[int] = None
    force_converter: Optional[Callable[[float], float]] = None

    @property
    def request_channel_count(self) -> int:
        return max(self.channels.keys()) + 1

    @property
    def request_channels(self) -> list[int]:
        return sorted(self.channels.keys())

    @property
    def chunk_size(self) -> int:
        return int(self.fs / self.chunk_rate_hz)

    @property
    def request_interval(self) -> float:
        return self.request_chunks_per_command / self.chunk_rate_hz


class ADioADC:
    def __init__(
            self,
            transport: ADioTransport,
            config: ADioADCConfig,
            ) -> None:
        self.io = transport
        self.config = config

    def _reset_state(self) -> None:
        self.raw_queue = Queue(maxsize=4000)
        self.file_queue = Queue(maxsize=20000)
        self.recv_done = threading.Event()
        self.log_done = threading.Event()
        self.receiver_ready = threading.Event()
        self.logger_ready = threading.Event()
        self.recv_chunk_index = defaultdict(int)
        self.stop_event = threading.Event()
    
    @staticmethod
    def raw_to_voltage(raw: int, input_range: float = 5.0) -> float:
        """
        Convert a 20-bit ADC value to voltage.
        """
        # Convert 20-bit two's complement value to signed integer.
        if raw & (1 << 19):
            raw -= (1 << 20)

        lsb = input_range / (2 ** 19)
        return raw * lsb

    def payload_to_volts(self, payload: bytes) -> list[float]:
        """
        Convert a payload of 5-digit hexadecimal ADC values to voltage values.
        """
        text = payload.decode("ascii", errors="ignore")
        values = []

        for i in range(0, len(text), 5):
            hex5 = text[i:i + 5]
            raw = int(hex5, 16)
            values.append(self.raw_to_voltage(raw, self.config.input_range))

        return values
    
    def set_sampling_rate(self, fs: Optional[int] = None) -> None:
        """
        Command 0: Set ADC speed (sampling rate).
        """
        if fs is None:
            fs = self.config.fs

        if fs not in HZ_TO_SPEED_CODE:
            raise ValueError(f"Unsupported sampling rate: {fs} Hz")

        groups = [0] if fs == 256000 else [0, 1]

        for group in groups:
            cmd = f"*0{group:02X}0{HZ_TO_SPEED_CODE[fs]:04X}#"
            self.io.send_cmd(cmd)

    def set_chunk_size(self, ch: int, chunk_size: int) -> None:
        """
        Command 1: Set number of samples returned per request.
        """
        if not (0 <= chunk_size <= 0x07FF):
            raise ValueError("chunk_size must be 0..0x07FF")
        resp = self.io.send_cmd(f"*1{ch:02X}0{chunk_size:04X}#",)
        if "*NG#" in resp:
            raise RuntimeError(f"Failed to set chunk size: {resp!r}")
        
    def request_data(self, request_chunks: Optional[int] = None) -> None:
        """
        Command 4 E=1: Request ADC data for all channels.
        """
        if request_chunks is None:
            request_chunks = self.config.request_chunks_per_command
        
        cmds = "".join(
            f"*4{ch:02X}1{request_chunks - 1:04X}#"
            for ch in self.config.request_channels
        )
        self.io.write(cmds)
        
    def start_accum_all(self) -> None:
        """
        Command 4 E=2 HH=00: Start accumulation for all channels.
        """
        resp = self.io.send_cmd("*40020000#")
        if "*NG#" in resp:
            raise RuntimeError(f"Start accum failed: {resp!r}")

    def stop_accum_all(self) -> None:
        """
        Command 4 E=3 HH=00: Stop accumulation for all channels.
        """
        resp = self.io.send_cmd("*40030000#")
        if "*NG#" in resp:
            raise RuntimeError(f"Stop accum failed: {resp!r}")
        
    def set_input_range(self, ch: int, input_range: float) -> None:
        """
        Command 5: Set input range (OP-AMP gain switching)
        """
        if input_range not in INPUT_VOLTAGE_TO_RANGE_CODE:
            raise ValueError(f"Unknown input_range: {input_range}")
        range_code = INPUT_VOLTAGE_TO_RANGE_CODE[input_range]
        resp = self.io.send_cmd(f"*5{ch:02X}0{range_code:04X}#")
        if "*NG#" in resp:
            raise RuntimeError(f"Set input range failed: {resp!r}")
    
    def receive_data(self):
        """
        Receive data from the device, parse it, and put it into the raw_queue.
        """
        self.receiver_ready.set()
        self.io.set_command_response_routing(True)

        try:
            while not self.stop_event.is_set() or self.io.bytes_available > 0:
                line = self.io.read_stream_packet(5 * self.config.chunk_size, timeout=0.5)

                if line is None:
                    if self.stop_event.is_set():
                        break
                    continue

                line = line.strip(b"\r\n")

                if not (line.startswith(b"*40") and line.endswith(b"#")):
                    if not self.io.route_command_response(line):
                        print(f"[WARN] invalid ADC packet: {line[:10]!r}")
                    continue

                ch = int(line[3:4], 16)
                payload = line[4:-1]

                if ch not in self.config.channels:
                    continue

                if len(payload) != 5 * self.config.chunk_size:
                    print(
                        f"[WARN] payload size mismatch: "
                        f"got={len(payload)} expected={5 * self.config.chunk_size}"
                    )
                    continue

                idx = self.recv_chunk_index[ch]
                self.recv_chunk_index[ch] += 1

                self.raw_queue.put((ch, idx, payload), timeout=0.2)

        finally:
            self.io.set_command_response_routing(False)
            self.recv_done.set()

    def writer_thread(self, csv_path: Path):
        csv_path.parent.mkdir(parents=True, exist_ok=True)

        expected_channels = sorted(self.config.channels.keys())
        pending_chunks = defaultdict(dict)
        fs_hz = float(self.config.fs)
        flush_every_chunks = 200
        written_chunk_count = 0

        def write_rows(writer, idx, channels_to_write):
            n_samples = min(len(pending_chunks[idx][ch]) for ch in channels_to_write)

            for sample_in_chunk in range(n_samples):
                sample_index = idx * self.config.chunk_size + sample_in_chunk
                time_sec = sample_index / fs_hz
                row = [sample_index, f"{time_sec:.6f}"]

                for ch in expected_channels:
                    if ch in channels_to_write:
                        value = pending_chunks[idx][ch][sample_in_chunk]
                        row.append(f"{value:.7f}")
                    else:
                        row.append("")

                writer.writerow(row)

        def write_complete_chunks(writer):
            nonlocal written_chunk_count

            while pending_chunks:
                idx = min(pending_chunks.keys())
                if not all(ch in pending_chunks[idx] for ch in expected_channels):
                    break

                write_rows(writer, idx, expected_channels)
                del pending_chunks[idx]
                written_chunk_count += 1
                if written_chunk_count % flush_every_chunks == 0:
                    writer_file.flush()

        with csv_path.open("w", newline="", encoding="utf-8") as writer_file:
            writer = csv.writer(writer_file)
            writer.writerow(["Sample Index", "Time [sec]"] + [self.config.channels[ch] for ch in expected_channels])

            while not self.log_done.is_set() or not self.file_queue.empty():
                try:
                    ch, idx, values = self.file_queue.get(timeout=0.5)
                except queue.Empty:
                    continue

                pending_chunks[idx][ch] = values
                write_complete_chunks(writer)

            for idx in sorted(pending_chunks.keys()):
                channels_to_write = sorted(pending_chunks[idx].keys())
                if channels_to_write:
                    write_rows(writer, idx, channels_to_write)

            writer_file.flush()
            os.fsync(writer_file.fileno())

    def logging_loop(
            self,
            plot_callback: Optional[Callable[[int, int, list[float]], None]] = None,
            ):
        self.logger_ready.set()

        while not self.recv_done.is_set() or not self.raw_queue.empty():
            try:
                ch, idx, payload = self.raw_queue.get(timeout=0.2)
            except queue.Empty:
                continue

            try:
                values = self.payload_to_volts(payload)
                if self.config.force_channel is not None and ch == self.config.force_channel:
                    values = [self.config.force_converter(v) if self.config.force_converter is not None else v for v in values]
                    
            except Exception as e:
                print(f"[WARN] parse/convert failed: ch{ch} idx={idx} err={e}")
                continue

            if len(values) != self.config.chunk_size:
                print(
                    f"[WARN] converted size mismatch: "
                    f"ch{ch} idx={idx} got={len(values)} expected={self.config.chunk_size}"
                )
                continue

            if plot_callback is not None:
                try:
                    plot_callback(ch, idx, values)
                except Exception as e:
                    print(f"[WARN] live plot callback failed: ch{ch} idx={idx} err={e}")

            try:
                self.file_queue.put((ch, idx, values), timeout=0.5)
            except queue.Full:
                print(f"[QUEUE FULL: file_queue] ch{ch} idx={idx}")
                continue

        self.log_done.set()

    def send_data_request_loop(self, interval):

        next_time = time.perf_counter()

        while not self.stop_event.is_set():
            try:
                self.request_data()
            except Exception as e:
                print(f"[SEND] Error is occurred during write: {e}")
                break

            next_time += interval
            sleep_time = next_time - time.perf_counter()
            if sleep_time > 0:
                self.stop_event.wait(sleep_time)
            else:
                print(f"[WARN] Data request is behind (behind by {-sleep_time:.3f}s)")
                next_time = time.perf_counter()

    def stream_to_csv(
            self,
            csv_path: Path,
            stop_event: threading.Event,
            started_event: threading.Event,
            plot_callback: Optional[Callable[[int, int, list[float]], None]] = None,
            ):
        self._reset_state()

        if self.config.chunk_size > 2047:
            raise ValueError(f"CHUNK_SIZE={self.config.chunk_size} is too large. Max is 2047.")

        if self.io.handle is None:
            raise RuntimeError("ADioTransport is not open.")

        writer = None
        recv_thread = None
        log_thread = None
        send_thread = None

        try:
            for ch in self.config.request_channels:
                self.set_chunk_size(ch, self.config.chunk_size)
                self.set_input_range(ch, self.config.input_range)

            self.set_sampling_rate()
            self.start_accum_all()

            writer = threading.Thread(target=self.writer_thread, args=(csv_path,), name="ADioADCWriter", daemon=False)
            writer.start()

            recv_thread = threading.Thread(target=self.receive_data, name="ADioADCReceiver", daemon=False)
            recv_thread.start()
            self.receiver_ready.wait(timeout=3)

            log_thread = threading.Thread(
                target=self.logging_loop,
                kwargs={"plot_callback": plot_callback},
                name="ADioADCLogger",
                daemon=False,
            )
            log_thread.start()
            self.logger_ready.wait(timeout=2)

            send_thread = threading.Thread(
                target=self.send_data_request_loop,
                args=(self.config.request_interval,),
                name="ADioADCRequester",
                daemon=False,
            )
            send_thread.start()

            print("Started streaming data with ADio ADC.")
            print(f"    Writing to {csv_path}")
            print(f"    Requesting data...({self.config.request_interval:.3f}s interval)\n")
            started_event.set()

            stop_event.wait()
            print("Stopping data streaming...")

        finally:
            self.stop_event.set()

            if send_thread is not None and send_thread.is_alive():
                send_thread.join(timeout=2.0)

            if recv_thread is not None and recv_thread.is_alive():
                recv_thread.join(timeout=2.0)

            try:
                self.stop_accum_all()
            except Exception as e:
                print(f"[WARN] Failed to stop accumulation: {e}")

            if log_thread is not None and log_thread.is_alive():
                log_thread.join(timeout=5.0)

            if writer is not None and writer.is_alive():
                writer.join(timeout=5.0)

            print("Stopped ADio ADC data streaming.\n")
