import React from 'react'

export default function Upload({ onUpload, dataset }) {
  return (
    <section className="card">
      <h2>1. Upload your dataset</h2>
      <input
        type="file"
        accept=".csv,.xlsx,.xls"
        onChange={e => e.target.files[0] && onUpload(e.target.files[0])}
      />
      {dataset && (
        <div className="meta">
          <div><strong>{dataset.name}</strong> — {dataset.rows} rows × {dataset.columns.length} cols</div>
          <div className="chips">
            {dataset.columns.map(c => <span key={c} className="chip">{c}</span>)}
          </div>
        </div>
      )}
    </section>
  )
}