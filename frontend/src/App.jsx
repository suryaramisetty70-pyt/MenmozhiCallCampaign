import { useState, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Phone, Upload, Settings, BarChart2, CheckCircle, XCircle, Trash2, Clock } from 'lucide-react'

export default function App() {
  const [activeTab, setActiveTab] = useState('dashboard')
  const [stats, setStats] = useState({ total: 0, success: 0, failed: 0, available: 0 })
  const [logs, setLogs] = useState([])
  const [uploading, setUploading] = useState(false)
  const [clearExisting, setClearExisting] = useState(true)

  const fetchDashboard = async () => {
    try {
      const res = await fetch('/api/v2/dashboard')
      if (res.ok) {
        const data = await res.json()
        setStats(data.stats)
        setLogs(data.logs)
      }
    } catch (e) {
      console.error(e)
    }
  }

  useEffect(() => {
    fetchDashboard()
    const interval = setInterval(fetchDashboard, 5000)
    return () => clearInterval(interval)
  }, [])

  const handleUpload = async (e) => {
    e.preventDefault()
    const file = e.target.file.files[0]
    if (!file) return
    
    setUploading(true)
    const formData = new FormData()
    formData.append('file', file)
    if (clearExisting) formData.append('clear_existing', 'true')
    
    try {
      await fetch('/api/v2/upload', { method: 'POST', body: formData })
      await fetchDashboard()
      alert("Contacts uploaded successfully!")
    } catch (e) {
      alert("Error uploading file.")
    }
    setUploading(false)
  }

  const launchCampaign = async () => {
    if (!confirm("This will call ALL contacts with a 10s delay. Continue?")) return
    try {
      await fetch('/api/v2/call-all', { method: 'POST' })
      alert("Campaign Launched! Calls are being made in the background.")
    } catch (e) {
      alert("Error launching campaign")
    }
  }

  const wipeLogs = async () => {
    if (!confirm("Delete all call logs?")) return
    await fetch('/api/v2/clear-logs', { method: 'POST' })
    fetchDashboard()
  }

  return (
    <div className="min-h-screen bg-slate-950 text-white font-sans selection:bg-indigo-500/30 pb-20">
      {/* Navbar */}
      <nav className="sticky top-0 z-50 border-b border-white/10 bg-slate-950/50 backdrop-blur-md">
        <div className="max-w-7xl mx-auto px-4 h-16 flex items-center justify-between">
          <motion.div 
            initial={{ opacity: 0, x: -20 }}
            animate={{ opacity: 1, x: 0 }}
            className="flex items-center gap-3 font-bold text-xl tracking-tight"
          >
            <div className="w-8 h-8 rounded-lg bg-indigo-500 flex items-center justify-center">
              <Phone className="w-5 h-5 text-white" />
            </div>
            Menmozhi AI
          </motion.div>
          
          <div className="flex items-center gap-6 text-sm font-medium text-slate-400">
            {['Dashboard', 'Logs'].map((tab) => (
              <button 
                key={tab}
                onClick={() => setActiveTab(tab.toLowerCase())}
                className={`transition-colors hover:text-white relative ${activeTab === tab.toLowerCase() ? 'text-white' : ''}`}
              >
                {tab}
                {activeTab === tab.toLowerCase() && (
                  <motion.div 
                    layoutId="underline"
                    className="absolute -bottom-[21px] left-0 right-0 h-[2px] bg-indigo-500 rounded-t-full"
                  />
                )}
              </button>
            ))}
          </div>
        </div>
      </nav>

      {/* Main Content Area */}
      <main className="max-w-7xl mx-auto px-4 py-8">
        <AnimatePresence mode="wait">
          {activeTab === 'dashboard' && (
            <motion.div
              key="dashboard"
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -20 }}
              transition={{ duration: 0.3 }}
              className="grid grid-cols-1 lg:grid-cols-3 gap-6"
            >
              {/* Hero Section */}
              <div className="lg:col-span-3">
                <div className="relative overflow-hidden rounded-2xl border border-white/10 bg-slate-900/50 p-8 backdrop-blur-sm">
                  <div className="absolute top-0 left-0 w-full h-full bg-gradient-to-br from-indigo-500/10 to-purple-500/10 pointer-events-none" />
                  <div className="relative z-10 flex flex-col md:flex-row gap-8 items-start md:items-center justify-between">
                    <div className="flex flex-col gap-4 max-w-xl">
                      <span className="px-3 py-1 text-xs font-semibold tracking-wider text-indigo-400 bg-indigo-500/10 rounded-full border border-indigo-500/20 w-fit">
                        SYSTEM READY
                      </span>
                      <h1 className="text-4xl md:text-5xl font-bold tracking-tight text-white">
                        Automate Your Call Campaigns
                      </h1>
                      <p className="text-lg text-slate-400">
                        Upload your contacts and launch hundreds of calls in seconds.
                      </p>
                      <div className="flex items-center gap-4 mt-2">
                        <motion.button 
                          whileHover={{ scale: 1.02 }}
                          whileTap={{ scale: 0.98 }}
                          onClick={launchCampaign}
                          className="flex items-center gap-2 bg-indigo-500 hover:bg-indigo-600 text-white px-6 py-3 rounded-xl font-semibold transition-colors shadow-lg shadow-indigo-500/20"
                        >
                          <Phone className="w-5 h-5" />
                          Launch Campaign
                        </motion.button>
                      </div>
                    </div>

                    {/* Upload Card */}
                    <div className="bg-slate-950/50 border border-white/10 p-6 rounded-xl w-full md:w-80 shrink-0">
                      <h3 className="font-semibold text-lg mb-4 flex items-center gap-2"><Upload className="w-5 h-5 text-indigo-400" /> Upload Contacts</h3>
                      <form onSubmit={handleUpload} className="flex flex-col gap-4">
                        <input type="file" name="file" accept=".xlsx,.xls" required className="text-sm text-slate-400 file:mr-4 file:py-2 file:px-4 file:rounded-full file:border-0 file:text-sm file:font-semibold file:bg-indigo-500/10 file:text-indigo-400 hover:file:bg-indigo-500/20 cursor-pointer" />
                        <label className="flex items-center gap-2 text-sm text-slate-300 cursor-pointer">
                          <input type="checkbox" checked={clearExisting} onChange={(e) => setClearExisting(e.target.checked)} className="rounded border-slate-700 bg-slate-900 text-indigo-500" />
                          Clear existing contacts
                        </label>
                        <button disabled={uploading} type="submit" className="bg-white/5 hover:bg-white/10 border border-white/10 px-4 py-2 rounded-lg font-medium transition-colors">
                          {uploading ? 'Uploading...' : 'Upload Excel'}
                        </button>
                      </form>
                    </div>
                  </div>
                </div>
              </div>

              {/* Stats Cards */}
              {[
                { label: 'Available Contacts', value: stats.available, icon: BarChart2, color: 'text-blue-400', bg: 'bg-blue-500/10' },
                { label: 'Success Calls', value: stats.success, icon: CheckCircle, color: 'text-green-400', bg: 'bg-green-500/10' },
                { label: 'Failed Calls', value: stats.failed, icon: XCircle, color: 'text-rose-400', bg: 'bg-rose-500/10' },
              ].map((stat, i) => (
                <motion.div
                  key={stat.label}
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: i * 0.1 }}
                  className="p-6 rounded-2xl border border-white/10 bg-slate-900/50 backdrop-blur-sm flex items-center gap-4"
                >
                  <div className={`p-4 rounded-xl ${stat.bg}`}>
                    <stat.icon className={`w-6 h-6 ${stat.color}`} />
                  </div>
                  <div>
                    <p className="text-sm font-medium text-slate-400">{stat.label}</p>
                    <p className="text-2xl font-bold text-white">{stat.value}</p>
                  </div>
                </motion.div>
              ))}
            </motion.div>
          )}

          {activeTab === 'logs' && (
            <motion.div
              key="logs"
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -20 }}
              transition={{ duration: 0.3 }}
              className="bg-slate-900/50 border border-white/10 rounded-2xl overflow-hidden backdrop-blur-sm"
            >
              <div className="p-6 border-b border-white/10 flex items-center justify-between">
                <h2 className="text-xl font-bold flex items-center gap-2"><Clock className="w-5 h-5 text-indigo-400" /> Recent Call Logs</h2>
                <button onClick={wipeLogs} className="flex items-center gap-2 text-sm text-rose-400 hover:text-rose-300 transition-colors bg-rose-500/10 px-3 py-1.5 rounded-lg">
                  <Trash2 className="w-4 h-4" /> Clear Logs
                </button>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-left border-collapse">
                  <thead>
                    <tr className="border-b border-white/10 text-sm text-slate-400 bg-black/20">
                      <th className="p-4 font-medium">Name</th>
                      <th className="p-4 font-medium">Phone</th>
                      <th className="p-4 font-medium">Status</th>
                      <th className="p-4 font-medium">Time</th>
                    </tr>
                  </thead>
                  <tbody>
                    {logs.length === 0 ? (
                      <tr><td colSpan="4" className="p-8 text-center text-slate-500">No calls made yet</td></tr>
                    ) : logs.map((log, i) => (
                      <motion.tr 
                        initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: i * 0.05 }}
                        key={i} className="border-b border-white/5 hover:bg-white/5 transition-colors"
                      >
                        <td className="p-4 font-medium">{log.name}</td>
                        <td className="p-4 text-slate-300">{log.phone}</td>
                        <td className="p-4">
                          <span className={`px-2.5 py-1 rounded-full text-xs font-medium border ${
                            log.status === 'AVAILABLE' ? 'bg-green-500/10 text-green-400 border-green-500/20' : 
                            log.status === 'NO RESPONSE' ? 'bg-yellow-500/10 text-yellow-400 border-yellow-500/20' : 
                            'bg-rose-500/10 text-rose-400 border-rose-500/20'
                          }`}>
                            {log.status}
                          </span>
                        </td>
                        <td className="p-4 text-slate-400 text-sm">{log.time}</td>
                      </motion.tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </main>
    </div>
  )
}
