import React from 'react'

export default function InsufficientEvidence({ failure, trace }) {
  return (
    <section className="card failure">
      <h2>⚠ Insufficient evidence</h2>
      <p className="headline">{failure.message}</p>
      <p className="detail">{failure.detail}</p>
      <div className="badge bad">Failure type: {failure.kind}</div>
      <ol className="trace">
        {trace.steps.map(s => (
          <li key={s.step}>
            <div className="step-num">{s.step}</div>
            <div className="step-body">
              <div className="step-name">{s.name}</div>
              <div className="step-val">
                {Array.isArray(s.value) ? s.value.join(', ')
                  : typeof s.value === 'object' && s.value !== null
                    ? JSON.stringify(s.value)
                    : String(s.value ?? '—')}
              </div>
              {s.detail && <div className="step-detail">{s.detail}</div>}
            </div>
          </li>
        ))}
      </ol>
    </section>
  )
}