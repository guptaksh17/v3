import { useEffect, useRef, useState } from "react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";

interface Detection {
  gender: string;
  confidence: number;
  bbox: [number, number, number, number];
}

const GenderDetection = () => {
  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const [isStreaming, setIsStreaming] = useState(false);

  const startWebcam = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: true });
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        setIsStreaming(true);
      }
    } catch (error) {
      console.error("Error accessing webcam:", error);
    }
  };

  const stopWebcam = () => {
    if (videoRef.current?.srcObject) {
      const stream = videoRef.current.srcObject as MediaStream;
      stream.getTracks().forEach(track => track.stop());
      videoRef.current.srcObject = null;
      setIsStreaming(false);
    }
  };

  const connectWebSocket = () => {
    wsRef.current = new WebSocket("ws://localhost:8001/ws");
    wsRef.current.onmessage = (event) => {
      const detections: Detection[] = JSON.parse(event.data);
      drawDetections(detections);
    };
    wsRef.current.onerror = (error) => {
      console.error("WebSocket error:", error);
    };
  };

  const drawDetections = (detections: Detection[]) => {
    if (!canvasRef.current || !videoRef.current) return;

    const ctx = canvasRef.current.getContext("2d");
    if (!ctx) return;

    // Clear previous drawings
    ctx.clearRect(0, 0, canvasRef.current.width, canvasRef.current.height);

    // Draw video frame
    ctx.drawImage(videoRef.current, 0, 0, canvasRef.current.width, canvasRef.current.height);

    // Draw detections
    detections.forEach(({ gender, confidence, bbox }) => {
      const [x, y, w, h] = bbox;
      
      // Draw rectangle
      ctx.strokeStyle = gender === "Male" ? "#2563eb" : "#db2777";
      ctx.lineWidth = 2;
      ctx.strokeRect(x, y, w, h);

      // Draw label
      ctx.fillStyle = gender === "Male" ? "#2563eb" : "#db2777";
      ctx.font = "16px Inter";
      const label = `${gender} (${(confidence * 100).toFixed(1)}%)`;
      ctx.fillText(label, x, y - 10);
    });
  };

  const sendFrame = () => {
    if (!canvasRef.current || !videoRef.current || !wsRef.current) return;

    const ctx = canvasRef.current.getContext("2d");
    if (!ctx) return;

    // Draw the current video frame
    ctx.drawImage(videoRef.current, 0, 0, canvasRef.current.width, canvasRef.current.height);

    // Get the frame as base64 data URL
    const frameData = canvasRef.current.toDataURL("image/jpeg", 0.8);

    // Send to WebSocket if connected
    if (wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(frameData);
    }
  };

  useEffect(() => {
    let frameInterval: number;

    if (isStreaming) {
      connectWebSocket();
      frameInterval = window.setInterval(sendFrame, 100); // Send frame every 100ms
    }

    return () => {
      clearInterval(frameInterval);
      wsRef.current?.close();
    };
  }, [isStreaming]);

  return (
    <div className="container mx-auto py-8">
      <Card className="p-6 max-w-3xl mx-auto">
        <h1 className="text-3xl font-bold mb-6">Real-Time Gender Detection</h1>
        <div className="relative aspect-video mb-4 bg-gray-100 dark:bg-gray-800 rounded-lg overflow-hidden">
          <video
            ref={videoRef}
            className="absolute inset-0 w-full h-full object-cover"
            autoPlay
            playsInline
            muted
          />
          <canvas
            ref={canvasRef}
            className="absolute inset-0 w-full h-full"
            width={640}
            height={360}
          />
        </div>
        <div className="flex justify-center gap-4">
          {!isStreaming ? (
            <Button onClick={startWebcam}>Start Webcam</Button>
          ) : (
            <Button variant="destructive" onClick={stopWebcam}>
              Stop Webcam
            </Button>
          )}
        </div>
      </Card>
    </div>
  );
};

export default GenderDetection;
