"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { LayoutDashboard, CloudUpload, GraduationCap, Sparkles, LogOut } from "lucide-react";
import { cn } from "@/lib/utils";
import { API_BASE } from "@/lib/api";

const links = [
  { href: "/", label: "Dashboard", icon: LayoutDashboard },
  { href: "/upload", label: "Upload Materials", icon: CloudUpload },
  { href: "/students", label: "Students", icon: GraduationCap },
];

export default function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="w-64 glass-sidebar text-white min-h-screen p-5 flex flex-col">
      <div className="mb-8 px-2">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-[#007AFF] flex items-center justify-center shadow-lg shadow-[#007AFF]/20">
            <Sparkles className="w-5 h-5 text-white" />
          </div>
          <div>
            <h1 className="text-lg font-semibold text-white tracking-tight">AI School</h1>
            <p className="text-xs text-white/40">Admin Panel</p>
          </div>
        </div>
      </div>

      <nav className="flex-1 space-y-1">
        {links.map((link) => {
          const isActive = pathname === link.href;
          const Icon = link.icon;
          return (
            <Link
              key={link.href}
              href={link.href}
              className={cn(
                "flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm transition-all duration-200",
                isActive
                  ? "bg-white/10 text-white border-l-2 border-[#007AFF] ml-0 pl-[10px]"
                  : "text-white/50 hover:text-white/90 hover:bg-white/5"
              )}
            >
              <Icon className="w-5 h-5 shrink-0" />
              <span className="font-medium">{link.label}</span>
            </Link>
          );
        })}
      </nav>

      <div className="mt-auto pt-4 border-t border-white/8 space-y-3">
        <button
          onClick={async () => {
            try {
              await fetch(`${API_BASE}/api/auth/logout`, {
                method: "POST",
                credentials: "include",
              });
            } catch {}
            document.cookie = "admin_logged_in=; path=/; max-age=0";
            window.location.href = "/login";
          }}
          className="flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm text-white/40 hover:text-white/70 hover:bg-white/5 transition-all duration-200 w-full"
        >
          <LogOut className="w-4 h-4 shrink-0" />
          <span className="font-medium">Sign Out</span>
        </button>
        <p className="text-xs text-white/30 px-2">Gen AI Course Assistant</p>
      </div>
    </aside>
  );
}
