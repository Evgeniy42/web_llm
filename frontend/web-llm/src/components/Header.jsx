export default function Header() {
  return (
    <header className="header">
      <div className="header__logo">
        <svg
          className="header__logo-icon"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
        </svg>
        <span className="header__logo-text">Чат с LLM</span>
      </div>
      <div className="header__auth">
        <button type="button" className="btn btn--ghost">
          Вход
        </button>
        <button type="button" className="btn btn--primary">
          Регистрация
        </button>
      </div>
    </header>
  )
}
