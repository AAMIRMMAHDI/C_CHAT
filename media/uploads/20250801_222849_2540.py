import socketio
import pyaudio
import threading
import time
import sys

# تنظیمات
SERVER_URL = "ws://ytjkyu.pythonanywhere.com/socket.io"  # آدرس سرور PythonAnywhere
CHUNK = 1024
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 44100

class VoiceClient:
    def __init__(self):
        self.sio = socketio.Client()
        self.audio = pyaudio.PyAudio()
        self.stream_in = None
        self.stream_out = None
        self.running = False

    def setup_socket(self):
        @self.sio.event
        def connect():
            print("Connected to server")
            self.running = True
            threading.Thread(target=self.record_and_send, daemon=True).start()

        @self.sio.event
        def connect_error(data):
            print(f"Connection failed: {data}")
            self.stop()

        @self.sio.event
        def disconnect():
            print("Disconnected from server")
            self.stop()

        @self.sio.on('voice')
        def on_voice(data):
            if self.stream_out and self.running:
                try:
                    self.stream_out.write(data)
                except Exception as e:
                    print(f"Error playing audio: {e}")

    def record_and_send(self):
        try:
            self.stream_in = self.audio.open(
                format=FORMAT,
                channels=CHANNELS,
                rate=RATE,
                input=True,
                frames_per_buffer=CHUNK
            )
            while self.running:
                try:
                    data = self.stream_in.read(CHUNK, exception_on_overflow=False)
                    self.sio.emit('voice', data)
                    time.sleep(0.01)  # جلوگیری از فشار بیش از حد به CPU
                except Exception as e:
                    print(f"Error in recording: {e}")
                    break
        except Exception as e:
            print(f"Error opening input stream: {e}")
        finally:
            if self.stream_in:
                self.stream_in.stop_stream()
                self.stream_in.close()

    def start(self):
        self.setup_socket()
        try:
            self.stream_out = self.audio.open(
                format=FORMAT,
                channels=CHANNELS,
                rate=RATE,
                output=True,
                frames_per_buffer=CHUNK
            )
            self.sio.connect(SERVER_URL, wait_timeout=10)
            self.sio.wait()
        except Exception as e:
            print(f"Connection error: {e}")
            self.stop()

    def stop(self):
        self.running = False
        if self.stream_out:
            self.stream_out.stop_stream()
            self.stream_out.close()
        self.audio.terminate()
        if self.sio.connected:
            self.sio.disconnect()
        print("Client stopped")
        sys.exit()

if __name__ == "__main__":
    client = VoiceClient()
    client.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        client.stop()