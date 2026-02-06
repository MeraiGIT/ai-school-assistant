"use client";

import { useCallback, useEffect, useState } from "react";
import {
  getStudents,
  addStudent,
  updateStudent,
  deleteStudent,
  getConversations,
  type Student,
  type Message,
} from "@/lib/api";

export default function StudentsPage() {
  const [students, setStudents] = useState<Student[]>([]);
  const [username, setUsername] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [adding, setAdding] = useState(false);
  const [selectedStudent, setSelectedStudent] = useState<Student | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);

  const loadStudents = useCallback(() => {
    getStudents().then(setStudents).catch(console.error);
  }, []);

  useEffect(() => {
    loadStudents();
  }, [loadStudents]);

  async function handleAdd(e: React.FormEvent) {
    e.preventDefault();
    if (!username.trim()) return;
    setAdding(true);
    try {
      await addStudent(username.trim(), displayName.trim() || undefined);
      setUsername("");
      setDisplayName("");
      loadStudents();
    } catch (e) {
      alert(`Failed: ${e instanceof Error ? e.message : e}`);
    } finally {
      setAdding(false);
    }
  }

  async function handleDelete(id: string) {
    if (!confirm("Remove this student?")) return;
    try {
      await deleteStudent(id);
      if (selectedStudent?.id === id) setSelectedStudent(null);
      loadStudents();
    } catch (e) {
      alert(`Failed: ${e instanceof Error ? e.message : e}`);
    }
  }

  async function handleLevelChange(id: string, level: string) {
    try {
      await updateStudent(id, { level });
      loadStudents();
    } catch (e) {
      alert(`Failed: ${e instanceof Error ? e.message : e}`);
    }
  }

  async function handleStatusChange(id: string, status: string) {
    try {
      await updateStudent(id, { status });
      loadStudents();
    } catch (e) {
      alert(`Failed: ${e instanceof Error ? e.message : e}`);
    }
  }

  async function viewConversation(student: Student) {
    setSelectedStudent(student);
    try {
      const msgs = await getConversations(student.id);
      setMessages(msgs);
    } catch {
      setMessages([]);
    }
  }

  const statusColors: Record<string, string> = {
    active: "bg-green-100 text-green-800",
    pending: "bg-yellow-100 text-yellow-800",
    paused: "bg-gray-100 text-gray-800",
  };

  return (
    <div>
      <h1 className="text-2xl font-bold text-gray-900 mb-6">Students</h1>

      {/* Add student form */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 mb-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">
          Add Student
        </h2>
        <form onSubmit={handleAdd} className="flex gap-3 items-end">
          <div className="flex-1">
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Telegram Username
            </label>
            <input
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder="@username"
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
          <div className="flex-1">
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Display Name (optional)
            </label>
            <input
              type="text"
              value={displayName}
              onChange={(e) => setDisplayName(e.target.value)}
              placeholder="Ivan Ivanov"
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
          <button
            type="submit"
            disabled={adding || !username.trim()}
            className="bg-blue-600 text-white px-6 py-2 rounded-lg text-sm hover:bg-blue-700 disabled:opacity-50 transition-colors whitespace-nowrap"
          >
            {adding ? "Adding..." : "Add Student"}
          </button>
        </form>
      </div>

      <div className="flex gap-6">
        {/* Student list */}
        <div className="flex-1 bg-white rounded-xl shadow-sm border border-gray-200">
          <div className="px-6 py-4 border-b border-gray-200">
            <h2 className="text-lg font-semibold text-gray-900">
              Student List ({students.length})
            </h2>
          </div>

          {students.length === 0 ? (
            <p className="p-6 text-gray-500 text-center">
              No students added yet.
            </p>
          ) : (
            <div className="divide-y divide-gray-200">
              {students.map((student) => (
                <div
                  key={student.id}
                  className={`px-6 py-4 hover:bg-gray-50 cursor-pointer ${
                    selectedStudent?.id === student.id ? "bg-blue-50" : ""
                  }`}
                  onClick={() => viewConversation(student)}
                >
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-sm font-medium text-gray-900">
                        @{student.telegram_username}
                        {student.display_name && (
                          <span className="text-gray-500 ml-2">
                            ({student.display_name})
                          </span>
                        )}
                      </p>
                      <div className="flex items-center gap-2 mt-1">
                        <span
                          className={`inline-block px-2 py-0.5 rounded-full text-xs font-medium ${
                            statusColors[student.status] || statusColors.pending
                          }`}
                        >
                          {student.status}
                        </span>
                        <select
                          value={student.level}
                          onChange={(e) => {
                            e.stopPropagation();
                            handleLevelChange(student.id, e.target.value);
                          }}
                          onClick={(e) => e.stopPropagation()}
                          className="text-xs border border-gray-200 rounded px-1 py-0.5"
                        >
                          <option value="beginner">beginner</option>
                          <option value="intermediate">intermediate</option>
                          <option value="advanced">advanced</option>
                        </select>
                        <select
                          value={student.status}
                          onChange={(e) => {
                            e.stopPropagation();
                            handleStatusChange(student.id, e.target.value);
                          }}
                          onClick={(e) => e.stopPropagation()}
                          className="text-xs border border-gray-200 rounded px-1 py-0.5"
                        >
                          <option value="pending">pending</option>
                          <option value="active">active</option>
                          <option value="paused">paused</option>
                        </select>
                      </div>
                    </div>
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        handleDelete(student.id);
                      }}
                      className="text-red-500 hover:text-red-700 text-sm"
                    >
                      Remove
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Conversation panel */}
        <div className="w-96 bg-white rounded-xl shadow-sm border border-gray-200 flex flex-col max-h-[600px]">
          <div className="px-6 py-4 border-b border-gray-200">
            <h2 className="text-lg font-semibold text-gray-900">
              {selectedStudent
                ? `Chat: @${selectedStudent.telegram_username}`
                : "Select a student"}
            </h2>
          </div>

          <div className="flex-1 overflow-y-auto p-4 space-y-3">
            {!selectedStudent ? (
              <p className="text-gray-400 text-center text-sm mt-8">
                Click a student to view their conversation
              </p>
            ) : messages.length === 0 ? (
              <p className="text-gray-400 text-center text-sm mt-8">
                No messages yet
              </p>
            ) : (
              messages.map((msg) => (
                <div
                  key={msg.id}
                  className={`text-sm rounded-lg p-3 max-w-[85%] ${
                    msg.role === "student"
                      ? "bg-gray-100 text-gray-900"
                      : "bg-blue-100 text-blue-900 ml-auto"
                  }`}
                >
                  <p className="whitespace-pre-wrap">{msg.content}</p>
                  <p className="text-xs opacity-50 mt-1">
                    {new Date(msg.created_at).toLocaleTimeString()}
                    {msg.intent && ` [${msg.intent}]`}
                  </p>
                </div>
              ))
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
