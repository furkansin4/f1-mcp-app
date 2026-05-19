import axios from 'axios'

const api = axios.create({
    baseURL: import.meta.env.VITE_API_URL ?? 'http://localhost:8000',
});


  export const postChat = async (query: string, conversationId: number | null = null) => {
    try {
        const response = await api.post('/chat', { 
            query, 
            conversation_id: conversationId  // Backend expects snake_case
        });
        return response.data;
    } catch (error) {
  
        console.error('Error getting tools:', error);
        throw error;
    }
  }

  export const postModel = async (model: string) => {
    try {
        const response = await api.post('/model', { model });
        return response.data;
    } catch (error) {
        console.error('Error posting model:', error);
        throw error;
    }
  }

  export const getCurrentModel = async () => {
    try {
        const response = await api.get('/model');
        return response.data;
    } catch (error) {
        console.error('Error getting current model:', error);
        throw error;
    }
  }

  export const getRecents = async () => {
    try {
        const response = await api.get('/recents');
        return response.data;
    } catch (error) {
        console.error('Error getting recents:', error);
        throw error;
    }
  }

  export const getConversation = async (conversationId: number) => {
    try {
        const response = await api.get(`/conversation/${conversationId}`);
        return response.data;
    } catch (error) {
        console.error('Error getting conversation:', error);
        throw error;
    }
  }
  export const getConversationMessages = async (conversationId: number) => {
    try {
        const response = await api.get(`/conversation/${conversationId}/messages`);
        return response.data;
    } catch (error) {
        console.error('Error getting conversation messages:', error);
        throw error;
    }
  }
  export const getTools = async () => {
    try {
        const response = await api.get('/tools');
        return response.data;
    } catch (error) {
        console.error('Error getting tools:', error);
        throw error;
    }
  }
  export const getConversationTools = async (conversationId: number) => {
    try {
        const response = await api.get(`/conversation/${conversationId}/tools`);
        return response.data;
    } catch (error) {
        console.error('Error getting conversation tools:', error);
        throw error;
    }
  }

  export const updateConversationTitle = async (conversationId: number, title: string) => {
    try {
        const response = await api.put(`/conversation/${conversationId}`, { title });
        return response.data;
    } catch (error) {
        console.error('Error updating conversation title:', error);
        throw error;
    }
  }

  export const deleteConversation = async (conversationId: number) => {
    try {
        const response = await api.delete(`/conversation/${conversationId}`);
        return response.data;
    } catch (error) {
        console.error('Error deleting conversation:', error);
        throw error;
    }
  }


