export class AudioStreamer {
  private ws?: WebSocket
  private audioCtx?: AudioContext
  private workletNode?: AudioWorkletNode
  private mediaStream?: MediaStream
  private source?: MediaStreamAudioSourceNode
  private _stopped = false
  private _started = false

  onText?: (text: string) => void

  async start(wsUrl: string) {
    if (this._started && !this._stopped) {
      console.warn("AudioStreamer already started")
      return
    }
    this._started = true
    this._stopped = false

    // 1) Mic
    this.mediaStream = await navigator.mediaDevices.getUserMedia({ audio: true })

    // 2) AudioContext
    this.audioCtx = new (window.AudioContext || (window as any).webkitAudioContext)({
      sampleRate: 16000,
    })

    // 3) Worklet
    await this.audioCtx.audioWorklet.addModule('/recorder-worklet.js')
    this.workletNode = new AudioWorkletNode(this.audioCtx, 'recorder-processor')

    // 4) Source
    this.source = this.audioCtx.createMediaStreamSource(this.mediaStream)
    this.source.connect(this.workletNode)
    // Không cần phát ra loa để tránh vọng:
    // this.workletNode.connect(this.audioCtx.destination)

    // 5) WebSocket
    const ws = new WebSocket(wsUrl)
    this.ws = ws
    ws.binaryType = 'arraybuffer'

    ws.onopen = () => {
      console.log("🟢 WS opened")
      if (!this.workletNode) return
      this.workletNode.port.onmessage = (e: MessageEvent<Float32Array>) => {
        if (!this.ws || this.ws.readyState !== WebSocket.OPEN) return
        const f32 = e.data
        if (!f32) return
        const i16 = new Int16Array(f32.length)
        for (let i = 0; i < f32.length; i++) {
          let s = Math.max(-1, Math.min(1, f32[i]))
          i16[i] = s < 0 ? s * 0x8000 : s * 0x7fff
        }
        this.ws.send(i16.buffer)
      }
    }

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)
        if (data?.text && this.onText) this.onText(data.text)
      } catch { /* ignore non-json */ }
    }

    ws.onerror = (e) => {
      console.warn("⚠️ WS error", e)
    }

    ws.onclose = () => {
      console.log("🔴 WS closed")
    }
  }

  stop() {
    if (this._stopped) return
    this._stopped = true

    try { this.ws?.close() } catch {}

    try {
      if (this.workletNode) {
        try { this.workletNode.disconnect() } catch {}
      }
      if (this.source) {
        try { this.source.disconnect() } catch {}
      }
    } catch {}

    try {
      this.mediaStream?.getTracks().forEach(t => {
        try { t.stop() } catch {}
      })
    } catch {}

    try {
      if (this.audioCtx && this.audioCtx.state !== "closed") {
        this.audioCtx.close().catch(() => {})
      }
    } catch {}

    this.ws = undefined
    this.workletNode = undefined
    this.source = undefined
    this.mediaStream = undefined
    this.audioCtx = undefined
  }
}