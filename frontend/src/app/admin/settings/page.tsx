"use client";

import { useEffect, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Save, CheckCircle } from "lucide-react";
import api from "@/lib/api";
import type { UserSettings } from "@/types/api";
import { Card, CardHeader, CardContent, CardFooter } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";

export default function SettingsPage() {
  const queryClient = useQueryClient();
  const [saved, setSaved] = useState(false);

  const { data: settings, isLoading } = useQuery({
    queryKey: ["settings"],
    queryFn: async () => {
      const res = await api.get<UserSettings>("/settings");
      return res.data;
    },
  });

  const [form, setForm] = useState<Partial<UserSettings>>({});

  useEffect(() => {
    if (settings) setForm(settings);
  }, [settings]);

  const update = useMutation({
    mutationFn: (data: Partial<UserSettings>) => api.put("/settings", data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["settings"] });
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    },
  });

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-16">
        <div className="h-6 w-6 animate-spin rounded-full border-2 border-blue-600 border-t-transparent" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Settings</h1>
        <p className="mt-1 text-sm text-gray-500">
          Configure call screening behavior and notification preferences
        </p>
      </div>

      <form
        onSubmit={(e) => {
          e.preventDefault();
          update.mutate(form);
        }}
      >
        {/* Greeting */}
        <Card className="mb-6">
          <CardHeader>
            <h3 className="text-lg font-semibold">Call Greeting</h3>
            <p className="text-sm text-gray-500">The message callers hear when they reach the screening service</p>
          </CardHeader>
          <CardContent>
            <textarea
              className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
              rows={3}
              value={form.greeting_message ?? ""}
              onChange={(e) => setForm({ ...form, greeting_message: e.target.value })}
            />
          </CardContent>
        </Card>

        {/* Screening */}
        <Card className="mb-6">
          <CardHeader>
            <h3 className="text-lg font-semibold">Screening</h3>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-1">
              <label className="block text-sm font-medium text-gray-700">Strictness</label>
              <select
                className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm max-w-xs"
                value={form.screening_strictness ?? "moderate"}
                onChange={(e) => setForm({ ...form, screening_strictness: e.target.value })}
              >
                <option value="permissive">Permissive — most calls forwarded</option>
                <option value="moderate">Moderate — balanced screening</option>
                <option value="strict">Strict — heavy screening, few forwarded</option>
              </select>
            </div>
          </CardContent>
        </Card>

        {/* Notifications */}
        <Card className="mb-6">
          <CardHeader>
            <h3 className="text-lg font-semibold">Notifications</h3>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-1">
              <label className="block text-sm font-medium text-gray-700">Preferred Channel</label>
              <select
                className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm max-w-xs"
                value={form.preferred_channel ?? "email"}
                onChange={(e) => setForm({ ...form, preferred_channel: e.target.value })}
              >
                <option value="email">Email</option>
                <option value="sms">SMS</option>
                <option value="telegram">Telegram</option>
                <option value="discord">Discord</option>
              </select>
            </div>
          </CardContent>
        </Card>

        {/* Quiet Hours */}
        <Card className="mb-6">
          <CardHeader>
            <h3 className="text-lg font-semibold">Quiet Hours</h3>
            <p className="text-sm text-gray-500">During quiet hours, all calls go to voicemail (except emergencies)</p>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-3 max-w-lg">
              <Input
                label="Start"
                type="time"
                value={form.quiet_hours_start ?? ""}
                onChange={(e) => setForm({ ...form, quiet_hours_start: e.target.value || null })}
              />
              <Input
                label="End"
                type="time"
                value={form.quiet_hours_end ?? ""}
                onChange={(e) => setForm({ ...form, quiet_hours_end: e.target.value || null })}
              />
              <div className="space-y-1">
                <label className="block text-sm font-medium text-gray-700">Timezone</label>
                <select
                  className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
                  value={form.quiet_hours_timezone ?? "America/New_York"}
                  onChange={(e) => setForm({ ...form, quiet_hours_timezone: e.target.value })}
                >
                  <option value="America/New_York">Eastern</option>
                  <option value="America/Chicago">Central</option>
                  <option value="America/Denver">Mountain</option>
                  <option value="America/Los_Angeles">Pacific</option>
                </select>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Caretaker */}
        <Card className="mb-6">
          <CardHeader>
            <h3 className="text-lg font-semibold">Caretaker Forwarding</h3>
            <p className="text-sm text-gray-500">Automatically forward messages to a caretaker based on priority</p>
          </CardHeader>
          <CardContent className="space-y-4">
            <label className="flex items-center gap-3">
              <input
                type="checkbox"
                className="h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                checked={form.caretaker_fork_enabled ?? false}
                onChange={(e) => setForm({ ...form, caretaker_fork_enabled: e.target.checked })}
              />
              <span className="text-sm font-medium text-gray-700">
                Enable caretaker message forwarding
              </span>
            </label>
            {form.caretaker_fork_enabled && (
              <div className="space-y-1 max-w-xs">
                <label className="block text-sm font-medium text-gray-700">Minimum Priority</label>
                <select
                  className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
                  value={form.caretaker_fork_priority ?? "urgent"}
                  onChange={(e) => setForm({ ...form, caretaker_fork_priority: e.target.value })}
                >
                  <option value="urgent">Urgent only</option>
                  <option value="normal">Normal and above</option>
                  <option value="low">All messages</option>
                </select>
              </div>
            )}
          </CardContent>
        </Card>

        {/* Save */}
        <div className="flex items-center gap-3">
          <Button type="submit" disabled={update.isPending}>
            <Save className="mr-2 h-4 w-4" />
            {update.isPending ? "Saving..." : "Save Settings"}
          </Button>
          {saved && (
            <span className="flex items-center gap-1 text-sm text-green-600">
              <CheckCircle className="h-4 w-4" /> Saved
            </span>
          )}
        </div>
      </form>
    </div>
  );
}
