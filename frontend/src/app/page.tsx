"use client";

import { useEffect, useState } from "react";
import { getStats } from "@/lib/api";
import { cn } from "@/lib/utils";
import { FileText, Users, MessageCircle } from "lucide-react";

export default function Dashboard() {
  const [stats, setStats] = useState({
    documents_count: 0,
    students_count: 0,
    messages_count: 0,
  });
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getStats()
      .then(setStats)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  const cards = [
    {
      label: "Documents",
      value: stats.documents_count,
      icon: FileText,
      color: "bg-[#007AFF]",
    },
    {
      label: "Students",
      value: stats.students_count,
      icon: Users,
      color: "bg-[#34C759]",
    },
    {
      label: "Messages",
      value: stats.messages_count,
      icon: MessageCircle,
      color: "bg-[#AF52DE]",
    },
  ];

  return (
    <div>
      <h1 className="text-3xl font-semibold text-[#1D1D1F] mb-8 tracking-tight">
        Dashboard
      </h1>

      {loading ? (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {[1, 2, 3].map((i) => (
            <div
              key={i}
              className="glass rounded-2xl p-6 h-[88px] animate-shimmer"
            />
          ))}
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {cards.map((card, index) => {
            const Icon = card.icon;
            return (
              <div
                key={card.label}
                className={cn(
                  "glass rounded-2xl p-6 transition-all duration-300",
                  "hover:shadow-lg hover:-translate-y-0.5",
                  "animate-fade-in-up",
                  `stagger-${index + 1}`
                )}
              >
                <div className="flex items-center gap-4">
                  <div
                    className={cn(
                      "p-3 rounded-xl shadow-sm",
                      card.color
                    )}
                  >
                    <Icon className="w-6 h-6 text-white" />
                  </div>
                  <div>
                    <p className="text-sm font-medium text-[#86868B]">
                      {card.label}
                    </p>
                    <p className="text-3xl font-semibold text-[#1D1D1F] tracking-tight">
                      {card.value}
                    </p>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
