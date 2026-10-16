'use client';

class AudioEngine {
  constructor() {
    this.enabled = true;
    this.ttsEnabled = true;
    
    if (typeof window !== 'undefined') {
      this.synth = window.speechSynthesis;
    }
  }

  playSFX(url) {
    if (!this.enabled || typeof window === 'undefined') return;
    try {
      const audio = new Audio(url);
      audio.volume = 0.5;
      audio.play().catch(e => console.log('SFX play failed (likely browser autoplay policy):', e));
    } catch (err) {
      console.error('Audio playback error:', err);
    }
  }

  playSynthesizedSfx(type = 'allocate') {
    if (!this.enabled || typeof window === 'undefined') return;
    try {
      const AudioCtx = window.AudioContext || window.webkitAudioContext;
      if (!AudioCtx) return;
      const ctx = this._audioCtx || (this._audioCtx = new AudioCtx());
      if (ctx.state === 'suspended') {
        ctx.resume().catch(() => {});
      }
      const now = ctx.currentTime;
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.connect(gain);
      gain.connect(ctx.destination);

      if (type === 'allocate') {
        // High harmonic chime
        osc.type = 'sine';
        osc.frequency.setValueAtTime(523.25, now); // C5
        osc.frequency.exponentialRampToValueAtTime(1046.50, now + 0.15); // C6
        gain.gain.setValueAtTime(0.12, now);
        gain.gain.exponentialRampToValueAtTime(0.001, now + 0.35);
        osc.start(now);
        osc.stop(now + 0.35);
      } else if (type === 'unlock') {
        // Celestial rising pulse
        osc.type = 'triangle';
        osc.frequency.setValueAtTime(440.0, now);
        osc.frequency.exponentialRampToValueAtTime(880.0, now + 0.25);
        gain.gain.setValueAtTime(0.15, now);
        gain.gain.exponentialRampToValueAtTime(0.001, now + 0.45);
        osc.start(now);
        osc.stop(now + 0.45);
      } else if (type === 'error') {
        // Low rejection buzz
        osc.type = 'sawtooth';
        osc.frequency.setValueAtTime(180.0, now);
        osc.frequency.linearRampToValueAtTime(110.0, now + 0.2);
        gain.gain.setValueAtTime(0.15, now);
        gain.gain.exponentialRampToValueAtTime(0.001, now + 0.25);
        osc.start(now);
        osc.stop(now + 0.25);
      } else {
        // Subtle click
        osc.type = 'sine';
        osc.frequency.setValueAtTime(800, now);
        gain.gain.setValueAtTime(0.08, now);
        gain.gain.exponentialRampToValueAtTime(0.001, now + 0.08);
        osc.start(now);
        osc.stop(now + 0.08);
      }
    } catch (err) {
      // Audio autoplay policy or AudioContext uninitialized in test
    }
  }

  say(text, voiceName = null) {
    if (!this.ttsEnabled || !this.synth) return;
    
    // Clean markdown and operational tags from text
    let cleanText = text.replace(/\[SHOUT\]|\[\/SHOUT\]|\[WHISPER\]|\[\/WHISPER\]/g, '');
    cleanText = cleanText.replace(/[*_`#]/g, '');
    cleanText = cleanText.replace(/\[\[(.*?)\]\]/g, '$1');
    cleanText = cleanText.replace(/(op|hop):\/\/\S+/g, '');

    const utterance = new SpeechSynthesisUtterance(cleanText);
    
    // Adjust tactical prosody
    if (text.includes('[SHOUT]')) {
      utterance.volume = 1.0;
      utterance.rate = 1.2;
    } else if (text.includes('[WHISPER]')) {
      utterance.volume = 0.4;
      utterance.rate = 0.8;
    } else {
      utterance.volume = 0.8;
      utterance.rate = 1.0;
    }

    if (voiceName) {
      const voices = this.synth.getVoices();
      // Try to find a matching voice by name, or fallback to the first English female/male voice loosely matching
      const voice = voices.find(v => v.name.includes(voiceName)) || voices.find(v => v.lang.startsWith('en'));
      if (voice) {
        utterance.voice = voice;
      }
    }

    this.synth.speak(utterance);
  }

  stopAll() {
    if (this.synth) {
      this.synth.cancel();
    }
  }
}

// Singleton instance
const engine = new AudioEngine();
export default engine;
