"use client";

import { useQuery } from "@tanstack/react-query";
import { Phone, ShieldCheck, ShieldAlert, MessageSquare } from "lucide-react";
import api from "@/lib/api";
import type { CallRecord, Message } from "@/types/api";
import { StatCard } from "@/components/dashboard/stat-card";
import { RecentCalls } from "@/components/dashboard/recent-calls";

export default function AdminDashboard() {
  const { data: calls } = useQuery({
    queryKey: ["calls", "stats"],
    queryFn: async () => {
      const res = await api.get<{ calls: CallRecord[] }>("/calls", {
        params: { limit: 100, offset: 0 },
      });
      return res.data.calls;
    },
  });

  const { data: messages } = useQuery({
    queryKey: ["messages", "stats"],
    queryFn: async () => {
      const res = await api.get<{ messages: Message[] }>("/messages");
      return res.data.messages;
    },
  });

  const totalCalls = calls?.length ?? 0;
  const blocked = calls?.filter((c) => c.disposition === "blocked").length ?? 0;
  const forwarded = calls?.filter((c) => c.disposition === "forwarded").length ?? 0;
  const unreadMessages = messages?.filter((m) => !m.read_at).length ?? 0;

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Dashboard</h1>
        <p className="mt-1 text-sm text-gray-500">
          Call screening overview and recent activity
        </p>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard title="Total Calls" value={totalCalls} icon={Phone} />
        <StatCard title="Calls Forwarded" value={forwarded} icon={ShieldCheck} />
        <StatCard title="Calls Blocked" value={blocked} icon={ShieldAlert} />
        <StatCard title="Unread Messages" value={unreadMessages} icon={MessageSquare} />
      </div>

      <RecentCalls />
    </div>
  );
}
