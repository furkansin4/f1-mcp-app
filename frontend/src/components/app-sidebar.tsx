import { Home, Inbox, Settings, Plus, Trash2, Edit3 } from "lucide-react"
import { Link, useNavigate } from "react-router-dom"
import { useEffect, useState } from "react"
import { getRecents, deleteConversation, updateConversationTitle, postModel, getCurrentModel } from "@/services/api"
import { toast } from "sonner"
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"

import {
  Sidebar,
  SidebarContent,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarRail,
  useSidebar,
} from "@/components/ui/sidebar"

// Menu items.
const items = [
  {
    title: "Home",
    url: "/",
    icon: Home,
  },
  {
    title: "Dashboard",
    url: "/dashboard",
    icon: Inbox,
  },
  {
    title: "Settings",
    url: "#",
    icon: Settings,
  },
]

interface RecentConversation {
  id: number;
  title: string;
  lastMessage?: string;
  updatedAt?: string;
}

export function AppSidebar() {
  const [recentConversations, setRecentConversations] = useState<RecentConversation[]>([]);
  const [loading, setLoading] = useState(true);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editingTitle, setEditingTitle] = useState("");
  const { state } = useSidebar();
  const isCollapsed = state === "collapsed";
  const navigate = useNavigate();

  useEffect(() => {
    const fetchRecents = async () => {
      try {
        const recents = await getRecents();
        setRecentConversations(recents);
      } catch (error) {
        console.error('Failed to fetch recent conversations:', error);
      } finally {
        setLoading(false);
      }
    };

    fetchRecents();
  }, []);

  const handleDeleteConversation = async (conversationId: number, event: React.MouseEvent) => {
    event.preventDefault();
    event.stopPropagation();
    
    try {
      await deleteConversation(conversationId);
      // Remove the deleted conversation from the state
      setRecentConversations(prev => prev.filter(conv => conv.id !== conversationId));
      
      // If we're currently viewing the deleted conversation, navigate to chat
      const currentPath = window.location.pathname;
      if (currentPath === `/chat/${conversationId}`) {
        navigate('/chat');
      }
    } catch (error) {
      console.error('Failed to delete conversation:', error);
    }
  };

  const handleEditConversation = (conversationId: number, currentTitle: string, event: React.MouseEvent) => {
    event.preventDefault();
    event.stopPropagation();
    setEditingId(conversationId);
    setEditingTitle(currentTitle);
  };

  const handleSaveTitle = async (conversationId: number) => {
    if (!editingTitle.trim()) return;
    
    try {
      await updateConversationTitle(conversationId, editingTitle.trim());
      // Update the conversation title in the state
      setRecentConversations(prev => 
        prev.map(conv => 
          conv.id === conversationId 
            ? { ...conv, title: editingTitle.trim() }
            : conv
        )
      );
      setEditingId(null);
      setEditingTitle("");
    } catch (error) {
      console.error('Failed to update conversation title:', error);
    }
  };

  const handleCancelEdit = () => {
    setEditingId(null);
    setEditingTitle("");
  };

  const handleKeyPress = (event: React.KeyboardEvent, conversationId: number) => {
    if (event.key === 'Enter') {
      handleSaveTitle(conversationId);
    } else if (event.key === 'Escape') {
      handleCancelEdit();
    }
  };

  function ControlledSelect() {
    const [selectedOption, setSelectedOption] = useState('gemini');
    const [loading, setLoading] = useState(false);

    // Load current model on component mount
    useEffect(() => {
      const loadCurrentModel = async () => {
        try {
          const response = await getCurrentModel();
          setSelectedOption(response.current_model);
        } catch (error) {
          console.error('Failed to load current model:', error);
          toast.error('Failed to load current model. Using default.');
          // Keep default value if loading fails
        }
      };

      loadCurrentModel();
    }, []);

    const handleModelChange = async (value: string) => {
      setLoading(true);
      try {
        await postModel(value);
        setSelectedOption(value);
        toast.success(`Model changed to ${value.charAt(0).toUpperCase() + value.slice(1)}`);
      } catch (error) {
        console.error('Failed to change model:', error);
        toast.error('Failed to change model. Please try again.');
        // Revert to previous selection on error
      } finally {
        setLoading(false);
      }
    };

    return (
        <Select
            value={selectedOption}
            onValueChange={handleModelChange}
            disabled={loading}
        >
            <SelectTrigger className="w-full text-foreground">
                <SelectValue placeholder={loading ? "Changing model..." : "Select model"} />
            </SelectTrigger>
            <SelectContent>
                <SelectGroup>
                    <SelectItem value="gemini">Gemini</SelectItem>
                    <SelectItem value="openai">OpenAI</SelectItem>
                    <SelectItem value="anthropic">Anthropic</SelectItem>
               </SelectGroup>
           </SelectContent>
       </Select>
   );
}

//<img src="/f1.png" alt="F1 Logo" className="h-8 w-auto" />

  return (
    <Sidebar collapsible="icon">
      <SidebarHeader>
        <Link to="/" className="flex items-center gap-2 px-2 py-1">
          {!isCollapsed && <span className="font-bold text-sm">F1 MCP Chat App</span>}
        </Link>
      </SidebarHeader>
      {!isCollapsed && (
        <SidebarGroup>
          <SidebarGroupLabel>Model</SidebarGroupLabel>
          <ControlledSelect />
        </SidebarGroup>
      )}
      <SidebarContent>
        <SidebarGroup>
          <SidebarGroupLabel>Chat</SidebarGroupLabel>
          <SidebarGroupContent>
            <SidebarMenu>
              <SidebarMenuItem>
                <SidebarMenuButton asChild tooltip="New Chat">
                  <Link to="/chat">
                    <Plus />
                    {!isCollapsed && <span>New Chat</span>}
                  </Link>
                </SidebarMenuButton>
              </SidebarMenuItem>
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>
        {!isCollapsed && (
          <SidebarGroup>
            <SidebarGroupLabel>Recent Conversations</SidebarGroupLabel>
            <SidebarGroupContent>
              <SidebarMenu>
                {loading ? (
                  <SidebarMenuItem>
                    <SidebarMenuButton>
                      <span>Loading...</span>
                    </SidebarMenuButton>
                  </SidebarMenuItem>
                ) : recentConversations.length > 0 ? (
                  recentConversations.map((conversation) => (
                    <SidebarMenuItem key={conversation.id}>
                      <div className="flex items-center w-full group/conversation">
                        {editingId === conversation.id ? (
                          <div className="flex-1 flex items-center gap-1">
                            <input
                              type="text"
                              value={editingTitle}
                              onChange={(e) => setEditingTitle(e.target.value)}
                              onKeyDown={(e) => handleKeyPress(e, conversation.id)}
                              onBlur={() => handleSaveTitle(conversation.id)}
                              className="flex-1 px-2 py-1 text-sm border rounded focus:outline-none focus:ring-1 focus:ring-blue-500"
                              autoFocus
                            />
                          </div>
                        ) : (
                          <SidebarMenuButton asChild tooltip={conversation.title || `Conversation ${conversation.id}`} className="flex-1">
                            <Link to={`/chat/${conversation.id}`}>
                              <span className="truncate">{conversation.title || `Conversation ${conversation.id}`}</span>
                            </Link>
                          </SidebarMenuButton>
                        )}
                        <div className="flex items-center opacity-0 group-hover/conversation:opacity-100 transition-all duration-200">
                          <button
                            onClick={(e) => handleEditConversation(conversation.id, conversation.title || `Conversation ${conversation.id}`, e)}
                            className="p-1 rounded-sm hover:bg-blue-100 hover:text-blue-600 transition-all duration-200"
                            title="Edit conversation title"
                          >
                            <Edit3 size={14} />
                          </button>
                          <button
                            onClick={(e) => handleDeleteConversation(conversation.id, e)}
                            className="p-1 rounded-sm hover:bg-red-100 hover:text-red-600 transition-all duration-200 ml-1"
                            title="Delete conversation"
                          >
                            <Trash2 size={14} />
                          </button>
                        </div>
                      </div>
                    </SidebarMenuItem>
                  ))
                ) : (
                  <SidebarMenuItem>
                    <SidebarMenuButton>
                      <span className="text-muted-foreground">No recent conversations</span>
                    </SidebarMenuButton>
                  </SidebarMenuItem>
                )}
              </SidebarMenu>
            </SidebarGroupContent>
          </SidebarGroup>
        )}
        <SidebarGroup>
          <SidebarGroupLabel>Navigation</SidebarGroupLabel>
          <SidebarGroupContent>
            <SidebarMenu>
              {items.map((item) => (
                <SidebarMenuItem key={item.title}>
                  <SidebarMenuButton asChild tooltip={item.title}>
                    {item.url.startsWith('#') ? (
                      <a href={item.url}>
                        <item.icon />
                        {!isCollapsed && <span>{item.title}</span>}
                      </a>
                    ) : (
                      <Link to={item.url}>
                        <item.icon />
                        {!isCollapsed && <span>{item.title}</span>}
                      </Link>
                    )}
                  </SidebarMenuButton>
                </SidebarMenuItem>
              ))}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>
      </SidebarContent>
      <SidebarRail />
    </Sidebar>
  )
}