import React from 'react'
import { BarChart, Bar, LineChart, Line, XAxis, YAxis, Tooltip, CartesianGrid, ResponsiveContainer } from 'recharts'

export default function ChartView({ chart }) {
  if (!chart || !chart.points?.length) return null
  const x = chart.x, y = chart.y
  return (
    <section className="card">
      <h2>Visualization</h2>
      <ResponsiveContainer width="100%" height={300}>
        {chart.type === 'line' ? (
          <LineChart data={chart.points}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey={x} /><YAxis /><Tooltip />
            <Line type="monotone" dataKey={y} stroke="#7c5cff" strokeWidth={2} />
          </LineChart>
        ) : (
          <BarChart data={chart.points}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey={x} /><YAxis /><Tooltip />
            <Bar dataKey={y} fill="#7c5cff" />
          </BarChart>
        )}
      </ResponsiveContainer>
    </section>
  )
}