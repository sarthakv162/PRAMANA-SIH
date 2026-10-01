import { useMemo, useState } from 'react';
import { Background, Controls, MiniMap, ReactFlow, type Edge, type Node } from '@xyflow/react';
import dagre from 'dagre';
import '@xyflow/react/dist/style.css';
import type { DecisionPath, EvidenceSpan } from '../api/types';
import { EvidenceDrawer, Panel } from './ui';

export function DecisionPathView({ path, evidence }: { path: DecisionPath; evidence: Record<string, EvidenceSpan> }) {
  const [selected, setSelected] = useState<EvidenceSpan | null>(null);
  const { nodes, edges } = useMemo(() => {
    const graph = new dagre.graphlib.Graph(); graph.setDefaultEdgeLabel(() => ({})); graph.setGraph({ rankdir: 'TB', nodesep: 30, ranksep: 60 });
    const width = 250; const height = 96;
    path.nodes.forEach((node) => graph.setNode(node.id, { width, height }));
    path.edges.forEach((edge) => graph.setEdge(edge.from, edge.to)); dagre.layout(graph);
    const nodes: Node[] = path.nodes.map((node) => { const pos = graph.node(node.id); return { id: node.id, position: { x: pos.x - width / 2, y: pos.y - height / 2 }, data: { label: <div className={`decision-node ${node.id === path.outcome_id ? 'outcome-node' : ''}`}><small>{node.kind}</small><b>{node.label}</b>{node.value && <span>{node.value}</span>}</div> }, style: { width, height, padding: 0, border: 'none', background: 'transparent', boxShadow: 'none' } }; });
    const edges: Edge[] = path.edges.map((edge, index) => ({ id: `${edge.from}-${edge.to}-${index}`, source: edge.from, target: edge.to, label: edge.label, animated: false, style: { stroke: '#759384', strokeWidth: 2 }, labelStyle: { fill: '#52695b', fontSize: 12 }, type: 'smoothstep' }));
    return { nodes, edges };
  }, [path]);
  return <><Panel className="decision-panel"><div className="section-title"><div><span className="eyebrow">TRACEABLE RULE OUTPUT</span><h2>Decision path</h2></div><span className="small-muted">Taken path</span></div>{nodes.length ? <div className="flow-wrap"><ReactFlow nodes={nodes} edges={edges} fitView minZoom={0.5} maxZoom={1.5} nodesDraggable={false} nodesConnectable={false} onNodeClick={(_, node) => { const sourceId = path.nodes.find((item) => item.id === node.id)?.evidence_ids[0]; setSelected(sourceId ? evidence[sourceId] ?? null : null); }}><Background color="#e8ece7" gap={20} /><Controls showInteractive={false} /><MiniMap nodeColor="#527663" maskColor="rgba(248,249,247,.65)" /></ReactFlow></div> : <p className="small-muted">No decision path was returned.</p>}{nodes.some((node) => path.nodes.find((item) => item.id === node.id)?.evidence_ids.length) && <p className="small-muted">Select a cited node to inspect its evidence.</p>}</Panel><EvidenceDrawer evidence={selected} onClose={() => setSelected(null)} /></>;
}
