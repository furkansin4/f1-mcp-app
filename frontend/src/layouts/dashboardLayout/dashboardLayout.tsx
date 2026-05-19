import { Outlet } from "react-router-dom"
import { AppSidebar } from "@/components/app-sidebar"
import "./dashboardLayout.css"

export default function DashboardLayout() {
    return (
        <div className="dashboardLayout">
            <AppSidebar />
            <div className="dashboard-content">
                <main className="dashboard-main">
                    <Outlet />
                </main>
            </div>
        </div>
    )
}



