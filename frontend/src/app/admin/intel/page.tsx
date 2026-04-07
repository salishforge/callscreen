"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Search, AlertTriangle, ShieldCheck } from "lucide-react";
import api from "@/lib/api";
import type { NumberIntel } from "@/types/api";
import { Card, CardHeader, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { formatPhone, trustScoreLabel, trustScoreColor, formatDate } from "@/lib/utils";

export default function IntelPage() {
  const [phone, setPhone] = useState("");
  const [searchNumber, setSearchNumber] = useState("");

  const { data: intel, isLoading, isError } = useQuery({
    queryKey: ["intel", searchNumber],
    queryFn: async () => {
      if (!searchNumber) return null;
      const res = await api.get<NumberIntel>(`/intel/${encodeURIComponent(searchNumber)}`);
      return res.data;
    },
    enabled: !!searchNumber,
  });

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Number Intelligence</h1>
        <p className="mt-1 text-sm text-gray-500">
          Look up carrier, trust score, and reputation data for any phone number
        </p>
      </div>

      {/* Search */}
      <Card>
        <CardContent>
          <form
            className="flex items-end gap-3"
            onSubmit={(e) => {
              e.preventDefault();
              setSearchNumber(phone);
            }}
          >
            <div className="flex-1 max-w-md">
              <Input
                label="Phone Number"
                placeholder="+15551234567"
                value={phone}
                onChange={(e) => setPhone(e.target.value)}
              />
            </div>
            <Button type="submit" disabled={!phone || isLoading}>
              <Search className="mr-2 h-4 w-4" />
              {isLoading ? "Looking up..." : "Lookup"}
            </Button>
          </form>
        </CardContent>
      </Card>

      {/* Results */}
      {isError && (
        <Card>
          <CardContent className="flex items-center gap-3 text-red-600">
            <AlertTriangle className="h-5 w-5" />
            <p>Failed to retrieve intelligence for this number.</p>
          </CardContent>
        </Card>
      )}

      {intel && (
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
          {/* Trust Score */}
          <Card>
            <CardHeader>
              <h3 className="text-lg font-semibold">Trust Assessment</h3>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex items-center gap-4">
                <div
                  className={`text-4xl font-bold ${trustScoreColor(intel.composite_trust_score)}`}
                >
                  {intel.composite_trust_score !== null
                    ? `${(intel.composite_trust_score * 100).toFixed(0)}%`
                    : "N/A"}
                </div>
                <div>
                  <p className={`text-lg font-medium ${trustScoreColor(intel.composite_trust_score)}`}>
                    {trustScoreLabel(intel.composite_trust_score)}
                  </p>
                  <p className="text-sm text-gray-500">
                    Seen {intel.call_count} time{intel.call_count !== 1 ? "s" : ""}
                  </p>
                </div>
              </div>

              <div className="space-y-2">
                {intel.community_blocklist_hit && (
                  <div className="flex items-center gap-2 text-red-600">
                    <AlertTriangle className="h-4 w-4" />
                    <span className="text-sm">Community blocklist match</span>
                  </div>
                )}
                {intel.is_medical_provider && (
                  <div className="flex items-center gap-2 text-green-600">
                    <ShieldCheck className="h-4 w-4" />
                    <span className="text-sm">Verified medical provider</span>
                  </div>
                )}
                {(intel.ftc_complaint_count ?? 0) > 0 && (
                  <div className="flex items-center gap-2 text-red-600">
                    <AlertTriangle className="h-4 w-4" />
                    <span className="text-sm">
                      {intel.ftc_complaint_count} FTC complaint{intel.ftc_complaint_count !== 1 ? "s" : ""}
                    </span>
                  </div>
                )}
              </div>
            </CardContent>
          </Card>

          {/* Carrier Info */}
          <Card>
            <CardHeader>
              <h3 className="text-lg font-semibold">Carrier Details</h3>
            </CardHeader>
            <CardContent>
              <dl className="space-y-3">
                <div className="flex justify-between">
                  <dt className="text-sm text-gray-500">Number</dt>
                  <dd className="text-sm font-medium">{formatPhone(intel.phone_number)}</dd>
                </div>
                <div className="flex justify-between">
                  <dt className="text-sm text-gray-500">Carrier</dt>
                  <dd className="text-sm font-medium">{intel.carrier_name ?? "Unknown"}</dd>
                </div>
                <div className="flex justify-between">
                  <dt className="text-sm text-gray-500">Line Type</dt>
                  <dd>
                    <Badge
                      variant={intel.line_type === "voip" ? "warning" : intel.line_type === "landline" ? "success" : "default"}
                    >
                      {intel.line_type}
                    </Badge>
                  </dd>
                </div>
                <div className="flex justify-between">
                  <dt className="text-sm text-gray-500">CNAM</dt>
                  <dd className="text-sm font-medium">{intel.cnam ?? "N/A"}</dd>
                </div>
                <div className="flex justify-between">
                  <dt className="text-sm text-gray-500">Last Seen</dt>
                  <dd className="text-sm text-gray-600">{formatDate(intel.last_seen)}</dd>
                </div>
              </dl>
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
}
