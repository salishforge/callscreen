"use client";

import { useQuery } from "@tanstack/react-query";
import api from "@/lib/api";
import type { CallRecord } from "@/types/api";
import { Card, CardHeader, CardContent } from "@/components/ui/card";
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { formatPhone, formatDate, trustScoreLabel, trustScoreColor, dispositionColor } from "@/lib/utils";

export function RecentCalls() {
  const { data, isLoading } = useQuery({
    queryKey: ["calls", "recent"],
    queryFn: async () => {
      const res = await api.get<{ calls: CallRecord[] }>("/calls", {
        params: { limit: 10, offset: 0 },
      });
      return res.data.calls;
    },
  });

  return (
    <Card>
      <CardHeader>
        <h3 className="text-lg font-semibold text-gray-900">Recent Calls</h3>
      </CardHeader>
      <CardContent className="p-0">
        {isLoading ? (
          <div className="flex items-center justify-center py-12">
            <div className="h-6 w-6 animate-spin rounded-full border-2 border-blue-600 border-t-transparent" />
          </div>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Caller</TableHead>
                <TableHead>Trust</TableHead>
                <TableHead>Disposition</TableHead>
                <TableHead>Time</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {data?.map((call) => {
                const dColor = dispositionColor(call.disposition);
                return (
                  <TableRow key={call.id}>
                    <TableCell>
                      <div>
                        <p className="font-medium">{call.caller_name ?? formatPhone(call.from_number)}</p>
                        {call.caller_name && (
                          <p className="text-xs text-gray-500">{formatPhone(call.from_number)}</p>
                        )}
                      </div>
                    </TableCell>
                    <TableCell>
                      <span className={trustScoreColor(call.trust_score)}>
                        {trustScoreLabel(call.trust_score)}
                      </span>
                    </TableCell>
                    <TableCell>
                      {call.disposition && (
                        <Badge className={`${dColor.bg} ${dColor.text}`}>
                          {call.disposition}
                        </Badge>
                      )}
                    </TableCell>
                    <TableCell className="text-gray-500">
                      {formatDate(call.created_at)}
                    </TableCell>
                  </TableRow>
                );
              })}
              {(!data || data.length === 0) && (
                <TableRow>
                  <TableCell colSpan={4} className="text-center text-gray-500 py-8">
                    No calls yet
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        )}
      </CardContent>
    </Card>
  );
}
