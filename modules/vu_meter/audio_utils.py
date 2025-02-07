
import pyaudio
import numpy as np

def get_microphone_level():
   audio = pyaudio.PyAudio()
   stream = audio.open(format=pyaudio.paInt16, channels=1, rate=44100, input=True, frames_per_buffer=1024)
   
   while True:
       data = np.frombuffer(stream.read(1024), dtype=np.int16)
       level = np.abs(data).mean()
       yield level

   stream.stop_stream()
   stream.close()
   audio.terminate()
