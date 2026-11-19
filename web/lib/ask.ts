// Client for the Python API's POST /api/ask (immigration_helper/api/app.py).

export const MAX_QUESTION_CHARS = 1000; // same limit the API enforces

export type AskResponse = {
  answerable: boolean;
  answer: string;
  sources: string[];
  warnings: string[];
  cost_usd: number;
};

export async function askQuestion(question: string): Promise<AskResponse> {
  let response: Response;
  try {
    response = await fetch("/api/ask", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question }),
    });
  } catch {
    throw new Error("Could not reach the server. Check that the API is running.");
  }
  if (!response.ok) {
    throw new Error(await errorMessage(response));
  }
  return response.json();
}

async function errorMessage(response: Response): Promise<string> {
  try {
    const body = await response.json();
    if (typeof body.detail === "string") return body.detail;
  } catch {
    // Not JSON (for example the dev proxy's own error page): fall through to the generic message.
  }
  if (response.status === 422) return "Please write a question of up to 1000 characters.";
  if (response.status >= 500) {
    // The dev proxy answers 500 when the Python API isn't running.
    return "The assistant is not available right now. Check that the API server is running, then try again.";
  }
  return `The server returned an error (${response.status}). Please try again.`;
}
