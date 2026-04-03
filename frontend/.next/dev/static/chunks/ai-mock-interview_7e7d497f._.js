(globalThis.TURBOPACK || (globalThis.TURBOPACK = [])).push([typeof document === "object" ? document.currentScript : undefined,
"[project]/ai-mock-interview/lib/audioStreamer.ts [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

// audio-streamer.ts
__turbopack_context__.s([
    "AudioStreamer",
    ()=>AudioStreamer
]);
class AudioStreamer {
    ws;
    audioCtx;
    recNode;
    playNode;
    source;
    media;
    cfg;
    pingTimer;
    startedAt;
    stopped = false;
    // Callbacks
    onText;
    onEvent;
    onStateChange;
    onError;
    onLevel;
    constructor(){}
    setState(s) {
        this.cfg?.debug && console.log('[AudioStreamer] state:', s);
        this.onStateChange?.(s);
    }
    async start(options) {
        this.stopped = false;
        // --- 0) Hợp nhất cấu hình
        const defaults = {
            wsUrl: options.wsUrl,
            inRate: options.inRate ?? 16000,
            outRate: options.outRate ?? 24000,
            chunkMs: options.chunkMs ?? 40,
            transport: options.transport ?? 'binary',
            pingIntervalMs: options.pingIntervalMs ?? 15000,
            debug: !!options.debug,
            token: options.token ?? ''
        };
        this.cfg = defaults;
        // --- 1) AudioContext + Worklets
        this.setState('connecting');
        this.audioCtx = new (window.AudioContext || window.webkitAudioContext)({
            latencyHint: 'interactive'
        });
        // Một số trình duyệt yêu cầu user gesture và resume sau khi tạo
        if (this.audioCtx.state === 'suspended') {
            try {
                await this.audioCtx.resume();
            } catch  {}
        }
        // Nạp worklets (đảm bảo các file được host đúng path/CORS)
        await this.audioCtx.audioWorklet.addModule('/recorder-worklet.js');
        await this.audioCtx.audioWorklet.addModule('/player-worklet.js');
        // --- 2) Mic -> RecorderWorklet
        this.media = await navigator.mediaDevices.getUserMedia({
            audio: true
        });
        this.source = this.audioCtx.createMediaStreamSource(this.media);
        // Truyền cấu hình cho worklet ghi: outRate, chunkSamples
        const chunkSamples = Math.round(this.cfg.inRate * (this.cfg.chunkMs / 1000)); // ví dụ 640 mẫu cho 40ms @16k
        this.recNode = new AudioWorkletNode(this.audioCtx, 'recorder-processor', {
            processorOptions: {
                targetRate: this.cfg.inRate,
                chunkSamples,
                vuMeter: true
            }
        });
        this.source.connect(this.recNode);
        // --- 3) PlayerWorklet -> Destination
        this.playNode = new AudioWorkletNode(this.audioCtx, 'player-processor', {
            numberOfOutputs: 1,
            numberOfInputs: 0
        });
        this.playNode.connect(this.audioCtx.destination);
        // --- 4) WebSocket
        const wsUrl = this.cfg.token ? this.cfg.wsUrl + (this.cfg.wsUrl.includes('?') ? '&' : '?') + 'token=' + encodeURIComponent(this.cfg.token) : this.cfg.wsUrl;
        this.ws = new WebSocket(wsUrl);
        this.ws.binaryType = 'arraybuffer';
        await new Promise((resolve, reject)=>{
            const to = setTimeout(()=>reject(new Error('WS open timeout')), 6000);
            this.ws.onopen = ()=>{
                clearTimeout(to);
                resolve();
            };
            this.ws.onerror = (e)=>{
                clearTimeout(to);
                reject(e instanceof Error ? e : new Error('WS error'));
            };
        });
        // Khai báo mime IN/OUT (nếu server dùng dạng config như bạn đã có)
        this.ws.send(JSON.stringify({
            type: 'config',
            direction: 'in',
            mime_type: `audio/pcm;rate=${this.cfg.inRate}`
        }));
        this.ws.send(JSON.stringify({
            type: 'config',
            direction: 'out',
            mime_type: `audio/pcm;rate=${this.cfg.outRate}`
        }));
        // --- 5) Đẩy PCM16 lên server (từ RecorderWorklet)
        this.recNode.port.onmessage = (evt)=>{
            const data = evt.data;
            if (!this.ws || this.ws.readyState !== WebSocket.OPEN) return;
            if (data?.type === 'vu') {
                // RMS cho VU meter
                this.onLevel?.(data.rms);
                return;
            }
            if (data instanceof ArrayBuffer) {
                // data là PCM16 @inRate, độ dài chunkSamples * 2 bytes
                if (this.cfg.transport === 'binary') {
                    this.ws.send(data);
                } else {
                    // JSON base64
                    const b64 = this.arrayBufferToBase64(data);
                    this.ws.send(JSON.stringify({
                        type: 'chunk',
                        direction: 'in',
                        data: b64,
                        mime_type: `audio/pcm;rate=${this.cfg.inRate}`
                    }));
                }
            }
        };
        // --- 6) Nhận dữ liệu (PCM16 @outRate) và phát
        this.ws.onmessage = async (event)=>{
            try {
                if (typeof event.data === 'string') {
                    // JSON: text / event / audio_out_base64
                    let msg;
                    try {
                        msg = JSON.parse(event.data);
                    } catch  {
                        msg = null;
                    }
                    if (msg) {
                        if (msg.type === 'text') this.onText?.(msg.text);
                        if (msg.type === 'event') {
                            this.onEvent?.(msg);
                            if (msg.name === 'interrupted' || msg.type === 'interrupted') {
                                // Barge-in: flush queue phát ngay
                                this.playNode?.port.postMessage({
                                    type: 'flush'
                                });
                            }
                        }
                        if (msg.type === 'audio_out_base64' && msg.data) {
                            const raw = this.base64ToArrayBuffer(msg.data);
                            const i16 = new Int16Array(raw);
                            const f32 = this.pcm16ToFloat32(i16);
                            const f32Out = this.resampleFloat32Cubic(f32, this.cfg.outRate, this.audioCtx.sampleRate);
                            // Transfer để tránh copy
                            const buf = f32Out.buffer;
                            this.playNode?.port.postMessage(new Float32Array(buf), [
                                buf
                            ]);
                        }
                        return;
                    }
                    // Nếu là string nhưng không phải JSON -> bỏ qua
                    return;
                }
                if (event.data instanceof ArrayBuffer) {
                    // Nhị phân: coi như PCM16 @outRate
                    const i16 = new Int16Array(event.data);
                    const f32 = this.pcm16ToFloat32(i16);
                    const f32Out = this.resampleFloat32Cubic(f32, this.cfg.outRate, this.audioCtx.sampleRate);
                    const buf = f32Out.buffer;
                    this.playNode?.port.postMessage(new Float32Array(buf), [
                        buf
                    ]);
                }
            } catch (err) {
                this.cfg.debug && console.error('[AudioStreamer] onmessage error', err);
            }
        };
        // Keep-alive ping
        this.pingTimer = window.setInterval(()=>{
            try {
                this.ws?.send(JSON.stringify({
                    type: 'ping',
                    t: Date.now()
                }));
            } catch  {}
        }, this.cfg.pingIntervalMs);
        this.startedAt = performance.now();
        this.setState('streaming');
    }
    stop(graceful = true) {
        this.stopped = true;
        this.setState('stopped');
        try {
            if (graceful) this.ws?.send(JSON.stringify({
                type: 'done'
            }));
        } catch  {}
        try {
            this.ws?.close();
        } catch  {}
        try {
            this.recNode?.disconnect();
        } catch  {}
        try {
            this.playNode?.disconnect();
        } catch  {}
        try {
            this.source?.disconnect();
        } catch  {}
        try {
            this.media?.getTracks().forEach((t)=>t.stop());
        } catch  {}
        try {
            if (this.audioCtx && this.audioCtx.state !== 'closed') this.audioCtx.close();
        } catch  {}
        if (this.pingTimer) {
            clearInterval(this.pingTimer);
            this.pingTimer = undefined;
        }
        this.ws = undefined;
        this.recNode = undefined;
        this.playNode = undefined;
        this.source = undefined;
        this.media = undefined;
        this.audioCtx = undefined;
    }
    // --- Utils
    pcm16ToFloat32(i16) {
        const f32 = new Float32Array(i16.length);
        for(let i = 0; i < i16.length; i++)f32[i] = Math.max(-1, i16[i] / 32768);
        return f32;
    }
    // Cubic Hermite interpolation – chất lượng tốt hơn linear, chi phí thấp
    resampleFloat32Cubic(input, inRate, outRate) {
        if (inRate === outRate) return input;
        const ratio = inRate / outRate;
        const outLen = Math.floor(input.length / ratio);
        const out = new Float32Array(outLen);
        // Helper: Hermite cubic
        const cubic = (y0, y1, y2, y3, t)=>{
            const a0 = -0.5 * y0 + 1.5 * y1 - 1.5 * y2 + 0.5 * y3;
            const a1 = y0 - 2.5 * y1 + 2 * y2 - 0.5 * y3;
            const a2 = -0.5 * y0 + 0.5 * y2;
            const a3 = y1;
            return ((a0 * t + a1) * t + a2) * t + a3;
        };
        for(let i = 0; i < outLen; i++){
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
    arrayBufferToBase64(buf) {
        const bin = String.fromCharCode(...new Uint8Array(buf));
        return btoa(bin);
    }
    base64ToArrayBuffer(b64) {
        const bin = atob(b64);
        const len = bin.length;
        const bytes = new Uint8Array(len);
        for(let i = 0; i < len; i++)bytes[i] = bin.charCodeAt(i);
        return bytes.buffer;
    }
}
if (typeof globalThis.$RefreshHelpers$ === 'object' && globalThis.$RefreshHelpers !== null) {
    __turbopack_context__.k.registerExports(__turbopack_context__.m, globalThis.$RefreshHelpers$);
}
}),
"[project]/ai-mock-interview/app/interview/page.tsx [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "default",
    ()=>InterviewPage
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$ai$2d$mock$2d$interview$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/ai-mock-interview/node_modules/next/dist/compiled/react/jsx-dev-runtime.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$ai$2d$mock$2d$interview$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/ai-mock-interview/node_modules/next/dist/compiled/react/index.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$ai$2d$mock$2d$interview$2f$lib$2f$audioStreamer$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/ai-mock-interview/lib/audioStreamer.ts [app-client] (ecmascript)");
;
var _s = __turbopack_context__.k.signature();
"use client";
;
;
function InterviewPage() {
    _s();
    const [recording, setRecording] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$ai$2d$mock$2d$interview$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useState"])(false);
    const [paused, setPaused] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$ai$2d$mock$2d$interview$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useState"])(false);
    const [transcript, setTranscript] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$ai$2d$mock$2d$interview$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useState"])("");
    const streamerRef = (0, __TURBOPACK__imported__module__$5b$project$5d2f$ai$2d$mock$2d$interview$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useRef"])(null);
    const makeWsUrl = (0, __TURBOPACK__imported__module__$5b$project$5d2f$ai$2d$mock$2d$interview$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useCallback"])({
        "InterviewPage.useCallback[makeWsUrl]": ()=>{
            return "ws://127.0.0.1:8000/ws";
        }
    }["InterviewPage.useCallback[makeWsUrl]"], []);
    (0, __TURBOPACK__imported__module__$5b$project$5d2f$ai$2d$mock$2d$interview$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useEffect"])({
        "InterviewPage.useEffect": ()=>{
            return ({
                "InterviewPage.useEffect": ()=>{
                    try {
                        streamerRef.current?.stop();
                    } catch  {}
                    streamerRef.current = null;
                }
            })["InterviewPage.useEffect"];
        }
    }["InterviewPage.useEffect"], []);
    const start = (0, __TURBOPACK__imported__module__$5b$project$5d2f$ai$2d$mock$2d$interview$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useCallback"])({
        "InterviewPage.useCallback[start]": async ()=>{
            if (recording && !paused) return;
            try {
                const streamer = new __TURBOPACK__imported__module__$5b$project$5d2f$ai$2d$mock$2d$interview$2f$lib$2f$audioStreamer$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["AudioStreamer"]();
                streamer.onText = ({
                    "InterviewPage.useCallback[start]": (text)=>setTranscript({
                            "InterviewPage.useCallback[start]": (prev)=>prev ? `${prev} ${text}` : text
                        }["InterviewPage.useCallback[start]"])
                })["InterviewPage.useCallback[start]"];
                streamerRef.current = streamer;
                const wsUrl = makeWsUrl();
                await streamer.start({
                    wsUrl,
                    inRate: 16000,
                    outRate: 24000,
                    chunkMs: 40,
                    transport: "binary",
                    debug: false
                });
                setRecording(true);
                setPaused(false);
            } catch (e) {
                console.error("Start error:", e);
                try {
                    streamerRef.current?.stop();
                } catch  {}
                streamerRef.current = null;
                setRecording(false);
                setPaused(false);
            }
        }
    }["InterviewPage.useCallback[start]"], [
        recording,
        paused,
        makeWsUrl
    ]);
    const stop = (0, __TURBOPACK__imported__module__$5b$project$5d2f$ai$2d$mock$2d$interview$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useCallback"])({
        "InterviewPage.useCallback[stop]": ()=>{
            if (!recording && !paused) return;
            try {
                streamerRef.current?.stop();
            } catch  {}
            streamerRef.current = null;
            setRecording(false);
            setPaused(false);
        }
    }["InterviewPage.useCallback[stop]"], [
        recording,
        paused
    ]);
    const pause = (0, __TURBOPACK__imported__module__$5b$project$5d2f$ai$2d$mock$2d$interview$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useCallback"])({
        "InterviewPage.useCallback[pause]": ()=>{
            if (!recording || paused) return;
            try {
                streamerRef.current?.stop();
            } catch  {}
            streamerRef.current = null;
            setPaused(true);
        }
    }["InterviewPage.useCallback[pause]"], [
        recording,
        paused
    ]);
    const resume = (0, __TURBOPACK__imported__module__$5b$project$5d2f$ai$2d$mock$2d$interview$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useCallback"])({
        "InterviewPage.useCallback[resume]": async ()=>{
            if (!paused) return;
            try {
                const streamer = new __TURBOPACK__imported__module__$5b$project$5d2f$ai$2d$mock$2d$interview$2f$lib$2f$audioStreamer$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["AudioStreamer"]();
                streamer.onText = ({
                    "InterviewPage.useCallback[resume]": (text)=>setTranscript({
                            "InterviewPage.useCallback[resume]": (prev)=>prev ? `${prev} ${text}` : text
                        }["InterviewPage.useCallback[resume]"])
                })["InterviewPage.useCallback[resume]"];
                streamerRef.current = streamer;
                const wsUrl = makeWsUrl();
                await streamer.start({
                    wsUrl,
                    inRate: 16000,
                    outRate: 24000,
                    chunkMs: 40,
                    transport: "binary",
                    debug: false
                });
                setPaused(false);
                setRecording(true);
            } catch (e) {
                console.error("Resume error:", e);
                try {
                    streamerRef.current?.stop();
                } catch  {}
                streamerRef.current = null;
                setPaused(true);
                setRecording(false);
            }
        }
    }["InterviewPage.useCallback[resume]"], [
        paused,
        makeWsUrl
    ]);
    return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$ai$2d$mock$2d$interview$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("main", {
        className: "container mx-auto px-4 py-16",
        children: [
            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$ai$2d$mock$2d$interview$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("h2", {
                className: "text-3xl font-bold mb-4",
                children: "Buổi phỏng vấn mô phỏng"
            }, void 0, false, {
                fileName: "[project]/ai-mock-interview/app/interview/page.tsx",
                lineNumber: 98,
                columnNumber: 7
            }, this),
            !recording && /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$ai$2d$mock$2d$interview$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("button", {
                onClick: start,
                className: "bg-green-500 text-white py-2 px-4 rounded",
                children: "Bắt đầu ghi âm"
            }, void 0, false, {
                fileName: "[project]/ai-mock-interview/app/interview/page.tsx",
                lineNumber: 101,
                columnNumber: 9
            }, this),
            recording && !paused && /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$ai$2d$mock$2d$interview$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                className: "flex gap-4",
                children: [
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$ai$2d$mock$2d$interview$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("button", {
                        onClick: pause,
                        className: "bg-yellow-500 text-white py-2 px-4 rounded",
                        children: "Tạm dừng"
                    }, void 0, false, {
                        fileName: "[project]/ai-mock-interview/app/interview/page.tsx",
                        lineNumber: 108,
                        columnNumber: 11
                    }, this),
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$ai$2d$mock$2d$interview$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("button", {
                        onClick: stop,
                        className: "bg-red-500 text-white py-2 px-4 rounded",
                        children: "Dừng ghi"
                    }, void 0, false, {
                        fileName: "[project]/ai-mock-interview/app/interview/page.tsx",
                        lineNumber: 111,
                        columnNumber: 11
                    }, this)
                ]
            }, void 0, true, {
                fileName: "[project]/ai-mock-interview/app/interview/page.tsx",
                lineNumber: 107,
                columnNumber: 9
            }, this),
            paused && /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$ai$2d$mock$2d$interview$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                className: "flex gap-4",
                children: [
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$ai$2d$mock$2d$interview$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("button", {
                        onClick: resume,
                        className: "bg-blue-500 text-white py-2 px-4 rounded",
                        children: "Tiếp tục"
                    }, void 0, false, {
                        fileName: "[project]/ai-mock-interview/app/interview/page.tsx",
                        lineNumber: 119,
                        columnNumber: 11
                    }, this),
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$ai$2d$mock$2d$interview$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("button", {
                        onClick: stop,
                        className: "bg-red-500 text-white py-2 px-4 rounded",
                        children: "Dừng ghi"
                    }, void 0, false, {
                        fileName: "[project]/ai-mock-interview/app/interview/page.tsx",
                        lineNumber: 122,
                        columnNumber: 11
                    }, this)
                ]
            }, void 0, true, {
                fileName: "[project]/ai-mock-interview/app/interview/page.tsx",
                lineNumber: 118,
                columnNumber: 9
            }, this),
            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$ai$2d$mock$2d$interview$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                className: "mt-10",
                children: [
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$ai$2d$mock$2d$interview$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("h3", {
                        className: "text-xl font-semibold mb-2",
                        children: "Bạn vừa nói:"
                    }, void 0, false, {
                        fileName: "[project]/ai-mock-interview/app/interview/page.tsx",
                        lineNumber: 129,
                        columnNumber: 9
                    }, this),
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$ai$2d$mock$2d$interview$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("p", {
                        className: "bg-gray-100 p-4 rounded",
                        children: transcript || "Chưa có nội dung"
                    }, void 0, false, {
                        fileName: "[project]/ai-mock-interview/app/interview/page.tsx",
                        lineNumber: 130,
                        columnNumber: 9
                    }, this)
                ]
            }, void 0, true, {
                fileName: "[project]/ai-mock-interview/app/interview/page.tsx",
                lineNumber: 128,
                columnNumber: 7
            }, this)
        ]
    }, void 0, true, {
        fileName: "[project]/ai-mock-interview/app/interview/page.tsx",
        lineNumber: 97,
        columnNumber: 5
    }, this);
}
_s(InterviewPage, "p7cZCW9n3ofe946vpPl0Odhkl/I=");
_c = InterviewPage;
var _c;
__turbopack_context__.k.register(_c, "InterviewPage");
if (typeof globalThis.$RefreshHelpers$ === 'object' && globalThis.$RefreshHelpers !== null) {
    __turbopack_context__.k.registerExports(__turbopack_context__.m, globalThis.$RefreshHelpers$);
}
}),
"[project]/ai-mock-interview/node_modules/next/dist/compiled/react/cjs/react-jsx-dev-runtime.development.js [app-client] (ecmascript)", ((__turbopack_context__, module, exports) => {
"use strict";

var __TURBOPACK__imported__module__$5b$project$5d2f$ai$2d$mock$2d$interview$2f$node_modules$2f$next$2f$dist$2f$build$2f$polyfills$2f$process$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = /*#__PURE__*/ __turbopack_context__.i("[project]/ai-mock-interview/node_modules/next/dist/build/polyfills/process.js [app-client] (ecmascript)");
/**
 * @license React
 * react-jsx-dev-runtime.development.js
 *
 * Copyright (c) Meta Platforms, Inc. and affiliates.
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */ "use strict";
"production" !== ("TURBOPACK compile-time value", "development") && function() {
    function getComponentNameFromType(type) {
        if (null == type) return null;
        if ("function" === typeof type) return type.$$typeof === REACT_CLIENT_REFERENCE ? null : type.displayName || type.name || null;
        if ("string" === typeof type) return type;
        switch(type){
            case REACT_FRAGMENT_TYPE:
                return "Fragment";
            case REACT_PROFILER_TYPE:
                return "Profiler";
            case REACT_STRICT_MODE_TYPE:
                return "StrictMode";
            case REACT_SUSPENSE_TYPE:
                return "Suspense";
            case REACT_SUSPENSE_LIST_TYPE:
                return "SuspenseList";
            case REACT_ACTIVITY_TYPE:
                return "Activity";
            case REACT_VIEW_TRANSITION_TYPE:
                return "ViewTransition";
        }
        if ("object" === typeof type) switch("number" === typeof type.tag && console.error("Received an unexpected object in getComponentNameFromType(). This is likely a bug in React. Please file an issue."), type.$$typeof){
            case REACT_PORTAL_TYPE:
                return "Portal";
            case REACT_CONTEXT_TYPE:
                return type.displayName || "Context";
            case REACT_CONSUMER_TYPE:
                return (type._context.displayName || "Context") + ".Consumer";
            case REACT_FORWARD_REF_TYPE:
                var innerType = type.render;
                type = type.displayName;
                type || (type = innerType.displayName || innerType.name || "", type = "" !== type ? "ForwardRef(" + type + ")" : "ForwardRef");
                return type;
            case REACT_MEMO_TYPE:
                return innerType = type.displayName || null, null !== innerType ? innerType : getComponentNameFromType(type.type) || "Memo";
            case REACT_LAZY_TYPE:
                innerType = type._payload;
                type = type._init;
                try {
                    return getComponentNameFromType(type(innerType));
                } catch (x) {}
        }
        return null;
    }
    function testStringCoercion(value) {
        return "" + value;
    }
    function checkKeyStringCoercion(value) {
        try {
            testStringCoercion(value);
            var JSCompiler_inline_result = !1;
        } catch (e) {
            JSCompiler_inline_result = !0;
        }
        if (JSCompiler_inline_result) {
            JSCompiler_inline_result = console;
            var JSCompiler_temp_const = JSCompiler_inline_result.error;
            var JSCompiler_inline_result$jscomp$0 = "function" === typeof Symbol && Symbol.toStringTag && value[Symbol.toStringTag] || value.constructor.name || "Object";
            JSCompiler_temp_const.call(JSCompiler_inline_result, "The provided key is an unsupported type %s. This value must be coerced to a string before using it here.", JSCompiler_inline_result$jscomp$0);
            return testStringCoercion(value);
        }
    }
    function getTaskName(type) {
        if (type === REACT_FRAGMENT_TYPE) return "<>";
        if ("object" === typeof type && null !== type && type.$$typeof === REACT_LAZY_TYPE) return "<...>";
        try {
            var name = getComponentNameFromType(type);
            return name ? "<" + name + ">" : "<...>";
        } catch (x) {
            return "<...>";
        }
    }
    function getOwner() {
        var dispatcher = ReactSharedInternals.A;
        return null === dispatcher ? null : dispatcher.getOwner();
    }
    function UnknownOwner() {
        return Error("react-stack-top-frame");
    }
    function hasValidKey(config) {
        if (hasOwnProperty.call(config, "key")) {
            var getter = Object.getOwnPropertyDescriptor(config, "key").get;
            if (getter && getter.isReactWarning) return !1;
        }
        return void 0 !== config.key;
    }
    function defineKeyPropWarningGetter(props, displayName) {
        function warnAboutAccessingKey() {
            specialPropKeyWarningShown || (specialPropKeyWarningShown = !0, console.error("%s: `key` is not a prop. Trying to access it will result in `undefined` being returned. If you need to access the same value within the child component, you should pass it as a different prop. (https://react.dev/link/special-props)", displayName));
        }
        warnAboutAccessingKey.isReactWarning = !0;
        Object.defineProperty(props, "key", {
            get: warnAboutAccessingKey,
            configurable: !0
        });
    }
    function elementRefGetterWithDeprecationWarning() {
        var componentName = getComponentNameFromType(this.type);
        didWarnAboutElementRef[componentName] || (didWarnAboutElementRef[componentName] = !0, console.error("Accessing element.ref was removed in React 19. ref is now a regular prop. It will be removed from the JSX Element type in a future release."));
        componentName = this.props.ref;
        return void 0 !== componentName ? componentName : null;
    }
    function ReactElement(type, key, props, owner, debugStack, debugTask) {
        var refProp = props.ref;
        type = {
            $$typeof: REACT_ELEMENT_TYPE,
            type: type,
            key: key,
            props: props,
            _owner: owner
        };
        null !== (void 0 !== refProp ? refProp : null) ? Object.defineProperty(type, "ref", {
            enumerable: !1,
            get: elementRefGetterWithDeprecationWarning
        }) : Object.defineProperty(type, "ref", {
            enumerable: !1,
            value: null
        });
        type._store = {};
        Object.defineProperty(type._store, "validated", {
            configurable: !1,
            enumerable: !1,
            writable: !0,
            value: 0
        });
        Object.defineProperty(type, "_debugInfo", {
            configurable: !1,
            enumerable: !1,
            writable: !0,
            value: null
        });
        Object.defineProperty(type, "_debugStack", {
            configurable: !1,
            enumerable: !1,
            writable: !0,
            value: debugStack
        });
        Object.defineProperty(type, "_debugTask", {
            configurable: !1,
            enumerable: !1,
            writable: !0,
            value: debugTask
        });
        Object.freeze && (Object.freeze(type.props), Object.freeze(type));
        return type;
    }
    function jsxDEVImpl(type, config, maybeKey, isStaticChildren, debugStack, debugTask) {
        var children = config.children;
        if (void 0 !== children) if (isStaticChildren) if (isArrayImpl(children)) {
            for(isStaticChildren = 0; isStaticChildren < children.length; isStaticChildren++)validateChildKeys(children[isStaticChildren]);
            Object.freeze && Object.freeze(children);
        } else console.error("React.jsx: Static children should always be an array. You are likely explicitly calling React.jsxs or React.jsxDEV. Use the Babel transform instead.");
        else validateChildKeys(children);
        if (hasOwnProperty.call(config, "key")) {
            children = getComponentNameFromType(type);
            var keys = Object.keys(config).filter(function(k) {
                return "key" !== k;
            });
            isStaticChildren = 0 < keys.length ? "{key: someKey, " + keys.join(": ..., ") + ": ...}" : "{key: someKey}";
            didWarnAboutKeySpread[children + isStaticChildren] || (keys = 0 < keys.length ? "{" + keys.join(": ..., ") + ": ...}" : "{}", console.error('A props object containing a "key" prop is being spread into JSX:\n  let props = %s;\n  <%s {...props} />\nReact keys must be passed directly to JSX without using spread:\n  let props = %s;\n  <%s key={someKey} {...props} />', isStaticChildren, children, keys, children), didWarnAboutKeySpread[children + isStaticChildren] = !0);
        }
        children = null;
        void 0 !== maybeKey && (checkKeyStringCoercion(maybeKey), children = "" + maybeKey);
        hasValidKey(config) && (checkKeyStringCoercion(config.key), children = "" + config.key);
        if ("key" in config) {
            maybeKey = {};
            for(var propName in config)"key" !== propName && (maybeKey[propName] = config[propName]);
        } else maybeKey = config;
        children && defineKeyPropWarningGetter(maybeKey, "function" === typeof type ? type.displayName || type.name || "Unknown" : type);
        return ReactElement(type, children, maybeKey, getOwner(), debugStack, debugTask);
    }
    function validateChildKeys(node) {
        isValidElement(node) ? node._store && (node._store.validated = 1) : "object" === typeof node && null !== node && node.$$typeof === REACT_LAZY_TYPE && ("fulfilled" === node._payload.status ? isValidElement(node._payload.value) && node._payload.value._store && (node._payload.value._store.validated = 1) : node._store && (node._store.validated = 1));
    }
    function isValidElement(object) {
        return "object" === typeof object && null !== object && object.$$typeof === REACT_ELEMENT_TYPE;
    }
    var React = __turbopack_context__.r("[project]/ai-mock-interview/node_modules/next/dist/compiled/react/index.js [app-client] (ecmascript)"), REACT_ELEMENT_TYPE = Symbol.for("react.transitional.element"), REACT_PORTAL_TYPE = Symbol.for("react.portal"), REACT_FRAGMENT_TYPE = Symbol.for("react.fragment"), REACT_STRICT_MODE_TYPE = Symbol.for("react.strict_mode"), REACT_PROFILER_TYPE = Symbol.for("react.profiler"), REACT_CONSUMER_TYPE = Symbol.for("react.consumer"), REACT_CONTEXT_TYPE = Symbol.for("react.context"), REACT_FORWARD_REF_TYPE = Symbol.for("react.forward_ref"), REACT_SUSPENSE_TYPE = Symbol.for("react.suspense"), REACT_SUSPENSE_LIST_TYPE = Symbol.for("react.suspense_list"), REACT_MEMO_TYPE = Symbol.for("react.memo"), REACT_LAZY_TYPE = Symbol.for("react.lazy"), REACT_ACTIVITY_TYPE = Symbol.for("react.activity"), REACT_VIEW_TRANSITION_TYPE = Symbol.for("react.view_transition"), REACT_CLIENT_REFERENCE = Symbol.for("react.client.reference"), ReactSharedInternals = React.__CLIENT_INTERNALS_DO_NOT_USE_OR_WARN_USERS_THEY_CANNOT_UPGRADE, hasOwnProperty = Object.prototype.hasOwnProperty, isArrayImpl = Array.isArray, createTask = console.createTask ? console.createTask : function() {
        return null;
    };
    React = {
        react_stack_bottom_frame: function(callStackForError) {
            return callStackForError();
        }
    };
    var specialPropKeyWarningShown;
    var didWarnAboutElementRef = {};
    var unknownOwnerDebugStack = React.react_stack_bottom_frame.bind(React, UnknownOwner)();
    var unknownOwnerDebugTask = createTask(getTaskName(UnknownOwner));
    var didWarnAboutKeySpread = {};
    exports.Fragment = REACT_FRAGMENT_TYPE;
    exports.jsxDEV = function(type, config, maybeKey, isStaticChildren) {
        var trackActualOwner = 1e4 > ReactSharedInternals.recentlyCreatedOwnerStacks++;
        if (trackActualOwner) {
            var previousStackTraceLimit = Error.stackTraceLimit;
            Error.stackTraceLimit = 10;
            var debugStackDEV = Error("react-stack-top-frame");
            Error.stackTraceLimit = previousStackTraceLimit;
        } else debugStackDEV = unknownOwnerDebugStack;
        return jsxDEVImpl(type, config, maybeKey, isStaticChildren, debugStackDEV, trackActualOwner ? createTask(getTaskName(type)) : unknownOwnerDebugTask);
    };
}();
}),
"[project]/ai-mock-interview/node_modules/next/dist/compiled/react/jsx-dev-runtime.js [app-client] (ecmascript)", ((__turbopack_context__, module, exports) => {
"use strict";

var __TURBOPACK__imported__module__$5b$project$5d2f$ai$2d$mock$2d$interview$2f$node_modules$2f$next$2f$dist$2f$build$2f$polyfills$2f$process$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = /*#__PURE__*/ __turbopack_context__.i("[project]/ai-mock-interview/node_modules/next/dist/build/polyfills/process.js [app-client] (ecmascript)");
'use strict';
if ("TURBOPACK compile-time falsy", 0) //TURBOPACK unreachable
;
else {
    module.exports = __turbopack_context__.r("[project]/ai-mock-interview/node_modules/next/dist/compiled/react/cjs/react-jsx-dev-runtime.development.js [app-client] (ecmascript)");
}
}),
]);

//# sourceMappingURL=ai-mock-interview_7e7d497f._.js.map