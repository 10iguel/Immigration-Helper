"use client";

import { FormEvent, KeyboardEvent, useEffect, useRef, useState } from "react";

import { AnswerReply, ApiError, ask, getConversation, MAX_QUESTION_CHARS, StoredMessage } from "@/lib/api";
import styles from "./chat.module.css";

type MessageContent =
  | { role: "user"; text: string }
  | { role: "assistant"; reply: AnswerReply }
  | { role: "error"; text: string };
type Message = MessageContent & { id: number };

const EXAMPLES = [
  "My green card application is still being processed. Can I get permission to work while I wait?",
  "My birth certificate is in Spanish. Do I need to get it translated?",
  "I have a green card and need to live abroad for about 18 months. How do I make sure I can come back?",
];

type ChatProps = {
  conversationId: number | null; // null starts a new conversation with the first question
  onSaved: (conversationId: number) => void;
  onSessionExpired: () => void;
};

export function Chat({ conversationId: openedId, onSaved, onSessionExpired }: ChatProps) {
  const [conversationId, setConversationId] = useState(openedId);
  const [messages, setMessages] = useState<Message[]>([]);
  const [loading, setLoading] = useState(openedId !== null);
  const [draft, setDraft] = useState("");
  const [pending, setPending] = useState(false);
  const nextId = useRef(0);
  const endRef = useRef<HTMLDivElement>(null);

  const withId = (content: MessageContent): Message => ({ ...content, id: nextId.current++ });
  const add = (content: MessageContent) => setMessages((current) => [...current, withId(content)]);

  useEffect(() => {
    if (openedId === null) return;
    getConversation(openedId)
      .then((conversation) => setMessages(conversation.messages.map((message) => withId(fromStored(message)))))
      .catch((error) => {
        if (error instanceof ApiError && error.status === 401) onSessionExpired();
        else setMessages([withId({ role: "error", text: messageOf(error) })]);
      })
      .finally(() => setLoading(false));
    // Runs once per opened conversation; the parent remounts this component to open another one.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages, pending]);

  async function send(question: string) {
    const text = question.trim();
    if (!text || pending) return;
    add({ role: "user", text });
    setDraft("");
    setPending(true);
    try {
      const reply = await ask(text, conversationId);
      add({ role: "assistant", reply });
      setConversationId(reply.conversation_id);
      onSaved(reply.conversation_id);
    } catch (error) {
      if (error instanceof ApiError && error.status === 401) onSessionExpired();
      else add({ role: "error", text: messageOf(error) });
    } finally {
      setPending(false);
    }
  }

  function onSubmit(event: FormEvent) {
    event.preventDefault();
    send(draft);
  }

  function onKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      send(draft);
    }
  }

  return (
    <div className={styles.chat}>
      <div className={styles.messages} aria-live="polite">
        {loading && <p className={styles.empty}>Loading conversation…</p>}
        {!loading && messages.length === 0 && (
          <div className={styles.empty}>
            <p>Ask about Forms I-130, I-131, I-485 or I-765. Your chat is saved, and you can ask follow-up questions
              like &ldquo;what about my mom?&rdquo;</p>
            <div className={styles.examples}>
              {EXAMPLES.map((example) => (
                <button key={example} type="button" className={styles.example} onClick={() => send(example)}>
                  {example}
                </button>
              ))}
            </div>
          </div>
        )}
        {messages.map((message) => (
          <MessageView key={message.id} message={message} />
        ))}
        {pending && <div className={`${styles.bubble} ${styles.assistant} ${styles.thinking}`}>Searching the instructions…</div>}
        <div ref={endRef} />
      </div>

      <form className={styles.composer} onSubmit={onSubmit}>
        <textarea
          className={styles.input}
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          onKeyDown={onKeyDown}
          maxLength={MAX_QUESTION_CHARS}
          rows={2}
          placeholder="Type your question… (Enter to send, Shift+Enter for a new line)"
          aria-label="Your question"
          disabled={loading}
        />
        <button className={styles.send} type="submit" disabled={pending || loading || !draft.trim()}>
          Send
        </button>
      </form>
    </div>
  );
}

function fromStored(message: StoredMessage): MessageContent {
  if (message.role === "user") return { role: "user", text: message.content };
  return {
    role: "assistant",
    reply: {
      reply_type: message.reply_type ?? "answer",
      answer: message.content,
      sources: message.sources,
      warnings: [],
      cost_usd: message.cost_usd ?? 0,
    },
  };
}

function messageOf(error: unknown): string {
  return error instanceof Error ? error.message : "Something went wrong.";
}

function MessageView({ message }: { message: Message }) {
  if (message.role === "user") {
    return <div className={`${styles.bubble} ${styles.user}`}>{message.text}</div>;
  }
  if (message.role === "error") {
    return <div className={`${styles.bubble} ${styles.error}`} role="alert">{message.text}</div>;
  }
  const { reply } = message;
  return (
    <div className={`${styles.bubble} ${styles.assistant} ${reply.reply_type === "not_covered" ? styles.declined : ""}`}>
      {reply.reply_type === "not_covered" && <p className={styles.tag}>Not covered by the loaded instructions</p>}
      <p className={styles.answer}>{reply.answer}</p>
      {reply.warnings.map((warning) => (
        <p key={warning} className={styles.warning}>⚠ {warning}</p>
      ))}
      {reply.sources.length > 0 && (
        <div className={styles.sources}>
          <p className={styles.sourcesTitle}>Sources</p>
          <ul>
            {reply.sources.map((source) => (
              <li key={source}>{source}</li>
            ))}
          </ul>
        </div>
      )}
      <p className={styles.cost}>Cost of this answer: ${reply.cost_usd.toFixed(4)}</p>
    </div>
  );
}
