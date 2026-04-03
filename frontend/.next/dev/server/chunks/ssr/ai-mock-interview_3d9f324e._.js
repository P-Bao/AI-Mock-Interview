module.exports = [
"[project]/ai-mock-interview/lib/audioStreamer.ts [app-ssr] (ecmascript)", ((__turbopack_context__) => {
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
}),
"[project]/ai-mock-interview/app/interview/page.tsx [app-ssr] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "default",
    ()=>InterviewPage
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$ai$2d$mock$2d$interview$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/ai-mock-interview/node_modules/next/dist/server/route-modules/app-page/vendored/ssr/react-jsx-dev-runtime.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$ai$2d$mock$2d$interview$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/ai-mock-interview/node_modules/next/dist/server/route-modules/app-page/vendored/ssr/react.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$ai$2d$mock$2d$interview$2f$lib$2f$audioStreamer$2e$ts__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/ai-mock-interview/lib/audioStreamer.ts [app-ssr] (ecmascript)");
"use client";
;
;
;
function InterviewPage() {
    const [recording, setRecording] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$ai$2d$mock$2d$interview$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useState"])(false);
    const [paused, setPaused] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$ai$2d$mock$2d$interview$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useState"])(false);
    const [transcript, setTranscript] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$ai$2d$mock$2d$interview$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useState"])("");
    const streamerRef = (0, __TURBOPACK__imported__module__$5b$project$5d2f$ai$2d$mock$2d$interview$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useRef"])(null);
    const makeWsUrl = (0, __TURBOPACK__imported__module__$5b$project$5d2f$ai$2d$mock$2d$interview$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useCallback"])(()=>{
        return "ws://127.0.0.1:8000/ws";
    }, []);
    (0, __TURBOPACK__imported__module__$5b$project$5d2f$ai$2d$mock$2d$interview$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useEffect"])(()=>{
        return ()=>{
            try {
                streamerRef.current?.stop();
            } catch  {}
            streamerRef.current = null;
        };
    }, []);
    const start = (0, __TURBOPACK__imported__module__$5b$project$5d2f$ai$2d$mock$2d$interview$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useCallback"])(async ()=>{
        if (recording && !paused) return;
        try {
            const streamer = new __TURBOPACK__imported__module__$5b$project$5d2f$ai$2d$mock$2d$interview$2f$lib$2f$audioStreamer$2e$ts__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["AudioStreamer"]();
            streamer.onText = (text)=>setTranscript((prev)=>prev ? `${prev} ${text}` : text);
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
    }, [
        recording,
        paused,
        makeWsUrl
    ]);
    const stop = (0, __TURBOPACK__imported__module__$5b$project$5d2f$ai$2d$mock$2d$interview$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useCallback"])(()=>{
        if (!recording && !paused) return;
        try {
            streamerRef.current?.stop();
        } catch  {}
        streamerRef.current = null;
        setRecording(false);
        setPaused(false);
    }, [
        recording,
        paused
    ]);
    const pause = (0, __TURBOPACK__imported__module__$5b$project$5d2f$ai$2d$mock$2d$interview$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useCallback"])(()=>{
        if (!recording || paused) return;
        try {
            streamerRef.current?.stop();
        } catch  {}
        streamerRef.current = null;
        setPaused(true);
    }, [
        recording,
        paused
    ]);
    const resume = (0, __TURBOPACK__imported__module__$5b$project$5d2f$ai$2d$mock$2d$interview$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useCallback"])(async ()=>{
        if (!paused) return;
        try {
            const streamer = new __TURBOPACK__imported__module__$5b$project$5d2f$ai$2d$mock$2d$interview$2f$lib$2f$audioStreamer$2e$ts__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["AudioStreamer"]();
            streamer.onText = (text)=>setTranscript((prev)=>prev ? `${prev} ${text}` : text);
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
    }, [
        paused,
        makeWsUrl
    ]);
    return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$ai$2d$mock$2d$interview$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("main", {
        className: "container mx-auto px-4 py-16",
        children: [
            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$ai$2d$mock$2d$interview$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("h2", {
                className: "text-3xl font-bold mb-4",
                children: "Buổi phỏng vấn mô phỏng"
            }, void 0, false, {
                fileName: "[project]/ai-mock-interview/app/interview/page.tsx",
                lineNumber: 98,
                columnNumber: 7
            }, this),
            !recording && /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$ai$2d$mock$2d$interview$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("button", {
                onClick: start,
                className: "bg-green-500 text-white py-2 px-4 rounded",
                children: "Bắt đầu ghi âm"
            }, void 0, false, {
                fileName: "[project]/ai-mock-interview/app/interview/page.tsx",
                lineNumber: 101,
                columnNumber: 9
            }, this),
            recording && !paused && /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$ai$2d$mock$2d$interview$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                className: "flex gap-4",
                children: [
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$ai$2d$mock$2d$interview$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("button", {
                        onClick: pause,
                        className: "bg-yellow-500 text-white py-2 px-4 rounded",
                        children: "Tạm dừng"
                    }, void 0, false, {
                        fileName: "[project]/ai-mock-interview/app/interview/page.tsx",
                        lineNumber: 108,
                        columnNumber: 11
                    }, this),
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$ai$2d$mock$2d$interview$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("button", {
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
            paused && /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$ai$2d$mock$2d$interview$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                className: "flex gap-4",
                children: [
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$ai$2d$mock$2d$interview$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("button", {
                        onClick: resume,
                        className: "bg-blue-500 text-white py-2 px-4 rounded",
                        children: "Tiếp tục"
                    }, void 0, false, {
                        fileName: "[project]/ai-mock-interview/app/interview/page.tsx",
                        lineNumber: 119,
                        columnNumber: 11
                    }, this),
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$ai$2d$mock$2d$interview$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("button", {
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
            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$ai$2d$mock$2d$interview$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                className: "mt-10",
                children: [
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$ai$2d$mock$2d$interview$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("h3", {
                        className: "text-xl font-semibold mb-2",
                        children: "Bạn vừa nói:"
                    }, void 0, false, {
                        fileName: "[project]/ai-mock-interview/app/interview/page.tsx",
                        lineNumber: 129,
                        columnNumber: 9
                    }, this),
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$ai$2d$mock$2d$interview$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("p", {
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
}),
"[project]/ai-mock-interview/node_modules/next/dist/server/route-modules/app-page/vendored/ssr/react-jsx-dev-runtime.js [app-ssr] (ecmascript)", ((__turbopack_context__, module, exports) => {
"use strict";

module.exports = __turbopack_context__.r("[project]/ai-mock-interview/node_modules/next/dist/server/route-modules/app-page/module.compiled.js [app-ssr] (ecmascript)").vendored['react-ssr'].ReactJsxDevRuntime; //# sourceMappingURL=react-jsx-dev-runtime.js.map
}),
];

//# sourceMappingURL=ai-mock-interview_3d9f324e._.js.map