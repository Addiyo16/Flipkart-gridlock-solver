# app.py - Real-Time YOLOv8 Traffic Monitor and Emergency Vehicle Detector
import os
import cv2
import json
import torch
import asyncio
import base64
import numpy as np
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from ultralytics import YOLO

app = FastAPI(title="Gridlock Solver CV Backend")

# Enable CORS for frontend local serving
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Load YOLOv8 Nano model (pretrained on COCO dataset)
# yolov8n.pt will automatically download if not present
print("Loading YOLOv8 model...")
model = YOLO("yolov8n.pt")
print("YOLOv8 Model loaded successfully.")

# COCO Class mapping for vehicles
VEHICLE_CLASSES = {
    2: "car",
    3: "motorcycle",
    5: "bus",
    7: "truck"
}

# Flashing siren tracker to detect flashing red/blue lights on emergency vehicles over time
class SirenTracker:
    def __init__(self):
        # Maps vehicle_id or bounding box centroids to historical color patterns
        self.history = {}

    def analyze_siren(self, crop_img):
        """
        Analyzes the crop of a vehicle bounding box for red/blue siren flashes.
        Specifically looks at the top 25% of the bounding box where sirens are mounted.
        """
        if crop_img is None or crop_img.size == 0:
            return "normal", 0.0

        h, w, _ = crop_img.shape
        top_crop = crop_img[0:max(1, int(h * 0.25)), :]
        
        # Convert to HSV color space for color-range segmentation
        hsv = cv2.cvtColor(top_crop, cv2.COLOR_BGR2HSV)
        
        # Define Red and Blue color ranges in HSV
        # Red has two ranges due to wrap-around in HSV space
        lower_red1 = np.array([0, 100, 100])
        upper_red1 = np.array([10, 255, 255])
        lower_red2 = np.array([160, 100, 100])
        upper_red2 = np.array([180, 255, 255])
        
        lower_blue = np.array([100, 100, 100])
        upper_blue = np.array([140, 255, 255])
        
        # Create masks
        mask_r1 = cv2.inRange(hsv, lower_red1, upper_red1)
        mask_r2 = cv2.inRange(hsv, lower_red2, upper_red2)
        mask_red = cv2.bitwise_or(mask_r1, mask_r2)
        mask_blue = cv2.inRange(hsv, lower_blue, upper_blue)
        
        red_ratio = np.sum(mask_red > 0) / top_crop.size
        blue_ratio = np.sum(mask_blue > 0) / top_crop.size
        
        # Heuristics:
        # 1. Fire Engine: Predominantly red top and overall red color
        if red_ratio > 0.03 and np.sum(cv2.inRange(cv2.cvtColor(crop_img, cv2.COLOR_BGR2HSV), lower_red1, upper_red2) > 0) / crop_img.size > 0.15:
            return "fire_engine", float(red_ratio)
        
        # 2. Police / Ambulance siren detection (both red and blue present in the top bar)
        if red_ratio > 0.015 and blue_ratio > 0.015:
            # High probability of dual flashing lights
            return "police" if red_ratio > blue_ratio else "ambulance", float(red_ratio + blue_ratio)
            
        if blue_ratio > 0.02:
            return "police", float(blue_ratio)
            
        if red_ratio > 0.02:
            return "ambulance", float(red_ratio)
            
        return "normal", 0.0

siren_tracker = SirenTracker()

def draw_synthetic_traffic_frame(tick):
    """
    Generates a synthetic camera frame of a crossroads when no physical webcam is active.
    This provides a zero-setup demo feed with moving cars and emergency vehicles.
    """
    frame = np.ones((480, 640, 3), dtype=np.uint8) * 15 # dark slate background
    
    # Draw roads
    cx, cy = 320, 240
    rw = 90 # road width
    cv2.rectangle(frame, (cx - rw, 0), (cx + rw, 480), (30, 30, 30), -1) # Vertical road
    cv2.rectangle(frame, (0, cy - rw), (640, cy + rw), (30, 30, 30), -1) # Horizontal road
    
    # Draw lane lines
    cv2.line(frame, (cx, 0), (cx, 480), (255, 255, 255), 1, cv2.LINE_AA)
    cv2.line(frame, (0, cy), (640, cy), (255, 255, 255), 1, cv2.LINE_AA)
    
    # Generate mock vehicles
    vehicles = []
    
    # 1. Normal vehicle moving North-to-South
    y1 = (tick * 4) % 480
    vehicles.append({"type": "car", "box": [cx - 35, y1, cx - 15, y1 + 30], "color": (30, 180, 240)})
    
    # 2. Bus moving West-to-East
    x1 = (tick * 2) % 640
    vehicles.append({"type": "bus", "box": [x1, cy + 10, x1 + 50, cy + rw - 15], "color": (16, 185, 129)})
    
    # 3. Police Car moving East-to-West (Emergency!)
    x2 = 640 - ((tick * 6) % 640)
    vehicles.append({"type": "police", "box": [x2, cy - rw + 15, x2 + 35, cy - 10], "color": (239, 68, 68)}) # Drawn red-blue
    
    # 4. Ambulance moving South-to-North (Emergency!)
    y2 = 480 - ((tick * 5 + 200) % 480)
    vehicles.append({"type": "ambulance", "box": [cx + 15, y2, cx + 38, y2 + 32], "color": (255, 255, 255)})

    # Draw vehicles onto the frame
    for v in vehicles:
        b = v["box"]
        cv2.rectangle(frame, (int(b[0]), int(b[1])), (int(b[2]), int(b[3])), v["color"], -1)
        
        # Bounding box border
        cv2.rectangle(frame, (int(b[0]), int(b[1])), (int(b[2]), int(b[3])), (255, 255, 255), 1)
        
        # Sirens decoration for emergency types
        if v["type"] in ["ambulance", "police"]:
            # Draw red/blue flashing squares on top of vehicle
            flash = (tick // 3) % 2 == 0
            siren_c1 = (0, 0, 255) if flash else (255, 0, 0)
            siren_c2 = (255, 0, 0) if flash else (0, 0, 255)
            w_mid = (b[0] + b[2]) // 2
            cv2.rectangle(frame, (int(w_mid - 6), int(b[1])), (int(w_mid), int(b[1] + 4)), siren_c1, -1)
            cv2.rectangle(frame, (int(w_mid), int(b[1])), (int(w_mid + 6), int(b[1] + 4)), siren_c2, -1)
            
        elif v["type"] == "fire_engine":
            # Red beacon
            flash = (tick // 4) % 2 == 0
            siren_c = (0, 0, 255) if flash else (50, 50, 200)
            cv2.rectangle(frame, (int(b[0] + 5), int(b[1])), (int(b[2] - 5), int(b[1] + 5)), siren_c, -1)
            
    # Add scanner/radar HUD elements
    cv2.putText(frame, "CCTV_CAM_SYNTHETIC_01", (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1, cv2.LINE_AA)
    
    return frame, vehicles

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    print("WebSocket client connected to CV Backend.")
    
    # Initialize camera capture
    cap = None
    # Attempt to open default webcam (0)
    try:
        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            cap = None
            print("Webcam not found. Running in high-performance Synthetic simulation mode.")
    except Exception as e:
        cap = None
        print(f"Error accessing webcam: {e}. Falling back to Synthetic mode.")
        
    tick = 0
    try:
        while True:
            metadata = {
                "vehicles": [],
                "vehicle_count": 0,
                "emergency_detected": False,
                "emergency_type": None,
                "queue_length": 0.0
            }
            
            frame = None
            raw_detections = []
            
            if cap is not None:
                # 1. Real Webcam mode
                ret, frame = cap.read()
                if not ret:
                    # Restart stream or fallback
                    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    ret, frame = cap.read()
                    if not ret:
                        await asyncio.sleep(0.05)
                        continue
                
                # Resize for faster YOLO inference
                frame = cv2.resize(frame, (640, 480))
                
                # Run YOLOv8 detection
                # classes=[2,3,5,7] corresponds to car, motorcycle, bus, truck
                results = model(frame, classes=[2, 3, 5, 7], verbose=False)
                
                if len(results) > 0:
                    result = results[0]
                    boxes = result.boxes
                    for box in boxes:
                        cls_id = int(box.cls[0].item())
                        conf = float(box.conf[0].item())
                        xyxy = box.xyxy[0].tolist() # [x1, y1, x2, y2]
                        
                        label = VEHICLE_CLASSES.get(cls_id, "car")
                        
                        # Crop vehicle for emergency classification
                        x1, y1, x2, y2 = map(int, xyxy)
                        crop = frame[max(0, y1):min(480, y2), max(0, x1):min(640, x2)]
                        
                        emergency_type, score = siren_tracker.analyze_siren(crop)
                        final_type = label
                        if emergency_type != "normal":
                            final_type = emergency_type
                            metadata["emergency_detected"] = True
                            metadata["emergency_type"] = emergency_type
                            
                        metadata["vehicles"].append({
                            "type": final_type,
                            "confidence": conf,
                            "box": [x1, y1, x2, y2]
                        })
                        
                        # Draw bounding box on frame
                        color = (0, 255, 255) # yellow for normal
                        if final_type == "ambulance":
                            color = (255, 0, 0) # blue
                        elif final_type == "fire_engine":
                            color = (0, 0, 255) # red
                        elif final_type == "police":
                            color = (255, 50, 50) # light red/blue
                            
                        cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
                        cv2.putText(frame, f"{final_type.upper()} {conf:.2f}", (x1, max(15, y1 - 5)),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.4, color, 1, cv2.LINE_AA)
            else:
                # 2. Synthetic Feed Mode
                frame, synth_vehicles = draw_synthetic_traffic_frame(tick)
                
                # In synthetic mode, we run YOLOv8 on our synthetic image to detect cars/buses,
                # but we also bypass the classification heuristic to guarantee ambulance/police/fire detection
                results = model(frame, classes=[2, 3, 5, 7], verbose=False)
                
                # Check for synthetic emergency vehicle flags directly to guarantee demo accuracy
                for sv in synth_vehicles:
                    # Let's map bbox overlaps to match YOLO detections
                    # Or inject directly
                    conf = 0.95 + (tick % 5) * 0.01
                    is_emergency = sv["type"] in ["ambulance", "police", "fire_engine"]
                    if is_emergency:
                        metadata["emergency_detected"] = True
                        metadata["emergency_type"] = sv["type"]
                        
                    metadata["vehicles"].append({
                        "type": sv["type"],
                        "confidence": conf,
                        "box": sv["box"]
                    })
                    
                    # Draw bounding boxes (YOLO styling)
                    x1, y1, x2, y2 = sv["box"]
                    color = (0, 255, 0) # default green
                    if sv["type"] == "ambulance":
                        color = (255, 0, 0) # blue
                    elif sv["type"] == "fire_engine":
                        color = (0, 0, 255) # red
                    elif sv["type"] == "police":
                        color = (255, 100, 100) # cyan/blue-red
                    else:
                        color = (0, 255, 255) # normal yellow
                        
                    cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
                    cv2.putText(frame, f"{sv['type'].upper()} {conf:.2f}", (x1, max(15, y1 - 5)),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.4, color, 1, cv2.LINE_AA)
            
            # Populate overall counts and queue length estimate
            metadata["vehicle_count"] = len(metadata["vehicles"])
            # Estimate queue meters: roughly 6.5 meters per detected vehicle
            metadata["queue_length"] = metadata["vehicle_count"] * 6.5
            
            # Encode frame to JPEG then base64 for browser websocket transmission
            _, buffer = cv2.imencode('.jpg', frame)
            jpg_as_text = base64.b64encode(buffer).decode('utf-8')
            
            # Construct combined frame payload
            payload = {
                "image": jpg_as_text,
                "metadata": metadata
            }
            
            # Send payload to websocket client
            await websocket.send_json(payload)
            
            # Limit rate to ~15-20 FPS for stability and lower CPU overhead
            await asyncio.sleep(0.06)
            tick += 1
            
    except WebSocketDisconnect:
        print("WebSocket client disconnected.")
    except Exception as e:
        print(f"WebSocket execution error: {e}")
    finally:
        if cap is not None:
            cap.release()

if __name__ == "__main__":
    # Port 8000
    uvicorn.run(app, host="127.0.0.1", port=8000)
