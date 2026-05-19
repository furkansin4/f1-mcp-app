import { Chat } from "@/components/ui/chat"
import { type Message } from "@/components/ui/chat-message"
import { useState, useEffect, useCallback } from "react"
import { postChat } from "@/services/api"
import { useNavigate } from "react-router-dom"

interface ChatWithSuggestionsProps {
  initialMessages?: Message[]
  conversationId?: number | null
}

export function ChatWithSuggestions({ 
  initialMessages = [], 
  conversationId: initialConversationId = null 
}: ChatWithSuggestionsProps) {
  const [messages, setMessages] = useState<Message[]>(initialMessages)
  const [input, setInput] = useState("")
  const [isGenerating, setIsGenerating] = useState(false)
  const [conversationId, setConversationId] = useState<number | null>(initialConversationId)
  const navigate = useNavigate()

  // Update messages when initialMessages prop changes
  useEffect(() => {
    setMessages(initialMessages)
  }, [initialMessages])

  // Update conversationId when prop changes
  useEffect(() => {
    setConversationId(initialConversationId)
  }, [initialConversationId])

  const handleInputChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setInput(e.target.value)
  }

  // Centralized function to send messages and handle responses
  const sendMessage = useCallback(async (messageContent: string) => {
    const userMessage: Message = {
      id: Date.now().toString(),
      role: "user",
      content: messageContent,
    }

    // Add user message
    setMessages(prev => [...prev, userMessage])
    setIsGenerating(true)

    try {
      // Call API with current conversation ID
      const data = await postChat(messageContent, conversationId)
      
      // Update conversation ID and navigate if this is a new conversation
      if ((!conversationId || conversationId === null) && data.conversation_id) {
        setConversationId(data.conversation_id)
        // Navigate to the new conversation URL
        navigate(`/chat/${data.conversation_id}`, { replace: true })
      }
      
      const assistantMessage: Message = {
        id: (Date.now() + 1).toString(),
        role: "assistant",
        content: data.response,
        tools: data.tools || [], // Include tool execution data from API response
      }
      
      setMessages(prev => [...prev, assistantMessage])
    } catch (error) {
      console.error("Error calling API:", error)
      
      const errorMessage: Message = {
        id: (Date.now() + 1).toString(),
        role: "assistant",
        content: "Sorry, I encountered an error while processing your request. Please try again.",
      }
      
      setMessages(prev => [...prev, errorMessage])
    } finally {
      setIsGenerating(false)
    }
  }, [conversationId, navigate])

  const handleSubmit = async (event?: { preventDefault?: () => void }) => {
    event?.preventDefault?.()
    
    if (!input.trim()) return

    const messageContent = input.trim()
    setInput("") // Clear input immediately
    
    await sendMessage(messageContent)
  }

  const append = async (message: { role: "user"; content: string }) => {
    await sendMessage(message.content)
  }

  const stop = () => {
    setIsGenerating(false)
  }

  return (    
    <Chat
      messages={messages}
      input={input}
      handleInputChange={handleInputChange}
      handleSubmit={handleSubmit}
      isGenerating={isGenerating}
      stop={stop}
      append={append}
      suggestions={[
        "Fastest laps in 2023 Monaco GP",
        "HAM and VER telemetry data in 2022 Belgian GP in lap 35",
        "Get rainy sessions in 2021",
      ]}
    />
  )
}