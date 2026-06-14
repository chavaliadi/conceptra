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
}

const statusColors: Record<ConceptStatus, { bg: string; border: string; text: string }> = {
    untouched: { bg: '#1e293b', border: '#475569', text: '#cbd5e1' },
    learned: { bg: '#064e3b', border: '#10b981', text: '#10b981' },
    struggling: { bg: '#78350f', border: '#f59e0b', text: '#f59e0b' },
    skipped: { bg: '#4c0519', border: '#ef4444', text: '#ef4444' },
}

export default function ConceptGraph({ plan, statuses, onSelectConcept }: ConceptGraphProps) {
    // Convert concepts to nodes
    const nodes = useMemo(() => {
        return plan.graph.concepts.map((concept, idx) => {
            const status = statuses[concept.id] ?? 'untouched'
            const colors = statusColors[status]

            return {
                id: concept.id,
                data: { label: concept.name },
                position: {
                    // Simple circular layout based on index
                    x: 400 + 300 * Math.cos((idx / plan.graph.concepts.length) * 2 * Math.PI),
                    y: 300 + 300 * Math.sin((idx / plan.graph.concepts.length) * 2 * Math.PI),
                },
                style: {
                    background: colors.bg,
                    border: `2px solid ${colors.border}`,
                    borderRadius: '8px',
                    padding: '16px',
                    width: '140px',
                    textAlign: 'center' as const,
                    fontSize: '12px',
                    fontWeight: '500',
                    color: colors.text,
                    cursor: 'pointer',
                    transition: 'all 200ms',
                },
            }
        })
    }, [plan.graph.concepts, statuses])

    // Convert edges to react-flow edges
    const edges = useMemo(() => {
        return plan.graph.edges.map((edge) => ({
            id: `${edge.from_id}-${edge.to_id}`,
            source: edge.from_id,
            target: edge.to_id,
            markerEnd: { type: MarkerType.ArrowClosed },
            style: { stroke: '#64748b', strokeWidth: 2 },
            animated: false,
        }))
    }, [plan.graph.edges])

    const [reactFlowNodes, setNodes] = useNodesState(nodes)
    const [reactFlowEdges, setEdges] = useEdgesState(edges)

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

    return (
        <div className="h-full rounded-2xl border border-slate-800 bg-slate-950 overflow-hidden">
            <ReactFlow
                nodes={reactFlowNodes}
                edges={reactFlowEdges}
                onNodesChange={() => { }}
                onEdgesChange={() => { }}
                onNodeClick={onNodeClick}
                fitView
            >
                <Background color="#334155" gap={16} size={1} />
                <Controls position="bottom-right" />
            </ReactFlow>
            <div className="absolute bottom-20 left-6 text-xs text-slate-500 max-w-xs pointer-events-none">
                <p className="font-semibold text-slate-400 mb-1">Legend:</p>
                <div className="space-y-1">
                    <div className="flex items-center gap-2">
                        <div className="w-3 h-3 rounded" style={{ backgroundColor: statusColors.learned.bg, border: `1px solid ${statusColors.learned.border}` }} />
                        <span>Learned</span>
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
