"use client";

import { FormEvent, KeyboardEvent, useEffect, useRef, useState } from "react";

import { askQuestion, AskResponse, MAX_QUESTION_CHARS } from "@/lib/ask";
import styles from "./chat.module.css";

type MessageContent =
  | { role: "user"; text: string }
  | { role: "assistant"; reply: AskResponse }
  | { role: "error"; text: string };
type Message = MessageContent & { id: number };

const EXAMPLES = [
  "My green card application is still being processed. Can I get permission to work while I wait?",
  "My birth certificate is in Spanish. Do I need to get it translated?",
  "I have a green card and need to live abroad for about 18 months. How do I make sure I can come back?",
];

export function Chat() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [draft, setDraft] = useState("");
  const [pending, setPending] = useState(false);
  const nextId = useRef(0);
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages, pending]);

  const add = (content: MessageContent) =>
    setMessages((current) => [...current, { ...content, id: nextId.current++ }]);

  async function send(question: string) {
    const text = question.trim();
    if (!text || pending) return;
    add({ role: "user", text });
    setDraft("");
    setPending(true);
    try {
      add({ role: "assistant", reply: await askQuestion(text) });
    } catch (error) {
      add({ role: "error", text: error instanceof Error ? error.message : "Something went wrong." });
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
        {messages.length === 0 && (
          <div className={styles.empty}>
            <p>Ask about Forms I-130, I-131, I-485 or I-765. Each question is answered on its own, so include
              the details that matter.</p>
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
        />
        <button className={styles.send} type="submit" disabled={pending || !draft.trim()}>
          Send
        </button>
      </form>
    </div>
  );
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
    <div className={`${styles.bubble} ${styles.assistant} ${reply.answerable ? "" : styles.declined}`}>
      {!reply.answerable && <p className={styles.tag}>Not covered by the loaded instructions</p>}
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
