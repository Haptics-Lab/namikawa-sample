from pathlib import Path
import threading
from typing import Callable

import numpy as np
import sounddevice as sd
from scipy.io.wavfile import write

class AudioRecorder:

    def __init__(self, device, sample_rate: int = 44100, channels=2, blocksize: int = 1024):
        self.device = device
        self.sample_rate = sample_rate
        self.channels = channels
        self.blocksize = blocksize

    def record(
            self,
            wav_path: Path,
            stop_event: threading.Event,
            preview_listener: Callable[[dict], None] | None = None,
            ):

        wav_path.parent.mkdir(parents=True, exist_ok=True)
        self._frames = []

        def callback(indata, frames, time_info, status):
            if status:
                print(status)
            self._frames.append(indata.copy())
            if preview_listener is not None and indata.size > 0:
                indata_f32 = indata.astype(np.float32)
                abs_values = np.abs(indata_f32)
                mono = np.mean(indata_f32, axis=1)
                wave_points = 64
                step = max(1, mono.shape[0] // wave_points)
                preview_listener(
                    {
                        "rms": np.sqrt(np.mean(np.square(indata_f32), axis=0)).tolist(),
                        "peak": np.max(abs_values, axis=0).tolist(),
                        "waveform": mono[::step][:wave_points].tolist(),
                    }
                )

        try:
            with sd.InputStream(
                    samplerate=self.sample_rate,
                    channels=self.channels,
                    blocksize=self.blocksize,
                    dtype='int16',
                    callback=callback,
                    device=self.device,
                ):

                print(f"Started recording audio.")
                print(f"    Writing to {wav_path}")

                stop_event.wait()
        
        finally:
            if self._frames:
                audio = np.concatenate(self._frames, axis=0)
                write(wav_path, self.sample_rate, audio)
                print("Stopped audio recording.")
            else:
                print("No audio data recorded.")

    @staticmethod
    def check_device():
        print("Available audio input devices:")
        print(sd.query_devices())

if __name__ == "__main__":
    
    AudioRecorder.check_device()

    audio_recorder = AudioRecorder(device=2, sample_rate=44100, channels=2, blocksize=1024)

    stop_event = threading.Event()
    thread = threading.Thread(
        target=audio_recorder.record,
        args=(Path("output") / "test" / "audio_data.wav", stop_event),
    )

    thread.start()

    try:
        input("Press Enter to stop recording...\n")
    finally:
        stop_event.set()
        thread.join()
