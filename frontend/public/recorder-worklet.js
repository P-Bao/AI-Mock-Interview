  // recorder-worklet.js
  class RecorderProcessor extends AudioWorkletProcessor {
    constructor(options) {
      super();
      const opt = options?.processorOptions || {};
      this.targetRate = opt.targetRate || 16000;
      this.chunkSamples = opt.chunkSamples || 640;
      this.doVU = !!opt.vuMeter;

      this.inRate = sampleRate; // sampleRate toàn cục của AudioWorklet
      this._buffer = []; // Float32 mono @inRate
    }

    _cubicResample(input, inRate, outRate) {
      if (inRate === outRate) return input;
      const ratio = inRate / outRate;
      const outLen = Math.floor(input.length / ratio);
      const out = new Float32Array(outLen);

      const cubic = (y0, y1, y2, y3, t) => {
        const a0 = -0.5*y0 + 1.5*y1 - 1.5*y2 + 0.5*y3;
        const a1 = y0 - 2.5*y1 + 2*y2 - 0.5*y3;
        const a2 = -0.5*y0 + 0.5*y2;
        const a3 = y1;
        return ((a0*t + a1)*t + a2)*t + a3;
      };

      for (let i = 0; i < outLen; i++) {
        const idx = i * ratio;
        const i1 = Math.floor(idx);
        const t = idx - i1;
        const i0 = Math.max(0, i1 - 1);
        const i2 = Math.min(input.length - 1, i1 + 1);
        const i3 = Math.min(input.length - 1, i1 + 2);
        out[i] = cubic(input[i0], input[i1], input[i2], input[i3], t);
      }
      return out;
    }

    _floatToPCM16(f32) {
      const i16 = new Int16Array(f32.length);
      for (let i = 0; i < f32.length; i++) {
        let s = Math.max(-1, Math.min(1, f32[i]));
        i16[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
      }
      return i16;
    }

    process(inputs, outputs) {
      const input = inputs[0];
      if (!input || input.length === 0) return true;
      const ch0 = input[0]; // mono kênh 0
      if (!ch0) return true;

      // Nếu stereo, có thể downmix: mono = (L + R)/2
      // Ở đây dùng ch0 cho đơn giản.

      // Thêm vào buffer @inRate
      this._buffer.push(new Float32Array(ch0));

      // Gom lại
      let total = 0;
      for (const b of this._buffer) total += b.length;
      const big = new Float32Array(total);
      let o = 0;
      for (const b of this._buffer) { big.set(b, o); o += b.length; }
      this._buffer.length = 0;

      // Downsample về targetRate
      const ds = this._cubicResample(big, this.inRate, this.targetRate);

      // VU meter (RMS)
      if (this.doVU) {
        let sum = 0;
        for (let i = 0; i < ds.length; i++) {
          const s = ds[i];
          sum += s * s;
        }
        const rms = Math.sqrt(sum / Math.max(1, ds.length));
        this.port.postMessage({ type: 'vu', rms });
      }

      // Đóng khung chunkSamples và postMessage PCM16
      let idx = 0;
      while (idx + this.chunkSamples <= ds.length) {
        const slice = ds.subarray(idx, idx + this.chunkSamples);
        const i16 = this._floatToPCM16(slice);
        // Gửi ArrayBuffer (transfer ownership)
        this.port.postMessage(i16.buffer, [i16.buffer]);
        idx += this.chunkSamples;
      }

      // Phần dư còn lại push lại buffer (để đủ khung lần sau)
      if (idx < ds.length) {
        const rest = ds.subarray(idx);
        const keep = new Float32Array(rest);
        this._buffer.push(keep);
      }

      return true;
    }
  }

  registerProcessor('recorder-processor', RecorderProcessor);