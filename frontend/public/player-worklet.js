// player-worklet.js
class PlayerProcessor extends AudioWorkletProcessor {
  constructor() {
    super();
    this.queue = []; // các Float32Array @AudioContext.sampleRate
    this.readOffset = 0;

    this.port.onmessage = (e) => {
      const data = e.data;
      if (data && data.type === 'flush') {
        this.queue = [];
        this.readOffset = 0;
        return;
      }
      if (data instanceof Float32Array) {
        this.queue.push(data);
      } else if (data && data.buffer instanceof ArrayBuffer) {
        // Phòng trường hợp nhận kiểu buffer thuần
        const f32 = new Float32Array(data.buffer);
        this.queue.push(f32);
      }
    };
  }

  process(inputs, outputs) {
    const output = outputs[0];
    if (!output || output.length === 0) return true;
    const ch0 = output[0];
    if (!ch0) return true;

    let remain = ch0.length;
    let write = 0;

    while (remain > 0) {
      if (this.queue.length === 0) {
        // không có dữ liệu -> fill zero
        for (let i = write; i < ch0.length; i++) ch0[i] = 0;
        break;
      }

      const head = this.queue[0];
      const canCopy = Math.min(remain, head.length - this.readOffset);
      ch0.set(head.subarray(this.readOffset, this.readOffset + canCopy), write);

      write += canCopy;
      remain -= canCopy;
      this.readOffset += canCopy;

      if (this.readOffset >= head.length) {
        this.queue.shift();
        this.readOffset = 0;
      }
    }

    // copy mono sang các kênh khác (nếu có)
    for (let c = 1; c < output.length; c++) {
      output[c].set(ch0);
    }

    return true;
  }
}

registerProcessor('player-processor', PlayerProcessor);