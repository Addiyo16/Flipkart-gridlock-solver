// Traffic Network Simulation Engine (Leaflet Map & Canvas Overlay Integration)

// Initialize Leaflet Map over Bengaluru
const map = L.map('leaflet-map', {
    zoomControl: false,
    attributionControl: false
}).setView([12.9180, 77.6250], 13);

// CartoDB Dark Matter tile layer
L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
    maxZoom: 19
}).addTo(map);

const canvas = document.getElementById('simulation-canvas');
const ctx = canvas.getContext('2d');

// Network State
let nodes = [];
let edges = [];
let vehicles = [];
let selectedNodeId = 0; // Central Hub Junction by default
let policy = 'dynamic'; // 'fixed', 'smart', or 'dynamic'
let spawnRate = 45; // vehicles spawned per minute
let maxGreenTime = 45; // seconds
const minGreenTime = 7; // seconds

// Statistics
let totalWaitTimeFixed = 0;
let totalWaitTimeDynamic = 0;
let vehiclesClearedFixed = 0;
let vehiclesClearedDynamic = 0;

let runTime = 0; // seconds
let activeAmbulances = [];

// Performance Tracking for A* vs Dijkstra
let totalAStarNodesExpanded = 0;
let aStarRouteCount = 0;
window.avgAStarNodesExpanded = "0.0";
window.logAStarPerformance = (count) => {
    totalAStarNodesExpanded += count;
    aStarRouteCount++;
    window.avgAStarNodesExpanded = (totalAStarNodesExpanded / aStarRouteCount).toFixed(1);
};

// Convert Lat/Lng to Canvas projected pixel coordinates
function getCanvasCoord(lat, lng) {
    const latLng = L.latLng(lat, lng);
    const containerPoint = map.latLngToContainerPoint(latLng);
    return { x: containerPoint.x, y: containerPoint.y };
}

// Sync canvas container size with map container
function syncCanvasSize() {
    const rect = map.getContainer().getBoundingClientRect();
    canvas.width = rect.width;
    canvas.height = rect.height;
}
syncCanvasSize();
window.addEventListener('resize', syncCanvasSize);

// Redraw hook on map zoom/pan
map.on('move zoom viewreset', () => {
    // Redraw loop runs via requestAnimationFrame, automatically using updated container points
});

// Helper for license plates
function generateMockPlateNumber() {
    const states = ["KA", "DL", "MH", "HR", "UP", "TN"];
    const letters = "ABCDEFGHIJKLMNOPQRSTUVWXYZ";
    const randState = states[Math.floor(Math.random() * states.length)];
    const randDist = String(Math.floor(Math.random() * 99) + 1).padStart(2, '0');
    const randChar1 = letters[Math.floor(Math.random() * 26)];
    const randChar2 = letters[Math.floor(Math.random() * 26)];
    const randNum = String(Math.floor(Math.random() * 9000) + 1000);
    return `${randState}-${randDist}-${randChar1}${randChar2}-${randNum}`;
}

// DB Logging endpoint fetcher
window.logViolationToDatabase = (vehicleNumber, vehicleType, violationType, location, confidence = 0.95, evidenceImage = null) => {
    const timestamp = new Date().toISOString();
    
    fetch('/api/violations', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            vehicle_number: vehicleNumber,
            vehicle_type: vehicleType,
            violation_type: violationType,
            timestamp: timestamp,
            location: location,
            confidence: parseFloat(confidence.toFixed(2)),
            evidence_image: evidenceImage
        })
    })
    .then(res => res.json())
    .then(data => {
        // Output RAG citation explanation to terminal log
        if (window.addIncidentLog) {
            window.addIncidentLog(data.legal_explanation, "var(--accent-cyan)");
        }
        // Force refresh the table
        if (window.refreshViolationsTable) {
            window.refreshViolationsTable();
        }
    })
    .catch(err => {
        console.error("Database connection error:", err);
    });
};

// Intersection Graph Structure
class TrafficNode {
    constructor(id, name, lat, lng) {
        this.id = id;
        this.name = name;
        this.lat = lat;
        this.lng = lng;
        
        // Pixel coordinates computed dynamically from map projection
        this.x = 0;
        this.y = 0;
        this.radius = 18;
        
        this.incomingEdges = [];
        this.outgoingEdges = [];
        
        // Signal State
        this.activePhase = 0; // 0: North/South, 1: East/West
        this.phaseTimer = 0; 
        this.minGreenTicks = minGreenTime * 60;
        this.maxGreenTicks = maxGreenTime * 60;
        
        // Amber Transition States
        this.isTransitioning = false;
        this.transitionTimer = 0;
        this.transitionDuration = 120; // 2 seconds
        this.previousPhase = 0;
        
        // Preemption
        this.emergencyOverride = false;
        this.emergencyIncomingEdge = null;
        this.arbitrationMessage = "";
    }

    updatePosition() {
        const pt = getCanvasCoord(this.lat, this.lng);
        this.x = pt.x;
        this.y = pt.y;
    }

    updateSignal() {
        // 1. Run Multi-Emergency Vehicle Arbitration
        TrafficAlgorithms.arbitrateJunctionEmergencies(this, edges, vehicles);

        // 2. Handle Amber transition timing
        if (this.isTransitioning) {
            this.transitionTimer--;
            if (this.transitionTimer <= 0) {
                this.isTransitioning = false;
                this.phaseTimer = 0;
            }
            return;
        }

        this.phaseTimer++;
        
        // 3. Emergency Preemption override bypasses normal cycle
        if (this.emergencyOverride) {
            if (this.emergencyIncomingEdge !== null) {
                const phaseRequired = TrafficAlgorithms.getPhaseForEdge(this, edges.find(e => e.id === this.emergencyIncomingEdge), edges);
                if (this.activePhase !== phaseRequired) {
                    this.activePhase = phaseRequired;
                    this.phaseTimer = 0;
                }
            }
            return;
        }

        let targetPhase = this.activePhase;

        // 4. Evaluate phase changes based on current policy
        if (policy === 'fixed') {
            const fixedDuration = (maxGreenTime / 2) * 60;
            if (this.phaseTimer >= fixedDuration) {
                targetPhase = 1 - this.activePhase;
            }
        } else if (policy === 'smart') {
            // Smart Adaptive Timer: Calculates green time based on the active queue length
            const activeQueue = this.calculatePhaseQueueLength(this.activePhase);
            const dynamicGreenTicks = Math.min(this.maxGreenTicks, this.minGreenTicks + (activeQueue * 3.5 * 60));
            
            if (this.phaseTimer >= dynamicGreenTicks) {
                targetPhase = 1 - this.activePhase;
            }
        } else {
            // OpenCV Max-Pressure Coordination Logic
            if (this.phaseTimer >= this.minGreenTicks && this.phaseTimer % 60 === 0) {
                const decision = TrafficAlgorithms.calculateMaxPressurePhase(this, edges);
                if (decision.phase !== this.activePhase || this.phaseTimer >= this.maxGreenTicks) {
                    targetPhase = decision.phase;
                }
            }
        }

        // 5. Trigger Amber Transition
        if (targetPhase !== this.activePhase) {
            this.isTransitioning = true;
            this.transitionTimer = this.transitionDuration;
            this.previousPhase = this.activePhase;
            this.activePhase = targetPhase;
        }
    }

    calculatePhasePressure(phase) {
        let incomingQueue = 0;
        let outgoingQueue = 0;
        
        this.incomingEdges.forEach(edgeId => {
            const edge = edges.find(e => e.id === edgeId);
            if (edge && TrafficAlgorithms.getPhaseForEdge(this, edge, edges) === phase) {
                incomingQueue += edge.getQueueLength();
            }
        });

        this.outgoingEdges.forEach(edgeId => {
            const edge = edges.find(e => e.id === edgeId);
            if (edge) {
                outgoingQueue += edge.getQueueLength() * 0.5;
            }
        });
        
        return Math.max(0, incomingQueue - outgoingQueue);
    }

    calculatePhaseQueueLength(phase) {
        let queueCount = 0;
        this.incomingEdges.forEach(edgeId => {
            const edge = edges.find(e => e.id === edgeId);
            if (edge && TrafficAlgorithms.getPhaseForEdge(this, edge, edges) === phase) {
                queueCount += edge.getQueueLength();
            }
        });
        return queueCount;
    }

    draw() {
        // Draw selection glow
        if (selectedNodeId === this.id) {
            ctx.beginPath();
            ctx.arc(this.x, this.y, this.radius + 6, 0, Math.PI * 2);
            ctx.strokeStyle = 'rgba(6, 182, 212, 0.4)';
            ctx.lineWidth = 2;
            ctx.stroke();
            ctx.fillStyle = 'rgba(6, 182, 212, 0.15)';
            ctx.fill();
        }

        // Base circle
        ctx.beginPath();
        ctx.arc(this.x, this.y, this.radius, 0, Math.PI * 2);
        ctx.fillStyle = '#111827';
        ctx.strokeStyle = selectedNodeId === this.id ? '#06B6D4' : '#374151';
        ctx.lineWidth = 3;
        ctx.stroke();
        ctx.fill();

        // Traffic lights colors
        const green = '#10B981';
        const red = '#EF4444';
        const amber = '#F59E0B';
        const blue = '#3B82F6';

        let p0Color = red;
        let p1Color = red;

        if (this.isTransitioning) {
            p0Color = this.previousPhase === 0 ? amber : red;
            p1Color = this.previousPhase === 1 ? amber : red;
        } else if (this.emergencyOverride) {
            p0Color = this.activePhase === 0 ? blue : red;
            p1Color = this.activePhase === 1 ? blue : red;
        } else {
            p0Color = this.activePhase === 0 ? green : red;
            p1Color = this.activePhase === 1 ? green : red;
        }

        // Draw mini light points (vertical / horizontal indicators)
        ctx.beginPath();
        ctx.arc(this.x, this.y - 7, 3, 0, Math.PI * 2);
        ctx.fillStyle = p0Color;
        ctx.fill();
        ctx.beginPath();
        ctx.arc(this.x, this.y + 7, 3, 0, Math.PI * 2);
        ctx.fillStyle = p0Color;
        ctx.fill();

        ctx.beginPath();
        ctx.arc(this.x - 7, this.y, 3, 0, Math.PI * 2);
        ctx.fillStyle = p1Color;
        ctx.fill();
        ctx.beginPath();
        ctx.arc(this.x + 7, this.y, 3, 0, Math.PI * 2);
        ctx.fillStyle = p1Color;
        ctx.fill();

        // Node Title
        ctx.fillStyle = '#F3F4F6';
        ctx.font = 'bold 9px var(--font-sans)';
        ctx.textAlign = 'center';
        ctx.fillText(this.name, this.x, this.y - this.radius - 6);
    }
}

class TrafficEdge {
    constructor(id, startNode, endNode) {
        this.id = id;
        this.startNode = startNode;
        this.endNode = endNode;
        this.width = 12;
        this.maxSpeed = 2.5; 
        this.capacity = 12;
    }

    getQueueLength() {
        return vehicles.filter(v => v.currentEdgeId === this.id && v.speed < 0.2).length;
    }

    draw() {
        // Draw main road lane representation
        ctx.beginPath();
        ctx.moveTo(this.startNode.x, this.startNode.y);
        ctx.lineTo(this.endNode.x, this.endNode.y);
        ctx.strokeStyle = 'rgba(31, 41, 55, 0.4)';
        ctx.lineWidth = this.width;
        ctx.stroke();

        // Draw center dashed lines
        ctx.beginPath();
        ctx.moveTo(this.startNode.x, this.startNode.y);
        ctx.lineTo(this.endNode.x, this.endNode.y);
        ctx.strokeStyle = 'rgba(255, 255, 255, 0.15)';
        ctx.lineWidth = 1;
        ctx.setLineDash([5, 8]);
        ctx.stroke();
        ctx.setLineDash([]);

        // Highlight congested lines in red
        const queue = this.getQueueLength();
        if (queue > 6) {
            ctx.beginPath();
            ctx.moveTo(this.startNode.x, this.startNode.y);
            ctx.lineTo(this.endNode.x, this.endNode.y);
            ctx.strokeStyle = 'rgba(239, 68, 68, 0.2)';
            ctx.lineWidth = this.width + 4;
            ctx.stroke();
        }
    }
}

class Vehicle {
    constructor(id, startEdge, type = 'car') {
        this.id = id;
        this.currentEdgeId = startEdge.id;
        this.progress = 0.0;
        this.type = type;
        this.plateNumber = generateMockPlateNumber();
        
        // Dimensions
        this.width = type === 'bus' ? 10 : type === 'fire_engine' ? 11 : type === 'car' ? 7 : type === 'police' ? 7 : type === 'ambulance' ? 8 : 5;
        this.height = type === 'bus' ? 20 : type === 'fire_engine' ? 22 : type === 'car' ? 12 : type === 'police' ? 13 : type === 'ambulance' ? 14 : 9;
        
        this.maxSpeed = type === 'bike' ? 2.8 : ['ambulance', 'police', 'fire_engine'].includes(type) ? 3.8 : type === 'bus' ? 1.8 : 2.2;
        this.speed = this.maxSpeed;
        
        this.color = type === 'bus' ? '#10B981' : 
                     type === 'car' ? '#F59E0B' : 
                     type === 'ambulance' ? '#3B82F6' : 
                     type === 'fire_engine' ? '#EF4444' : 
                     type === 'police' ? '#1E3A8A' : '#9CA3AF';
        
        this.waitTicks = 0;
        this.isWaiting = false;
        
        // Infractions simulation configuration
        this.isAccident = false;
        this.hasRedLightViolation = false;
        this.hasSpeedViolation = false;
        this.hasHelmetViolation = (type === 'bike' && Math.random() < 0.05); // 5% no helmet
        this.hasSeatbeltViolation = (type === 'car' && Math.random() < 0.04); // 4% no seatbelt
        this.hasComplianceLogged = false;
        
        this.path = [];
        this.selectDestination(startEdge.startNode.id);
    }

    selectDestination(startNodeId) {
        let destNodeId = Math.floor(Math.random() * nodes.length);
        while (destNodeId === startNodeId) {
            destNodeId = Math.floor(Math.random() * nodes.length);
        }

        const computedPath = TrafficAlgorithms.findOptimalPathAStar(
            startNodeId,
            destNodeId,
            nodes,
            edges,
            vehicles
        );

        const currentEdge = edges.find(e => e.id === this.currentEdgeId);
        if (computedPath) {
            this.path = computedPath;
        } else if (currentEdge) {
            this.path = [startNodeId, currentEdge.endNode.id];
            let currentNode = nodes.find(n => n.id === this.path[1]);
            for (let i = 0; i < 3; i++) {
                if (currentNode && currentNode.outgoingEdges.length > 0) {
                    const randEdgeId = currentNode.outgoingEdges[Math.floor(Math.random() * currentNode.outgoingEdges.length)];
                    const e = edges.find(edge => edge.id === randEdgeId);
                    if (e) {
                        this.path.push(e.endNode.id);
                        currentNode = e.endNode;
                    }
                }
            }
        } else {
            this.path = [startNodeId];
        }
    }

    update() {
        const edge = edges.find(e => e.id === this.currentEdgeId);
        if (!edge) return;

        if (this.isAccident) {
            this.speed = 0;
            this.isWaiting = true;
            this.waitTicks++;
            return;
        }

        const startX = edge.startNode.x;
        const startY = edge.startNode.y;
        const endX = edge.endNode.x;
        const endY = edge.endNode.y;
        const distance = Math.hypot(endX - startX, endY - startY);
        
        const isEmergency = ['ambulance', 'police', 'fire_engine'].includes(this.type);

        let leadVehicle = null;
        let minDistance = Infinity;

        vehicles.forEach(other => {
            if (other.id !== this.id && other.currentEdgeId === this.currentEdgeId && other.progress > this.progress) {
                const dist = (other.progress - this.progress) * distance;
                if (dist < minDistance) {
                    minDistance = dist;
                    leadVehicle = other;
                }
            }
        });

        let targetSpeed = this.maxSpeed;
        const remainingDist = (1.0 - this.progress) * distance;
        
        if (remainingDist < 30) {
            const junction = edge.endNode;
            const myPhase = TrafficAlgorithms.getPhaseForEdge(junction, edge, edges);
            
            if (junction.activePhase !== myPhase) {
                if (!isEmergency) {
                    if (junction.isTransitioning && junction.previousPhase === myPhase) {
                        if (remainingDist > 20) {
                            targetSpeed = 0;
                        }
                    } else {
                        targetSpeed = 0;

                        // Red Light Camera Capture
                        if (remainingDist < 12 && this.speed > 0.8 && !this.hasRedLightViolation) {
                            this.hasRedLightViolation = true;
                            if (window.addIncidentLog) {
                                window.addIncidentLog(`[RED-LIGHT CAMERA] Vehicle ${this.plateNumber} crossed the line on red at ${junction.name}. Capturing database record...`, "var(--traffic-red)");
                            }
                            if (window.logViolationToDatabase) {
                                window.logViolationToDatabase(this.plateNumber, this.type, "red_light_violation", junction.name, 0.92 + Math.random()*0.07);
                            }
                        }
                    }
                }
            }

            // Check Helmet / Seatbelt compliance near intersections (simulating OCR and CV camera triggers)
            if (remainingDist < 25 && !this.hasComplianceLogged) {
                this.hasComplianceLogged = true;
                if (this.type === 'bike' && this.hasHelmetViolation) {
                    if (window.addIncidentLog) {
                        window.addIncidentLog(`[CV HELMET SCAN] Rider on bike ${this.plateNumber} detected without helmet at ${junction.name}. Logging offense.`, "var(--traffic-red)");
                    }
                    if (window.logViolationToDatabase) {
                        window.logViolationToDatabase(this.plateNumber, this.type, "helmet_non_compliance", junction.name, 0.95 + Math.random()*0.04);
                    }
                } else if (this.type === 'car' && this.hasSeatbeltViolation) {
                    if (window.addIncidentLog) {
                        window.addIncidentLog(`[CV SEATBELT SCAN] Driver in car ${this.plateNumber} detected without seatbelt at ${junction.name}. Logging offense.`, "var(--traffic-red)");
                    }
                    if (window.logViolationToDatabase) {
                        window.logViolationToDatabase(this.plateNumber, this.type, "seatbelt_non_compliance", junction.name, 0.93 + Math.random()*0.06);
                    }
                }
            }
        }

        // Buffer space
        if (leadVehicle) {
            const safetyBuffer = this.type === 'bus' || this.type === 'fire_engine' ? 20 : 14;
            if (minDistance < safetyBuffer) {
                targetSpeed = 0;
            } else if (minDistance < safetyBuffer * 2) {
                targetSpeed = Math.min(targetSpeed, leadVehicle.speed * 0.85);
            }
        }

        if (this.speed > targetSpeed) {
            this.speed = Math.max(targetSpeed, this.speed - 0.2);
        } else if (this.speed < targetSpeed) {
            this.speed = Math.min(targetSpeed, this.speed + 0.15);
        }

        const progressIncrement = this.speed / distance;
        this.progress += progressIncrement;

        // Speed Violation Check (Traps on roads)
        if (this.type === 'bike' && this.speed > 2.7 && this.progress > 0.3 && this.progress < 0.7 && !this.hasSpeedViolation && Math.random() < 0.003) {
            this.hasSpeedViolation = true;
            const speedKmh = Math.round(this.speed * 28);
            if (window.addIncidentLog) {
                window.addIncidentLog(`[SPEED TRAP ALERT] Vehicle ${this.plateNumber} clocked at ${speedKmh} km/h (Limit: 60 km/h) on ${edge.startNode.name} -> ${edge.endNode.name}.`, "var(--traffic-amber)");
            }
            if (window.logViolationToDatabase) {
                window.logViolationToDatabase(this.plateNumber, this.type, "speeding", `${edge.startNode.name} -> ${edge.endNode.name}`, 0.94 + Math.random()*0.05);
            }
        }

        if (this.speed < 0.1) {
            this.isWaiting = true;
            this.waitTicks++;
            if (policy === 'fixed') {
                totalWaitTimeFixed += 1 / 60;
            } else {
                totalWaitTimeDynamic += 1 / 60;
            }
        } else {
            this.isWaiting = false;
        }

        // Loop transitions
        if (this.progress >= 0.98) {
            const currentEndNodeId = edge.endNode.id;
            const nextNodeIndexInPath = this.path.indexOf(currentEndNodeId);
            
            if (nextNodeIndexInPath !== -1 && nextNodeIndexInPath < this.path.length - 1) {
                const nextNodeId = this.path[nextNodeIndexInPath + 1];
                const nextEdge = edges.find(e => e.startNode.id === currentEndNodeId && e.endNode.id === nextNodeId);
                
                if (nextEdge) {
                    this.currentEdgeId = nextEdge.id;
                    this.progress = 0.0;
                    this.speed = this.maxSpeed;
                    this.hasComplianceLogged = false; // re-enable compliance scanner for next junction
                } else {
                    this.retire();
                }
            } else {
                this.retire();
            }
        }
    }

    retire() {
        if (policy === 'fixed') {
            vehiclesClearedFixed++;
        } else {
            vehiclesClearedDynamic++;
        }
        
        if (this.type === 'ambulance' && this.rescueTargetVehicleId !== undefined) {
            const targetVehicle = vehicles.find(v => v.id === this.rescueTargetVehicleId);
            if (targetVehicle) {
                targetVehicle.isAccident = false;
                targetVehicle.speed = targetVehicle.maxSpeed;
                if (window.addIncidentLog) {
                    window.addIncidentLog(`[RESCUE COMPLETED] Ambulance cleared accident site on ${edges.find(e => e.id === targetVehicle.currentEdgeId).startNode.name}. Flow restored.`, "var(--traffic-green)");
                }
            }
        }
        
        vehicles = vehicles.filter(v => v.id !== this.id);
        const isEmergency = ['ambulance', 'police', 'fire_engine'].includes(this.type);
        if (isEmergency) {
            activeAmbulances = activeAmbulances.filter(a => a.id !== this.id);
            nodes.forEach(n => {
                TrafficAlgorithms.arbitrateJunctionEmergencies(n, edges, vehicles);
            });
        }
    }

    draw() {
        const edge = edges.find(e => e.id === this.currentEdgeId);
        if (!edge) return;

        const startX = edge.startNode.x;
        const startY = edge.startNode.y;
        const endX = edge.endNode.x;
        const endY = edge.endNode.y;

        const positionX = startX + (endX - startX) * this.progress;
        const positionY = startY + (endY - startY) * this.progress;
        const angle = Math.atan2(endY - startY, endX - startX);

        ctx.save();
        ctx.translate(positionX, positionY);
        ctx.rotate(angle);

        const isEmergency = ['ambulance', 'police', 'fire_engine'].includes(this.type);
        if (isEmergency) {
            const flash = Math.floor(Date.now() / 130) % 2 === 0;
            ctx.beginPath();
            ctx.arc(0, 0, 14, 0, Math.PI * 2);
            
            if (this.type === 'fire_engine') {
                ctx.fillStyle = flash ? 'rgba(239, 68, 68, 0.45)' : 'rgba(150, 20, 20, 0.45)';
            } else if (this.type === 'police') {
                ctx.fillStyle = flash ? 'rgba(30, 64, 175, 0.45)' : 'rgba(239, 68, 68, 0.45)';
            } else {
                ctx.fillStyle = flash ? 'rgba(59, 130, 246, 0.45)' : 'rgba(239, 68, 68, 0.45)';
            }
            ctx.fill();
            
            ctx.fillStyle = this.color;
            ctx.fillRect(-this.height/2, -this.width/2, this.height, this.width);
            
            if (this.type === 'ambulance') {
                ctx.fillStyle = '#FFFFFF';
                ctx.fillRect(-2, -this.width/2 + 2, 4, this.width - 4);
                ctx.fillRect(-this.height/2 + 3, -2, this.height - 6, 4);
            }
        } else {
            ctx.fillStyle = this.color;
            ctx.fillRect(-this.height/2, -this.width/2, this.height, this.width);
            ctx.fillStyle = 'rgba(0,0,0,0.5)';
            ctx.fillRect(this.height/4, -this.width/2 + 1, 2, this.width - 2);
        }

        if (this.isAccident) {
            const flash = Math.floor(Date.now() / 250) % 2 === 0;
            ctx.rotate(-angle);
            ctx.beginPath();
            ctx.arc(0, 0, 14, 0, Math.PI * 2);
            ctx.fillStyle = flash ? 'rgba(239, 68, 68, 0.5)' : 'rgba(245, 158, 11, 0.2)';
            ctx.fill();
            ctx.fillStyle = '#FFFFFF';
            ctx.font = 'bold 9px var(--font-sans)';
            ctx.textAlign = 'center';
            ctx.fillText("⚠️", 0, 3);
            ctx.rotate(angle);
        }

        ctx.restore();
    }
}

// Initialize Graph Network (Real Geolocation coordinates in Bengaluru)
function initNetwork() {
    nodes = [
        new TrafficNode(0, "Central Hub Junction", 12.9176, 77.6244),
        new TrafficNode(1, "North-East Junction", 12.9348, 77.6322),
        new TrafficNode(2, "South-East Junction", 12.9116, 77.6388),
        new TrafficNode(3, "West Junction", 12.9166, 77.6080),
        new TrafficNode(4, "South Bypass Junction", 12.8488, 77.6599),
        new TrafficNode(5, "North Circle", 12.9602, 77.5976)
    ];

    let edgeIdCounter = 0;
    function addRoad(nodeA, nodeB) {
        const e1 = new TrafficEdge(edgeIdCounter++, nodeA, nodeB);
        const e2 = new TrafficEdge(edgeIdCounter++, nodeB, nodeA);
        
        edges.push(e1);
        edges.push(e2);
        
        nodeA.outgoingEdges.push(e1.id);
        nodeA.incomingEdges.push(e2.id);
        
        nodeB.outgoingEdges.push(e2.id);
        nodeB.incomingEdges.push(e1.id);
    }

    addRoad(nodes[5], nodes[0]); // North Circle <-> Central Hub
    addRoad(nodes[3], nodes[0]); // West Junction <-> Central Hub
    addRoad(nodes[0], nodes[4]); // Central Hub <-> South Bypass
    addRoad(nodes[1], nodes[0]); // North-East <-> Central Hub
    addRoad(nodes[2], nodes[0]); // South-East <-> Central Hub
    
    addRoad(nodes[5], nodes[1]); // North Circle <-> North-East
    addRoad(nodes[1], nodes[2]); // North-East <-> South-East
    addRoad(nodes[2], nodes[4]); // South-East <-> South Bypass
    addRoad(nodes[4], nodes[3]); // South Bypass <-> West Junction
    addRoad(nodes[3], nodes[5]); // West Junction <-> North Circle
}

// Spawning vehicles
let spawnTimer = 0;
let vehicleIdCounter = 0;

function spawnVehicle(type = 'car', specificEdge = null) {
    const edge = specificEdge || edges[Math.floor(Math.random() * edges.length)];
    const v = new Vehicle(vehicleIdCounter++, edge, type);
    vehicles.push(v);
    
    if (['ambulance', 'police', 'fire_engine'].includes(type)) {
        activeAmbulances.push(v);
    }
    return v;
}

// Convert coordinates to projected pixels
function updateNodeCoordinates() {
    nodes.forEach(node => {
        node.updatePosition();
    });
}

// Add invisible interactive Leaflet shapes on top of the real map to handle map selection clicks
function initInteractiveMapTriggers() {
    nodes.forEach(node => {
        const marker = L.circleMarker([node.lat, node.lng], {
            radius: 18,
            fillColor: 'transparent',
            color: 'transparent',
            interactive: true
        }).addTo(map);
        
        marker.on('click', () => {
            selectedNodeId = node.id;
            if (window.updateCVFeedJunction) {
                window.updateCVFeedJunction(node);
            }
        });
    });
}

// Main Frame Rendering Loop
function updateSim() {
    runTime += 1 / 60;
    
    spawnTimer++;
    const framesPerSpawn = (60 * 60) / spawnRate;
    if (spawnTimer >= framesPerSpawn) {
        const roll = Math.random();
        let type = 'car';
        if (roll < 0.22) type = 'bike';
        else if (roll < 0.31) type = 'bus';
        else if (roll < 0.33) {
            const types = ['ambulance', 'police', 'fire_engine'];
            type = types[Math.floor(Math.random() * types.length)];
        }
        
        // Safety cap
        if (vehicles.length < 150) {
            spawnVehicle(type);
        }
        spawnTimer = 0;
    }

    // Dynamic Leaflet container point calculations
    updateNodeCoordinates();

    // Update nodes signal states
    nodes.forEach(n => n.updateSignal());

    // Update active vehicles positions
    vehicles.forEach(v => v.update());

    // Clear Canvas and Redraw projected network
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    
    edges.forEach(e => e.draw());
    nodes.forEach(n => n.draw());
    vehicles.forEach(v => v.draw());

    requestAnimationFrame(updateSim);
}

// Initialization triggers
initNetwork();
initInteractiveMapTriggers();
requestAnimationFrame(updateSim);

// Expose variables globally
window.nodes = nodes;
window.edges = edges;
window.vehicles = vehicles;
window.activeAmbulances = activeAmbulances;
window.getSelectedNode = () => nodes.find(n => n.id === selectedNodeId);
window.getPolicy = () => policy;
window.setPolicy = (newPolicy) => {
    policy = newPolicy;
};
window.setSpawnRate = (rate) => {
    spawnRate = rate;
};
window.setMaxGreen = (secs) => {
    maxGreenTime = secs;
    nodes.forEach(n => {
        n.maxGreenTicks = maxGreenTime * 60;
    });
};
window.spawnAmbulance = () => {
    const types = ['ambulance', 'police', 'fire_engine'];
    const randType = types[Math.floor(Math.random() * types.length)];
    const outerEdges = edges.filter(e => e.startNode.id === 5 || e.startNode.id === 4 || e.startNode.id === 3);
    const edge = outerEdges[Math.floor(Math.random() * outerEdges.length)];
    spawnVehicle(randType, edge);
};
window.getStats = () => {
    return {
        totalWaitTimeFixed,
        totalWaitTimeDynamic,
        vehiclesClearedFixed,
        vehiclesClearedDynamic,
        runTime
    };
};

window.triggerAccident = () => {
    const eligible = vehicles.filter(v => !v.isAccident && !['ambulance', 'police', 'fire_engine'].includes(v.type) && v.progress > 0.15 && v.progress < 0.85);
    
    if (eligible.length === 0) {
        if (window.addIncidentLog) {
            window.addIncidentLog("Cannot trigger accident: No moving vehicles on roads.", "var(--text-muted)");
        }
        return;
    }
    
    const target = eligible[Math.floor(Math.random() * eligible.length)];
    target.isAccident = true;
    target.speed = 0;
    
    const edge = edges.find(e => e.id === target.currentEdgeId);
    const roadName = edge ? `${edge.startNode.name} to ${edge.endNode.name}` : "road";
    
    if (window.addIncidentLog) {
        window.addIncidentLog(`[CRASH ALERT] Traffic accident reported on ${roadName} involving vehicle #${target.id}. Notifying medical units...`, "var(--traffic-red)");
    }
    
    // Auto-dispatch rescue ambulance
    const amb = spawnVehicle('ambulance');
    if (edge) {
        const startNodeId = amb.path[0] || 5;
        const destNodeId = edge.endNode.id;
        const path = TrafficAlgorithms.findOptimalPathAStar(startNodeId, destNodeId, nodes, edges, vehicles);
        if (path) {
            amb.path = path;
        }
        amb.rescueTargetVehicleId = target.id;
    }
};
