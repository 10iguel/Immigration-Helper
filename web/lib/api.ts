// Client for the Python API (immigration_helper/api/app.py). The login cookie is HttpOnly: the browser sends it
// automatically and this code never sees it.

export const MAX_QUESTION_CHARS = 1000; // same limit the API enforces

export class ApiError extends Error {
  constructor(message: string, readonly status: number) {
    super(message);
  }
}

export type UserInfo = { email: string };

// answer: from the instructions, with sources; not_covered: searched, not in the instructions; conversation: small talk
export type ReplyType = "answer" | "not_covered" | "conversation";

export type AnswerReply = {
  reply_type: ReplyType;
  answer: string;
  sources: string[];
  warnings: string[];
  cost_usd: number;
};

export type AskResponse = AnswerReply & { conversation_id: number };

export type ConversationSummary = { id: number; title: string; updated_at: string };

export type StoredMessage = {
  role: "user" | "assistant";
  content: string;
  reply_type: ReplyType | null;
  sources: string[];
  cost_usd: number | null;
};

export type ConversationDetail = { id: number; title: string; messages: StoredMessage[] };

export const getMe = () => request<UserInfo>("/api/auth/me");
export const signUp = (email: string, password: string) => post<UserInfo>("/api/auth/signup", { email, password });
export const logIn = (email: string, password: string) => post<UserInfo>("/api/auth/login", { email, password });
export const logOut = () => post<void>("/api/auth/logout", {});
export const listConversations = () => request<ConversationSummary[]>("/api/conversations");
export const getConversation = (id: number) => request<ConversationDetail>(`/api/conversations/${id}`);
export const ask = (question: string, conversationId: number | null) =>
  post<AskResponse>("/api/ask", { question, conversation_id: conversationId });

export type ReviewIssue = {
  severity: "error" | "warning";
  location: string; // e.g. "Part 2, Item Number 16"
  message: string;
  source: string | null; // the instruction passage behind the check
};

export type ReviewSummary = {
  id: number;
  form: string;
  filename: string;
  checked_at: string;
  errors: number;
  warnings: number;
};

export type ReviewDetail = ReviewSummary & { issues: ReviewIssue[] };

export const MAX_UPLOAD_BYTES = 5 * 1024 * 1024; // same limit the API enforces

export const checkForm = (file: File) => {
  const body = new FormData(); // the browser sets the multipart Content-Type itself
  body.append("file", file);
  return request<ReviewDetail>("/api/reviews", { method: "POST", body });
};
export const listReviews = () => request<ReviewSummary[]>("/api/reviews");
export const getReview = (id: number) => request<ReviewDetail>(`/api/reviews/${id}`);
export const deleteReview = (id: number) => request<void>(`/api/reviews/${id}`, { method: "DELETE" });

function post<T>(path: string, body: object): Promise<T> {
  return request<T>(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(path, init);
  } catch {
    throw new ApiError("Could not reach the server. Check your connection and try again.", 0);
  }
  if (!response.ok) {
    throw new ApiError(await errorMessage(response), response.status);
  }
  return response.status === 204 ? (undefined as T) : response.json();
}

async function errorMessage(response: Response): Promise<string> {
  try {
    const body = await response.json();
    if (typeof body.detail === "string") return body.detail; // our own messages, written for users
  } catch {
    // Not JSON (for example the dev proxy's own error page): fall through to a generic message.
  }
  if (response.status === 422) return `Please check what you typed (questions can be up to ${MAX_QUESTION_CHARS} characters).`;
  if (response.status >= 500) {
    // The dev proxy answers 500 when the Python API isn't running.
    return "The assistant is not available right now. Check that the API server is running, then try again.";
  }
  return `The server returned an error (${response.status}). Please try again.`;
}
