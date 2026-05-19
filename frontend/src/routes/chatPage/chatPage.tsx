import { useParams, useSearchParams } from "react-router-dom"
import { useEffect, useState } from "react"
import { ChatWithSuggestions } from "@/components/app-chat"
import { getConversationMessages, getConversationTools } from "@/services/api"
import { type Message } from "@/components/ui/chat-message"
import "./chatPage.css"

export default function ChatPage() {
    const { conversationId } = useParams<{ conversationId: string }>()
    const [searchParams] = useSearchParams()
    const initialQuery = searchParams.get("q") ?? undefined
    const [initialMessages, setInitialMessages] = useState<Message[]>([])
    const [loading, setLoading] = useState(false)
    const [conversationTitle, setConversationTitle] = useState<string>("")

    useEffect(() => {
        // Reset state when conversationId changes
        setInitialMessages([])
        setConversationTitle("")
        
        if (conversationId) {
            loadConversation(parseInt(conversationId))
        } else {
            setConversationTitle("New Chat")
        }
    }, [conversationId])

    const loadConversation = async (id: number) => {
        setLoading(true)
        try {
            // Load both messages and tools in parallel
            const [messages, tools] = await Promise.all([
                getConversationMessages(id),
                getConversationTools(id)
            ])

            // Create a map of conversation tools - since tools don't have message_id,
            // we'll associate them with assistant messages based on chronological order
            const assistantMessages = messages.filter((msg: any) => msg.role === "assistant")
            const toolsByAssistantMessage = new Map()
            
            if (tools && Array.isArray(tools) && assistantMessages.length > 0) {
                // Sort tools by creation time
                const sortedTools = tools.sort((a: any, b: any) => 
                    new Date(a.created_at).getTime() - new Date(b.created_at).getTime()
                )
                
                // Distribute tools among assistant messages
                // For simplicity, if there's only one assistant message, assign all tools to it
                // Otherwise, distribute evenly or assign to the most recent assistant message
                const targetAssistantMessage = assistantMessages[assistantMessages.length - 1]
                
                const formattedTools = sortedTools.map((tool: any, index: number) => {
                    let toolArgs = {}
                    
                    try {
                        if (tool.tool_request) {
                            if (typeof tool.tool_request === 'string') {
                                toolArgs = JSON.parse(tool.tool_request)
                            } else if (typeof tool.tool_request === 'object') {
                                toolArgs = tool.tool_request
                            }
                        }
                    } catch (e) {
                        console.warn("Failed to parse tool_request:", tool.tool_request, e)
                        // If JSON parsing fails, create a meaningful fallback
                        toolArgs = { raw_request: tool.tool_request }
                    }
                    
                    // Ensure toolArgs is not empty - if it is, create a placeholder
                    if (!toolArgs || Object.keys(toolArgs).length === 0) {
                        toolArgs = { tool_name: tool.tool_name, note: "No request parameters available" }
                    }
                    
                    return {
                        iteration: index + 1, // Use index as iteration number
                        tool_name: tool.tool_name,
                        tool_args: toolArgs,
                        result: tool.tool_response,
                        error: undefined, // Not stored in current schema
                        status: "success" as const // Assume success since errors aren't stored
                    }
                })
                
                toolsByAssistantMessage.set(targetAssistantMessage.id, formattedTools)
            }

            const formattedMessages: Message[] = messages.map((msg: any) => ({
                id: msg.id.toString(),
                role: msg.role as "user" | "assistant",
                content: msg.message,
                tools: toolsByAssistantMessage.get(msg.id) || [] // Associate tools with the message
            }))
            setInitialMessages(formattedMessages)
            
            // Set title from first user message or fallback
            const firstUserMessage = messages.find((msg: any) => msg.role === "user")
            setConversationTitle(
                firstUserMessage?.message?.slice(0, 50) + 
                (firstUserMessage?.message?.length > 50 ? "..." : "") || 
                `Conversation ${id}`
            )
        } catch (error) {
            console.error("Error loading conversation:", error)
            setConversationTitle(`Conversation ${id}`)
        } finally {
            setLoading(false)
        }
    }

    if (loading) {
        return (
            <div className="chat-page">
                <div className="chat-container">
                    <div className="chat-header">
                        <h1 className="chat-title">Loading...</h1>
                    </div>
                    <div className="chat-content">
                        <div className="loading-state">
                            <div className="loading-spinner"></div>
                            <div className="loading-text">Loading conversation...</div>
                        </div>
                    </div>
                </div>
            </div>
        )
    }

    return (
        <div className="chat-page">
            <div className="chat-container">
                <div className="chat-header">
                    <h1 className="chat-title">{conversationTitle}</h1>
                </div>
                <div className="chat-content">
                    <ChatWithSuggestions
                        initialMessages={initialMessages}
                        conversationId={conversationId ? parseInt(conversationId) : null}
                        initialQuery={initialQuery}
                    />
                </div>
            </div>
        </div>
    )
}