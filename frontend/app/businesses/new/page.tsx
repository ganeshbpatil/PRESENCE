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
import { ErrorState } from "@/components/ui";
import { AppShell } from "@/components/shell/app-shell";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

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
    <AppShell title="Add a business">
      <div className="mx-auto w-full max-w-md">
        <Card>
          <CardContent>
            <form onSubmit={handleSubmit} className="space-y-3">
              <Input
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="Business name"
                required
              />
              <Select
                value={category}
                onValueChange={(v) => setCategory(v as BusinessCategory)}
              >
                <SelectTrigger className="w-full">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="salon_spa_gym">Salon / Spa / Gym</SelectItem>
                  <SelectItem value="clinic_healthcare">Clinic / Healthcare</SelectItem>
                  <SelectItem value="fnb">Food & Beverage</SelectItem>
                  <SelectItem value="retail_fashion_jewellery">
                    Retail / Fashion / Jewellery
                  </SelectItem>
                </SelectContent>
              </Select>
              <Select value={tier} onValueChange={(v) => setTier(v as BusinessTier)}>
                <SelectTrigger className="w-full">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="starter">Starter</SelectItem>
                  <SelectItem value="growth">Growth</SelectItem>
                  <SelectItem value="scale">Scale</SelectItem>
                </SelectContent>
              </Select>
              <Input
                value={inviteCode}
                onChange={(e) => setInviteCode(e.target.value)}
                placeholder="Invite code (if required)"
              />
              {error && <ErrorState message={error} />}
              <Button type="submit" disabled={submitting} className="w-full">
                {submitting ? "Creating..." : "Create business"}
              </Button>
            </form>
          </CardContent>
        </Card>
      </div>
    </AppShell>
  );
}
