import sounddevice as sd
import soundfile as sf

def play_sound(file_path):
    # read the audio file
    data, samplerate = sf.read(file_path)
    
    # play the audio data
    sd.play(data, samplerate)
    
    # wait until playback is finished
    sd.wait()
