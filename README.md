# Intelligent Traffic Management System (ITMS) — Gridlock Solver

Intelligent Traffic Management System (ITMS) built for the **Flipkart Gridlock Hackathon**. It features a **Hybrid Edge-Cloud Architecture** that combines offline Machine Learning demand models with real-time Computer Vision (YOLOv8 + PyTorch), decentralized Max-Pressure signal controllers, dynamic A* routing, automated law enforcement, and emergency rescue preemption.

---

## 🚀 Key Features

1. **Covariate-Shift Demand Prediction (ML)**: A Log-Ratio Ensemble (LightGBM, XGBoost, CatBoost) that predicts relative spatial-temporal demand multipliers against a sliding baseline to resolve scale shifts.
2. **Decentralized Max-Pressure Signal Control**: A localized, collision-free control algorithm that maximizes junction throughput based on queue pressure differences between incoming and outgoing lanes.
3. **Smart Adaptive Timer (Queue Extension)**: A dynamic local signal policy that extends green light durations proportionally to vehicle queue size ($T_{\text{green}} = \min(T_{\text{max}}, T_{\text{min}} + \eta \cdot Q)$) to eliminate empty-lane green starvation.
4. **Emergency Green-Wave Preemption**: Captures emergency vehicle shapes (YOLOv8) and flash strobes (temporal FFT) to arbitrate multi-emergency conflicts and open A*-calculated clearance corridors.
5. **E-Enforcement & Traffic Law Monitors**: Automatically detects Red Light Violations (RLVD) and Speeding Violations (SVD), cropping license plates for automated fine logs.
6. **Automatic Accident Detection & Rescue Dispatch**: Detects traffic collisions using anomalous deceleration vectors and automatically routes a rescue ambulance to clear the gridlock.
7. **System Resilience**: Incorporates edge-compute limits, capacity-based frame throttling, and timeout fallbacks to prevent software crashes under heavy congestion.

---

## 🛠 Technology Stack

### 1. Deep Learning & Computer Vision (Edge AI)
* **PyTorch (v2.0+)**: Core runtime engine for running the deep neural network forward pass (inference).
* **YOLOv8 (Ultralytics)**: Object detection model optimized for real-time vehicle classification (cars, buses, trucks, bikes) and emergency vehicle detection.
* **OpenCV (v4.7+)**: Video capture, frame resizing, colorspace conversions (BGR to HSV), crop overlays, and red/blue strobe frequency color segmentation.

### 2. Backend API & Stream Serving
* **FastAPI**: High-performance, asynchronous web framework for streaming video feeds and telemetry.
* **Uvicorn**: Asynchronous ASGI web server hosting the FastAPI backend.
* **WebSockets**: Full-duplex communication protocol for low-latency JSON metadata and JPEG streaming to the browser dashboard.

### 3. Machine Learning & Forecasting
* **LightGBM / XGBoost / CatBoost**: Gradient-boosted decision trees forming the Log-Ratio ensemble.
* **Scikit-learn**: Validation split mapping (KFold), label encoding, and validation metric evaluations.
* **Pandas & NumPy**: Data manipulation, sliding baseline calculations, and spatial coordinate decoding.

### 4. Interactive Simulation & Front-end Dashboard
* **HTML5 Canvas**: Low-latency rendering of road network graphs, moving vehicle particles, and CCTV feeds.
* **CSS3 (Vanilla)**: Glassmorphism layout design, responsive flex grids, and dark-theme aesthetics.
* **JavaScript (Vanilla)**: Core simulation state-machine, min-heap prioritized Dijkstra/A* routing, and max-pressure control loops.
* **Lucide Icons**: SVG icon sets for modern interface designs.

---

## 📂 Project Directory Structure

```
Flipkart-gridlock-solver/
│
├── gridlock-solver/                   # Real-Time Simulation & CV Backend
│   ├── app.py                         # FastAPI + YOLOv8 + Siren Detector Backend
│   ├── algorithms.js                  # A* Search, Min-Heap, Max-Pressure Control
│   ├── simulation.js                  # Graph simulation engine, Accidents, & Violations
│   ├── cv_feed.js                     # CCTV stream renderer & WebSocket consumer
│   ├── dashboard.js                   # UI controllers, charts, and metrics aggregator
│   ├── index.html                     # Frontend dashboard layout
│   ├── style.css                      # Modern dark slate glassmorphism stylesheet
│   └── requirements.txt               # Backend Python dependencies list
│
├── traffic-prediction/                # Machine Learning Demand Forecasting
│   ├── train.py                       # Ensemble training and validation scripts
│   ├── traffic_prediction.ipynb       # Jupyter exploratory data analysis
│   └── approach.txt                   # Hackathon log-ratio formulation summary
│
├── run.bat                            # Single-click Windows execution launcher
└── README.md                          # Industry-oriented documentation
```

---

## ⚙️ Getting Started

### Prerequisites
* Python 3.10 or higher installed.
* PowerShell or cmd with execution permissions.

### Installation
1. Clone this repository and navigate into it:
   ```cmd
   git clone <your-repo-url>
   cd Flipkart-gridlock-solver
   ```
2. Install dependencies:
   ```cmd
   pip install -r gridlock-solver/requirements.txt
   ```

### Running the System
You can execute the entire project (Python backend + web interface) with a **single command** or by double-clicking the launcher file:

* **Command Line**:
  ```cmd
  .\run.bat
  ```
* **GUI**: Double-click `run.bat` in Windows File Explorer.

---

## 📈 System Evaluation & Metrics

The system tracks several key performance indicators in the dashboard:
* **Average Waiting Time**: Tracks reductions (typically >40% vs. fixed-timer baselines).
* **Clearing Throughput**: Measured in vehicles cleared per minute (+18-25% improvement).
* **Carbon Emissions Saved**: Calculates dynamic CO2 offsets based on reduced vehicle idling times.
* **Graph Search Space**: A* search expands fewer nodes ($\approx 1.5$/6 nodes) compared to brute-force Dijkstra (6/6 nodes).
