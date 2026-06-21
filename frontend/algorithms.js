// Core Algorithms: Max-Pressure Traffic Control, Dijkstra/A* Routing, and Multi-Emergency Priority Arbitration
// 

// --- Binary Min-Heap Priority Queue for Optimized DSA Routing ---
// Space Complexity: O(N)
// Operations (Insert, ExtractMin): O(log N)
class MinHeap {
    constructor() {
        this.heap = [];
    }

    insert(key, value) {
        this.heap.push({ key, value });
        this.bubbleUp(this.heap.length - 1);
    }

    extractMin() {
        if (this.heap.length === 0) return null;
        const min = this.heap[0];
        const end = this.heap.pop();
        if (this.heap.length > 0) {
            this.heap[0] = end;
            this.sinkDown(0);
        }
        return min;
    }

    isEmpty() {
        return this.heap.length === 0;
    }

    bubbleUp(idx) {
        const element = this.heap[idx];
        while (idx > 0) {
            let parentIdx = Math.floor((idx - 1) / 2);
            let parent = this.heap[parentIdx];
            if (element.value >= parent.value) break;
            this.heap[idx] = parent;
            idx = parentIdx;
        }
        this.heap[idx] = element;
    }

    sinkDown(idx) {
        const length = this.heap.length;
        const element = this.heap[idx];
        while (true) {
            let leftChildIdx = 2 * idx + 1;
            let rightChildIdx = 2 * idx + 2;
            let leftChild, rightChild;
            let swap = null;

            if (leftChildIdx < length) {
                leftChild = this.heap[leftChildIdx];
                if (leftChild.value < element.value) {
                    swap = leftChildIdx;
                }
            }

            if (rightChildIdx < length) {
                rightChild = this.heap[rightChildIdx];
                if (
                    (swap === null && rightChild.value < element.value) || 
                    (swap !== null && rightChild.value < leftChild.value)
                ) {
                    swap = rightChildIdx;
                }
            }

            if (swap === null) break;
            this.heap[idx] = this.heap[swap];
            idx = swap;
        }
        this.heap[idx] = element;
    }
}

const TrafficAlgorithms = {
    // 1. Max-Pressure Signal Control Policy
    // Selects the phase that maximizes clearing pressure (inflow queue - outflow capacity).
    // Time Complexity: O(1) per evaluation (constant number of phases/lanes)
    calculateMaxPressurePhase: function(node, edgesList) {
        const phases = [0, 1]; // Phase 0: North-South, Phase 1: East-West
        let maxPressureVal = -Infinity;
        let selectedPhase = node.activePhase;

        phases.forEach(phase => {
            let incomingQueue = 0;
            let outgoingQueue = 0;

            // Find all incoming edges for this phase
            node.incomingEdges.forEach(edgeId => {
                const edge = edgesList.find(e => e.id === edgeId);
                if (edge && this.getPhaseForEdge(node, edge, edgesList) === phase) {
                    incomingQueue += edge.getQueueLength();
                }
            });

            // Find all outgoing edges
            node.outgoingEdges.forEach(edgeId => {
                const edge = edgesList.find(e => e.id === edgeId);
                if (edge) {
                    // Queue downstream decreases our pressure (blocks flow)
                    outgoingQueue += edge.getQueueLength() * 0.5;
                }
            });

            const pressure = Math.max(0, incomingQueue - outgoingQueue);
            if (pressure > maxPressureVal) {
                maxPressureVal = pressure;
                selectedPhase = phase;
            }
        });

        return {
            phase: selectedPhase,
            pressure: maxPressureVal
        };
    },

    // Helper: Determine phase of an incoming edge based on angle
    getPhaseForEdge: function(node, edge, edgesList) {
        const dx = node.x - edge.startNode.x;
        const dy = node.y - edge.startNode.y;
        const angle = Math.abs(Math.atan2(dy, dx) * 180 / Math.PI);
        
        // Horizontal edges (0 to 45 or 135 to 180 deg) map to Phase 1 (East-West)
        if ((angle >= 0 && angle < 45) || (angle >= 135 && angle <= 180)) {
            return 1;
        } else {
            return 0; // Phase 0 (North-South)
        }
    },

    // 2. Dynamic Weight Calculation for Routing
    // In a smart city, graph edge weights update with real-time density and queue status
    calculateEdgeWeight: function(edge, vehiclesList) {
        const vehiclesOnEdge = vehiclesList.filter(v => v.currentEdgeId === edge.id);
        const queueCount = vehiclesOnEdge.filter(v => v.speed < 0.2).length;
        
        // Base weight is physical length of road (distance between junctions)
        const baseDistance = Math.hypot(edge.endNode.x - edge.startNode.x, edge.endNode.y - edge.startNode.y);
        
        // Travel time penalty is proportional to queue length
        const penalty = queueCount * 45; // 45 pixels of delay per queued vehicle
        
        return baseDistance + penalty;
    },

    // 3. Dijkstra's Algorithm for Shortest Path Routing (Min-Heap Optimized)
    // Complexity: O((|V| + |E|) * log |V|)
    findOptimalPath: function(startNodeId, endNodeId, nodesList, edgesList, vehiclesList) {
        const distances = {};
        const previous = {};
        const heap = new MinHeap();
        const visited = new Set();

        nodesList.forEach(node => {
            distances[node.id] = Infinity;
            previous[node.id] = null;
        });
        distances[startNodeId] = 0;
        heap.insert(startNodeId, 0);

        while (!heap.isEmpty()) {
            const minNode = heap.extractMin();
            const currentNodeId = minNode.key;

            if (visited.has(currentNodeId)) continue;
            visited.add(currentNodeId);

            if (currentNodeId === endNodeId) {
                break;
            }

            const currentNode = nodesList.find(n => n.id === currentNodeId);
            if (!currentNode) continue;

            // Check neighbors
            currentNode.outgoingEdges.forEach(edgeId => {
                const edge = edgesList.find(e => e.id === edgeId);
                if (edge) {
                    const neighborId = edge.endNode.id;
                    if (!visited.has(neighborId)) {
                        const weight = this.calculateEdgeWeight(edge, vehiclesList);
                        const alt = distances[currentNodeId] + weight;
                        if (alt < distances[neighborId]) {
                            distances[neighborId] = alt;
                            previous[neighborId] = currentNodeId;
                            heap.insert(neighborId, alt);
                        }
                    }
                }
            });
        }

        // Reconstruct path
        const path = [];
        let u = endNodeId;
        while (u !== null) {
            path.unshift(u);
            u = previous[u];
        }

        return path.length > 1 && path[0] === startNodeId ? path : null;
    },

    // 4. A* Search Algorithm for Route Optimization (Min-Heap + Spatial Heuristic)
    // Complexity: O((|V| + |E|) * log |V|) - average case expanded nodes are far fewer than Dijkstra
    findOptimalPathAStar: function(startNodeId, endNodeId, nodesList, edgesList, vehiclesList) {
        const destNode = nodesList.find(n => n.id === endNodeId);
        if (!destNode) return this.findOptimalPath(startNodeId, endNodeId, nodesList, edgesList, vehiclesList);

        const distances = {};
        const previous = {};
        const heap = new MinHeap();
        const visited = new Set();

        nodesList.forEach(node => {
            distances[node.id] = Infinity;
            previous[node.id] = null;
        });
        distances[startNodeId] = 0;

        // Heuristic: Euclidean distance to destination
        const getHeuristic = (nodeId) => {
            const node = nodesList.find(n => n.id === nodeId);
            if (!node) return 0;
            return Math.hypot(destNode.x - node.x, destNode.y - node.y);
        };

        // Insert start node with heuristic cost f(n) = g(n) + h(n) = 0 + h(start)
        heap.insert(startNodeId, getHeuristic(startNodeId));

        let nodesExpanded = 0;

        while (!heap.isEmpty()) {
            const minNode = heap.extractMin();
            const currentNodeId = minNode.key;

            if (visited.has(currentNodeId)) continue;
            visited.add(currentNodeId);
            nodesExpanded++;

            if (currentNodeId === endNodeId) {
                break;
            }

            const currentNode = nodesList.find(n => n.id === currentNodeId);
            if (!currentNode) continue;

            currentNode.outgoingEdges.forEach(edgeId => {
                const edge = edgesList.find(e => e.id === edgeId);
                if (edge) {
                    const neighborId = edge.endNode.id;
                    if (!visited.has(neighborId)) {
                        const weight = this.calculateEdgeWeight(edge, vehiclesList);
                        const gScore = distances[currentNodeId] + weight;
                        
                        if (gScore < distances[neighborId]) {
                            distances[neighborId] = gScore;
                            previous[neighborId] = currentNodeId;
                            
                            // f(n) = g(n) + h(n)
                            const fScore = gScore + getHeuristic(neighborId);
                            heap.insert(neighborId, fScore);
                        }
                    }
                }
            });
        }

        // Reconstruct path
        const path = [];
        let u = endNodeId;
        while (u !== null) {
            path.unshift(u);
            u = previous[u];
        }

        // Log A* performance compared to Dijkstra
        if (window.logAStarPerformance) {
            window.logAStarPerformance(nodesExpanded);
        }

        return path.length > 1 && path[0] === startNodeId ? path : null;
    },

    // 5. Emergency Arbitration & Corridor Routing
    // Handles multi-emergency vehicle situations by prioritizing based on:
    //   - Emergency vehicle type (Fire Engine > Ambulance > Police)
    //   - Current queue lengths at incoming lanes
    //   - Waiting times of the emergency vehicles
    arbitrateJunctionEmergencies: function(node, edgesList, vehiclesList) {
        // Find all emergency vehicles in the system
        const emergencies = vehiclesList.filter(v => 
            ['ambulance', 'police', 'fire_engine'].includes(v.type)
        );

        if (emergencies.length === 0) {
            node.emergencyOverride = false;
            node.emergencyIncomingEdge = null;
            node.arbitrationMessage = "";
            return;
        }

        // Filter emergency vehicles approaching this node on an incoming edge
        const approaching = [];
        emergencies.forEach(ev => {
            if (node.incomingEdges.includes(ev.currentEdgeId) && ev.progress < 0.98) {
                approaching.push(ev);
            }
        });

        if (approaching.length === 0) {
            // Check if this node is in the lookahead path of any emergency vehicles to prepare "green wave"
            let lookaheadEdgeId = null;
            let lookaheadEV = null;
            
            emergencies.forEach(ev => {
                const path = ev.path;
                const edge = edgesList.find(e => e.id === ev.currentEdgeId);
                if (edge && path) {
                    const nextNode = edge.endNode;
                    const nextNodeIdx = path.indexOf(nextNode.id);
                    if (nextNodeIdx !== -1 && nextNodeIdx < path.length - 1) {
                        const lookaheadNodeId = path[nextNodeIdx + 1];
                        if (lookaheadNodeId === node.id) {
                            lookaheadEdgeId = edgesList.find(e => e.startNode.id === nextNode.id && e.endNode.id === lookaheadNodeId)?.id;
                            lookaheadEV = ev;
                        }
                    }
                }
            });

            if (lookaheadEdgeId) {
                node.emergencyOverride = true;
                node.emergencyIncomingEdge = lookaheadEdgeId;
                node.arbitrationMessage = `Preempting for approaching ${lookaheadEV.type.toUpperCase()}`;
            } else {
                node.emergencyOverride = false;
                node.emergencyIncomingEdge = null;
                node.arbitrationMessage = "";
            }
            return;
        }

        // Multi-emergency arbitration scoring:
        // Score = TypePriority * 1000 + QueueLength * 10 + WaitTimeSeconds
        const scoredVehicles = approaching.map(ev => {
            let typePriority = 1; // Default police
            if (ev.type === 'fire_engine') typePriority = 3;
            else if (ev.type === 'ambulance') typePriority = 2;

            const edge = edgesList.find(e => e.id === ev.currentEdgeId);
            const queueLength = edge ? edge.getQueueLength() : 0;
            const waitTime = ev.waitTicks / 60; // seconds

            const score = typePriority * 1000 + queueLength * 15 + waitTime;
            return { vehicle: ev, score: score, edgeId: ev.currentEdgeId };
        });

        // Sort descending by score
        scoredVehicles.sort((a, b) => b.score - a.score);

        // Select the winning emergency vehicle to grant immediate green wave clearance
        const winner = scoredVehicles[0];
        node.emergencyOverride = true;
        node.emergencyIncomingEdge = winner.edgeId;
        
        if (scoredVehicles.length > 1) {
            const conflictDetails = scoredVehicles.map(sv => `${sv.vehicle.type.toUpperCase()} (Score: ${sv.score.toFixed(0)})`).join(', ');
            node.arbitrationMessage = `Conflict Resolved: Clearing ${winner.vehicle.type.toUpperCase()} first. Queue: [${conflictDetails}]`;
        } else {
            node.arbitrationMessage = `Clearing corridor for active ${winner.vehicle.type.toUpperCase()}`;
        }
    }
};

// Bind to window context
window.MinHeap = MinHeap;
window.TrafficAlgorithms = TrafficAlgorithms;
