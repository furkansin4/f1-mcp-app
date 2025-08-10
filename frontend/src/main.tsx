import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'
import { createBrowserRouter, RouterProvider } from 'react-router-dom'
import RootLayout from './layouts/rootLayout/rootLayout.tsx'
import DashboardLayout from './layouts/dashboardLayout/dashboardLayout.tsx'
import DashboardPage from './routes/dashboardPage/dashboardPage.tsx'
import ChatPage from './routes/chatPage/chatPage.tsx'

const router = createBrowserRouter([
  {
    path: "/",
    element: <RootLayout />,
    children: [
      {
        path: "/",
        element: <App />,
      },
      {
        element: <DashboardLayout />,
        children: [
          {
            path: "/dashboard",
            element: <DashboardPage />,
          },
          {
            path: "/chat/:conversationId",
            element: <ChatPage />,
          },
          {
            path: "/chat",
            element: <ChatPage />,
          },
        ],
      },

    ],
  },
])

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <RouterProvider router={router} />
  </StrictMode>,
)