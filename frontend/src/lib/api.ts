const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

function getToken(): string {
  if (typeof document === "undefined") return "";
  const match = document.cookie.match(/(?:^|; )admin_token=([^;]*)/);
  return match ? decodeURIComponent(match[1]) : "";
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const token = getToken();
  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      ...options?.headers,
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
  });

  if (!res.ok) {
    if (res.status === 401) {
      // Token invalid or expired — clear cookie and redirect to login
      document.cookie = "admin_token=; path=/; max-age=0";
      window.location.href = "/login";
      throw new Error("Unauthorized");
    }
    const error = await res.text();
    throw new Error(error || `Request failed: ${res.status}`);
  }

  return res.json();
}

// Auth
export async function validateToken(token: string): Promise<boolean> {
  try {
    const res = await fetch(`${API_BASE}/api/stats`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    return res.ok;
  } catch {
    return false;
  }
}

// Stats
export async function getStats() {
  return request<{
    documents_count: number;
    students_count: number;
    messages_count: number;
  }>("/api/stats");
}

// Documents
export interface Document {
  id: string;
  filename: string;
  file_type: string;
  title: string;
  module: string;
  chunk_count: number;
  uploaded_at: string;
}

export async function getDocuments() {
  return request<Document[]>("/api/documents");
}

export async function uploadDocument(file: File, title?: string, module?: string) {
  const formData = new FormData();
  formData.append("file", file);
  if (title) formData.append("title", title);
  if (module) formData.append("module", module);

  return request<{ document_id: string; chunks: number; filename: string }>(
    "/api/documents/upload",
    { method: "POST", body: formData }
  );
}

export async function deleteDocument(id: string) {
  return request<{ status: string }>(`/api/documents/${id}`, { method: "DELETE" });
}

// Students
export interface Student {
  id: string;
  telegram_username: string;
  telegram_id: number | null;
  display_name: string | null;
  level: string;
  status: string;
  first_contact_at: string | null;
  last_active_at: string | null;
  created_at: string;
}

export async function getStudents() {
  return request<Student[]>("/api/students");
}

export async function addStudent(telegram_username: string, display_name?: string) {
  return request<Student>("/api/students", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ telegram_username, display_name }),
  });
}

export async function updateStudent(
  id: string,
  updates: { level?: string; status?: string; display_name?: string }
) {
  return request<{ status: string }>(`/api/students/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(updates),
  });
}

export async function deleteStudent(id: string) {
  return request<{ status: string }>(`/api/students/${id}`, { method: "DELETE" });
}

// Conversations
export interface Message {
  id: string;
  student_id: string;
  role: string;
  content: string;
  intent: string | null;
  created_at: string;
}

export async function getConversations(studentId: string) {
  return request<Message[]>(`/api/conversations/${studentId}`);
}
