import { Link } from "react-router-dom"
import "./homePage.css"
import { getTools } from "@/services/api"


export default function HomePage() {
    return (
        <div className="home-page">
            <div className="hero-bg-decoration"></div>
            
            <section className="home-hero">
                <div className="hero-content">
                    <h1 className="hero-title">F1 MCP Chat</h1>
                    <p className="hero-subtitle">Your AI-Powered Formula 1 Assistant</p>
                    <p className="hero-description">
                        Get instant access to Formula 1 data, statistics, and insights through our intelligent chat interface. 
                        Ask questions about races, drivers, teams, and get real-time analysis powered by advanced AI.
                    </p>
                    <div className="hero-actions">
                        <Link to="/chat" className="hero-button primary">
                            🏎️ Start Chatting
                        </Link>
                        <Link to="/dashboard" className="hero-button secondary">
                            📊 View Dashboard
                        </Link>
                    </div>
                </div>
            </section>

            <section className="features-section">
                <div className="features-container">
                    <h2 className="features-title">What You Can Ask</h2>
                    <div className="features-grid">
                        <div className="feature-card">
                            <span className="feature-icon">🏁</span>
                            <h3 className="feature-title">Race Results & Statistics</h3>
                            <p className="feature-description">
                                Get detailed race results, lap times, qualifying positions, and championship standings 
                                from any season or specific Grand Prix.
                            </p>
                        </div>
                        
                        <div className="feature-card">
                            <span className="feature-icon">👨‍🏁</span>
                            <h3 className="feature-title">Driver & Team Data</h3>
                            <p className="feature-description">
                                Access comprehensive information about drivers, their career statistics, 
                                team performances, and head-to-head comparisons.
                            </p>
                        </div>
                        
                        <div className="feature-card">
                            <span className="feature-icon">📈</span>
                            <h3 className="feature-title">Telemetry Analysis</h3>
                            <p className="feature-description">
                                Analyze telemetry data, compare lap times between drivers, 
                                and understand performance differences across different circuits.
                            </p>
                        </div>
                        
                        <div className="feature-card">
                            <span className="feature-icon">🌧️</span>
                            <h3 className="feature-title">Weather & Conditions</h3>
                            <p className="feature-description">
                                Find information about weather conditions during races, 
                                wet sessions, and how weather affected race outcomes.
                            </p>
                        </div>
                        
                        <div className="feature-card">
                            <span className="feature-icon">🏆</span>
                            <h3 className="feature-title">Historical Records</h3>
                            <p className="feature-description">
                                Explore Formula 1 history, record holders, milestone achievements, 
                                and legendary moments from past seasons.
                            </p>
                        </div>
                        
                        <div className="feature-card">
                            <span className="feature-icon">🔮</span>
                            <h3 className="feature-title">AI-Powered Insights</h3>
                            <p className="feature-description">
                                Get intelligent analysis and predictions based on historical data, 
                                trends, and performance patterns.
                            </p>
                        </div>
                    </div>
                </div>
            </section>
        </div>
    )
}
