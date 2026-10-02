import React from 'react'

export default function EvidencePanel({ evidence }) {
  return (
    <section className="card">
      <h2>Evidence</h2>
      <div className="kv">
        <div><span>Rows used</span><strong>{evidence.row_count_used}</strong></div>
        <div><span>Columns used</span><strong>{evidence.columns_used.join(', ') || '—'}</strong></div>
      </div>
      {evidence.table?.length > 0 && (
        <table>
          <thead>
            <tr>{Object.keys(evidence.table[0]).map(k => <th key={k}>{k}</th>)}</tr>
          </thead>
          <tbody>
            {evidence.table.slice(0, 20).map((r, i) => (
              <tr key={i}>{Object.keys(r).map(k => <td key={k}>{String(r[k])}</td>)}</tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  )
}