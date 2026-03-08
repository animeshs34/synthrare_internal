'use client'
import { useState, useEffect } from 'react'
import { api } from '@/lib/api'

type Domain = { id: number; name: string; slug: string }
type Dataset = {
  id: number
  name: string
  description: string
  domain: Domain
  row_count: number
  column_count: number
  credit_cost: number
  status: string
}

const DOMAIN_COLORS: Record<string, string> = {
  finance: 'bg-green-500/10 text-green-400 border-green-500/20',
  aviation: 'bg-blue-500/10 text-blue-400 border-blue-500/20',
  healthcare: 'bg-purple-500/10 text-purple-400 border-purple-500/20',
}

export default function CatalogPage() {
  const [datasets, setDatasets] = useState<Dataset[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    api.getDatasets()
      .then(setDatasets)
      .catch(() => setError('Failed to load catalog'))
      .finally(() => setLoading(false))
  }, [])

  // Group datasets by domain
  const groups: Record<string, Dataset[]> = {}
  for (const ds of datasets) {
    const key = ds.domain.name
    if (!groups[key]) groups[key] = []
    groups[key].push(ds)
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[calc(100vh-57px)]">
        <p className="text-gray-500">Loading catalog…</p>
      </div>
    )
  }

  return (
    <div className="max-w-4xl mx-auto px-4 py-10">
      <h1 className="text-2xl font-bold text-white mb-2">Data Catalog</h1>
      <p className="text-gray-400 text-sm mb-8">
        Pre-built synthetic datasets ready to generate. Sign in to create custom jobs.
      </p>

      {error && <p className="text-red-400 text-sm mb-6">{error}</p>}

      {Object.keys(groups).length === 0 && !error && (
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-10 text-center">
          <p className="text-gray-500 text-sm">No datasets in catalog yet.</p>
        </div>
      )}

      <div className="flex flex-col gap-8">
        {Object.entries(groups).map(([domainName, domainDatasets]) => {
          const slug = domainDatasets[0].domain.slug
          const colorClass = DOMAIN_COLORS[slug] ?? 'bg-gray-500/10 text-gray-400 border-gray-500/20'
          return (
            <div key={domainName}>
              <div className="flex items-center gap-3 mb-4">
                <span className={`px-3 py-1 rounded-full text-xs font-medium border ${colorClass}`}>
                  {domainName}
                </span>
              </div>
              <div className="grid gap-3">
                {domainDatasets.map(ds => (
                  <div key={ds.id} className="bg-gray-900 border border-gray-800 rounded-xl p-5">
                    <div className="flex items-start justify-between gap-4">
                      <div className="flex-1 min-w-0">
                        <h3 className="text-white font-medium text-sm mb-1">{ds.name}</h3>
                        <p className="text-gray-400 text-xs leading-relaxed">{ds.description}</p>
                      </div>
                      <div className="text-right shrink-0">
                        <p className="text-white text-sm font-medium">{ds.credit_cost} credit{ds.credit_cost !== 1 ? 's' : ''}</p>
                      </div>
                    </div>
                    <div className="flex gap-4 mt-3 pt-3 border-t border-gray-800">
                      <span className="text-xs text-gray-500">{ds.row_count.toLocaleString()} rows</span>
                      <span className="text-xs text-gray-500">{ds.column_count} columns</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
