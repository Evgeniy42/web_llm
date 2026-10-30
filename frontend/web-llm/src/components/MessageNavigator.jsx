export default function MessageNavigator({ messages, onNavigate }) {
  const userMessages = messages.filter((m) => m.sender === 'user')

  return (
    <aside className="navigator">
      <h3 className="navigator__title">Ваши сообщения</h3>
      {userMessages.length === 0 ? (
        <p className="navigator__empty">Сообщений пока нет</p>
      ) : (
        <ul className="navigator__list">
          {userMessages.map((msg, index) => (
            <li key={msg.id}>
              <button type="button" className="navigator__item" onClick={() => onNavigate(msg.id)}>
                <span className="navigator__number">{index + 1}</span>
                <span className="navigator__text">{msg.text}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </aside>
  )
}
