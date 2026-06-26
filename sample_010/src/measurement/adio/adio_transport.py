import time
import threading
import queue
from queue import Queue
from typing import Optional

import ftd2xx
import ftd2xx.defines as fd


class ADioTransport:
    def __init__(
            self,
            serial: str,
            in_timeout_ms: int = 100,
            out_timeout_ms: int = 100,
            latency_ms: int = 2,
            usb_in_kb: int = 64,
            usb_out_kb: int = 64,
            ):
        self.serial: str = serial
        self.in_timeout_ms: int = in_timeout_ms
        self.out_timeout_ms: int = out_timeout_ms
        self.latency_ms: int = latency_ms
        self.usb_in_kb: int = usb_in_kb
        self.usb_out_kb: int = usb_out_kb
        self.handle: Optional[ftd2xx.FTD2XX] = None

        self.cmd_lock = threading.Lock()

        self._rx_buf = bytearray()
        self._route_cmd_responses = threading.Event()
        self._cmd_response_queue = Queue()

    @staticmethod
    def list_serials() -> list[str]:
        """
        Get a list of serial numbers for connected FTDI devices.
        """
        devices: list = ftd2xx.listDevices() or []
        serials: list[str] = []

        for dev in devices:
            if isinstance(dev, (bytes, bytearray)):
                dev = dev.decode(errors="ignore")
            serials.append(str(dev).strip())

        return serials

    def open(self) -> "ADioTransport":
        """
        Open the device. If it's already open, do nothing.
        """
        if self.handle is not None:
            return self
        
        try:
            handle: ftd2xx.FTD2XX = ftd2xx.openEx(self.serial.encode("ascii"))

            handle.resetDevice()
            time.sleep(0.1)

            handle.purge(fd.PURGE_RX | fd.PURGE_TX)
            handle.setTimeouts(self.in_timeout_ms, self.out_timeout_ms)
            handle.setUSBParameters(self.usb_in_kb * 1024, self.usb_out_kb * 1024)
            handle.setLatencyTimer(self.latency_ms)
            handle.setFlowControl(fd.FLOW_NONE, 0, 0)
            handle.purge(fd.PURGE_RX | fd.PURGE_TX)

            self.handle = handle

            return self

        except Exception as e:
            available_serials = ", ".join(self.list_serials())

            raise RuntimeError(
                f"Failed to open ADioTransport with serial {self.serial}.\n"
                f"Available serials: {available_serials}"
            ) from e

    def close(self) -> None:
        """
        Close the device if it's open.
        """
        if self.handle is not None:
            self.handle.close()
            self.handle = None

    def __enter__(self) -> "ADioTransport":
        """
        Context manager entry: opens the device and returns self.
        """
        self.open()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        """
        Context manager exit: closes the device.
        """
        self.close()

    def read_until_hash(self, timeout: float = 1.0) -> Optional[bytes]:
        """
        Read a line ending with '#' from the device within the specified timeout.
        """
        deadline = time.time() + timeout

        while time.time() < deadline:
            hash_pos = self._rx_buf.find(b"#")
            if hash_pos >= 0:
                packet = bytes(self._rx_buf[:hash_pos + 1])
                del self._rx_buf[:hash_pos + 1]
                return packet

            n = self.handle.getQueueStatus()
            if n > 0:
                self._rx_buf.extend(self.handle.read(n))
            else:
                time.sleep(0.001)

        return None

    def set_command_response_routing(self, enabled: bool) -> None:
        if enabled:
            self._route_cmd_responses.set()
        else:
            self._route_cmd_responses.clear()

    def route_command_response(self, packet: bytes) -> bool:
        text = packet.strip()
        if text.startswith((b"*OK", b"*NG")):
            self._cmd_response_queue.put(text)
            return True
        return False

    def read_stream_packet(self, adc_payload_size: int, timeout: float = 1.0) -> Optional[bytes]:
        """
        Read one packet while ADC streaming is active.

        ADC packets are fixed length (*40 + ch + payload + #), while command
        responses such as *OK# and *NG# are variable length.
        """
        deadline = time.time() + timeout
        adc_packet_size = 4 + adc_payload_size + 1

        while time.time() < deadline:
            markers = [
                pos for pos in (
                    self._rx_buf.find(b"*40"),
                    self._rx_buf.find(b"*OK"),
                    self._rx_buf.find(b"*NG"),
                )
                if pos >= 0
            ]

            if markers:
                first_marker = min(markers)
                if first_marker > 0:
                    del self._rx_buf[:first_marker]
            elif len(self._rx_buf) > 2:
                del self._rx_buf[:-2]

            if self._rx_buf.startswith(b"*40"):
                if len(self._rx_buf) >= adc_packet_size:
                    packet = bytes(self._rx_buf[:adc_packet_size])
                    if packet.endswith(b"#"):
                        del self._rx_buf[:adc_packet_size]
                        while self._rx_buf[:1] in (b"\r", b"\n"):
                            del self._rx_buf[:1]
                        return packet

                    del self._rx_buf[:1]

            elif self._rx_buf.startswith((b"*OK", b"*NG")):
                hash_pos = self._rx_buf.find(b"#")
                if hash_pos >= 0:
                    packet = bytes(self._rx_buf[:hash_pos + 1])
                    del self._rx_buf[:hash_pos + 1]
                    while self._rx_buf[:1] in (b"\r", b"\n"):
                        del self._rx_buf[:1]
                    return packet

            n = self.handle.getQueueStatus()
            if n > 0:
                self._rx_buf.extend(self.handle.read(n))
            else:
                time.sleep(0.001)

        return None
    
    def write(self, command: str) -> None:
        """
        Write a command to the device.
        """
        self.handle.write(command.encode())

    def send_cmd(self, command: str, timeout: float = 1.0) -> str:
        """
        Send a command to the device and wait for a response.
        """
        with self.cmd_lock:
            self.write(command)

            if self._route_cmd_responses.is_set():
                try:
                    resp = self._cmd_response_queue.get(timeout=timeout)
                except queue.Empty:
                    resp = None
            else:
                resp = self.read_until_hash(timeout)

            if resp is None:
                raise TimeoutError(
                    f"Timeout waiting for response to {command}"
                )

            return resp.decode(errors="ignore").strip()
    
    @property
    def bytes_available(self) -> int:
        return self.handle.getQueueStatus()
    
    def purge(self) -> None:
        """
        Purge both RX and TX buffers.
        """
        self.handle.purge(fd.PURGE_RX | fd.PURGE_TX)

    def flush_input_buffer(self, quiet_time: float = 0.05) -> None:
        """
        Flush the input buffer by reading until no new data arrives for quiet_time seconds.
        """
        deadline = time.time() + quiet_time

        while time.time() < deadline:
            n = self.handle.getQueueStatus()

            if n > 0:
                self.handle.read(n)
                deadline = time.time() + quiet_time
            else:
                time.sleep(0.001)

    def reset_all(self) -> None:
        """
        Reset all channels to default settings.
        """
        self.purge()
        _ = self.send_cmd("*F0000000#", timeout=1.0)
        self.flush_input_buffer()
