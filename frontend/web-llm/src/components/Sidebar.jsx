export default function Sidebar({ chats, activeChatId, onSelectChat, onCreateChat }) {
  return (
    <aside className="sidebar">
      <button type="button" className="btn btn--primary sidebar__new-chat" onClick={onCreateChat}>
        <svg
          className="btn-icon"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          <line x1="12" y1="5" x2="12" y2="19" />
          <line x1="5" y1="12" x2="19" y2="12" />
        </svg>
        Новый чат
      </button>
      <nav className="sidebar__chats">
        {chats.length === 0 ? (
          <p className="sidebar__empty">Нет созданных чатов</p>
        ) : (
          <ul className="sidebar__list">
            {chats.map((chat) => (
              <li key={chat.id}>
                <button
                  type="button"
                  className={`sidebar__chat-item ${chat.id === activeChatId ? 'sidebar__chat-item--active' : ''}`}
                  onClick={() => onSelectChat(chat.id)}
                >
                  <svg
                    className="sidebar__chat-icon"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  >
                    <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
                  </svg>
                  <span className="sidebar__chat-title">{chat.title}</span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </nav>
    </aside>
  )
}
