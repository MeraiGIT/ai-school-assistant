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
import { cn } from "@/lib/utils";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { UserPlus, Trash2, MessageCircle } from "lucide-react";

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

  return (
    <div>
      <h1 className="text-3xl font-semibold text-[#1D1D1F] mb-8 tracking-tight">
        Students
      </h1>

      {/* Add student form */}
      <div className="glass rounded-2xl p-6 mb-6">
        <h2 className="text-lg font-semibold text-[#1D1D1F] mb-4 flex items-center gap-2">
          <UserPlus className="w-5 h-5 text-[#007AFF]" />
          Add Student
        </h2>
        <form onSubmit={handleAdd} className="flex gap-3 items-end">
          <div className="flex-1">
            <label className="block text-sm font-medium text-[#1D1D1F]/80 mb-1.5">
              Telegram Username
            </label>
            <Input
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder="@username"
            />
          </div>
          <div className="flex-1">
            <label className="block text-sm font-medium text-[#1D1D1F]/80 mb-1.5">
              Display Name (optional)
            </label>
            <Input
              type="text"
              value={displayName}
              onChange={(e) => setDisplayName(e.target.value)}
              placeholder="Ivan Ivanov"
            />
          </div>
          <Button
            type="submit"
            disabled={adding || !username.trim()}
            className="bg-[#007AFF] hover:bg-[#0066DD] text-white shadow-sm"
          >
            {adding ? "Adding..." : "Add Student"}
          </Button>
        </form>
      </div>

      <div className="flex gap-6">
        {/* Student list */}
        <div className="flex-1 glass rounded-2xl overflow-hidden">
          <div className="px-6 py-4 border-b border-black/[0.04]">
            <h2 className="text-lg font-semibold text-[#1D1D1F]">
              Student List ({students.length})
            </h2>
          </div>

          {students.length === 0 ? (
            <p className="p-6 text-[#86868B] text-center">
              No students added yet.
            </p>
          ) : (
            <div className="divide-y divide-black/[0.04]">
              {students.map((student) => (
                <div
                  key={student.id}
                  className={cn(
                    "px-6 py-4 cursor-pointer transition-colors duration-150",
                    selectedStudent?.id === student.id
                      ? "bg-[#007AFF]/8 border-l-2 border-[#007AFF] pl-[22px]"
                      : "hover:bg-[#007AFF]/[0.03]"
                  )}
                  onClick={() => viewConversation(student)}
                >
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-sm font-medium text-[#1D1D1F]">
                        @{student.telegram_username}
                        {student.display_name && (
                          <span className="text-[#86868B] ml-2">
                            ({student.display_name})
                          </span>
                        )}
                      </p>
                      <div className="flex items-center gap-2 mt-2">
                        <Badge
                          variant="secondary"
                          className={cn(
                            "text-xs border",
                            student.status === "active" &&
                              "bg-[#34C759]/15 text-[#248A3D] border-[#34C759]/30",
                            student.status === "pending" &&
                              "bg-[#FF9500]/15 text-[#C93400] border-[#FF9500]/30",
                            student.status === "paused" &&
                              "bg-[#8E8E93]/15 text-[#636366] border-[#8E8E93]/30"
                          )}
                        >
                          {student.status}
                        </Badge>
                        <Select
                          value={student.level}
                          onValueChange={(val) =>
                            handleLevelChange(student.id, val)
                          }
                        >
                          <SelectTrigger
                            size="sm"
                            className="h-6 w-[110px] text-xs"
                            onClick={(e) => e.stopPropagation()}
                          >
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            <SelectItem value="beginner">beginner</SelectItem>
                            <SelectItem value="intermediate">
                              intermediate
                            </SelectItem>
                            <SelectItem value="advanced">advanced</SelectItem>
                          </SelectContent>
                        </Select>
                        <Select
                          value={student.status}
                          onValueChange={(val) =>
                            handleStatusChange(student.id, val)
                          }
                        >
                          <SelectTrigger
                            size="sm"
                            className="h-6 w-[90px] text-xs"
                            onClick={(e) => e.stopPropagation()}
                          >
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            <SelectItem value="pending">pending</SelectItem>
                            <SelectItem value="active">active</SelectItem>
                            <SelectItem value="paused">paused</SelectItem>
                          </SelectContent>
                        </Select>
                      </div>
                    </div>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={(e) => {
                        e.stopPropagation();
                        handleDelete(student.id);
                      }}
                      className="text-[#86868B] hover:text-[#FF3B30] hover:bg-[#FF3B30]/10"
                    >
                      <Trash2 className="w-4 h-4" />
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Conversation panel */}
        <div className="w-96 glass rounded-2xl flex flex-col max-h-[600px]">
          <div className="px-6 py-4 border-b border-black/[0.04]">
            <h2 className="text-lg font-semibold text-[#1D1D1F] flex items-center gap-2">
              <MessageCircle className="w-5 h-5 text-[#007AFF]" />
              {selectedStudent
                ? `@${selectedStudent.telegram_username}`
                : "Select a student"}
            </h2>
          </div>

          <div className="flex-1 overflow-y-auto p-4 space-y-3 custom-scrollbar">
            {!selectedStudent ? (
              <p className="text-[#AEAEB2] text-center text-sm mt-8">
                Click a student to view their conversation
              </p>
            ) : messages.length === 0 ? (
              <p className="text-[#AEAEB2] text-center text-sm mt-8">
                No messages yet
              </p>
            ) : (
              messages.map((msg) => (
                <div
                  key={msg.id}
                  className={cn(
                    "text-sm p-3 max-w-[85%]",
                    msg.role === "student"
                      ? "bg-[#E9E9EB] text-[#1D1D1F] rounded-2xl rounded-bl-md"
                      : "bg-[#007AFF] text-white ml-auto rounded-2xl rounded-br-md"
                  )}
                >
                  <p className="whitespace-pre-wrap">{msg.content}</p>
                  <p
                    className={cn(
                      "text-xs mt-1",
                      msg.role === "student"
                        ? "text-[#86868B]"
                        : "text-white/60"
                    )}
                  >
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
