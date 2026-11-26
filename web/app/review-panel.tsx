"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";

import {
  ApiError,
  checkForm,
  deleteReview,
  getReview,
  listReviews,
  MAX_UPLOAD_BYTES,
  ReviewDetail,
  ReviewIssue,
  ReviewSummary,
} from "@/lib/api";
import styles from "./review-panel.module.css";

export function ReviewPanel({ onSessionExpired }: { onSessionExpired: () => void }) {
  const [file, setFile] = useState<File | null>(null);
  const [current, setCurrent] = useState<ReviewDetail | null>(null);
  const [history, setHistory] = useState<ReviewSummary[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  const fail = useCallback((failure: unknown) => {
    if (failure instanceof ApiError && failure.status === 401) onSessionExpired();
    else setError(failure instanceof Error ? failure.message : "Something went wrong.");
  }, [onSessionExpired]);

  const refresh = useCallback(() => {
    listReviews().then(setHistory).catch(fail);
  }, [fail]);

  useEffect(refresh, [refresh]);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    if (!file) return;
    if (file.size > MAX_UPLOAD_BYTES) {
      setError("The file is too large. Upload a PDF of 5 MB or less.");
      return;
    }
    setPending(true);
    setError(null);
    try {
      setCurrent(await checkForm(file));
      refresh();
    } catch (failure) {
      fail(failure);
    } finally {
      setPending(false);
    }
  }

  async function open(id: number) {
    setError(null);
    try {
      setCurrent(await getReview(id));
    } catch (failure) {
      fail(failure);
    }
  }

  async function remove(id: number) {
    setError(null);
    try {
      await deleteReview(id);
      if (current?.id === id) setCurrent(null);
      refresh();
    } catch (failure) {
      fail(failure);
    }
  }

  return (
    <section className={styles.panel} aria-label="Check a form">
      <h2>Check your Form I-765</h2>
      <p className={styles.hint}>
        Upload the official fillable PDF from uscis.gov after you fill it in on a computer. ClearPath checks common
        mistakes and shows the instruction behind each one. Your file is read once and <strong>not kept</strong>:
        only the list of problems is saved. Scanned or printed forms can&apos;t be read.
      </p>

      <form className={styles.upload} onSubmit={onSubmit}>
        <input
          type="file"
          accept="application/pdf,.pdf"
          aria-label="Filled-in Form I-765 (PDF)"
          onChange={(event) => setFile(event.target.files?.[0] ?? null)}
        />
        <button className={styles.check} type="submit" disabled={!file || pending}>
          {pending ? "Checking…" : "Check form"}
        </button>
      </form>
      {error && <p className={styles.error} role="alert">{error}</p>}

      {current && <ReviewResult review={current} />}

      {history.length > 0 && (
        <div className={styles.history}>
          <h3>Earlier checks</h3>
          <ul>
            {history.map((review) => (
              <li key={review.id} className={review.id === current?.id ? styles.selected : ""}>
                <button type="button" className={styles.open} onClick={() => open(review.id)}>
                  <span>{review.filename}</span>
                  <span className={styles.meta}>
                    {new Date(review.checked_at).toLocaleString()} · {count(review.errors, "error")},{" "}
                    {count(review.warnings, "warning")}
                  </span>
                </button>
                <button type="button" className={styles.delete} onClick={() => remove(review.id)}
                        aria-label={`Delete the check of ${review.filename}`}>
                  Delete
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}

function ReviewResult({ review }: { review: ReviewDetail }) {
  return (
    <div className={styles.result} aria-live="polite">
      <p className={styles.summary}>
        <strong>{review.filename}</strong>: {count(review.errors, "error")} and {count(review.warnings, "warning")}.
      </p>
      {review.issues.length === 0 && (
        <p className={styles.clean}>
          No problems found by these checks. They cover common mistakes only, so this doesn&apos;t guarantee USCIS will
          accept the form. Remember to sign it by hand.
        </p>
      )}
      <ul className={styles.issues}>
        {review.issues.map((issue, index) => (
          <IssueView key={index} issue={issue} />
        ))}
      </ul>
    </div>
  );
}

function IssueView({ issue }: { issue: ReviewIssue }) {
  return (
    <li className={`${styles.issue} ${issue.severity === "error" ? styles.issueError : styles.issueWarning}`}>
      <span className={styles.badge}>{issue.severity === "error" ? "Error" : "Check"}</span>
      <div>
        <p className={styles.location}>{issue.location}</p>
        <p>{issue.message}</p>
        {issue.source && <p className={styles.source}>Source: {issue.source}</p>}
      </div>
    </li>
  );
}

function count(n: number, word: string): string {
  return `${n} ${word}${n === 1 ? "" : "s"}`;
}
