"use client";

import { useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import {
  createBusiness,
  ApiError,
  type BusinessCategory,
  type BusinessTier,
} from "@/lib/api";
import { Button, ErrorState, Select, TextInput } from "@/components/ui";

export default function NewBusinessPage() {
  const { user } = useAuth();
  const router = useRouter();
  const [name, setName] = useState("");
  const [category, setCategory] = useState<BusinessCategory>("salon_spa_gym");
  const [tier, setTier] = useState<BusinessTier>("starter");
  const [inviteCode, setInviteCode] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      const business = await createBusiness(null, {
        name,
        category,
        tier,
        agency_id: user?.agency_id ?? undefined,
        invite_code: inviteCode || undefined,
      });
      router.push(`/businesses/${business.id}`);
    } catch (err) {
      setError(
        err instanceof ApiError && err.status === 403
          ? "Invalid invite code."
          : "Could not create business."
      );
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="flex-1 p-6 max-w-md mx-auto w-full">
      <h1 className="text-lg font-semibold mb-4">Add a business</h1>
      <form onSubmit={handleSubmit} className="space-y-3">
        <TextInput
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="Business name"
          required
        />
        <Select value={category} onChange={(e) => setCategory(e.target.value as BusinessCategory)}>
          <option value="salon_spa_gym">Salon / Spa / Gym</option>
          <option value="clinic_healthcare">Clinic / Healthcare</option>
          <option value="fnb">Food & Beverage</option>
          <option value="retail_fashion_jewellery">Retail / Fashion / Jewellery</option>
        </Select>
        <Select value={tier} onChange={(e) => setTier(e.target.value as BusinessTier)}>
          <option value="starter">Starter</option>
          <option value="growth">Growth</option>
          <option value="scale">Scale</option>
        </Select>
        <TextInput
          value={inviteCode}
          onChange={(e) => setInviteCode(e.target.value)}
          placeholder="Invite code (if required)"
        />
        {error && <ErrorState message={error} />}
        <Button type="submit" disabled={submitting} className="w-full">
          {submitting ? "Creating..." : "Create business"}
        </Button>
      </form>
    </main>
  );
}
