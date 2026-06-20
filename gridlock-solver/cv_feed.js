// OpenCV CCTV camera feed simulator / Live YOLOv8 Backend WebSocket Consumer

const cctvCanvas = document.getElementById('cctv-canvas');
const cctvCtx = cctvCanvas.getContext('2d');

let isEmergencyAlertActive = false;

// WebSocket Connection Variables
let ws = null;
let backendConnected = false;
let latestBackendFrame = null;
let latestBackendMetadata = null;

function setupCctvCanvas() {
    cctvCanvas.width = cctvCanvas.parentElement.clientWidth;
    cctvCanvas.height = cctvCanvas.parentElement.clientHeight;
}

function connectWebSocket() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsHost = window.location.host || 'localhost:8000';
    ws = new WebSocket(`${protocol}//${wsHost}/ws`);
    
    ws.onopen = () => {
        console.log("Successfully connected to YOLOv8 CV Backend");
        backendConnected = true;
        updateConnectionBadge(true);
    };
    
    ws.onmessage = (event) => {
        try {
            const data = JSON.parse(event.data);
            if (data.image) {
                const img = new Image();
                img.src = 'data:image/jpeg;base64,' + data.image;
                img.onload = () => {
                    latestBackendFrame = img;
                };
            }
            if (data.metadata) {
                latestBackendMetadata = data.metadata;
            }
        } catch (e) {
            console.error("Error parsing WebSocket frame: ", e);
        }
    };
    
    ws.onclose = () => {
        console.log("Disconnected from YOLOv8 CV Backend. Reconnecting in 5s...");
        backendConnected = false;
        latestBackendFrame = null;
        latestBackendMetadata = null;
        updateConnectionBadge(false);
        setTimeout(connectWebSocket, 5000);
    };
    
    ws.onerror = (err) => {
        backendConnected = false;
        updateConnectionBadge(false);
    };
}

function updateConnectionBadge(connected) {
    const badge = document.getElementById('connection-status-badge');
    if (badge) {
        if (connected) {
            badge.innerText = "YOLOv8 Live";
            badge.className = "live-badge";
            badge.style.background = "#10B981"; // green
        } else {
            badge.innerText = "CV Offline (Sim Mode)";
            badge.className = "live-badge";
            badge.style.background = "#4B5563"; // gray-muted
        }
    }
}

// Initialize Connection
connectWebSocket();

// Update the CCTV simulation and UI panels
function updateCVFeed() {
    setupCctvCanvas();
    
    const node = window.getSelectedNode();
    if (!node) {
        requestAnimationFrame(updateCVFeed);
        return;
    }

    // 1. --- LIVE BACKEND MODE ---
    if (backendConnected && latestBackendFrame) {
        // Draw the frame streamed from the Python YOLOv8 detector
        cctvCtx.drawImage(latestBackendFrame, 0, 0, cctvCanvas.width, cctvCanvas.height);
        
        // Update Panel stats from actual detections
        if (latestBackendMetadata) {
            const m = latestBackendMetadata;
            document.getElementById('cv-vehicle-count').innerText = m.vehicle_count;
            document.getElementById('cv-queue-length').innerText = `${m.queue_length.toFixed(0)} m`;
            
            // Speed and density estimates based on actual counts
            const speedVal = m.emergency_detected ? 25 : Math.max(12, 45 - m.vehicle_count * 1.8);
            document.getElementById('cv-avg-speed').innerText = `${Math.floor(speedVal)} km/h`;
            
            const densityVal = Math.min(100, Math.floor((m.vehicle_count / 16) * 100));
            const densityElement = document.getElementById('cv-density');
            densityElement.innerText = `${densityVal}%`;
            if (densityVal < 40) {
                densityElement.style.color = 'var(--traffic-green)';
            } else if (densityVal < 75) {
                densityElement.style.color = 'var(--traffic-amber)';
            } else {
                densityElement.style.color = 'var(--traffic-red)';
            }
            
            // Emergency Alert Banner Activation
            const alertBanner = document.getElementById('emergency-alert-banner');
            const alertDesc = document.getElementById('emergency-alert-desc');
            if (m.emergency_detected && m.emergency_type) {
                alertBanner.classList.remove('hidden');
                alertDesc.innerText = `YOLOv8 ACTIVE: Detected approaching ${m.emergency_type.toUpperCase()} at ${node.name}. Routing priority cleared!`;
                isEmergencyAlertActive = true;
                
                // Inject emergency preemption immediately in the simulation node
                node.emergencyOverride = true;
                if (node.incomingEdges.length > 0 && node.emergencyIncomingEdge === null) {
                    node.emergencyIncomingEdge = node.incomingEdges[0];
                }
            } else {
                alertBanner.classList.add('hidden');
                isEmergencyAlertActive = false;
            }
        }
        
        // HUD text overlays
        cctvCtx.fillStyle = 'rgba(0,0,0,0.6)';
        cctvCtx.fillRect(10, cctvCanvas.height - 35, cctvCanvas.width - 20, 25);
        cctvCtx.fillStyle = '#FFFFFF';
        cctvCtx.font = '9px monospace';
        cctvCtx.textAlign = 'left';
        cctvCtx.fillText(`JUNC: ${node.name.toUpperCase()}  |  BACKEND: YOLOv8  |  STATUS: CONNECTED`, 20, cctvCanvas.height - 18);
        
        // Visual Scan Lines
        cctvCtx.strokeStyle = 'rgba(255, 255, 255, 0.015)';
        cctvCtx.lineWidth = 1;
        for (let i = 0; i < cctvCanvas.height; i += 4) {
            cctvCtx.beginPath();
            cctvCtx.moveTo(0, i);
            cctvCtx.lineTo(cctvCanvas.width, i);
            cctvCtx.stroke();
        }
        
        requestAnimationFrame(updateCVFeed);
        return;
    }

    // 2. --- SIMULATION FALLBACK MODE ---
    // Clear Canvas
    cctvCtx.fillStyle = '#060810';
    cctvCtx.fillRect(0, 0, cctvCanvas.width, cctvCanvas.height);

    // Draw grid overlay for technical camera style
    cctvCtx.strokeStyle = 'rgba(255, 255, 255, 0.02)';
    cctvCtx.lineWidth = 1;
    const spacing = 30;
    for (let x = 0; x < cctvCanvas.width; x += spacing) {
        cctvCtx.beginPath();
        cctvCtx.moveTo(x, 0);
        cctvCtx.lineTo(x, cctvCanvas.height);
        cctvCtx.stroke();
    }
    for (let y = 0; y < cctvCanvas.height; y += spacing) {
        cctvCtx.beginPath();
        cctvCtx.moveTo(0, y);
        cctvCtx.lineTo(cctvCanvas.width, y);
        cctvCtx.stroke();
    }

    // Render lanes in CCTV View
    const centerX = cctvCanvas.width / 2;
    const centerY = cctvCanvas.height / 2;
    const laneWidth = 45;

    cctvCtx.fillStyle = '#111827';
    cctvCtx.fillRect(centerX - laneWidth, 0, laneWidth * 2, cctvCanvas.height);
    cctvCtx.fillRect(0, centerY - laneWidth, cctvCanvas.width, laneWidth * 2);

    // Draw lane dividers
    cctvCtx.strokeStyle = 'rgba(255, 255, 255, 0.2)';
    cctvCtx.lineWidth = 1;
    cctvCtx.setLineDash([5, 10]);
    cctvCtx.beginPath();
    cctvCtx.moveTo(centerX, 0);
    cctvCtx.lineTo(centerX, cctvCanvas.height);
    cctvCtx.stroke();
    cctvCtx.beginPath();
    cctvCtx.moveTo(0, centerY);
    cctvCtx.lineTo(cctvCanvas.width, centerY);
    cctvCtx.stroke();
    cctvCtx.setLineDash([]);

    // Draw CCTV Region of Interest (ROI) boundaries
    cctvCtx.strokeStyle = 'rgba(6, 182, 212, 0.2)';
    cctvCtx.lineWidth = 1.5;
    cctvCtx.strokeRect(20, 20, cctvCanvas.width - 40, cctvCanvas.height - 40);
    
    // Draw Corner Reticles
    const reticleLen = 15;
    cctvCtx.strokeStyle = 'var(--accent-cyan)';
    cctvCtx.lineWidth = 2.5;

    // Top-Left
    cctvCtx.beginPath();
    cctvCtx.moveTo(20, 20 + reticleLen); cctvCtx.lineTo(20, 20); cctvCtx.lineTo(20 + reticleLen, 20);
    cctvCtx.stroke();
    // Top-Right
    cctvCtx.beginPath();
    cctvCtx.moveTo(cctvCanvas.width - 20, 20 + reticleLen); cctvCtx.lineTo(cctvCanvas.width - 20, 20); cctvCtx.lineTo(cctvCanvas.width - 20 - reticleLen, 20);
    cctvCtx.stroke();
    // Bottom-Left
    cctvCtx.beginPath();
    cctvCtx.moveTo(20, cctvCanvas.height - 20 - reticleLen); cctvCtx.lineTo(20, cctvCanvas.height - 20); cctvCtx.lineTo(20 + reticleLen, cctvCanvas.height - 20);
    cctvCtx.stroke();
    // Bottom-Right
    cctvCtx.beginPath();
    cctvCtx.moveTo(cctvCanvas.width - 20, cctvCanvas.height - 20 - reticleLen); cctvCtx.lineTo(cctvCanvas.width - 20, cctvCanvas.height - 20); cctvCtx.lineTo(cctvCanvas.width - 20 - reticleLen, cctvCanvas.height - 20);
    cctvCtx.stroke();

    // Map incoming vehicles to this node
    const incomingVehicles = window.vehicles.filter(v => {
        const edge = window.edges.find(e => e.id === v.currentEdgeId);
        return edge && edge.endNode.id === node.id;
    });

    let detectedCount = 0;
    let maxQueueLength = 0;
    let emergencyDetected = false;
    let emergencyIncomingEdge = null;
    let emergencyVehicleType = null;
    let speedsSum = 0;

    incomingVehicles.forEach((vehicle, idx) => {
        const edge = window.edges.find(e => e.id === vehicle.currentEdgeId);
        if (!edge) return;

        const progress = vehicle.progress;
        const dx = node.x - edge.startNode.x;
        const dy = node.y - edge.startNode.y;
        
        let vehicleX = centerX;
        let vehicleY = centerY;
        const offset = (vehicle.id % 2 === 0 ? 1 : -1) * 20;
        const displayDist = (1.0 - progress) * 200;

        if (Math.abs(dx) > Math.abs(dy)) {
            if (dx > 0) {
                vehicleX = centerX - displayDist;
                vehicleY = centerY + offset;
            } else {
                vehicleX = centerX + displayDist;
                vehicleY = centerY + offset;
            }
        } else {
            if (dy > 0) {
                vehicleX = centerX + offset;
                vehicleY = centerY - displayDist;
            } else {
                vehicleX = centerX + offset;
                vehicleY = centerY + displayDist;
            }
        }

        // Bounding Box overlays
        if (vehicleX > 20 && vehicleX < cctvCanvas.width - 20 && vehicleY > 20 && vehicleY < cctvCanvas.height - 20) {
            detectedCount++;
            speedsSum += vehicle.speed;
            
            const isEV = ['ambulance', 'police', 'fire_engine'].includes(vehicle.type);
            if (isEV) {
                emergencyDetected = true;
                emergencyIncomingEdge = edge.id;
                emergencyVehicleType = vehicle.type;
            }

            const boxW = vehicle.type === 'bus' || vehicle.type === 'fire_engine' ? 24 : 18;
            const boxH = vehicle.type === 'bus' || vehicle.type === 'fire_engine' ? 36 : 24;

            cctvCtx.strokeStyle = isEV ? '#EF4444' : 'var(--accent-cyan)';
            cctvCtx.lineWidth = 1.5;
            
            // Blinking border for active emergency
            if (isEV && Math.floor(Date.now() / 200) % 2 === 0) {
                cctvCtx.strokeStyle = '#3B82F6';
            }

            cctvCtx.strokeRect(vehicleX - boxW/2, vehicleY - boxH/2, boxW, boxH);

            // Bounding Box Label
            cctvCtx.fillStyle = cctvCtx.strokeStyle;
            cctvCtx.font = 'bold 8px monospace';
            const confidence = Math.floor(88 + (vehicle.id % 12));
            const labelText = `${vehicle.type.toUpperCase()} [${confidence}%]`;
            cctvCtx.fillText(labelText, vehicleX - boxW/2, vehicleY - boxH/2 - 4);

            // Centroid
            cctvCtx.fillStyle = '#EF4444';
            cctvCtx.beginPath();
            cctvCtx.arc(vehicleX, vehicleY, 2, 0, Math.PI * 2);
            cctvCtx.fill();
        }
    });

    const alertBanner = document.getElementById('emergency-alert-banner');
    const alertDesc = document.getElementById('emergency-alert-desc');
    if (emergencyDetected) {
        alertBanner.classList.remove('hidden');
        alertDesc.innerText = `EMERGENCY SIREN WARNING: ${emergencyVehicleType.toUpperCase()} detected at ${node.name}. Routing preemption coordinated.`;
        isEmergencyAlertActive = true;
    } else {
        alertBanner.classList.add('hidden');
        isEmergencyAlertActive = false;
    }

    // Calculations for metrics display
    node.incomingEdges.forEach(eId => {
        const edge = window.edges.find(e => e.id === eId);
        if (edge) {
            const queueMeters = edge.getQueueLength() * 6.5;
            if (queueMeters > maxQueueLength) {
                maxQueueLength = queueMeters;
            }
        }
    });

    const avgSpeedVal = detectedCount > 0 
        ? Math.floor((speedsSum / detectedCount) * 15) + 8 
        : 45;
        
    const totalCapacity = node.incomingEdges.length * 10;
    const densityVal = Math.min(100, Math.floor((detectedCount / totalCapacity) * 100));

    // UI Updates
    document.getElementById('cv-vehicle-count').innerText = detectedCount;
    document.getElementById('cv-queue-length').innerText = `${maxQueueLength.toFixed(0)} m`;
    document.getElementById('cv-avg-speed').innerText = `${avgSpeedVal} km/h`;
    
    const densityElement = document.getElementById('cv-density');
    densityElement.innerText = `${densityVal}%`;
    if (densityVal < 40) {
        densityElement.style.color = 'var(--traffic-green)';
    } else if (densityVal < 75) {
        densityElement.style.color = 'var(--traffic-amber)';
    } else {
        densityElement.style.color = 'var(--traffic-red)';
    }

    cctvCtx.fillStyle = 'rgba(0,0,0,0.5)';
    cctvCtx.fillRect(10, cctvCanvas.height - 35, cctvCanvas.width - 20, 25);
    cctvCtx.fillStyle = '#FFFFFF';
    cctvCtx.font = '9px monospace';
    cctvCtx.textAlign = 'left';
    cctvCtx.fillText(`JUNC: ${node.name.toUpperCase()}  |  FPS: 60  |  OBJECTS: ${detectedCount}`, 20, cctvCanvas.height - 18);
    
    cctvCtx.strokeStyle = 'rgba(255, 255, 255, 0.015)';
    cctvCtx.lineWidth = 1;
    for (let i = 0; i < cctvCanvas.height; i += 4) {
        cctvCtx.beginPath();
        cctvCtx.moveTo(0, i);
        cctvCtx.lineTo(cctvCanvas.width, i);
        cctvCtx.stroke();
    }

    requestAnimationFrame(updateCVFeed);
}

// Update Active Junction name in interface
function updateCVFeedJunction(node) {
    document.getElementById('cctv-junction-name').innerText = `CAM: ${node.name.replace(/\s+/g, '_').toUpperCase()}`;
    
    const statusText = document.getElementById('coordination-status-text');
    
    const checkStatus = () => {
        if (node.arbitrationMessage) {
            statusText.innerText = node.arbitrationMessage;
            statusText.style.color = "#60A5FA"; // cyan-blue glow
        } else {
            const adjacentNames = [];
            node.incomingEdges.forEach(eId => {
                const edge = window.edges.find(e => e.id === eId);
                if (edge && !adjacentNames.includes(edge.startNode.name)) {
                    adjacentNames.push(edge.startNode.name);
                }
            });
            const pressureDiff = node.calculatePhasePressure(node.activePhase) - node.calculatePhasePressure(1 - node.activePhase);
            statusText.innerText = `Coordinating signals with ${adjacentNames.join(', ')}. Queue pressure delta: ${pressureDiff.toFixed(0)}. System balanced.`;
            statusText.style.color = "";
        }
    };
    
    if (window.statusInterval) clearInterval(window.statusInterval);
    window.statusInterval = setInterval(checkStatus, 500);
    checkStatus();
}

requestAnimationFrame(updateCVFeed);
window.updateCVFeedJunction = updateCVFeedJunction;
