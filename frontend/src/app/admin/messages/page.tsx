"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Mail, MailOpen } from "lucide-react";
import api from "@/lib/api";
import type { Message } from "@/types/api";
import { Card, CardHeader, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { formatDate } from "@/lib/utils";

const priorityVariant: Record<string, "danger" | "warning" | "default"> = {
  urgent: "danger",
  normal: "warning",
  low: "default",
};

export default function MessagesPage() {
  const queryClient = useQueryClient();

  const { data: messages, isLoading } = useQuery({
    queryKey: ["messages"],
    queryFn: async () => {
      const res = await api.get<{ messages: Message[] }>("/messages");
      return res.data.messages;
    },
  });

  const markRead = useMutation({
    mutationFn: (id: string) => api.put(`/messages/${id}/read`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["messages"] }),
  });

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Messages</h1>
        <p className="mt-1 text-sm text-gray-500">
          Voicemail transcripts and caller messages
        </p>
      </div>

      {isLoading ? (
        <div className="flex items-center justify-center py-16">
          <div className="h-6 w-6 animate-spin rounded-full border-2 border-blue-600 border-t-transparent" />
        </div>
      ) : (
        <div className="space-y-3">
          {messages?.map((msg) => (
            <Card key={msg.id} className={msg.read_at ? "opacity-75" : ""}>
              <CardContent className="flex items-start gap-4">
                <div className="mt-1">
                  {msg.read_at ? (
                    <MailOpen className="h-5 w-5 text-gray-400" />
                  ) : (
                    <Mail className="h-5 w-5 text-blue-600" />
                  )}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <Badge variant={priorityVariant[msg.priority] ?? "default"}>
                      {msg.priority}
                    </Badge>
                    <Badge variant="info">{msg.category}</Badge>
                    <span className="text-xs text-gray-500">{formatDate(msg.created_at)}</span>
                  </div>
                  {msg.summary && (
                    <p className="text-sm font-medium text-gray-900 mb-1">{msg.summary}</p>
                  )}
                  <p className="text-sm text-gray-600 line-clamp-3">{msg.content}</p>
                  {msg.audio_ref && (
                    <p className="mt-2 text-xs text-blue-600">Audio recording available</p>
                  )}
                </div>
                <div className="shrink-0">
                  {!msg.read_at && (
                    <button
                      className="text-xs text-blue-600 hover:underline"
                      onClick={() => markRead.mutate(msg.id)}
                    >
                      Mark read
                    </button>
                  )}
                </div>
              </CardContent>
            </Card>
          ))}
          {(!messages || messages.length === 0) && (
            <Card>
              <CardContent className="text-center text-gray-500 py-12">
                No messages yet. Messages from screened callers will appear here.
              </CardContent>
            </Card>
          )}
        </div>
      )}
    </div>
  );
}
