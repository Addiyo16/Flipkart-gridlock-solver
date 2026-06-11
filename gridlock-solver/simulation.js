// Bengaluru Traffic Network Simulation Engine (Integrated with TrafficAlgorithms)

const canvas = document.getElementById('simulation-canvas');
const ctx = canvas.getContext('2d');

// Network State
let nodes = [];
let edges = [];
let vehicles = [];
let selectedNodeId = 0; // Silk Board by default
let policy = 'dynamic'; // 'fixed' or 'dynamic'
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

// Zoom & Pan
let zoom = 1.0;
let offsetX = 0;
let offsetY = 0;
let isDragging = false;
let startDragX = 0;
let startDragY = 0;

// Performance Tracking for A* vs Dijkstra
let totalAStarNodesExpanded = 0;
let aStarRouteCount = 0;
window.avgAStarNodesExpanded = "0.0";
window.logAStarPerformance = (count) => {
    totalAStarNodesExpanded += count;
    aStarRouteCount++;
    window.avgAStarNodesExpanded = (totalAStarNodesExpanded / aStarRouteCount).toFixed(1);
};

// Intersection Graph Structure representing South Bengaluru hotspots
class TrafficNode {
    constructor(id, name, x, y) {
        this.id = id;
        this.name = name;
        this.x = x;
        this.y = y;
        this.radius = 22;
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
        this.transitionDuration = 120; // 2 seconds at 60 fps
        this.previousPhase = 0;
        
        // Coordination & Arbitration variables
        this.emergencyOverride = false;
        this.emergencyIncomingEdge = null;
        this.arbitrationMessage = "";
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
                    // For emergency overrides, switch immediately (amber is bypassed for safety corridor clearance)
                    this.activePhase = phaseRequired;
                    this.phaseTimer = 0;
                }
            }
            return;
        }

        let targetPhase = this.activePhase;

        // 4. Evaluate phase changes based on current policy
        if (policy === 'fixed') {
            const fixedDuration = (maxGreenTime / 2) * 60; // standard fixed cycle
            if (this.phaseTimer >= fixedDuration) {
                targetPhase = 1 - this.activePhase;
            }
        } else if (policy === 'smart') {
            // Smart Adaptive Timer: Calculates green time dynamically based on the queue length.
            // Green Ticks = minGreenTime + queueCount * 3.5 seconds
            const activeQueue = this.calculatePhaseQueueLength(this.activePhase);
            const dynamicGreenTicks = Math.min(this.maxGreenTicks, this.minGreenTicks + (activeQueue * 3.5 * 60));
            
            if (this.phaseTimer >= dynamicGreenTicks) {
                targetPhase = 1 - this.activePhase;
            }
        } else {
            // OpenCV Max-Pressure Coordination Logic
            // Evaluate pressure balances at regular intervals to allow traffic packets to pass and honor minimum green times
            if (this.phaseTimer >= this.minGreenTicks && this.phaseTimer % 60 === 0) {
                const decision = TrafficAlgorithms.calculateMaxPressurePhase(this, edges);
                
                // If the algorithm demands a phase switch or we exceed the safety cap
                if (decision.phase !== this.activePhase || this.phaseTimer >= this.maxGreenTicks) {
                    targetPhase = decision.phase;
                }
            }
        }

        // 5. Trigger Amber Transition if a phase change is scheduled
        if (targetPhase !== this.activePhase) {
            this.isTransitioning = true;
            this.transitionTimer = this.transitionDuration;
            this.previousPhase = this.activePhase;
            this.activePhase = targetPhase; // Phase state updates, but previous phase is drawn orange
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
        // Draw glow if selected
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
        const amber = '#F59E0B'; // Orange
        const blue = '#3B82F6';

        let p0Color = red;
        let p1Color = red;

        if (this.isTransitioning) {
            // Outgoing phase is Amber, incoming phase is Red
            p0Color = this.previousPhase === 0 ? amber : red;
            p1Color = this.previousPhase === 1 ? amber : red;
        } else if (this.emergencyOverride) {
            p0Color = this.activePhase === 0 ? blue : red;
            p1Color = this.activePhase === 1 ? blue : red;
        } else {
            p0Color = this.activePhase === 0 ? green : red;
            p1Color = this.activePhase === 1 ? green : red;
        }

        // Draw mini light points (Visualizing traffic lights)
        // Vertical light dots
        ctx.beginPath();
        ctx.arc(this.x, this.y - 8, 4, 0, Math.PI * 2);
        ctx.fillStyle = p0Color;
        ctx.fill();

        ctx.beginPath();
        ctx.arc(this.x, this.y + 8, 4, 0, Math.PI * 2);
        ctx.fillStyle = p0Color;
        ctx.fill();

        // Horizontal light dots
        ctx.beginPath();
        ctx.arc(this.x - 8, this.y, 4, 0, Math.PI * 2);
        ctx.fillStyle = p1Color;
        ctx.fill();

        ctx.beginPath();
        ctx.arc(this.x + 8, this.y, 4, 0, Math.PI * 2);
        ctx.fillStyle = p1Color;
        ctx.fill();

        // Node Title
        ctx.fillStyle = '#F3F4F6';
        ctx.font = 'bold 10px var(--font-sans)';
        ctx.textAlign = 'center';
        ctx.fillText(this.name, this.x, this.y - this.radius - 8);
    }
}

class TrafficEdge {
    constructor(id, startNode, endNode) {
        this.id = id;
        this.startNode = startNode;
        this.endNode = endNode;
        this.width = 16;
        this.maxSpeed = 2.5; 
        this.capacity = 12;
    }

    getQueueLength() {
        return vehicles.filter(v => v.currentEdgeId === this.id && v.speed < 0.2).length;
    }

    draw() {
        // Draw double lanes
        ctx.beginPath();
        ctx.moveTo(this.startNode.x, this.startNode.y);
        ctx.lineTo(this.endNode.x, this.endNode.y);
        ctx.strokeStyle = 'rgba(31, 41, 55, 0.6)';
        ctx.lineWidth = this.width;
        ctx.stroke();

        // Draw middle dashed line
        ctx.beginPath();
        ctx.moveTo(this.startNode.x, this.startNode.y);
        ctx.lineTo(this.endNode.x, this.endNode.y);
        ctx.strokeStyle = 'rgba(255, 255, 255, 0.2)';
        ctx.lineWidth = 1;
        ctx.setLineDash([5, 10]);
        ctx.stroke();
        ctx.setLineDash([]);

        // Highlight heavily congested edges
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
        
        // Dimensions and speed configs based on vehicle class
        this.width = type === 'bus' ? 12 : type === 'fire_engine' ? 13 : type === 'car' ? 8 : type === 'police' ? 8 : type === 'ambulance' ? 9 : 6;
        this.height = type === 'bus' ? 22 : type === 'fire_engine' ? 24 : type === 'car' ? 14 : type === 'police' ? 15 : type === 'ambulance' ? 16 : 10;
        
        this.maxSpeed = type === 'bike' ? 2.8 : ['ambulance', 'police', 'fire_engine'].includes(type) ? 3.8 : type === 'bus' ? 1.8 : 2.2;
        this.speed = this.maxSpeed;
        
        this.color = type === 'bus' ? '#10B981' : 
                     type === 'car' ? '#F59E0B' : 
                     type === 'ambulance' ? '#3B82F6' : 
                     type === 'fire_engine' ? '#EF4444' : 
                     type === 'police' ? '#1E3A8A' : '#9CA3AF';
        
        this.waitTicks = 0;
        this.isWaiting = false;
        
        // Safety violations and incident indicators
        this.isAccident = false;
        this.hasRedLightViolation = false;
        this.hasSpeedViolation = false;
        
        // Destination Selection & A* routing pathing
        this.path = [];
        this.selectDestination(startEdge.startNode.id);
    }

    selectDestination(startNodeId) {
        let destNodeId = Math.floor(Math.random() * nodes.length);
        while (destNodeId === startNodeId) {
            destNodeId = Math.floor(Math.random() * nodes.length);
        }

        // Calculate dynamic shortest path using A* Search Algorithm
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
            // Fallback: simple random walk pathing with safety checks
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

        // Space buffer: detect vehicle in front
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

        // Speed management
        let targetSpeed = this.maxSpeed;
        
        // Signal logic at the end of the edge (near junction)
        const remainingDist = (1.0 - this.progress) * distance;
        
        if (remainingDist < 40) {
            const junction = edge.endNode;
            const myPhase = TrafficAlgorithms.getPhaseForEdge(junction, edge, edges);
            
            // If traffic light is RED for our phase
            if (junction.activePhase !== myPhase) {
                if (!isEmergency) {
                    // Check if light is Amber (transitioning from my phase)
                    if (junction.isTransitioning && junction.previousPhase === myPhase) {
                        // Amber Light Behavior: If close enough (dist < 28px) we pass, else we slow down to stop
                        if (remainingDist > 28) {
                            targetSpeed = 0;
                        }
                    } else {
                        // Red Light: Complete stop
                        targetSpeed = 0;

                        // Law Violation Detection: crossing stop line on Red
                        if (remainingDist < 12 && this.speed > 0.8 && !this.hasRedLightViolation) {
                            this.hasRedLightViolation = true;
                            if (window.addIncidentLog) {
                                window.addIncidentLog(`RED LIGHT VIOLATION: ${this.type.toUpperCase()} #${this.id} crossed stop line at ${junction.name}. Fined.`, "var(--traffic-red)");
                            }
                        }
                    }
                }
            }
        }

        // Keep distance to lead vehicle
        if (leadVehicle) {
            const safetyBuffer = this.type === 'bus' || this.type === 'fire_engine' ? 24 : 16;
            if (minDistance < safetyBuffer) {
                targetSpeed = 0; // stop
            } else if (minDistance < safetyBuffer * 2) {
                targetSpeed = Math.min(targetSpeed, leadVehicle.speed * 0.85);
            }
        }

        // Apply acceleration/deceleration
        if (this.speed > targetSpeed) {
            this.speed = Math.max(targetSpeed, this.speed - 0.2);
        } else if (this.speed < targetSpeed) {
            this.speed = Math.min(targetSpeed, this.speed + 0.15);
        }

        // Progress along road
        const progressIncrement = this.speed / distance;
        this.progress += progressIncrement;

        // Speed limit violation check
        if (this.type === 'bike' && this.speed > 2.7 && this.progress > 0.3 && this.progress < 0.7 && !this.hasSpeedViolation && Math.random() < 0.003) {
            this.hasSpeedViolation = true;
            if (window.addIncidentLog) {
                const speedKmh = Math.round(this.speed * 28);
                window.addIncidentLog(`SPEEDING: Bike #${this.id} clocked at ${speedKmh} km/h (Limit: 60 km/h) on ${edge.startNode.name} -> ${edge.endNode.name}.`, "var(--traffic-amber)");
            }
        }

        // Check if vehicle stopped
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

        // Transition to next edge when complete
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
        
        // Check if this is a rescue ambulance arriving to clear an accident scene
        if (this.type === 'ambulance' && this.rescueTargetVehicleId !== undefined) {
            const targetVehicle = vehicles.find(v => v.id === this.rescueTargetVehicleId);
            if (targetVehicle) {
                targetVehicle.isAccident = false;
                targetVehicle.speed = targetVehicle.maxSpeed;
                if (window.addIncidentLog) {
                    window.addIncidentLog(`RESCUE SUCCESS: Ambulance cleared accident scene. Traffic flow restored.`, "var(--traffic-green)");
                }
            }
        }
        
        // Remove from list
        vehicles = vehicles.filter(v => v.id !== this.id);
        const isEmergency = ['ambulance', 'police', 'fire_engine'].includes(this.type);
        if (isEmergency) {
            activeAmbulances = activeAmbulances.filter(a => a.id !== this.id);
            // Re-arbitrate signals at all junctions immediately
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

        // Render emergency siren overlay circles
        const isEmergency = ['ambulance', 'police', 'fire_engine'].includes(this.type);
        if (isEmergency) {
            const flash = Math.floor(Date.now() / 130) % 2 === 0;
            ctx.beginPath();
            ctx.arc(0, 0, 18, 0, Math.PI * 2);
            
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
                // Cross markings
                ctx.fillStyle = '#FFFFFF';
                ctx.fillRect(-2, -this.width/2 + 2, 4, this.width - 4);
                ctx.fillRect(-this.height/2 + 3, -2, this.height - 6, 4);
            } else if (this.type === 'police') {
                // Roof bars
                ctx.fillStyle = '#FFFFFF';
                ctx.fillRect(-2, -this.width/2 + 1, 5, this.width - 2);
                ctx.fillStyle = '#1E3A8A';
                ctx.fillRect(0, -this.width/4, 1, this.width/2);
            } else if (this.type === 'fire_engine') {
                // Warning stripes
                ctx.fillStyle = '#F59E0B';
                ctx.fillRect(-this.height/2 + 3, -this.width/2 + 1, 2, this.width - 2);
                ctx.fillRect(this.height/2 - 5, -this.width/2 + 1, 2, this.width - 2);
            }
        } else {
            // Normal vehicle box
            ctx.fillStyle = this.color;
            ctx.fillRect(-this.height/2, -this.width/2, this.height, this.width);
            ctx.fillStyle = 'rgba(0,0,0,0.5)';
            ctx.fillRect(this.height/4, -this.width/2 + 1, 2, this.width - 2);
        }

        if (this.isAccident) {
            // Draw warning hazard flash
            const flash = Math.floor(Date.now() / 250) % 2 === 0;
            ctx.rotate(-angle); // un-rotate to keep text upright
            ctx.beginPath();
            ctx.arc(0, 0, 16, 0, Math.PI * 2);
            ctx.fillStyle = flash ? 'rgba(239, 68, 68, 0.45)' : 'rgba(245, 158, 11, 0.15)';
            ctx.fill();
            
            ctx.fillStyle = '#FFFFFF';
            ctx.font = 'bold 10px var(--font-sans)';
            ctx.textAlign = 'center';
            ctx.fillText("⚠️", 0, 3);
            ctx.rotate(angle); // restore
        }

        ctx.restore();
    }
}

// Initialize Graph Structure (South Bengaluru Junctions)
function initNetwork() {
    nodes = [
        new TrafficNode(0, "Silk Board Junction", 400, 350),
        new TrafficNode(1, "Koramangala 80ft Rd", 560, 230),
        new TrafficNode(2, "HSR Layout Junction", 560, 470),
        new TrafficNode(3, "BTM Layout Junction", 240, 350),
        new TrafficNode(4, "Electronic City Flyover", 400, 500),
        new TrafficNode(5, "Richmond Circle", 400, 200)
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

    addRoad(nodes[5], nodes[0]); // Richmond Circle <-> Silk Board
    addRoad(nodes[3], nodes[0]); // BTM Layout <-> Silk Board
    addRoad(nodes[0], nodes[4]); // Silk Board <-> Electronic City
    addRoad(nodes[1], nodes[0]); // Koramangala <-> Silk Board
    addRoad(nodes[2], nodes[0]); // HSR Layout <-> Silk Board
    
    addRoad(nodes[5], nodes[1]); // Richmond Circle <-> Koramangala
    addRoad(nodes[1], nodes[2]); // Koramangala <-> HSR Layout
    addRoad(nodes[2], nodes[4]); // HSR Layout <-> Electronic City
    addRoad(nodes[4], nodes[3]); // Electronic City <-> BTM Layout
    addRoad(nodes[3], nodes[5]); // BTM Layout <-> Richmond Circle
}

// Spawning Logic
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

// Zoom & Pan Canvas Helpers
function setupCanvas() {
    const parent = canvas.parentElement;
    canvas.width = parent.clientWidth;
    canvas.height = parent.clientHeight;
}

window.addEventListener('resize', () => {
    setupCanvas();
});

// Canvas Pan and Zoom Event Listeners
canvas.addEventListener('mousedown', (e) => {
    isDragging = true;
    startDragX = e.clientX - offsetX;
    startDragY = e.clientY - offsetY;
});

window.addEventListener('mousemove', (e) => {
    if (isDragging) {
        offsetX = e.clientX - startDragX;
        offsetY = e.clientY - startDragY;
    }
});

canvas.addEventListener('mouseup', (e) => {
    isDragging = false;
    
    const dragDist = Math.hypot(e.clientX - startDragX - offsetX, e.clientY - startDragY - offsetY);
    if (dragDist < 5) {
        const rect = canvas.getBoundingClientRect();
        const clickX = (e.clientX - rect.left - offsetX) / zoom;
        const clickY = (e.clientY - rect.top - offsetY) / zoom;
        
        let clickedNode = null;
        nodes.forEach(n => {
            const dist = Math.hypot(n.x - clickX, n.y - clickY);
            if (dist < n.radius + 10) {
                clickedNode = n;
            }
        });

        if (clickedNode) {
            selectedNodeId = clickedNode.id;
            updateCVFeedJunction(clickedNode);
        }
    }
});

canvas.addEventListener('wheel', (e) => {
    e.preventDefault();
    const zoomFactor = 1.1;
    if (e.deltaY < 0) {
        zoom *= zoomFactor;
    } else {
        zoom /= zoomFactor;
    }
    zoom = Math.max(0.5, Math.min(3.0, zoom));
});

document.getElementById('btn-zoom-in').addEventListener('click', () => {
    zoom = Math.min(3.0, zoom * 1.2);
});

document.getElementById('btn-zoom-out').addEventListener('click', () => {
    zoom = Math.max(0.5, zoom / 1.2);
});

document.getElementById('btn-reset').addEventListener('click', () => {
    zoom = 1.0;
    offsetX = 0;
    offsetY = 0;
});

// Main Loop
function updateSim() {
    runTime += 1 / 60;
    
    // Spawn Vehicles based on spawnRate
    spawnTimer++;
    const framesPerSpawn = (60 * 60) / spawnRate;
    if (spawnTimer >= framesPerSpawn) {
        const roll = Math.random();
        let type = 'car';
        if (roll < 0.22) type = 'bike';
        else if (roll < 0.31) type = 'bus';
        else if (roll < 0.33) {
            // Organically spawn emergency vehicles 
            const types = ['ambulance', 'police', 'fire_engine'];
            type = types[Math.floor(Math.random() * types.length)];
        }
        
        // Safety cap: Prevent browser slowdown or crash under heavy congestion by limiting active vehicles
        if (vehicles.length < 180) {
            spawnVehicle(type);
        }
        spawnTimer = 0;
    }

    // Update Nodes (Signals and Arbitration)
    nodes.forEach(n => n.updateSignal());

    // Update Vehicles
    vehicles.forEach(v => v.update());

    // Clear and redraw canvas
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    
    ctx.save();
    ctx.translate(offsetX, offsetY);
    ctx.scale(zoom, zoom);

    // Draw grid lines in background
    ctx.strokeStyle = 'rgba(255, 255, 255, 0.012)';
    ctx.lineWidth = 1;
    const gridSize = 40;
    for (let x = -2000; x < 2000; x += gridSize) {
        ctx.beginPath();
        ctx.moveTo(x, -2000);
        ctx.lineTo(x, 2000);
        ctx.stroke();
    }
    for (let y = -2000; y < 2000; y += gridSize) {
        ctx.beginPath();
        ctx.moveTo(-2000, y);
        ctx.lineTo(2000, y);
        ctx.stroke();
    }

    // Draw Edges
    edges.forEach(e => e.draw());

    // Draw Nodes
    nodes.forEach(n => n.draw());

    // Draw Vehicles
    vehicles.forEach(v => v.draw());

    ctx.restore();
    
    requestAnimationFrame(updateSim);
}

// Initialization trigger
initNetwork();
setupCanvas();
requestAnimationFrame(updateSim);

// Expose elements globally
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
    // Spawn a random emergency vehicle on outer borders
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
        window.addIncidentLog(`CRASH DETECTED: Accident on ${roadName} involving vehicle #${target.id}. Dispatching rescue...`, "var(--traffic-red)");
    }
    
    // Spawn rescue ambulance
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
