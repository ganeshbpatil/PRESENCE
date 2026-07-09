import { Building2, LayoutDashboard, Users } from "lucide-react";
import type { UserResponse } from "@/lib/api";

export interface NavItem {
  label: string;
  href: string;
  icon: typeof Building2;
}

export function getNavItems(user: UserResponse | null): NavItem[] {
  if (!user || user.role === "smb_owner") return [];
  const items: NavItem[] = [
    { label: "Dashboard", href: "/", icon: LayoutDashboard },
    { label: "Businesses", href: "/businesses", icon: Building2 },
  ];
  if (user.agency_id) {
    items.push({ label: "Agency", href: `/agencies/${user.agency_id}`, icon: Users });
  }
  return items;
}
