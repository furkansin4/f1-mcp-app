import { Outlet } from "react-router-dom"
import "./rootLayout.css"
import { SidebarProvider } from "@/components/ui/sidebar"
import { AppSidebar } from "@/components/app-sidebar"
import { Toaster } from "@/components/ui/sonner"

export default function RootLayout() {
    return (
        <div className="root-layout">
            <SidebarProvider>
                <AppSidebar />
                <div className="root-content">
                    <Outlet/>
                </div>
            </SidebarProvider>
            <Toaster />
        </div>
    )
}