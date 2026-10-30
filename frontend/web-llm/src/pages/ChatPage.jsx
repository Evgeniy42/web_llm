import { useState } from 'react'
import Header from '../components/Header'
import Sidebar from '../components/Sidebar'
import Chat from '../components/Chat'
import MessageNavigator from '../components/MessageNavigator'
import Footer from '../components/Footer'
import { useChat } from '../hooks/useChat'

export default function ChatPage() {
  const { chats, activeChat, activeChatId, isLoading, sendMessage, createNewChat, selectChat } = useChat()
  const [scrollToMessageId, setScrollToMessageId] = useState(null)

  const handleNavigate = (messageId) => {
    setScrollToMessageId(null)
    requestAnimationFrame(() => setScrollToMessageId(messageId))
  }

  return (
    <div className="app">
      <Header />
      <div className="app__body">
        <Sidebar
          chats={chats}
          activeChatId={activeChatId}
          onSelectChat={selectChat}
          onCreateChat={createNewChat}
        />
        <Chat chat={activeChat} onSendMessage={sendMessage} scrollToMessageId={scrollToMessageId} isLoading={isLoading} />
        <MessageNavigator messages={activeChat.messages} onNavigate={handleNavigate} />
      </div>
      <Footer />
    </div>
  )
}
