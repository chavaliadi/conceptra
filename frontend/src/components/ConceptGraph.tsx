import { useCallback, useMemo } from 'react'
import ReactFlow, {
    Controls,
    Background,
    useNodesState,
    useEdgesState,
    MarkerType,
} from 'reactflow'
import 'reactflow/dist/style.css'
import type { Plan, Concept, ConceptStatus, ConceptProgressDetail } from '../types'

interface ConceptGraphProps {
    plan: Plan
    statuses: Record<string, ConceptStatus>
    progressDetails?: Record<string, ConceptProgressDetail>
    onSelectConcept: (concept: Concept) => void
    onSelectEdge: (fromId: string, toId: string, fromName: string, toName: string) => void
}

type GraphNodeStatus = 'blocked' | 'ready' | 'learned' | 'struggling' | 'forgotten' | 'skipped'

const statusColors: Record<GraphNodeStatus, { bg: string; border: string; text: string }> = {
    blocked: { bg: '#0f172a', border: '#1e293b', text: '#475569' },
    ready: { bg: '#172554', border: '#3b82f6', text: '#93c5fd' },
    learned: { bg: '#022c22', border: '#10b981', text: '#34d399' },
    struggling: { bg: '#451a03', border: '#f59e0b', text: '#fbbf24' },
    forgotten: { bg: '#2e1065', border: '#8b5cf6', text: '#ddd6fe' },
    skipped: { bg: '#4c0519', border: '#ef4444', text: '#f87171' },
}

export default function ConceptGraph({ plan, statuses, progressDetails, onSelectConcept, onSelectEdge }: ConceptGraphProps) {
    // Convert concepts to nodes using a hierarchical level layout
    const nodes = useMemo(() => {
        // 1. Build adjacency list & count in-degrees
        const adj: Record<string, string[]> = {}
        const inDegree: Record<string, number> = {}
        plan.graph.concepts.forEach(c => {
            adj[c.id] = []
            inDegree[c.id] = 0
        })
        plan.graph.edges.forEach(e => {
            if (adj[e.from_id]) {
                adj[e.from_id].push(e.to_id)
                inDegree[e.to_id] = (inDegree[e.to_id] || 0) + 1
            }
        })

        // 2. Compute topological levels using BFS (Kahn's style)
        const levels: Record<string, number> = {}
        let queue: string[] = plan.graph.concepts.filter(c => inDegree[c.id] === 0).map(c => c.id)

        let currentLevel = 0
        while (queue.length > 0) {
            const nextQueue: string[] = []
            queue.forEach(cid => {
                levels[cid] = currentLevel
                adj[cid]?.forEach(neighbor => {
                    inDegree[neighbor]--
                    if (inDegree[neighbor] === 0) {
                        nextQueue.push(neighbor)
                    }
                })
            })
            queue = nextQueue
            currentLevel++
        }

        // Fallback for unvisited nodes (if cycle exists)
        plan.graph.concepts.forEach(c => {
            if (levels[c.id] === undefined) {
                levels[c.id] = 0
            }
        })

        // Group concepts by level to center them horizontally
        const levelGroups: Record<number, string[]> = {}
        plan.graph.concepts.forEach(c => {
            const lvl = levels[c.id]
            if (!levelGroups[lvl]) {
                levelGroups[lvl] = []
            }
            levelGroups[lvl].push(c.id)
        })

        // Determine X & Y coordinate layout
        const positions: Record<string, { x: number; y: number }> = {}
        Object.entries(levelGroups).forEach(([lvlStr, ids]) => {
            const lvl = parseInt(lvlStr)
            const y = 80 + lvl * 150 // Vertical separation of 150px
            const totalWidth = (ids.length - 1) * 220 // Horizontal separation of 220px
            ids.forEach((id, idx) => {
                const x = ids.length === 1 ? 400 : 400 - (totalWidth / 2) + (idx * 220)
                positions[id] = { x, y }
            })
        })

        // Helper: Check if concept is blocked by incomplete prerequisites
        const isBlocked = (conceptId: string) => {
            const prereqs = plan.graph.edges
                .filter(e => e.to_id === conceptId)
                .map(e => e.from_id)
            if (prereqs.length === 0) return false
            return prereqs.some(pid => {
                const pStatus = statuses[pid] ?? 'untouched'
                return pStatus !== 'learned' && pStatus !== 'skipped'
            })
        }

        // Helper: Check if concept is forgotten due to decay or overdue SM-2 review
        const isForgotten = (conceptId: string) => {
            const detail = progressDetails?.[conceptId]
            if (!detail) return false
            if (detail.status !== 'learned') return false
            const isRetentionDecayed = detail.retention_pct < 50
            const isOverdue = detail.next_review_at ? new Date(detail.next_review_at) <= new Date() : false
            return isRetentionDecayed || isOverdue
        }

        return plan.graph.concepts.map((concept) => {
            const baseStatus = statuses[concept.id] ?? 'untouched'

            // Map base DB statuses into dynamic graph states
            let computedStatus: GraphNodeStatus = 'untouched' as any
            if (baseStatus === 'skipped') {
                computedStatus = 'skipped'
            } else if (baseStatus === 'struggling') {
                computedStatus = 'struggling'
            } else if (baseStatus === 'learned') {
                computedStatus = isForgotten(concept.id) ? 'forgotten' : 'learned'
            } else {
                computedStatus = isBlocked(concept.id) ? 'blocked' : 'ready'
            }

            const colors = statusColors[computedStatus]
            const position = positions[concept.id] ?? { x: 400, y: 100 }

            return {
                id: concept.id,
                data: { label: concept.name },
                position,
                style: {
                    background: colors.bg,
                    border: `2px solid ${colors.border}`,
                    borderRadius: '12px',
                    padding: '16px',
                    width: '180px',
                    textAlign: 'center' as const,
                    fontSize: '12px',
                    fontWeight: '600',
                    color: colors.text,
                    cursor: 'pointer',
                    boxShadow: computedStatus === 'learned'
                        ? '0 0 15px rgba(16, 185, 129, 0.25)'
                        : computedStatus === 'ready'
                        ? '0 0 15px rgba(59, 130, 246, 0.2)'
                        : computedStatus === 'forgotten'
                        ? '0 0 15px rgba(139, 92, 246, 0.25)'
                        : 'none',
                    opacity: computedStatus === 'blocked' ? 0.5 : 1,
                    transition: 'all 200ms',
                },
            }
        })
    }, [plan.graph.concepts, plan.graph.edges, statuses, progressDetails])

    // Convert edges to react-flow edges with status-aware brightening
    const edges = useMemo(() => {
        return plan.graph.edges.map((edge) => {
            const isMastered = statuses[edge.from_id] === 'learned' && statuses[edge.to_id] === 'learned'

            return {
                id: `${edge.from_id}-${edge.to_id}`,
                source: edge.from_id,
                target: edge.to_id,
                markerEnd: {
                    type: MarkerType.ArrowClosed,
                    color: isMastered ? '#10b981' : '#475569',
                },
                style: {
                    stroke: isMastered ? '#10b981' : '#475569',
                    strokeWidth: isMastered ? 3 : 1.5,
                },
                animated: isMastered,
            }
        })
    }, [plan.graph.edges, statuses])

    const [reactFlowNodes, setNodes] = useNodesState(nodes)
    const [reactFlowEdges, setEdges] = useEdgesState(edges)

    // Sync state when props change
    useMemo(() => {
        setNodes(nodes)
        setEdges(edges)
    }, [nodes, edges, setNodes, setEdges])

    // Handle node click
    const onNodeClick = useCallback(
        (_event: React.MouseEvent, node: any) => {
            const concept = plan.graph.concepts.find((c) => c.id === node.id)
            if (concept) {
                onSelectConcept(concept)
            }
        },
        [plan.graph.concepts, onSelectConcept],
    )

    // Handle edge click
    const onEdgeClick = useCallback(
        (_event: React.MouseEvent, edge: any) => {
            const fromConcept = plan.graph.concepts.find((c) => c.id === edge.source)
            const toConcept = plan.graph.concepts.find((c) => c.id === edge.target)
            if (fromConcept && toConcept) {
                onSelectEdge(fromConcept.id, toConcept.id, fromConcept.name, toConcept.name)
            }
        },
        [plan.graph.concepts, onSelectEdge],
    )

    return (
        <div className="h-full rounded-2xl border border-slate-900 bg-slate-950 overflow-hidden relative">
            <ReactFlow
                nodes={reactFlowNodes}
                edges={reactFlowEdges}
                onNodesChange={() => { }}
                onEdgesChange={() => { }}
                onNodeClick={onNodeClick}
                onEdgeClick={onEdgeClick}
                fitView
            >
                <Background color="#1e293b" gap={18} size={1} />
                <Controls position="bottom-right" />
            </ReactFlow>
            <div className="absolute bottom-6 left-6 text-xs text-slate-500 max-w-xs pointer-events-none p-3 bg-slate-950/80 border border-slate-900 rounded-xl backdrop-blur-sm">
                <p className="font-semibold text-slate-400 mb-1">Legend:</p>
                <div className="space-y-1">
                    <div className="flex items-center gap-2">
                        <div className="w-3 h-3 rounded" style={{ backgroundColor: statusColors.learned.bg, border: `1px solid ${statusColors.learned.border}` }} />
                        <span>Mastered</span>
                    </div>
                    <div className="flex items-center gap-2">
                        <div className="w-3 h-3 rounded" style={{ backgroundColor: statusColors.struggling.bg, border: `1px solid ${statusColors.struggling.border}` }} />
                        <span>Struggling</span>
                    </div>
                    <div className="flex items-center gap-2">
                        <div className="w-3 h-3 rounded" style={{ backgroundColor: statusColors.forgotten.bg, border: `1px solid ${statusColors.forgotten.border}` }} />
                        <span>Forgotten (Due Review)</span>
                    </div>
                    <div className="flex items-center gap-2">
                        <div className="w-3 h-3 rounded" style={{ backgroundColor: statusColors.ready.bg, border: `1px solid ${statusColors.ready.border}` }} />
                        <span>Ready to Learn</span>
                    </div>
                    <div className="flex items-center gap-2">
                        <div className="w-3 h-3 rounded" style={{ backgroundColor: statusColors.blocked.bg, border: `1px solid ${statusColors.blocked.border}`, opacity: 0.5 }} />
                        <span>Blocked (Prereqs remain)</span>
                    </div>
                </div>
            </div>
        </div>
    )
}

