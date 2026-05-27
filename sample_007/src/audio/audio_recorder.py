from pathlib import Path
import threading

import numpy as np
import sounddevice as sd
from scipy.io.wavfile import write

class AudioRecorder:

    def __init__(
            self,
            device,
            sample_rate: int = 44100,
            channels=2,
            blocksize: int = 1024
            ):
        self.device = device
        self.sample_rate = sample_rate
        self.channels = channels
        self.blocksize = blocksize
        
    def record(
            self,
            wav_path: Path,
            stop_event: threading.Event,
            started_event: threading.Event
            ):
        
        wav_path.parent.mkdir(parents=True, exist_ok=True)
        self._frames = []

        def callback(indata, frames, time_info, status):
            if status:
                print(status)
            self._frames.append(indata.copy())

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

                started_event.set()

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

    audio_recorder = AudioRecorder(device=5, sample_rate=44100, channels=2, blocksize=1024)

    started_event = threading.Event()
    stop_event = threading.Event()
    thread = threading.Thread(
        target=audio_recorder.record,
        kwargs={
            "wav_path": Path("output") / "test" / "audio_data.wav",
            "stop_event": stop_event,
            "started_event": started_event,
        },
    )

    thread.start()
    started_event.wait()

    try:
        input("Press Enter to stop recording...\n")
    finally:
        stop_event.set()
        thread.join()
