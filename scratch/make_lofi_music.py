import numpy as np
from scipy.io import wavfile
from scipy.signal import butter, lfilter

def butter_lowpass_filter(data, cutoff, fs, order=2):
    nyq = 0.5 * fs
    normal_cutoff = cutoff / nyq
    b, a = butter(order, normal_cutoff, btype='low', analog=False)
    return lfilter(b, a, data)

def butter_highpass_filter(data, cutoff, fs, order=2):
    nyq = 0.5 * fs
    normal_cutoff = cutoff / nyq
    b, a = butter(order, normal_cutoff, btype='high', analog=False)
    return lfilter(b, a, data)

def generate_lofi_beat(duration_sec=45, sample_rate=44100):
    bpm = 88
    beat_dur = 60.0 / bpm  # ~0.6818s per beat
    bar_dur = beat_dur * 4 # ~2.727s per bar
    num_samples = int(duration_sec * sample_rate)
    t = np.linspace(0, duration_sec, num_samples, endpoint=False)
    audio = np.zeros(num_samples)

    # --- 1. Chords (E. Piano style) ---
    # Cmaj7, Am7, Dm7, G7
    chords = [
        [261.63, 329.63, 392.00, 493.88], # Cmaj7
        [220.00, 261.63, 329.63, 392.00], # Am7
        [293.66, 349.23, 440.00, 523.25], # Dm7
        [196.00, 246.94, 293.66, 349.23], # G7
    ]
    chord_audio = np.zeros(num_samples)

    num_bars = int(np.ceil(duration_sec / bar_dur))
    for bar_idx in range(num_bars):
        chord_freqs = chords[bar_idx % len(chords)]
        bar_start_sample = int(bar_idx * bar_dur * sample_rate)
        bar_end_sample = min(int((bar_idx + 1) * bar_dur * sample_rate), num_samples)
        bar_len = bar_end_sample - bar_start_sample
        if bar_len <= 0:
            continue

        bar_t = np.linspace(0, bar_len / sample_rate, bar_len, endpoint=False)

        # Strum chord twice per bar (beats 1 and 3)
        for chord_hit in [0.0, bar_dur / 2.0]:
            hit_t = bar_t - chord_hit
            mask = hit_t >= 0
            decay = np.exp(-1.8 * hit_t[mask])
            tremolo = 1.0 + 0.15 * np.sin(2 * np.pi * 5 * hit_t[mask])

            synth_wave = np.zeros(np.sum(mask))
            for f in chord_freqs:
                # Fundamental + soft harmonics
                synth_wave += 0.25 * np.sin(2 * np.pi * f * hit_t[mask])
                synth_wave += 0.08 * np.sin(2 * np.pi * (f * 2) * hit_t[mask])

            chord_audio[bar_start_sample + np.where(mask)[0]] += synth_wave * decay * tremolo

    # Warm lowpass filter for lo-fi aesthetic
    chord_audio = butter_lowpass_filter(chord_audio, 1600, sample_rate)

    # --- 2. Sub Bass ---
    bass_audio = np.zeros(num_samples)
    bass_notes = [130.81, 110.00, 146.83, 98.00] # C3, A2, D3, G2
    for bar_idx in range(num_bars):
        bass_freq = bass_notes[bar_idx % len(chords)]
        bar_start_sample = int(bar_idx * bar_dur * sample_rate)
        bar_end_sample = min(int((bar_idx + 1) * bar_dur * sample_rate), num_samples)
        bar_len = bar_end_sample - bar_start_sample
        if bar_len <= 0:
            continue
        bar_t = np.linspace(0, bar_len / sample_rate, bar_len, endpoint=False)
        # Groove: hit on beat 1, 2.5, 3
        for bass_hit in [0.0, beat_dur * 1.5, beat_dur * 2.0]:
            hit_t = bar_t - bass_hit
            mask = hit_t >= 0
            decay = np.exp(-2.5 * hit_t[mask])
            note_wave = 0.35 * np.sin(2 * np.pi * bass_freq * hit_t[mask])
            bass_audio[bar_start_sample + np.where(mask)[0]] += note_wave * decay

    bass_audio = butter_lowpass_filter(bass_audio, 300, sample_rate)

    # --- 3. Drums (Kick, Snare, Hi-hat) ---
    drums_audio = np.zeros(num_samples)
    total_beats = int(np.ceil(duration_sec / beat_dur))

    for beat_idx in range(total_beats):
        beat_start_sample = int(beat_idx * beat_dur * sample_rate)
        beat_type = beat_idx % 4  # 0=kick, 1=snare, 2=kick, 3=snare

        # Kick on 0 and beat 2.5
        if beat_type == 0 or beat_type == 2:
            kick_dur = 0.25
            kick_len = int(kick_dur * sample_rate)
            if beat_start_sample + kick_len < num_samples:
                kt = np.linspace(0, kick_dur, kick_len, endpoint=False)
                # Pitch sweep from 130Hz down to 45Hz
                freq_env = 45 + (130 - 45) * np.exp(-30 * kt)
                phase = 2 * np.pi * np.cumsum(freq_env) / sample_rate
                kick_wave = 0.5 * np.sin(phase) * np.exp(-8 * kt)
                drums_audio[beat_start_sample:beat_start_sample+kick_len] += kick_wave

        # Snare on 1 and 3
        if beat_type == 1 or beat_type == 3:
            snare_dur = 0.2
            snare_len = int(snare_dur * sample_rate)
            if beat_start_sample + snare_len < num_samples:
                st = np.linspace(0, snare_dur, snare_len, endpoint=False)
                body = 0.2 * np.sin(2 * np.pi * 180 * st) * np.exp(-15 * st)
                noise = 0.25 * (np.random.rand(snare_len) * 2 - 1) * np.exp(-20 * st)
                snare_wave = body + noise
                drums_audio[beat_start_sample:beat_start_sample+snare_len] += snare_wave

        # Eighth note hi-hats
        for hh_offset in [0.0, beat_dur / 2.0]:
            hh_start = int((beat_idx * beat_dur + hh_offset) * sample_rate)
            hh_dur = 0.05
            hh_len = int(hh_dur * sample_rate)
            if hh_start + hh_len < num_samples:
                ht = np.linspace(0, hh_dur, hh_len, endpoint=False)
                noise = 0.12 * (np.random.rand(hh_len) * 2 - 1) * np.exp(-60 * ht)
                noise = butter_highpass_filter(noise, 4000, sample_rate)
                drums_audio[hh_start:hh_start+hh_len] += noise

    # --- 4. Subtle Vinyl Crackle ---
    crackle = 0.015 * (np.random.rand(num_samples) * 2 - 1)
    # Random pops
    pop_indices = np.random.choice(num_samples, size=int(duration_sec * 8), replace=False)
    crackle[pop_indices] += np.random.uniform(0.04, 0.08, size=len(pop_indices))

    # --- Master Mix ---
    mix = chord_audio + bass_audio + drums_audio + crackle
    mix = mix / (np.max(np.abs(mix)) + 1e-6) * 0.85 # Normalize to headroom

    # Convert to 16-bit PCM WAV
    audio_int16 = (mix * 32767).astype(np.int16)
    wav_path = "/config/Desktop/Session1/wanderlust-concierge/scratch/lofi_beat.wav"
    wavfile.write(wav_path, sample_rate, audio_int16)
    print(f"Upbeat lo-fi beat generated successfully at: {wav_path}")
    return wav_path

if __name__ == "__main__":
    generate_lofi_beat()
