'use client'
import { useState, useEffect, useRef } from 'react'
import { useRouter } from 'next/navigation'
import { api } from '@/lib/api'
import { isLoggedIn } from '@/lib/auth'

type Domain = { id: number; name: string; slug: string; description: string }
type Job = {
  id: number
  status: string
  domain_id: number
  row_count: number
  result_path: string | null
  error_message: string | null
  created_at: string
}

const STATUS_STYLES: Record<string, string> = {
  pending: 'bg-yellow-500/20 text-yellow-400',
  running: 'bg-blue-500/20 text-blue-400',
  completed: 'bg-green-500/20 text-green-400',
  failed: 'bg-red-500/20 text-red-400',
}

function StatusBadge({ status }: { status: string }) {
  return (
    <span className={`px-2 py-0.5 rounded text-xs font-medium ${STATUS_STYLES[status] ?? 'bg-gray-700 text-gray-300'}`}>
      {status === 'running' ? '⟳ running' : status}
    </span>
  )
}

export default function DashboardPage() {
  const router = useRouter()
  const [domains, setDomains] = useState<Domain[]>([])
  const [jobs, setJobs] = useState<Job[]>([])
  const [loading, setLoading] = useState(true)
  const [creating, setCreating] = useState(false)
  const [domainId, setDomainId] = useState<number | ''>('')
  const [rowCount, setRowCount] = useState(1000)
  const [formError, setFormError] = useState('')
  const [downloadLoading, setDownloadLoading] = useState<number | null>(null)
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)

  useEffect(() => {
    if (!isLoggedIn()) {
      router.replace('/login')
      return
    }
    loadData()
  }, [])

  const loadData = async () => {
    try {
      const [d, j] = await Promise.all([api.getDomains(), api.listJobs()])
      setDomains(d)
      setJobs(j)
      if (d.length > 0 && domainId === '') setDomainId(d[0].id)
      schedulePoll(j)
    } catch {
      // token may be expired
    } finally {
      setLoading(false)
    }
  }

  const schedulePoll = (currentJobs: Job[]) => {
    const hasActive = currentJobs.some(j => j.status === 'pending' || j.status === 'running')
    if (pollRef.current) clearInterval(pollRef.current)
    if (hasActive) {
      pollRef.current = setInterval(async () => {
        try {
          const updated = await api.listJobs()
          setJobs(updated)
          const stillActive = updated.some((j: Job) => j.status === 'pending' || j.status === 'running')
          if (!stillActive && pollRef.current) {
            clearInterval(pollRef.current)
            pollRef.current = null
          }
        } catch {}
      }, 3000)
    }
  }

  useEffect(() => () => { if (pollRef.current) clearInterval(pollRef.current) }, [])

  const handleCreateJob = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!domainId) return
    setFormError('')
    setCreating(true)
    try {
      const job = await api.createJob({ domain_id: Number(domainId), row_count: rowCount })
      const updated = [job, ...jobs]
      setJobs(updated)
      schedulePoll(updated)
    } catch (err: unknown) {
      setFormError(err instanceof Error ? err.message : 'Failed to create job')
    } finally {
      setCreating(false)
    }
  }

  const handleDownload = async (jobId: number) => {
    setDownloadLoading(jobId)
    try {
      const { download_url } = await api.getJobResult(jobId)
      window.open(download_url, '_blank')
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : 'Download failed')
    } finally {
      setDownloadLoading(null)
    }
  }

  const domainName = (id: number) => domains.find(d => d.id === id)?.name ?? `Domain ${id}`

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[calc(100vh-57px)]">
        <p className="text-gray-500">Loading…</p>
      </div>
    )
  }

  return (
    <div className="max-w-4xl mx-auto px-4 py-10">
      <h1 className="text-2xl font-bold text-white mb-8">Dashboard</h1>

      {/* Create job form */}
      <div className="bg-gray-900 border border-gray-800 rounded-xl p-6 mb-8">
        <h2 className="text-base font-semibold text-white mb-4">Generate synthetic data</h2>
        <form onSubmit={handleCreateJob} className="flex flex-col sm:flex-row gap-3 items-end">
          <div className="flex-1">
            <label className="block text-xs text-gray-400 mb-1">Domain</label>
            <select
              value={domainId}
              onChange={e => setDomainId(Number(e.target.value))}
              required
              className="w-full bg-gray-800 text-white rounded-lg px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-blue-500 border border-gray-700"
            >
              {domains.map(d => (
                <option key={d.id} value={d.id}>{d.name}</option>
              ))}
            </select>
          </div>
          <div className="w-36">
            <label className="block text-xs text-gray-400 mb-1">Row count</label>
            <input
              type="number"
              value={rowCount}
              onChange={e => setRowCount(Number(e.target.value))}
              min={1}
              max={1000000}
              required
              className="w-full bg-gray-800 text-white rounded-lg px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-blue-500 border border-gray-700"
            />
          </div>
          <button
            type="submit"
            disabled={creating}
            className="px-5 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors whitespace-nowrap"
          >
            {creating ? 'Creating…' : 'Generate'}
          </button>
        </form>
        {formError && <p className="text-red-400 text-sm mt-2">{formError}</p>}
      </div>

      {/* Jobs list */}
      <h2 className="text-base font-semibold text-white mb-4">Your jobs</h2>
      {jobs.length === 0 ? (
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-10 text-center">
          <p className="text-gray-500 text-sm">No jobs yet. Generate your first dataset above.</p>
        </div>
      ) : (
        <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-800 text-left">
                <th className="px-4 py-3 text-xs text-gray-500 font-medium">ID</th>
                <th className="px-4 py-3 text-xs text-gray-500 font-medium">Domain</th>
                <th className="px-4 py-3 text-xs text-gray-500 font-medium">Rows</th>
                <th className="px-4 py-3 text-xs text-gray-500 font-medium">Status</th>
                <th className="px-4 py-3 text-xs text-gray-500 font-medium">Created</th>
                <th className="px-4 py-3 text-xs text-gray-500 font-medium"></th>
              </tr>
            </thead>
            <tbody>
              {jobs.map((job, i) => (
                <tr key={job.id} className={`border-b border-gray-800/50 last:border-0 ${i % 2 === 0 ? '' : 'bg-gray-900/50'}`}>
                  <td className="px-4 py-3 text-gray-400">#{job.id}</td>
                  <td className="px-4 py-3 text-white">{domainName(job.domain_id)}</td>
                  <td className="px-4 py-3 text-gray-300">{job.row_count.toLocaleString()}</td>
                  <td className="px-4 py-3">
                    <StatusBadge status={job.status} />
                    {job.error_message && (
                      <p className="text-red-400 text-xs mt-1 max-w-xs truncate" title={job.error_message}>
                        {job.error_message}
                      </p>
                    )}
                  </td>
                  <td className="px-4 py-3 text-gray-500">
                    {new Date(job.created_at).toLocaleDateString()}
                  </td>
                  <td className="px-4 py-3 text-right">
                    {job.status === 'completed' && (
                      <button
                        onClick={() => handleDownload(job.id)}
                        disabled={downloadLoading === job.id}
                        className="text-blue-400 hover:text-blue-300 text-xs disabled:opacity-50"
                      >
                        {downloadLoading === job.id ? 'Getting link…' : 'Download'}
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
