"use client";

import { useCallback, useEffect, useState } from "react";
import {
  getDocuments,
  uploadDocument,
  deleteDocument,
  type Document,
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
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { CloudUpload, Loader2, Trash2 } from "lucide-react";

export default function UploadPage() {
  const [documents, setDocuments] = useState<Document[]>([]);
  const [uploading, setUploading] = useState(false);
  const [dragOver, setDragOver] = useState(false);
  const [title, setTitle] = useState("");
  const [module, setModule] = useState("general");

  const loadDocuments = useCallback(() => {
    getDocuments().then(setDocuments).catch(console.error);
  }, []);

  useEffect(() => {
    loadDocuments();
  }, [loadDocuments]);

  async function handleUpload(file: File) {
    setUploading(true);
    try {
      await uploadDocument(file, title || undefined, module);
      setTitle("");
      loadDocuments();
    } catch (e) {
      alert(`Upload failed: ${e instanceof Error ? e.message : e}`);
    } finally {
      setUploading(false);
    }
  }

  async function handleDelete(id: string) {
    if (!confirm("Delete this document and all its chunks?")) return;
    try {
      await deleteDocument(id);
      loadDocuments();
    } catch (e) {
      alert(`Delete failed: ${e instanceof Error ? e.message : e}`);
    }
  }

  function handleDrop(e: React.DragEvent) {
    e.preventDefault();
    setDragOver(false);
    const file = e.dataTransfer.files[0];
    if (file) handleUpload(file);
  }

  function handleFileSelect(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (file) handleUpload(file);
  }

  return (
    <div>
      <h1 className="text-3xl font-semibold text-[#1D1D1F] mb-8 tracking-tight">
        Upload Course Materials
      </h1>

      {/* Upload form */}
      <div className="glass rounded-2xl p-6 mb-6">
        <div className="grid grid-cols-2 gap-4 mb-4">
          <div>
            <label className="block text-sm font-medium text-[#1D1D1F]/80 mb-1.5">
              Title (optional)
            </label>
            <Input
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="Document title"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-[#1D1D1F]/80 mb-1.5">
              Module
            </label>
            <Select value={module} onValueChange={setModule}>
              <SelectTrigger className="w-full">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="general">General</SelectItem>
                <SelectItem value="intro">Introduction</SelectItem>
                <SelectItem value="llm">LLM Basics</SelectItem>
                <SelectItem value="prompting">Prompt Engineering</SelectItem>
                <SelectItem value="rag">RAG</SelectItem>
                <SelectItem value="agents">AI Agents</SelectItem>
                <SelectItem value="fine-tuning">Fine-tuning</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </div>

        <div
          onDragOver={(e) => {
            e.preventDefault();
            setDragOver(true);
          }}
          onDragLeave={() => setDragOver(false)}
          onDrop={handleDrop}
          className={cn(
            "border-2 border-dashed rounded-2xl p-12 text-center transition-all duration-300",
            dragOver
              ? "border-[#007AFF]/50 bg-[#007AFF]/5 shadow-lg shadow-[#007AFF]/5 scale-[1.005]"
              : "border-[#1D1D1F]/10 hover:border-[#1D1D1F]/20 hover:bg-black/[0.01]"
          )}
        >
          {uploading ? (
            <div className="text-[#86868B]">
              <Loader2 className="w-8 h-8 mx-auto mb-3 text-[#007AFF] animate-spin" />
              Processing document...
            </div>
          ) : (
            <>
              <CloudUpload className="w-10 h-10 mx-auto mb-3 text-[#AEAEB2]" />
              <p className="text-[#1D1D1F]/70 mb-2">
                Drag and drop a file here, or click to select
              </p>
              <p className="text-sm text-[#AEAEB2]">
                Supports PDF, DOCX, and TXT files
              </p>
              <input
                type="file"
                accept=".pdf,.docx,.txt"
                onChange={handleFileSelect}
                className="hidden"
                id="file-input"
              />
              <Button asChild className="mt-4 bg-[#007AFF] hover:bg-[#0066DD] text-white shadow-sm">
                <label htmlFor="file-input" className="cursor-pointer">
                  Select File
                </label>
              </Button>
            </>
          )}
        </div>
      </div>

      {/* Document list */}
      <div className="glass rounded-2xl overflow-hidden">
        <div className="px-6 py-4 border-b border-black/[0.04]">
          <h2 className="text-lg font-semibold text-[#1D1D1F]">
            Uploaded Documents ({documents.length})
          </h2>
        </div>

        {documents.length === 0 ? (
          <p className="p-6 text-[#86868B] text-center">
            No documents uploaded yet.
          </p>
        ) : (
          <Table>
            <TableHeader>
              <TableRow className="border-black/[0.04] hover:bg-transparent">
                <TableHead className="px-6">Title</TableHead>
                <TableHead>Type</TableHead>
                <TableHead>Module</TableHead>
                <TableHead>Chunks</TableHead>
                <TableHead>Uploaded</TableHead>
                <TableHead className="text-right pr-6">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {documents.map((doc) => (
                <TableRow
                  key={doc.id}
                  className="border-black/[0.04] hover:bg-[#007AFF]/[0.03] transition-colors"
                >
                  <TableCell className="px-6 font-medium text-[#1D1D1F]">
                    {doc.title}
                  </TableCell>
                  <TableCell>
                    <Badge variant="outline" className="text-xs uppercase font-medium">
                      {doc.file_type}
                    </Badge>
                  </TableCell>
                  <TableCell className="text-[#86868B]">{doc.module}</TableCell>
                  <TableCell className="text-[#86868B]">{doc.chunk_count}</TableCell>
                  <TableCell className="text-[#86868B]">
                    {new Date(doc.uploaded_at).toLocaleDateString()}
                  </TableCell>
                  <TableCell className="text-right pr-6">
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => handleDelete(doc.id)}
                      className="text-[#86868B] hover:text-[#FF3B30] hover:bg-[#FF3B30]/10"
                    >
                      <Trash2 className="w-4 h-4" />
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </div>
    </div>
  );
}
