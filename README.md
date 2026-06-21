# IntelliFlow: AI-Powered Traffic Violation Detection & Enforcement Platform

IntelliFlow is an advanced, industry-grade traffic violation detection and automated enforcement platform built to scale urban law compliance. It features a high-performance computer vision pipeline (YOLOv8 + PyTorch) designed to automatically process traffic images, localize vehicles, classify traffic infractions, extract license plates using OCR, and log annotated evidence into a relational database. It leverages a local Statutory RAG (Retrieval-Augmented Generation) Engine to link violations directly to penal codes and compile court-ready warning warnings. 

Additionally, the platform includes adaptive traffic optimization policies (decentralized Max-Pressure control and A* heap-based preemption) as future scale-up extensions.

---

## 🚀 Core Platform Architecture

```
                 [ CAMERA FEED / SURVEILLANCE IMAGE ]
                                  │
                                  ▼
                     [ CLAHE & Bilateral Preprocessor ]
                                  │
                                  ▼
                   [ YOLOv8 Bounding Box Detector ]
                                  │
         ┌────────────────────────┼────────────────────────┐
         ▼                        ▼                        ▼
 [Helmet Compliance]     [Seatbelt Compliance]     [Trajectory Tracker]
 (Secondary CNN Class)   (Chest Pattern Scanner)   (Wrong-Side Trap)
         │                        │                        │
         └────────────────────────┼────────────────────────┘
                                  ▼
                     [ License Plate Crop Node ]
                                  │
                                  ▼
                     [ Alphanumeric OCR Engine ]
                                  │
                                  ▼
                  [ SQLite Archive & RAG Linker ]
                                  │
                                  ▼
                  [ Interactive Analytics Console ]
```

---

## 🌟 Key Features

### 1. Multi-Class Traffic Violation Scanners
IntelliFlow implements specialized real-time computer vision classifiers for critical infractions:
* **Helmet Non-Compliance**: YOLOv8 localizes 2-wheelers. A secondary head-crop classifier evaluates whether the rider is wearing a helmet (Target Precision >96%).
* **Seatbelt Non-Compliance**: Analyzes car windshield coordinates to segment the driver chest region, verifying diagonal belt patterns.
* **Triple Riding Classifier**: Evaluates passenger density overlaps within motorcycle bounding boxes, triggering alerts for counts > 2.
* **Wrong-Side Driving Trap**: Tracks frame-by-frame vehicle center trajectories to compare vector direction angles against designated lane headings.
* **Red-Light & Stop-Line Violations**: Intersects vehicle bounding-boxes with crosswalk polygons during signal stop phases.
* **Illegal Parking Monitor**: Computes pixel-level stationary timers for vehicles parked inside restricted tow-away zones.

### 2. High-Precision License Plate OCR Engine
* **Localization**: Runs a dedicated sub-detector on vehicle bounding boxes to crop the license plate zone.
* **Text Extraction**: Uses OCR models optimized for alphanumeric plate characters (supporting standard, commercial, and green EV plate styles).
* **Noise Mitigation**: Applies contrast-limited adaptive histogram equalization (CLAHE), deskewing (bilinear transformation), and sharpening to recover text from dirty or angled plates.
* **Confidence Gating**: Flags captures falling below a 90% confidence score for manual review to eliminate false enforcement actions.

### 3. Court-Ready Evidence Generation & SQLite Archive
* **Annotated Frame Output**: Automatically saves high-definition evidence photos overlaying infraction labels, bounding boxes, and plate crops.
* **Relational SQLite Schema**: Organizes records with fields for timestamp, location, plate text, infraction type, class confidence, and citation text.
* **Searchable Registry**: The dashboard presents a searchable records ledger where entries can be filtered by plate or violation type.

### 4. Local Statutory RAG Citation Engine
* **Legal Knowledge-Base**: Integrates codifications of the **Indian Motor Vehicles Act (1988/2019)** and **Central Motor Vehicles Rules (1989)**.
* **Dynamic Synthesis**: Translates database logs into official e-challan legal documents. For example, helmet infractions retrieve Section 129, appending legal penalties (INR 1,000 fine + 3-month license suspension) and scientific collision statistics to the notice.
* **Interactive Modal View**: Clicking any row in the violations panel renders the fully synthesized legal notice overlay.

### 5. Interactive Geographic Analytics Dashboard
* **Leaflet.js mapping**: Embeds an interactive layout styled with **CartoDB Dark Matter** tiles, flashing warning rings over geographic coordinates during active violations.
* **Real-time Trend Charting**: Displays spatial-temporal infraction heatmaps, violation comparison bar graphs, and vehicle distribution charts.

### 6. Future Scale-Up Extensions (Smart Signals & Emergency Routing)
* **Decentralized Max-Pressure Control**: Local signal cycles optimize junction throughput dynamically based on incoming queue pressures.
* **A* Min-Heap Preemption**: Spawns green-light preemption wave corridors ahead of emergency vehicles (ambulances/fire engines) along dynamic shortest paths.

---

## 🛠 Technology Stack

* **Computer Vision**: PyTorch, YOLOv8, OpenCV (CLAHE, Bilateral filtering, HSV siren tracking)
* **Backend Framework**: FastAPI, Uvicorn, SQLite3
* **Communication**: WebSockets (low-latency JPEG and metadata streaming)
* **Front-end Console**: Leaflet.js, HTML5 Canvas, CSS3 (Glassmorphic dark UI), Javascript (Vanilla)

---

## 📂 Project Directory Structure

```
Flipkart-gridlock-solver/
│
├── gridlock-solver/                   # Core Codebase
│   ├── app.py                         # FastAPI + YOLOv8 + SQLite Backend
│   ├── index.html                     # Frontend Rebranded Dashboard UI
│   ├── style.css                      # Modern dark slate glassmorphism stylesheet
│   ├── cv_feed.js                     # CCTV stream renderer & WebSocket consumer
│   ├── dashboard.js                   # UI controllers, charts, and metrics aggregator
│   ├── simulation.js                  # Graph simulation engine & Leaflet Map integration
│   ├── algorithms.js                  # A* Search, Min-Heap, Max-Pressure Control
│   └── requirements.txt               # Backend Python dependencies list
```

---

## ⚙️ Getting Started

### Prerequisites
* Python 3.10 or higher.
* Web browser with internet access (to fetch Leaflet OSM map tiles).

### Installation & Launch
1. Clone this repository and navigate into it:
   ```cmd
   git clone <your-repo-url>
   cd Flipkart-gridlock-solver
   ```
2. Install Python dependencies:
   ```cmd
   pip install -r gridlock-solver/requirements.txt
   ```
3. Run the system using the batch file or manual command:
   * **Option A: Launcher Script**: Double-click `run.bat` or run:
     ```cmd
     .\run.bat
     ```
   * **Option B: Manual Command**:
     ```cmd
     cd gridlock-solver
     python app.py
     ```

Once started, open your browser and go to:
👉 **[http://localhost:8000/](http://localhost:8000/)**

---

## 📊 Evaluation Metrics
The computer vision pipeline is evaluated using standard machine learning metrics:
* **Detection accuracy & Localization mAP**: Target bounding box localization accuracy of $mAP@0.5 > 93\%$.
* **Classification Precision/Recall**: Targets $>94\%$ Precision across helmet and seatbelt streams to prevent false citations.
* **Inference Latency**: Target edge frame processing latency under 8ms to enable real-time tracking.
