from dataclasses import dataclass
import threading
from typing import Optional

from src.adio_transport import ADioTransport


@dataclass(frozen=True)
class ADioPWMConfig:
    """
    Configuration for PWM measurement.
    """
    bit: int            # 0..7 (D0..D7)
    freq_hz: int        # 0..4095 (1Hz step)
    duty: float         # 0.0..1.0
    idle_state: int = 0 # 0=LOW, 1=HIGH


class ADioPWM:
    """
    Class for controlling PWM output on ADio GPIO (D0..D7).
    """
    def __init__(
            self,
            transport: ADioTransport,
            config: ADioPWMConfig
            ) -> None:
        self.io = transport
        self.config = config
        self.set_dir_output(self.config.bit)        # must be output for PWM to work
        self.set_pwm_mode(self.config.bit, True)    # select PWM mode

    @staticmethod
    def _bit_mask(bit: int) -> int:
        if not (0 <= bit <= 7):
            raise ValueError("bit must be 0..7")
        return 1 << bit
    
    def set_dir_output(self, bit: int) -> None:
        """
        Command 9 (DIR): set the specified GPIO bit to OUTPUT.
        Note: In the manual, DDDD data says 1=input, 0=output.
        This function enables only the bit via HH mask and set DDDD bit to 0.
        """
        hh = self._bit_mask(bit)    # enable only this bit
        dddd = 0x0000               # 0 means output for enabled bits
        resp = self.io.send_cmd(f"*9{hh:02X}0{dddd:04X}#", timeout=1.0)
        if "*NG#" in resp:
            raise RuntimeError(f"DIR set failed: {resp!r}")
        
    def set_pwm_mode(self, bit: int, enable: bool = True) -> None:
        """
        Command A (E=0): PWM/GPIO mode switch.
        DDDD bit: 1=PWM, 0=GPIO for enabled bits.
        """
        hh = self._bit_mask(bit)    # enable only this bit
        dddd = self._bit_mask(bit) if enable else 0x0000
        resp = self.io.send_cmd(f"*A{hh:02X}0{dddd:04X}#", timeout=1.0)
        if "*NG#" in resp:
            raise RuntimeError(f"PWM mode set failed: {resp!r}")

    def set_pwm_frequency(self, bit: int, freq_hz: int) -> None:
        """
        Command B: PWM frequency.
        0..4095 Hz in 1 Hz steps (DDDD=0000..0FFF).
        """
        if not (0 <= freq_hz <= 4095):
            raise ValueError("freq_hz must be 0..4095")
        resp = self.io.send_cmd(f"*B{bit:02X}0{freq_hz:04X}#", timeout=1.0)
        if "*NG#" in resp:
            raise RuntimeError(f"PWM frequency set failed: {resp!r}")

    def set_pwm_duty(self, bit: int, duty: float) -> None:
        """
        Command C: PWM duty.
        DDDD:
          0000h -> stop output=0
          0001h..03FEh -> 1/1024 .. 1022/1024
          03FFh -> stop output=1
        """
        if not (0.0 <= duty <= 1.0):
            raise ValueError("duty must be 0.0..1.0")

        if duty <= 0.0:
            dddd = 0x0000
        elif duty >= 1.0:
            dddd = 0x03FF
        else:
            # map duty to 1..1022
            val = int(round(duty * 1024))
            val = max(1, min(1022, val))
            dddd = val

        resp = self.io.send_cmd(f"*C{bit:02X}0{dddd:04X}#", timeout=1.0)
        if "*NG#" in resp:
            raise RuntimeError(f"PWM duty set failed: {resp!r}")

    def hold_low(self, bit: Optional[int] = None) -> None:
        bit = bit if bit is not None else self.config.bit
        self.set_pwm_duty(bit, 0.0)

    def hold_high(self, bit: Optional[int] = None) -> None:
        bit = bit if bit is not None else self.config.bit
        self.set_pwm_duty(bit, 1.0)

    def output_sync_signal(
            self,
            start_event: threading.Event,
            stop_event: threading.Event,
            duration_s: float | None = None
            ) -> None:
        """
        Convenience method: configure and start PWM output.
        """
        if self.config.idle_state == 0:
            self.hold_low()
        elif self.config.idle_state == 1:
            self.hold_high()
        else:
            raise ValueError("idle_state must be 0 (LOW) or 1 (HIGH)")

        start_event.wait()

        try:
            self.set_pwm_frequency(self.config.bit, self.config.freq_hz)
            self.set_pwm_duty(self.config.bit, self.config.duty)

            if duration_s is None:
                stop_event.wait()
            else:
                stop_event.wait(timeout=duration_s)
        finally:
            if self.config.idle_state == 0:
                self.hold_low()
            else:
                self.hold_high()

if __name__ == "__main__":
    adio_pwm_config = ADioPWMConfig(bit=0, freq_hz=0, duty=0.40, idle_state=0)

    io = ADioTransport(serial="FT9IK4VX")
    io.open()
    io.reset_all()
    
    pwm = ADioPWM(io, adio_pwm_config)

    start_event = threading.Event()
    stop_event = threading.Event()
    thread = threading.Thread(
        target=pwm.output_sync_signal,
        kwargs={
            "start_event": start_event,
            "stop_event": stop_event,
            "duration_s": None
        },
        daemon=False,
    )
    
    thread.start()

    input("Press Enter to start sync signal...\n")
    start_event.set()
        
    input("Press Enter to stop sync signal...\n")
    stop_event.set()
    
    thread.join()
    io.close()
