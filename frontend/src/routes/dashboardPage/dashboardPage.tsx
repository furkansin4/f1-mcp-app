import { Link } from "react-router-dom"
import "./dashboardPage.css"

export default function DashboardPage() {
    return (
        <div className="dashboard-page">
            <div className="dashboard-header">
                <h1 className="dashboard-title">Dashboard</h1>
                <p className="dashboard-subtitle">Your F1 data command center</p>
            </div>

            <div className="dashboard-grid">
                <Link to="/chat" className="dashboard-card">
                    <span className="card-icon">💬</span>
                    <h3 className="card-title">Start New Chat</h3>
                    <p className="card-description">
                        Begin a new conversation with our AI assistant to get F1 insights, 
                        race data, and detailed analysis.
                    </p>
                    <span className="card-action">
                        Start Chatting →
                    </span>
                </Link>

                <div className="dashboard-card">
                    <span className="card-icon">📊</span>
                    <h3 className="card-title">Race Analytics</h3>
                    <p className="card-description">
                        Access comprehensive race statistics, lap times, and performance 
                        data from current and historical seasons.
                    </p>
                    <span className="card-action">
                        View Analytics →
                    </span>
                </div>

                <div className="dashboard-card">
                    <span className="card-icon">🏆</span>
                    <h3 className="card-title">Championship Standings</h3>
                    <p className="card-description">
                        Stay updated with the latest driver and constructor championship 
                        standings and points progression.
                    </p>
                    <span className="card-action">
                        View Standings →
                    </span>
                </div>

                <div className="dashboard-card">
                    <span className="card-icon">📈</span>
                    <h3 className="card-title">Telemetry Data</h3>
                    <p className="card-description">
                        Explore detailed telemetry information, compare driver performances, 
                        and analyze racing lines and speeds.
                    </p>
                    <span className="card-action">
                        Explore Data →
                    </span>
                </div>
            </div>

            <div className="quick-actions">
                <h2 className="quick-actions-title">
                    ⚡ Quick Questions
                </h2>
                <div className="quick-actions-grid">
                    <Link to="/chat" className="quick-action-button">
                        🏁 Latest race winner
                    </Link>
                    <Link to="/chat" className="quick-action-button">
                        🏎️ Fastest lap records
                    </Link>
                    <Link to="/chat" className="quick-action-button">
                        🌧️ Wet weather races 2024
                    </Link>
                    <Link to="/chat" className="quick-action-button">
                        📊 Driver comparison
                    </Link>
                    <Link to="/chat" className="quick-action-button">
                        🏆 Championship leaders
                    </Link>
                    <Link to="/chat" className="quick-action-button">
                        📈 Team performance trends
                    </Link>
                </div>
            </div>
        </div>
    )
}