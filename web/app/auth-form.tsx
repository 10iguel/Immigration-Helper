"use client";

import { FormEvent, useState } from "react";

import { logIn, signUp, UserInfo } from "@/lib/api";
import styles from "./auth-form.module.css";

type Mode = "login" | "signup";

export function AuthForm({ onAuthenticated }: { onAuthenticated: (user: UserInfo) => void }) {
  const [mode, setMode] = useState<Mode>("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setPending(true);
    setError(null);
    try {
      onAuthenticated(await (mode === "login" ? logIn : signUp)(email, password));
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : "Something went wrong.");
    } finally {
      setPending(false);
    }
  }

  function switchMode() {
    setMode(mode === "login" ? "signup" : "login");
    setError(null);
  }

  return (
    <form className={styles.card} onSubmit={onSubmit}>
      <h2>{mode === "login" ? "Log in" : "Create an account"}</h2>
      <p className={styles.hint}>Your chats are saved to your account so you can come back to them.</p>
      <label className={styles.field}>
        Email
        <input type="email" autoComplete="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
      </label>
      <label className={styles.field}>
        Password
        <input
          type="password"
          autoComplete={mode === "login" ? "current-password" : "new-password"}
          required
          minLength={mode === "signup" ? 8 : undefined}
          maxLength={200}
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />
        {mode === "signup" && <span className={styles.hint}>At least 8 characters.</span>}
      </label>
      {error && <p className={styles.error} role="alert">{error}</p>}
      <button className={styles.submit} type="submit" disabled={pending}>
        {pending ? "Please wait…" : mode === "login" ? "Log in" : "Create account"}
      </button>
      <button className={styles.switch} type="button" onClick={switchMode}>
        {mode === "login" ? "New here? Create an account" : "Already have an account? Log in"}
      </button>
    </form>
  );
}
