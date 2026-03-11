"use client"

import { useState, useRef } from "react"
import "./interview.css"

export default function InterviewPage() {

  const [text, setText] = useState("Chưa có nội dung")
  const [isRecording, setIsRecording] = useState(false)
  const [isSpeaking, setIsSpeaking] = useState(false)
  const [volume, setVolume] = useState(0)

  const socketRef = useRef<WebSocket | null>(null)
  const audioContextRef = useRef<AudioContext | null>(null)
  const workletNodeRef = useRef<AudioWorkletNode | null>(null)
  const streamRef = useRef<MediaStream | null>(null)

  const silenceTimerRef = useRef<any>(null)

  const startRecording = async () => {

    const socket = new WebSocket("ws://127.0.0.1:8000/ws")
    socketRef.current = socket

    socket.binaryType = "arraybuffer"

    socket.onopen = async () => {

      setIsRecording(true)

      const stream = await navigator.mediaDevices.getUserMedia({
        audio: true
      })

      streamRef.current = stream

      const audioContext = new AudioContext()
      audioContextRef.current = audioContext

      await audioContext.audioWorklet.addModule("/worklets/recorder-worklet.js")

      const source = audioContext.createMediaStreamSource(stream)

      const workletNode = new AudioWorkletNode(
        audioContext,
        "recorder-processor",
        {
          processorOptions: {
            targetRate: 16000,
            chunkSamples: 640,
            vuMeter: true
          }
        }
      )

      workletNodeRef.current = workletNode

      workletNode.port.onmessage = (event) => {

        // audio PCM chunk
        if (event.data instanceof ArrayBuffer) {

          if (socket.readyState === WebSocket.OPEN) {
            socket.send(event.data)
          }
        }

        // VU meter
        if (event.data?.type === "vu") {

          const rms = event.data.rms
          setVolume(rms)

          if (rms > 0.02) {

            setIsSpeaking(true)

            if (silenceTimerRef.current) {
              clearTimeout(silenceTimerRef.current)
            }

          } else {

            silenceTimerRef.current = setTimeout(() => {
              setIsSpeaking(false)
            }, 500)

          }

        }

      }

      source.connect(workletNode)

    }

    socket.onmessage = (event) => {

      if (!event.data) return

      try {
        const data = JSON.parse(event.data)

        setText((prev) => prev + " " + data.text)

      } catch (err) {
        console.log("Invalid JSON", err)
      }
    }
  }

  const stopRecording = () => {

    setIsRecording(false)
    setIsSpeaking(false)
    setVolume(0)

    workletNodeRef.current?.disconnect()

    streamRef.current?.getTracks().forEach((track) => track.stop())

    audioContextRef.current?.close()

    socketRef.current?.close()
  }

  return (

    <div style={{ padding: 40 }}>

      <h1 style={{
      }
      }>Buổi phỏng vấn mô phỏng</h1>

      <div style={{ marginBottom: 20 }}>

        {!isRecording && (
          <button className="btn start" onClick={startRecording}>
            Bắt đầu ghi
          </button>
        )}

        {isRecording && /*isSpeaking &&*/ (
          <button className="btn stop" onClick={stopRecording}>
            Dừng ghi
          </button>
        )}

      </div>

      {/* Mic volume */}
      
      {isRecording && (
        <div className="mic-meter">
          <p>volume:</p>
          <div className="volume-bar">
            <div
              className="volume-level"
              style={{ width: `${Math.min(volume * 2000, 100)}%` }}
            />
          </div>
        </div>
      )}

      <h3>Bạn vừa nói:</h3>

      <div
        style={{
          background: "#eee",
          padding: 20,
          minHeight: 80
        }}
      >
        {text}
      </div>

    </div>

  )

}