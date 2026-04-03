import React, { useState, useEffect, useRef } from "react";
import "./LiveAPIDemo.css";
import "./LiveAPIDemo.css";

const LiveAPIDemo = () => {
  // Connection State
  const [connected, setConnected] = useState(false);
  const [debugInfo, setDebugInfo] = useState("Ready to connect...");
  // Application Config (Hidden from UI)
  const proxyUrl = import.meta.env.VITE_PROXY_URL || "ws://localhost:8000/ws/interview";
  const projectId = import.meta.env.VITE_PROJECT_ID || "";
  const model = import.meta.env.VITE_MODEL || "gemini-live-2.5-flash-native-audio";

  const systemInstructions = import.meta.env.VITE_SYSTEM_INSTRUCTIONS || "You are an AI mock interviewer. Be concise, professional and friendly.";
  const voice = "Puck";
  const temperature = 1.0;
  const enableProactiveAudio = true;
  const enableGrounding = false;
  const enableAffectiveDialog = true;
  const enableAlertTool = true;
  const enableCssStyleTool = true;
  const enableInputTranscription = true;
  const enableOutputTranscription = true;

  // Activity Detection State
  const disableActivityDetection = false;
  const silenceDuration = 500;
  const prefixPadding = 500;
  const endSpeechSensitivity = "END_SENSITIVITY_UNSPECIFIED";
  const startSpeechSensitivity = "START_SENSITIVITY_UNSPECIFIED";

  // Media State
  const [audioStreaming, setAudioStreaming] = useState(false);
  const [videoStreaming, setVideoStreaming] = useState(false);
  const [screenSharing, setScreenSharing] = useState(false);
  const [volume, setVolume] = useState(80);
  const [audioInputDevices, setAudioInputDevices] = useState([]);
  const [videoInputDevices, setVideoInputDevices] = useState([]);
  const [selectedMic, setSelectedMic] = useState("");
  const [selectedCamera, setSelectedCamera] = useState("");

  // Chat State
  const [chatMessages, setChatMessages] = useState([]);
  const [chatInput, setChatInput] = useState("");

  // Refs
  const wsRef = useRef(null);
  const recognitionRef = useRef(null);
  const isListeningRef = useRef(false);
  const isAiSpeakingRef = useRef(false);
  const audioStreamerRef = useRef(null);
  const videoStreamerRef = useRef(null);
  const screenCaptureRef = useRef(null);
  const audioPlayerRef = useRef(null);
  const videoPreviewRef = useRef(null);
  const chatContainerRef = useRef(null);

  // Initialize Media Devices
  useEffect(() => {
    const getDevices = async () => {
      try {
        const devices = await navigator.mediaDevices.enumerateDevices();
        setAudioInputDevices(
          devices.filter((device) => device.kind === "audioinput")
        );
        setVideoInputDevices(
          devices.filter((device) => device.kind === "videoinput")
        );
      } catch (error) {
        console.error("Error enumerating devices:", error);
      }
    };
    getDevices();
  }, []);

  // Scroll to bottom of chat
  useEffect(() => {
    if (chatContainerRef.current) {
      chatContainerRef.current.scrollTop =
        chatContainerRef.current.scrollHeight;
    }
  }, [chatMessages]);

  const addMessage = (text, type, mode = "add", isFinished = false) => {
    setChatMessages((prev) => {
      // Logic REPLACE: Cập nhật tin nhắn cuối nếu cùng loại và chưa kết thúc
      if (
        mode === "replace" &&
        prev.length > 0 &&
        prev[prev.length - 1].type === type &&
        !prev[prev.length - 1].isFinished
      ) {
        const newMessages = [...prev];
        newMessages[newMessages.length - 1] = {
          ...newMessages[newMessages.length - 1],
          text: text,
          isFinished: isFinished
        };
        return newMessages;
      }

      // Logic ADD: Thêm mới
      if (!text && !isFinished) return prev;
      return [...prev, { text: text || "", type, isFinished }];
    });
  };

  const speakText = (text) => {
    if ("speechSynthesis" in window) {
      window.speechSynthesis.cancel();
      const utterance = new SpeechSynthesisUtterance(text);

      const voices = window.speechSynthesis.getVoices();
      const viVoice = voices.find(v => v.lang.includes("vi-VN") || v.lang.includes("vi_VN"));

      if (viVoice) {
        utterance.voice = viVoice;
      }

      utterance.lang = "vi-VN";

      // TỰ ĐỘNG BẬT MIC KHI AI NÓI XONG
      utterance.onstart = () => {
        isAiSpeakingRef.current = true;
      };

      utterance.onend = () => {
        isAiSpeakingRef.current = false;
        if (connected) {
          setTimeout(() => {
            startListening();
          }, 300);
        }
      };

      window.speechSynthesis.speak(utterance);
    }
  };

  const handleMessage = (event) => {
    try {
      const message = JSON.parse(event.data);
      setDebugInfo(`Received: ${message.type}`);

      switch (message.type) {
        case "question":
          addMessage(message.data, "assistant");
          speakText(message.data);
          break;
        case "feedback":
          addMessage(message.data, "assistant");
          break;
        case "error":
          addMessage(`Lỗi: ${message.data}`, "system");
          break;
        default:
          console.log("Loại tin nhắn không xác định:", message);
      }
    } catch (error) {
      console.error("Error parsing message:", error);
    }
  };

  const disconnect = () => {
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }

    if (recognitionRef.current) {
      recognitionRef.current.stop();
      recognitionRef.current = null;
    }

    setConnected(false);
    setAudioStreaming(false);
    setVideoStreaming(false);
    setScreenSharing(false);
    setDebugInfo("Đã ngắt kết nối");

    if (videoPreviewRef.current) {
      videoPreviewRef.current.srcObject = null;
      videoPreviewRef.current.hidden = true;
    }
  };

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      disconnect();
    };
  }, []);

  const connect = async () => {
    try {
      // YÊU CẦU QUYỀN TRUY CẬP MICRO NGAY KHI NHẤN KẾT NỐI
      setDebugInfo("Yêu cầu quyền truy cập Micro...");
      await navigator.mediaDevices.getUserMedia({ audio: true });
      addMessage("Quyền Micro đã được duyệt. Đang chuẩn bị buổi phỏng vấn...", "system");

      setDebugInfo("Đang kết nối tới: " + proxyUrl);
      wsRef.current = new WebSocket(proxyUrl);

      wsRef.current.onopen = () => {
        setConnected(true);
        setDebugInfo("Kết nối thành công");
        addMessage("Buổi phỏng vấn bắt đầu!", "system");
      };

      wsRef.current.onmessage = handleMessage;

      wsRef.current.onclose = () => {
        setConnected(false);
        disconnect();
      };

      wsRef.current.onerror = (error) => {
        console.error("Lỗi WebSocket:", error);
        setDebugInfo("Lỗi kết nối");
      };
    } catch (error) {
      console.error("Kết nối thất bại:", error);
      setDebugInfo("Lỗi: " + error.message);
    }
  };

  const startListening = () => {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;

    if (!SpeechRecognition) {
      alert("Trình duyệt không hỗ trợ nhận diện giọng nói.");
      return;
    }

    // Nếu đang stream thì dừng lại trước khi bắt đầu cái mới
    if (recognitionRef.current) {
      recognitionRef.current.stop();
      isListeningRef.current = false;
    }

    try {
      const recognition = new SpeechRecognition();
      recognition.lang = "vi-VN";
      recognition.interimResults = true;
      recognition.continuous = true; // CHẾ ĐỘ LIÊN TỤC: Không tự ngắt khi im lặng

      recognition.onstart = () => {
        setAudioStreaming(true);
        isListeningRef.current = true;
        addMessage("[Hệ thống đang mở Mic, mời bạn trả lời...]", "system");
      };

      recognition.onresult = (event) => {
        if (!isListeningRef.current) return;

        const transcript = Array.from(event.results)
          .map(result => result[0])
          .map(result => result.transcript)
          .join("");

        setChatInput(transcript);
      };

      recognition.onend = () => {
        setAudioStreaming(false);
        isListeningRef.current = false;
        // Không thêm tin nhắn hệ thống phiền phức ở đây nữa
      };

      recognition.onerror = (event) => {
        console.error("Lỗi Mic:", event.error);
        setAudioStreaming(false);
        isListeningRef.current = false;
        if (event.error !== 'no-speech') {
          addMessage("[Lỗi Micro: " + event.error + "]", "system");
        }
      };

      recognition.start();
      recognitionRef.current = recognition;

    } catch (error) {
      console.error("Micro error:", error);
    }
  };

  const sendMessage = (textToSend = null) => {
    const text = textToSend !== null ? textToSend : chatInput;
    if (!text || !text.trim()) return;

    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      // 1. Dừng Micro ngay lập tức để tránh buffer
      if (recognitionRef.current) {
        isListeningRef.current = false;
        recognitionRef.current.stop();
        setAudioStreaming(false);
      }

      // 2. Hiện tin nhắn lên khung chat
      addMessage(text, "user");

      // 3. Gửi sang Server
      wsRef.current.send(JSON.stringify({
        answer: text
      }));

      // 4. Xóa sạch ô nhập liệu (2 lần để chắc chắn)
      setChatInput("");
      setTimeout(() => setChatInput(""), 10);

    } else {
      addMessage("[Vui lòng kết nối trước]", "system");
    }
  };

  const toggleAudio = async () => {
    if ("speechSynthesis" in window) {
      window.speechSynthesis.cancel();
    }

    if (audioStreaming) {
      if (recognitionRef.current) recognitionRef.current.stop();
      setAudioStreaming(false);
      isListeningRef.current = false;
    } else {
      startListening();
    }
  };

  const toggleVideo = async () => {
    if (!videoStreaming) {
      try {
        if (!videoStreamerRef.current && clientRef.current) {
          videoStreamerRef.current = new VideoStreamer(clientRef.current);
        }

        if (videoStreamerRef.current) {
          const video = await videoStreamerRef.current.start({
            deviceId: selectedCamera,
          });
          setVideoStreaming(true);
          if (videoPreviewRef.current) {
            videoPreviewRef.current.srcObject = video.srcObject;
            videoPreviewRef.current.hidden = false;
          }
          addMessage("[Camera on]", "system");
        } else {
          addMessage("[Connect to Gemini first]", "system");
        }
      } catch (error) {
        addMessage("[Video error: " + error.message + "]", "system");
      }
    } else {
      if (videoStreamerRef.current) videoStreamerRef.current.stop();
      setVideoStreaming(false);
      if (videoPreviewRef.current) {
        videoPreviewRef.current.srcObject = null;
        videoPreviewRef.current.hidden = true;
      }
      addMessage("[Camera off]", "system");
    }
  };

  const toggleScreen = async () => {
    if (!screenSharing) {
      try {
        if (!screenCaptureRef.current && clientRef.current) {
          screenCaptureRef.current = new ScreenCapture(clientRef.current);
        }

        if (screenCaptureRef.current) {
          const video = await screenCaptureRef.current.start();
          setScreenSharing(true);
          if (videoPreviewRef.current) {
            videoPreviewRef.current.srcObject = video.srcObject;
            videoPreviewRef.current.hidden = false;
          }
          addMessage("[Screen sharing on]", "system");
        } else {
          addMessage("[Connect to Gemini first]", "system");
        }
      } catch (error) {
        addMessage("[Screen share error: " + error.message + "]", "system");
      }
    } else {
      if (screenCaptureRef.current) screenCaptureRef.current.stop();
      setScreenSharing(false);
      if (!videoStreaming && videoPreviewRef.current) {
        videoPreviewRef.current.srcObject = null;
        videoPreviewRef.current.hidden = true;
      }
      addMessage("[Screen sharing off]", "system");
    }
  };

  // Hàm cũ đã được hợp nhất vào bên trên

  const finishInterview = () => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      addMessage("Đang kết thúc phỏng vấn và lập báo cáo...", "system");
      wsRef.current.send(JSON.stringify({
        type: "finish"
      }));
    } else {
      disconnect();
    }
  };

  const handleVolumeChange = (e) => {
    const newVolume = e.target.value;
    setVolume(newVolume);
    if (audioPlayerRef.current) {
      audioPlayerRef.current.setVolume(newVolume / 100);
    }
  };

  return (
    <div className="live-api-demo">
      <div className="toolbar">
        <div className="toolbar-left">
          <h1 className="brand-title">AI Mockk Interview</h1>
        </div>

        <div className="toolbar-center">
          <button
            onClick={connected ? disconnect : connect}
            className={connected ? "disconnect" : "active"}
          >
            {connected ? "Ngắt kết nối" : "Kết nối"}
          </button>

          {connected && (
            <button
              onClick={toggleAudio}
              className={audioStreaming ? "active" : ""}
              style={{ backgroundColor: audioStreaming ? '#2ecc71' : '#3498db', color: 'white' }}
            >
              {audioStreaming ? "🎙️ Đang nghe..." : "🎙️ Bật Mic"}
            </button>
          )}

          {connected && (
            <button
              onClick={finishInterview}
              className="disconnect-alt"
            >
              🏁 Kết thúc
            </button>
          )}

          <div className="dropdown">
            <button className="dropbtn">Media ▾</button>
            <div className="dropdown-content media-dropdown">
              <div className="control-group">
                <div className="input-group">
                  <label>Microphone:</label>
                  <select value={selectedMic} onChange={(e) => setSelectedMic(e.target.value)}>
                    <option value="">Default Microphone</option>
                    {audioInputDevices.map((device) => (
                      <option key={device.deviceId} value={device.deviceId}>
                        {device.label || `Microphone ${device.deviceId}`}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="input-group">
                  <label>Camera:</label>
                  <select value={selectedCamera} onChange={(e) => setSelectedCamera(e.target.value)}>
                    <option value="">Default Camera</option>
                    {videoInputDevices.map((device) => (
                      <option key={device.deviceId} value={device.deviceId}>
                        {device.label || `Camera ${device.deviceId}`}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="button-group-vertical">
                  <button onClick={toggleVideo}>{videoStreaming ? "Tắt Camera" : "Bật Camera"}</button>
                  <button onClick={toggleScreen}>{screenSharing ? "Dừng Chia sẻ" : "Chia sẻ màn hình"}</button>
                </div>

                <div className="input-group">
                  <label>Output volume: {volume}%</label>
                  <input
                    type="range"
                    min="0"
                    max="100"
                    value={volume}
                    onChange={handleVolumeChange}
                  />
                </div>

                <video
                  ref={videoPreviewRef}
                  autoPlay
                  playsInline
                  muted
                  hidden
                  className="video-preview"
                />
              </div>
            </div>
          </div>

        </div> {/* end toolbar-center */}
      </div> {/* end toolbar */}

      <div className="chat-container" ref={chatContainerRef}>
        {chatMessages.map((message, index) => (
          <div key={index} className={`message ${message.type}`}>
            <div className="message-content">
              {message.type === "system" ? (
                <span className="system-text">{message.text}</span>
              ) : (
                message.text
              )}
            </div>
          </div>
        ))}
      </div>

      <div className="input-container">
        <textarea
          value={chatInput}
          onChange={(e) => setChatInput(e.target.value)}
          placeholder="Nhập câu trả lời của bạn hoặc nói vào Micro..."
        />
        <button onClick={() => sendMessage()}>Gửi</button>
      </div>

      {/* Debug Info Section */}
      <div className="debug-info">
        <pre className="setup-json-display">{debugInfo}</pre>
      </div>

      <div className="footer-title" style={{ textAlign: 'center', padding: '10px', color: '#7f8c8d', fontSize: '0.8rem' }}>
        <h3>Gemini Live API React Demo</h3>
      </div>
    </div>
  );
};

export default LiveAPIDemo;
