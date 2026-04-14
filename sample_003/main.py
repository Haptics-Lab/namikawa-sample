from pathlib import Path

from src.audio_recorder import AudioRecorder

def main():
    recorder = AudioRecorder(device=1, sample_rate=44100, channels=2, blocksize=1024)
    recorder.record(Path("output\\audio_data.wav"))

if __name__ == "__main__":
    main()
