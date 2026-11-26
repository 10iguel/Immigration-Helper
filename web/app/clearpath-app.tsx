"use client";

import { useCallback, useEffect, useState } from "react";

import { ApiError, ConversationSummary, getMe, listConversations, logOut, UserInfo } from "@/lib/api";
import { AuthForm } from "./auth-form";
import { Chat } from "./chat";
import { ReviewPanel } from "./review-panel";
import styles from "./clearpath-app.module.css";
import { Sidebar } from "./sidebar";

// undefined = still checking the login cookie, null = logged out
type Session = UserInfo | null | undefined;

export function ClearPathApp() {
  const [user, setUser] = useState<Session>(undefined);
  const [startupError, setStartupError] = useState<string | null>(null);

  useEffect(() => {
    getMe()
      .then(setUser)
      .catch((error) => {
        if (!(error instanceof ApiError && error.status === 401)) setStartupError(error.message);
        setUser(null);
      });
  }, []);

  if (user === undefined) return <p className={styles.status}>Loading…</p>;
  if (user === null) {
    return (
      <>
        {startupError && <p className={styles.status} role="alert">{startupError}</p>}
        <AuthForm onAuthenticated={setUser} />
      </>
    );
  }
  return <Workspace user={user} onLoggedOut={() => setUser(null)} />;
}

function Workspace({ user, onLoggedOut }: { user: UserInfo; onLoggedOut: () => void }) {
  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const [listError, setListError] = useState<string | null>(null);
  // `opened` remounts the chat (a new key) when the user opens a chat or starts a new one; `activeId` only
  // highlights the current chat, so saving the first question doesn't reload the chat on screen.
  const [opened, setOpened] = useState<{ key: number; id: number | null }>({ key: 0, id: null });
  const [activeId, setActiveId] = useState<number | null>(null);
  const [reviewing, setReviewing] = useState(false);

  const refresh = useCallback(() => {
    listConversations()
      .then((list) => {
        setConversations(list);
        setListError(null);
      })
      .catch((error) => setListError(error.message));
  }, []);

  useEffect(refresh, [refresh]);

  function open(id: number | null) {
    setOpened((current) => ({ key: current.key + 1, id }));
    setActiveId(id);
    setReviewing(false);
  }

  function onSaved(id: number) {
    setActiveId(id);
    refresh();
  }

  async function onLogOut() {
    try {
      await logOut();
    } finally {
      onLoggedOut(); // the cookie is cleared by the server; leave the page either way
    }
  }

  return (
    <div className={styles.workspace}>
      <Sidebar
        email={user.email}
        conversations={conversations}
        activeId={activeId}
        error={listError}
        onSelect={open}
        onNewChat={() => open(null)}
        reviewing={reviewing}
        onCheckForm={() => setReviewing(true)}
        onLogOut={onLogOut}
      />
      {reviewing
        ? <ReviewPanel onSessionExpired={onLoggedOut} />
        : <Chat key={opened.key} conversationId={opened.id} onSaved={onSaved} onSessionExpired={onLoggedOut} />}
    </div>
  );
}
