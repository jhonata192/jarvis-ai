import math
import wave
import struct
from pathlib import Path

def generate_beep(filename: str, freq1: float, freq2: float, duration: float = 0.15, sample_rate: int = 44100):
    """Gera um arquivo de áudio WAV suave sintetizado com transição de frequência."""
    num_samples = int(duration * sample_rate)
    with wave.open(filename, 'w') as wav_file:
        wav_file.setnchannels(1)  # Mono
        wav_file.setsampwidth(2)  # 16-bit
        wav_file.setframerate(sample_rate)

        for i in range(num_samples):
            t = i / num_samples
            freq = freq1 + (freq2 - freq1) * t
            envelope = math.sin(math.pi * t)  # Fade-in and fade-out suave
            val = int(envelope * 16000 * math.sin(2 * math.pi * freq * (i / sample_rate)))
            wav_file.writeframes(struct.pack('<h', max(-32767, min(32767, val))))

if __name__ == "__main__":
    assets_dir = Path(__file__).resolve().parent / "assets" / "sounds"
    assets_dir.mkdir(parents=True, exist_ok=True)
    
    # Tom ascendente suave para início da escuta (ex: 520Hz -> 880Hz)
    start_path = assets_dir / "listen_start.wav"
    generate_beep(str(start_path), freq1=520, freq2=880, duration=0.18)
    print(f"Criado: {start_path}")

    # Tom descendente suave para término da escuta (ex: 880Hz -> 440Hz)
    stop_path = assets_dir / "listen_stop.wav"
    generate_beep(str(stop_path), freq1=880, freq2=440, duration=0.15)
    print(f"Criado: {stop_path}")
