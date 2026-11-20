"use client";

import { ConversationSummary } from "@/lib/api";
import styles from "./sidebar.module.css";

type SidebarProps = {
  email: string;
  conversations: ConversationSummary[];
  activeId: number | null;
  error: string | null;
  onSelect: (id: number) => void;
  onNewChat: () => void;
  onLogOut: () => void;
};

export function Sidebar({ email, conversations, activeId, error, onSelect, onNewChat, onLogOut }: SidebarProps) {
  return (
    <nav className={styles.sidebar} aria-label="Your chats">
      <button className={styles.newChat} type="button" onClick={onNewChat}>
        + New chat
      </button>
      <ul className={styles.list}>
        {conversations.map((conversation) => (
          <li key={conversation.id}>
            <button
              type="button"
              className={`${styles.item} ${conversation.id === activeId ? styles.active : ""}`}
              aria-current={conversation.id === activeId ? "page" : undefined}
              onClick={() => onSelect(conversation.id)}
            >
              <span className={styles.title}>{conversation.title}</span>
              <span className={styles.date}>{new Date(conversation.updated_at).toLocaleDateString()}</span>
            </button>
          </li>
        ))}
        {conversations.length === 0 && !error && <li className={styles.note}>No saved chats yet.</li>}
        {error && <li className={styles.error} role="alert">{error}</li>}
      </ul>
      <div className={styles.account}>
        <span className={styles.email} title={email}>{email}</span>
        <button className={styles.logOut} type="button" onClick={onLogOut}>
          Log out
        </button>
      </div>
    </nav>
  );
}
