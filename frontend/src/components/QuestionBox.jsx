import React from 'react'

export default function QuestionBox({ value, onChange, onSubmit, loading }) {
  return (
    <section className="card">
      <h2>2. Ask a business question</h2>
      <div className="row">
        <input
          type="text"
          placeholder="e.g. Why did revenue decrease in July?"
          value={value}
          onChange={e => onChange(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && onSubmit()}
        />
        <button onClick={onSubmit} disabled={loading}>
          {loading ? 'Analyzing…' : 'Ask'}
        </button>
      </div>
    </section>
  )
}