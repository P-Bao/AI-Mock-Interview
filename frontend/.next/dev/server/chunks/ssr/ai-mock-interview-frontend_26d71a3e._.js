module.exports = [
"[project]/ai-mock-interview-frontend/app/interview/page.tsx [app-ssr] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "default",
    ()=>InterviewPage
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$ai$2d$mock$2d$interview$2d$frontend$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/ai-mock-interview-frontend/node_modules/next/dist/server/route-modules/app-page/vendored/ssr/react-jsx-dev-runtime.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$ai$2d$mock$2d$interview$2d$frontend$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/ai-mock-interview-frontend/node_modules/next/dist/server/route-modules/app-page/vendored/ssr/react.js [app-ssr] (ecmascript)");
"use client";
;
;
;
function InterviewPage() {
    const [messages, setMessages] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$ai$2d$mock$2d$interview$2d$frontend$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useState"])([]);
    const [isRecording, setIsRecording] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$ai$2d$mock$2d$interview$2d$frontend$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useState"])(false);
    const [volume, setVolume] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$ai$2d$mock$2d$interview$2d$frontend$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useState"])(0);
    const socketRef = (0, __TURBOPACK__imported__module__$5b$project$5d2f$ai$2d$mock$2d$interview$2d$frontend$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useRef"])(null);
    const audioContextRef = (0, __TURBOPACK__imported__module__$5b$project$5d2f$ai$2d$mock$2d$interview$2d$frontend$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useRef"])(null);
    const workletNodeRef = (0, __TURBOPACK__imported__module__$5b$project$5d2f$ai$2d$mock$2d$interview$2d$frontend$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useRef"])(null);
    const streamRef = (0, __TURBOPACK__imported__module__$5b$project$5d2f$ai$2d$mock$2d$interview$2d$frontend$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useRef"])(null);
    const chatEndRef = (0, __TURBOPACK__imported__module__$5b$project$5d2f$ai$2d$mock$2d$interview$2d$frontend$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useRef"])(null);
    (0, __TURBOPACK__imported__module__$5b$project$5d2f$ai$2d$mock$2d$interview$2d$frontend$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useEffect"])(()=>{
        const handleBeforeUnload = (e)=>{
            if (isRecording) {
                e.preventDefault();
                e.returnValue = "Bạn đang trong buổi phỏng vấn!";
            }
        };
        window.addEventListener("beforeunload", handleBeforeUnload);
        return ()=>{
            window.removeEventListener("beforeunload", handleBeforeUnload);
        };
    }, [
        isRecording
    ]);
    (0, __TURBOPACK__imported__module__$5b$project$5d2f$ai$2d$mock$2d$interview$2d$frontend$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useEffect"])(()=>{
        chatEndRef.current?.scrollIntoView({
            behavior: "smooth"
        });
    }, [
        messages
    ]);
    const startRecording = async ()=>{
        setIsRecording(true);
        const stream = await navigator.mediaDevices.getUserMedia({
            audio: true
        });
        streamRef.current = stream;
        const audioContext = new AudioContext();
        audioContextRef.current = audioContext;
        await audioContext.audioWorklet.addModule("/recorder-worklet.js");
        const source = audioContext.createMediaStreamSource(stream);
        const workletNode = new AudioWorkletNode(audioContext, "recorder-processor", {
            processorOptions: {
                targetRate: 16000,
                chunkSamples: 640,
                vuMeter: true
            }
        });
        workletNodeRef.current = workletNode;
        const socket = new WebSocket("ws://127.0.0.1:8000/ws/audio");
        socketRef.current = socket;
        socket.binaryType = "arraybuffer";
        socket.onopen = ()=>{
            console.log("Đã kết nối WebSocket");
        };
        socket.onmessage = (event)=>{
            console.log("Tin nhắn WebSocket:", event.data);
            if (typeof event.data === "string") {
                try {
                    const data = JSON.parse(event.data);
                    if (data.text) {
                        setMessages((prev)=>[
                                ...prev,
                                {
                                    role: "user",
                                    text: data.text
                                }
                            ]);
                    }
                    if (data.ai) {
                        setMessages((prev)=>[
                                ...prev,
                                {
                                    role: "ai",
                                    text: data.ai
                                }
                            ]);
                    }
                } catch  {
                    console.log("JSON không hợp lệ");
                }
            }
        };
        workletNode.port.onmessage = (event)=>{
            if (event.data instanceof ArrayBuffer) {
                // 1. Kiểm tra kích thước byte
                const byteLength = event.data.byteLength;
                // 2. Chuyển đổi sang Int16Array để xem giá trị âm thanh thực tế
                const pcm16Data = new Int16Array(event.data);
                // 3. Tính toán một vài giá trị để kiểm tra "độ sống" của mic
                // Lấy 5 mẫu đầu tiên để xem giá trị có khác 0 không
                const samplePreview = pcm16Data.slice(0, 5).join(", ");
                // Tìm giá trị cực đại (Peak) trong chunk này để biết mic to hay nhỏ
                let maxAmp = 0;
                for(let i = 0; i < pcm16Data.length; i++){
                    if (Math.abs(pcm16Data[i]) > maxAmp) maxAmp = Math.abs(pcm16Data[i]);
                }
                // 4. In log chi tiết
                // console.log(
                //     `%c[Gửi Audio] Kích thước: ${byteLength} bytes | Mẫu: ${pcm16Data.length} | Đỉnh: ${maxAmp} | Dữ liệu: [${samplePreview}...]`,
                //     "color: #00d1b2; font-weight: bold;"
                // );
                // Kiểm tra nếu mic "chết" (tất cả đều là số 0)
                if (maxAmp === 0) {
                    console.warn("%c[Warning] Dữ liệu âm thanh toàn số 0. Mic có thể bị chặn hoặc lỗi kết nối!", "color: orange");
                }
                // Gửi sang Backend
                if (socketRef.current?.readyState === WebSocket.OPEN) {
                    socketRef.current.send(event.data);
                }
            }
            if (event.data?.type === "vu") {
                setVolume(event.data.rms);
            }
        };
        source.connect(workletNode);
    };
    const stopRecording = ()=>{
        setIsRecording(false);
        setVolume(0);
        workletNodeRef.current?.disconnect();
        streamRef.current?.getTracks().forEach((track)=>track.stop());
        audioContextRef.current?.close();
        socketRef.current?.close();
    };
    return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$ai$2d$mock$2d$interview$2d$frontend$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
        className: "container",
        children: [
            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$ai$2d$mock$2d$interview$2d$frontend$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("h1", {
                children: "Buổi phỏng vấn mô phỏng"
            }, void 0, false, {
                fileName: "[project]/ai-mock-interview-frontend/app/interview/page.tsx",
                lineNumber: 171,
                columnNumber: 7
            }, this),
            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$ai$2d$mock$2d$interview$2d$frontend$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                className: "button-group",
                children: [
                    !isRecording && /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$ai$2d$mock$2d$interview$2d$frontend$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("button", {
                        className: "btn start",
                        onClick: startRecording,
                        children: "Bắt đầu phỏng vấn"
                    }, void 0, false, {
                        fileName: "[project]/ai-mock-interview-frontend/app/interview/page.tsx",
                        lineNumber: 176,
                        columnNumber: 11
                    }, this),
                    isRecording && /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$ai$2d$mock$2d$interview$2d$frontend$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("button", {
                        className: "btn stop",
                        onClick: stopRecording,
                        children: "Kết thúc phỏng vấn"
                    }, void 0, false, {
                        fileName: "[project]/ai-mock-interview-frontend/app/interview/page.tsx",
                        lineNumber: 182,
                        columnNumber: 11
                    }, this)
                ]
            }, void 0, true, {
                fileName: "[project]/ai-mock-interview-frontend/app/interview/page.tsx",
                lineNumber: 173,
                columnNumber: 7
            }, this),
            isRecording && /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$ai$2d$mock$2d$interview$2d$frontend$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                className: "mic-meter",
                children: [
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$ai$2d$mock$2d$interview$2d$frontend$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("p", {
                        children: "Âm lượng Mic"
                    }, void 0, false, {
                        fileName: "[project]/ai-mock-interview-frontend/app/interview/page.tsx",
                        lineNumber: 192,
                        columnNumber: 11
                    }, this),
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$ai$2d$mock$2d$interview$2d$frontend$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                        className: "volume-bar",
                        children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$ai$2d$mock$2d$interview$2d$frontend$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                            className: "volume-level",
                            style: {
                                width: `${Math.min(volume * 2000, 100)}%`
                            }
                        }, void 0, false, {
                            fileName: "[project]/ai-mock-interview-frontend/app/interview/page.tsx",
                            lineNumber: 195,
                            columnNumber: 13
                        }, this)
                    }, void 0, false, {
                        fileName: "[project]/ai-mock-interview-frontend/app/interview/page.tsx",
                        lineNumber: 194,
                        columnNumber: 11
                    }, this)
                ]
            }, void 0, true, {
                fileName: "[project]/ai-mock-interview-frontend/app/interview/page.tsx",
                lineNumber: 190,
                columnNumber: 9
            }, this),
            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$ai$2d$mock$2d$interview$2d$frontend$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("h3", {
                children: "Cuộc trò chuyện"
            }, void 0, false, {
                fileName: "[project]/ai-mock-interview-frontend/app/interview/page.tsx",
                lineNumber: 206,
                columnNumber: 7
            }, this),
            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$ai$2d$mock$2d$interview$2d$frontend$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                className: "chat-box",
                children: [
                    messages.map((msg, i)=>/*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$ai$2d$mock$2d$interview$2d$frontend$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                            className: `message ${msg.role}`,
                            children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$ai$2d$mock$2d$interview$2d$frontend$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                className: `bubble ${msg.role}`,
                                children: msg.text
                            }, void 0, false, {
                                fileName: "[project]/ai-mock-interview-frontend/app/interview/page.tsx",
                                lineNumber: 214,
                                columnNumber: 13
                            }, this)
                        }, i, false, {
                            fileName: "[project]/ai-mock-interview-frontend/app/interview/page.tsx",
                            lineNumber: 212,
                            columnNumber: 11
                        }, this)),
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$ai$2d$mock$2d$interview$2d$frontend$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                        ref: chatEndRef
                    }, void 0, false, {
                        fileName: "[project]/ai-mock-interview-frontend/app/interview/page.tsx",
                        lineNumber: 222,
                        columnNumber: 9
                    }, this)
                ]
            }, void 0, true, {
                fileName: "[project]/ai-mock-interview-frontend/app/interview/page.tsx",
                lineNumber: 208,
                columnNumber: 7
            }, this)
        ]
    }, void 0, true, {
        fileName: "[project]/ai-mock-interview-frontend/app/interview/page.tsx",
        lineNumber: 169,
        columnNumber: 5
    }, this);
}
}),
"[project]/ai-mock-interview-frontend/node_modules/next/dist/server/route-modules/app-page/vendored/ssr/react-jsx-dev-runtime.js [app-ssr] (ecmascript)", ((__turbopack_context__, module, exports) => {
"use strict";

module.exports = __turbopack_context__.r("[project]/ai-mock-interview-frontend/node_modules/next/dist/server/route-modules/app-page/module.compiled.js [app-ssr] (ecmascript)").vendored['react-ssr'].ReactJsxDevRuntime; //# sourceMappingURL=react-jsx-dev-runtime.js.map
}),
];

//# sourceMappingURL=ai-mock-interview-frontend_26d71a3e._.js.map