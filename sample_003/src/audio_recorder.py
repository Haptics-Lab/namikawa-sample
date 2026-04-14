from pathlib import Path

import numpy as np
import sounddevice as sd
from scipy.io.wavfile import write

class AudioRecorder:

    def __init__(self, device, sample_rate: int = 44100, channels=2, blocksize: int = 1024):
        self.device = device
        self.sample_rate = sample_rate
        self.channels = channels
        self.blocksize = blocksize
        
    def record(self, wav_path: Path):
        
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

                print(f"Started recording audio. Ctrl+C to stop.")
                print(f"    Writing to {wav_path}")

                while True:
                    sd.sleep(500)

        except KeyboardInterrupt:
            print("\nKeyboardInterrupt received. Stopping audio recording...")
        
        finally:
            if self._frames:
                audio = np.concatenate(self._frames, axis=0)
                write(wav_path, self.sample_rate, audio)
            else:
                print("No audio data recorded.")

    @staticmethod
    def check_device():
        print("Available audio input devices:")
        print(sd.query_devices())

if __name__ == "__main__":
    
    AudioRecorder.check_device()

    recorder = AudioRecorder(device=1, sample_rate=44100, channels=2, blocksize=1024)
    recorder.record(Path("output\\audio_data.wav"))
