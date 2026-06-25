import { useCallback, useMemo } from 'react'
import ReactFlow, {
    Controls,
    Background,
    useNodesState,
    useEdgesState,
    MarkerType,
} from 'reactflow'
import 'reactflow/dist/style.css'
import type { Plan, Concept, ConceptStatus } from '../types'

interface ConceptGraphProps {
    plan: Plan
    statuses: Record<string, ConceptStatus>
    onSelectConcept: (concept: Concept) => void
    onSelectEdge: (fromId: string, toId: string, fromName: string, toName: string) => void
}

const statusColors: Record<ConceptStatus, { bg: string; border: string; text: string }> = {
    untouched: { bg: '#0f172a', border: '#334155', text: '#94a3b8' },
    learned: { bg: '#064e3b', border: '#10b981', text: '#34d399' },
    struggling: { bg: '#78350f', border: '#f59e0b', text: '#fbbf24' },
    skipped: { bg: '#4c0519', border: '#ef4444', text: '#f87171' },
}

export default function ConceptGraph({ plan, statuses, onSelectConcept, onSelectEdge }: ConceptGraphProps) {
    // Convert concepts to nodes
    const nodes = useMemo(() => {
        return plan.graph.concepts.map((concept, idx) => {
            const status = statuses[concept.id] ?? 'untouched'
            const colors = statusColors[status]

            return {
                id: concept.id,
                data: { label: concept.name },
                position: {
                    x: 400 + 300 * Math.cos((idx / plan.graph.concepts.length) * 2 * Math.PI),
                    y: 300 + 300 * Math.sin((idx / plan.graph.concepts.length) * 2 * Math.PI),
                },
                style: {
                    background: colors.bg,
                    border: `2px solid ${colors.border}`,
                    borderRadius: '12px',
                    padding: '16px',
                    width: '140px',
                    textAlign: 'center' as const,
                    fontSize: '12px',
                    fontWeight: '600',
                    color: colors.text,
                    cursor: 'pointer',
                    boxShadow: status === 'learned' ? '0 0 15px rgba(16, 185, 129, 0.25)' : 'none',
                    transition: 'all 200ms',
                },
            }
        })
    }, [plan.graph.concepts, statuses])

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
                        <span>Learned (Mastered)</span>
                    </div>
                    <div className="flex items-center gap-2">
                        <div className="w-3 h-3 rounded" style={{ backgroundColor: statusColors.struggling.bg, border: `1px solid ${statusColors.struggling.border}` }} />
                        <span>Struggling</span>
                    </div>
                    <div className="flex items-center gap-2">
                        <div className="w-3 h-3 rounded" style={{ backgroundColor: statusColors.untouched.bg, border: `1px solid ${statusColors.untouched.border}` }} />
                        <span>Untouched</span>
                    </div>
                </div>
            </div>
        </div>
    )
}
