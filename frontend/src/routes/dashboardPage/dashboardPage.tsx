import { Link } from "react-router-dom"
import { useEffect, useState } from "react"
import { getRecents } from "@/services/api"
import "./dashboardPage.css"

interface Conversation {
    id: number
    title: string
    created_at: string
}

const CARD_QUERIES = [
    {
        icon: "💬",
        title: "New Chat",
        description: "Start a fresh conversation with the F1 AI assistant.",
        action: "Start Chatting →",
        href: "/chat",
    },
    {
        icon: "📊",
        title: "Race Analytics",
        description: "Explore lap times, sector splits and race results.",
        action: "View Analytics →",
        href: "/chat?q=Show me the race results and fastest laps for the latest 2025 Grand Prix",
    },
    {
        icon: "🏆",
        title: "Championship Standings",
        description: "Driver and constructor standings with points breakdown.",
        action: "View Standings →",
        href: "/chat?q=Show me the current 2025 F1 driver and constructor championship standings",
    },
    {
        icon: "📈",
        title: "Telemetry Analysis",
        description: "Compare speed, throttle and braking data between drivers.",
        action: "Explore Data →",
        href: "/chat?q=Compare HAM and VER telemetry data from the 2024 Abu Dhabi GP final lap",
    },
]

const QUICK_QUESTIONS = [
    { label: "🏁 Latest race winner",         q: "Who won the most recent F1 Grand Prix in 2025?" },
    { label: "🏎️ Fastest lap records",        q: "What are the fastest laps recorded in the 2025 season so far?" },
    { label: "🌧️ Wet weather races 2024",     q: "Which sessions had rainfall in the 2024 F1 season?" },
    { label: "📊 Driver comparison",           q: "Compare Hamilton and Verstappen's performance in the 2024 season" },
    { label: "🏆 Championship leaders",       q: "Who leads the 2025 F1 drivers championship and by how many points?" },
    { label: "📈 Team performance trends",    q: "Show me constructor performance trends across the 2024 season" },
]

export default function DashboardPage() {
    const [recents, setRecents] = useState<Conversation[]>([])
    const [loadingRecents, setLoadingRecents] = useState(true)

    useEffect(() => {
        getRecents()
            .then(data => setRecents(data.slice(0, 5)))
            .catch(() => {})
            .finally(() => setLoadingRecents(false))
    }, [])

    return (
        <div className="dashboard-page">
            <div className="dashboard-header">
                <h1 className="dashboard-title">Dashboard</h1>
                <p className="dashboard-subtitle">Your F1 data command center</p>
            </div>

            <div className="dashboard-grid">
                {CARD_QUERIES.map((card) => (
                    <Link to={card.href} key={card.title} className="dashboard-card">
                        <span className="card-icon">{card.icon}</span>
                        <h3 className="card-title">{card.title}</h3>
                        <p className="card-description">{card.description}</p>
                        <span className="card-action">{card.action}</span>
                    </Link>
                ))}
            </div>

            <div className="dashboard-bottom">
                <div className="quick-actions">
                    <h2 className="quick-actions-title">Quick Questions</h2>
                    <div className="quick-actions-grid">
                        {QUICK_QUESTIONS.map(({ label, q }) => (
                            <Link
                                key={label}
                                to={`/chat?q=${encodeURIComponent(q)}`}
                                className="quick-action-button"
                            >
                                {label}
                            </Link>
                        ))}
                    </div>
                </div>

                <div className="recent-conversations">
                    <h2 className="recent-title">Recent Conversations</h2>
                    {loadingRecents ? (
                        <p className="recent-empty">Loading...</p>
                    ) : recents.length === 0 ? (
                        <p className="recent-empty">No conversations yet. Start chatting!</p>
                    ) : (
                        <ul className="recent-list">
                            {recents.map((conv) => (
                                <li key={conv.id}>
                                    <Link to={`/chat/${conv.id}`} className="recent-item">
                                        <span className="recent-item-title">
                                            {conv.title || `Conversation ${conv.id}`}
                                        </span>
                                        <span className="recent-item-date">
                                            {new Date(conv.created_at).toLocaleDateString()}
                                        </span>
                                    </Link>
                                </li>
                            ))}
                        </ul>
                    )}
                </div>
            </div>
        </div>
    )
}
