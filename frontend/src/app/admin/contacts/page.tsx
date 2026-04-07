"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Plus, Trash2 } from "lucide-react";
import api from "@/lib/api";
import type { Contact, ContactCreate, ContactType } from "@/types/api";
import { Card, CardHeader, CardContent } from "@/components/ui/card";
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { formatPhone, formatDate } from "@/lib/utils";

const typeVariant: Record<ContactType, "success" | "danger" | "info"> = {
  whitelist: "success",
  blocklist: "danger",
  known: "info",
};

export default function ContactsPage() {
  const queryClient = useQueryClient();
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState<ContactCreate>({
    phone_number: "",
    name: "",
    contact_type: "whitelist",
    category: "personal",
  });

  const { data: contacts, isLoading } = useQuery({
    queryKey: ["contacts"],
    queryFn: async () => {
      const res = await api.get<{ contacts: Contact[] }>("/contacts");
      return res.data.contacts;
    },
  });

  const addContact = useMutation({
    mutationFn: (data: ContactCreate) => api.post("/contacts", data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["contacts"] });
      setShowForm(false);
      setForm({ phone_number: "", name: "", contact_type: "whitelist", category: "personal" });
    },
  });

  const deleteContact = useMutation({
    mutationFn: (id: string) => api.delete(`/contacts/${id}`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["contacts"] }),
  });

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Contacts</h1>
          <p className="mt-1 text-sm text-gray-500">
            Manage whitelist, blocklist, and known contacts
          </p>
        </div>
        <Button onClick={() => setShowForm(!showForm)}>
          <Plus className="mr-2 h-4 w-4" />
          Add Contact
        </Button>
      </div>

      {/* Add contact form */}
      {showForm && (
        <Card>
          <CardHeader>
            <h3 className="text-lg font-semibold">New Contact</h3>
          </CardHeader>
          <CardContent>
            <form
              className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4"
              onSubmit={(e) => {
                e.preventDefault();
                addContact.mutate(form);
              }}
            >
              <Input
                label="Phone Number"
                placeholder="+15551234567"
                value={form.phone_number}
                onChange={(e) => setForm({ ...form, phone_number: e.target.value })}
                required
              />
              <Input
                label="Name"
                placeholder="Dr. Smith"
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
                required
              />
              <div className="space-y-1">
                <label className="block text-sm font-medium text-gray-700">Type</label>
                <select
                  className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
                  value={form.contact_type}
                  onChange={(e) => setForm({ ...form, contact_type: e.target.value as ContactType })}
                >
                  <option value="whitelist">Whitelist</option>
                  <option value="blocklist">Blocklist</option>
                  <option value="known">Known</option>
                </select>
              </div>
              <div className="flex items-end">
                <Button type="submit" disabled={addContact.isPending}>
                  {addContact.isPending ? "Adding..." : "Add Contact"}
                </Button>
              </div>
            </form>
            {addContact.isError && (
              <p className="mt-2 text-sm text-red-600">
                Failed to add contact. Check the phone number format.
              </p>
            )}
          </CardContent>
        </Card>
      )}

      {/* Contacts table */}
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
                  <TableHead>Name</TableHead>
                  <TableHead>Phone</TableHead>
                  <TableHead>Type</TableHead>
                  <TableHead>Category</TableHead>
                  <TableHead>Added</TableHead>
                  <TableHead className="w-16"></TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {contacts?.map((contact) => (
                  <TableRow key={contact.id}>
                    <TableCell className="font-medium">{contact.name}</TableCell>
                    <TableCell>{formatPhone(contact.phone_number)}</TableCell>
                    <TableCell>
                      <Badge variant={typeVariant[contact.contact_type]}>
                        {contact.contact_type}
                      </Badge>
                    </TableCell>
                    <TableCell className="capitalize text-gray-600">{contact.category}</TableCell>
                    <TableCell className="text-gray-500">{formatDate(contact.created_at)}</TableCell>
                    <TableCell>
                      <button
                        className="rounded p-1 text-gray-400 hover:bg-red-50 hover:text-red-600"
                        onClick={() => {
                          if (confirm("Remove this contact?")) {
                            deleteContact.mutate(contact.id);
                          }
                        }}
                      >
                        <Trash2 className="h-4 w-4" />
                      </button>
                    </TableCell>
                  </TableRow>
                ))}
                {(!contacts || contacts.length === 0) && (
                  <TableRow>
                    <TableCell colSpan={6} className="text-center text-gray-500 py-12">
                      No contacts yet. Add a whitelist entry to get started.
                    </TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
