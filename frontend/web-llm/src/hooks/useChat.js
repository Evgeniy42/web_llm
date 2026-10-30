import { useState, useCallback } from 'react'
import { sendMessage as sendMessageToApi } from '../services/chatService'

let nextId = 1

const generateId = () => nextId++

const createMessage = (text, sender) => ({
  id: generateId(),
  text,
  sender,
  timestamp: new Date().toISOString(),
})

const createChat = (title) => ({
  id: generateId(),
  title,
  messages: [],
  createdAt: new Date().toISOString(),
})

export function useChat() {
  const [chats, setChats] = useState(() => [createChat('Новый чат')])
  const [activeChatId, setActiveChatId] = useState(() => chats[0].id)
  const [isLoading, setIsLoading] = useState(false)

  const activeChat = chats.find((c) => c.id === activeChatId) || chats[0]

  const sendMessage = useCallback(async (text) => {
    const trimmed = text.trim()
    if (!trimmed) return

    const userMessage = createMessage(trimmed, 'user')

    setChats((prev) =>
      prev.map((chat) => {
        if (chat.id !== activeChatId) return chat
        const isFirstMessage = chat.messages.length === 0
        return {
          ...chat,
          title: isFirstMessage ? trimmed.slice(0, 30) : chat.title,
          messages: [...chat.messages, userMessage],
        }
      })
    )

    setIsLoading(true)

    try {
      const { response } = await sendMessageToApi(trimmed)
      const botMessage = createMessage(response, 'bot')

      setChats((prev) =>
        prev.map((chat) => {
          if (chat.id !== activeChatId) return chat
          return { ...chat, messages: [...chat.messages, botMessage] }
        })
      )
    } catch {
      const errorMessage = createMessage('Ошибка соединения с сервером. Попробуйте позже.', 'bot')

      setChats((prev) =>
        prev.map((chat) => {
          if (chat.id !== activeChatId) return chat
          return { ...chat, messages: [...chat.messages, errorMessage] }
        })
      )
    } finally {
      setIsLoading(false)
    }
  }, [activeChatId])

  const createNewChat = useCallback(() => {
    const chat = createChat('Новый чат')
    setChats((prev) => [...prev, chat])
    setActiveChatId(chat.id)
  }, [])

  const selectChat = useCallback((chatId) => {
    setActiveChatId(chatId)
  }, [])

  return {
    chats,
    activeChat,
    activeChatId,
    isLoading,
    sendMessage,
    createNewChat,
    selectChat,
  }
}
