"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import api from "@/lib/api";
import type { CallRecord } from "@/types/api";
import { Card, CardHeader, CardContent } from "@/components/ui/card";
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { formatPhone, formatDate, formatDuration, trustScoreLabel, trustScoreColor, dispositionColor } from "@/lib/utils";

export default function CallsPage() {
  const [page, setPage] = useState(0);
  const limit = 25;

  const { data, isLoading } = useQuery({
    queryKey: ["calls", page],
    queryFn: async () => {
      const res = await api.get<{ calls: CallRecord[]; total: number }>("/calls", {
        params: { limit, offset: page * limit },
      });
      return res.data;
    },
  });

  const calls = data?.calls ?? [];
  const total = data?.total ?? 0;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Call History</h1>
        <p className="mt-1 text-sm text-gray-500">
          All incoming calls processed by the screening system
        </p>
      </div>

      <Card>
        <CardContent className="p-0">
          {isLoading ? (
            <div className="flex items-center justify-center py-16">
              <div className="h-6 w-6 animate-spin rounded-full border-2 border-blue-600 border-t-transparent" />
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Caller</TableHead>
                  <TableHead>Intent</TableHead>
                  <TableHead>Trust Score</TableHead>
                  <TableHead>STIR/SHAKEN</TableHead>
                  <TableHead>Disposition</TableHead>
                  <TableHead>Duration</TableHead>
                  <TableHead>Time</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {calls.map((call) => {
                  const dColor = dispositionColor(call.disposition);
                  return (
                    <TableRow key={call.id}>
                      <TableCell>
                        <div>
                          <p className="font-medium">
                            {call.caller_name ?? formatPhone(call.from_number)}
                          </p>
                          {call.caller_name && (
                            <p className="text-xs text-gray-500">{formatPhone(call.from_number)}</p>
                          )}
                        </div>
                      </TableCell>
                      <TableCell className="text-gray-600 max-w-[200px] truncate">
                        {call.caller_intent ?? "--"}
                      </TableCell>
                      <TableCell>
                        <span className={trustScoreColor(call.trust_score)}>
                          {call.trust_score !== null
                            ? `${(call.trust_score * 100).toFixed(0)}% — ${trustScoreLabel(call.trust_score)}`
                            : "N/A"}
                        </span>
                      </TableCell>
                      <TableCell>
                        <Badge variant={call.stir_attestation === "A" ? "success" : call.stir_attestation === "C" ? "danger" : "default"}>
                          {call.stir_attestation}
                        </Badge>
                      </TableCell>
                      <TableCell>
                        {call.disposition ? (
                          <Badge className={`${dColor.bg} ${dColor.text}`}>{call.disposition}</Badge>
                        ) : (
                          <span className="text-gray-400">{call.status}</span>
                        )}
                      </TableCell>
                      <TableCell className="text-gray-500">
                        {formatDuration(call.duration_seconds)}
                      </TableCell>
                      <TableCell className="text-gray-500">
                        {formatDate(call.created_at)}
                      </TableCell>
                    </TableRow>
                  );
                })}
                {calls.length === 0 && (
                  <TableRow>
                    <TableCell colSpan={7} className="text-center text-gray-500 py-12">
                      No calls recorded yet
                    </TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      {/* Pagination */}
      {total > limit && (
        <div className="flex items-center justify-between">
          <p className="text-sm text-gray-500">
            Showing {page * limit + 1}–{Math.min((page + 1) * limit, total)} of {total}
          </p>
          <div className="flex gap-2">
            <Button variant="secondary" size="sm" disabled={page === 0} onClick={() => setPage(page - 1)}>
              Previous
            </Button>
            <Button variant="secondary" size="sm" disabled={(page + 1) * limit >= total} onClick={() => setPage(page + 1)}>
              Next
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
