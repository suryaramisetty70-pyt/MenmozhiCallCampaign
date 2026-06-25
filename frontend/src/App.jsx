import { useState } from 'react'
import { motion } from 'framer-motion'
import { Phone, Upload, Settings, BarChart2 } from 'lucide-react'

export default function App() {
  const [activeTab, setActiveTab] = useState('dashboard')

  return (
    <div className="min-h-screen bg-slate-950 text-white font-sans selection:bg-indigo-500/30">
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
            {['Dashboard', 'Contacts', 'Settings'].map((tab) => (
              <button 
                key={tab}
                onClick={() => setActiveTab(tab.toLowerCase())}
                className={`transition-colors hover:text-white ${activeTab === tab.toLowerCase() ? 'text-white' : ''}`}
              >
                {tab}
                {activeTab === tab.toLowerCase() && (
                  <motion.div 
                    layoutId="underline"
                    className="h-0.5 bg-indigo-500 mt-1 rounded-full"
                  />
                )}
              </button>
            ))}
          </div>
        </div>
      </nav>

      {/* Main Content Area */}
      <main className="max-w-7xl mx-auto px-4 py-8">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
          className="grid grid-cols-1 lg:grid-cols-3 gap-6"
        >
          {/* Hero Section */}
          <div className="lg:col-span-3">
            <div className="relative overflow-hidden rounded-2xl border border-white/10 bg-slate-900/50 p-8 backdrop-blur-sm">
              <div className="absolute top-0 left-0 w-full h-full bg-gradient-to-br from-indigo-500/10 to-purple-500/10 pointer-events-none" />
              <div className="relative z-10 flex flex-col items-start gap-4">
                <span className="px-3 py-1 text-xs font-semibold tracking-wider text-indigo-400 bg-indigo-500/10 rounded-full border border-indigo-500/20">
                  SYSTEM READY
                </span>
                <h1 className="text-4xl md:text-5xl font-bold tracking-tight text-white">
                  Automate Your Call Campaigns
                </h1>
                <p className="text-lg text-slate-400 max-w-2xl">
                  Upload your contacts, generate an AI voice script, and launch hundreds of calls in seconds.
                </p>
                <div className="flex items-center gap-4 mt-4">
                  <motion.button 
                    whileHover={{ scale: 1.02 }}
                    whileTap={{ scale: 0.98 }}
                    className="flex items-center gap-2 bg-indigo-500 hover:bg-indigo-600 text-white px-6 py-3 rounded-xl font-semibold transition-colors shadow-lg shadow-indigo-500/20"
                  >
                    <Phone className="w-5 h-5" />
                    Launch Campaign
                  </motion.button>
                  <motion.button 
                    whileHover={{ scale: 1.02 }}
                    whileTap={{ scale: 0.98 }}
                    className="flex items-center gap-2 bg-slate-800 hover:bg-slate-700 text-white px-6 py-3 rounded-xl font-semibold transition-colors border border-white/5"
                  >
                    <Upload className="w-5 h-5" />
                    Upload Excel
                  </motion.button>
                </div>
              </div>
            </div>
          </div>

          {/* Stats Cards */}
          {[
            { label: 'Total Calls', value: '0', icon: BarChart2, color: 'text-blue-400', bg: 'bg-blue-500/10' },
            { label: 'Success Rate', value: '0%', icon: Phone, color: 'text-green-400', bg: 'bg-green-500/10' },
            { label: 'Failed Calls', value: '0', icon: Settings, color: 'text-rose-400', bg: 'bg-rose-500/10' },
          ].map((stat, i) => (
            <motion.div
              key={stat.label}
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.1 + 0.2 }}
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
      </main>
    </div>
  )
}
