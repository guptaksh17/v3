import { useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { useToast } from "@/hooks/use-toast";
import { Loader2, RefreshCw } from "lucide-react";

interface WebcamVerificationProps {
  onVerificationComplete: (success: boolean) => void;
  onCancel: () => void;
}

const WebcamVerification = ({ onVerificationComplete, onCancel }: WebcamVerificationProps) => {
  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const frameIntervalRef = useRef<number | null>(null);
  const [isVerifying, setIsVerifying] = useState(false);
  const { toast } = useToast();
  const [detectionMessage, setDetectionMessage] = useState<string>('');
  const [showError, setShowError] = useState(false);
  const [isVerified, setIsVerified] = useState(false);

  const startWebcam = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: true });
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        setIsVerifying(true);
      }
    } catch (error) {
      console.error("Error accessing webcam:", error);
      toast({
        title: "Camera Access Error",
        description: "Please allow camera access for gender verification",
        variant: "destructive",
      });
      onCancel();
    }
  };

  const stopWebcam = () => {
    if (videoRef.current?.srcObject) {
      const stream = videoRef.current.srcObject as MediaStream;
      stream.getTracks().forEach(track => track.stop());
      videoRef.current.srcObject = null;
    }
    setIsVerifying(false);
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
    if (frameIntervalRef.current) {
      clearInterval(frameIntervalRef.current);
      frameIntervalRef.current = null;
    }
  };

  const connectWebSocket = () => {
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }

    try {
      const wsUrl = `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.hostname}:8001/ws`;
      console.log("Connecting to WebSocket at:", wsUrl);
      
      wsRef.current = new WebSocket(wsUrl);
      
      wsRef.current.onopen = () => {
        console.log("WebSocket connected successfully");
        setShowError(false);
        wsRef.current?.send("start_stream");
        startFrameCapture();
      };
      
      wsRef.current.onmessage = (event) => {
        try {
          console.log("Received WebSocket message:", event.data);
          const data = JSON.parse(event.data);
          
          if (data.error) {
            console.error("Server error:", data.error);
            setDetectionMessage(data.error);
            setShowError(true);
            onVerificationComplete(false);
            return;
          }
          
          if (data.success === false) {
            console.log("Verification failed:", data.error);
            setDetectionMessage(data.error || "Verification failed");
            setShowError(true);
            onVerificationComplete(false);
            return;
          }

          if (data.success === true) {
            console.log("Female user verified");
            stopWebcam();
            setIsVerified(true);
            onVerificationComplete(true);
            return;
          }
        } catch (error) {
          console.error("Error processing WebSocket message:", error);
          setDetectionMessage("Error processing response. Please try again.");
          setShowError(true);
          onVerificationComplete(false);
        }
      };
      
      wsRef.current.onerror = (event) => {
        console.error("WebSocket error:", event);
        setDetectionMessage("Connection error. Please check your connection and try again.");
        setShowError(true);
        stopFrameCapture();
      };

      wsRef.current.onclose = (event) => {
        console.log("WebSocket closed with code:", event.code, "reason:", event.reason);
        if (!isVerified) {
          setDetectionMessage("Connection closed. Please try again.");
          setShowError(true);
          stopFrameCapture();
        }
      };
    } catch (error) {
      console.error("Error creating WebSocket:", error);
      setDetectionMessage("Could not establish connection. Please try again.");
      setShowError(true);
    }
  };

  const startFrameCapture = () => {
    if (frameIntervalRef.current) {
      clearInterval(frameIntervalRef.current);
    }
    frameIntervalRef.current = window.setInterval(sendFrame, 500);
  };

  const stopFrameCapture = () => {
    if (frameIntervalRef.current) {
      clearInterval(frameIntervalRef.current);
      frameIntervalRef.current = null;
    }
  };

  const sendFrame = () => {
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
      console.log("WebSocket not ready");
      return;
    }

    try {
      const canvas = canvasRef.current;
      const video = videoRef.current;
      
      if (!canvas || !video) {
        console.log("Canvas or video not ready");
        return;
      }
      
      const context = canvas.getContext('2d');
      if (!context) {
        console.log("Could not get canvas context");
        return;
      }
      
      // Draw the current video frame on the canvas
      context.drawImage(video, 0, 0, canvas.width, canvas.height);
      
      // Get the frame data as base64
      const frameData = canvas.toDataURL('image/jpeg', 0.8);
      
      // Send the frame data to the server
      wsRef.current.send(frameData);
    } catch (error) {
      console.error("Error sending frame:", error);
      setDetectionMessage("Error capturing video frame. Please try again.");
      setShowError(true);
    }
  };

  const handleRetry = () => {
    setShowError(false);
    setDetectionMessage('');
    connectWebSocket();
  };

  useEffect(() => {
    const initialize = async () => {
      try {
        await startWebcam();
        // Wait for webcam to be ready
        await new Promise(resolve => setTimeout(resolve, 1000));
        connectWebSocket();
      } catch (error) {
        console.error("Error initializing:", error);
        setDetectionMessage("Error initializing camera. Please try again.");
        setShowError(true);
      }
    };

    initialize();

    return () => {
      stopWebcam();
    };
  }, []);

  return (
    <Card className="p-6">
      <div className="relative">
        <video
          ref={videoRef}
          autoPlay
          playsInline
          muted
          className="w-full rounded-lg"
        />
        <canvas ref={canvasRef} style={{ display: 'none' }} width="640" height="480" />
        
        {isVerifying && !showError && (
          <div className="absolute inset-0 flex items-center justify-center bg-black/10">
            <div className="flex flex-col items-center gap-2 text-white">
              <Loader2 className="h-8 w-8 animate-spin" />
              <p className="text-lg font-medium">Verifying...</p>
            </div>
          </div>
        )}
      </div>

      <div className="mt-4 space-y-4">
        {showError && (
          <div className="text-center text-red-500">
            <p>{detectionMessage}</p>
            <Button
              variant="outline"
              className="mt-2"
              onClick={handleRetry}
            >
              <RefreshCw className="w-4 h-4 mr-2" />
              Try Again
            </Button>
          </div>
        )}

        <div className="flex justify-between">
          <Button variant="outline" onClick={onCancel}>Cancel</Button>
        </div>
      </div>
    </Card>
  );
};

export default WebcamVerification;
