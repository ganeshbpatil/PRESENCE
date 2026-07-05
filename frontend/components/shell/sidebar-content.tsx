"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { LayoutGrid } from "lucide-react";
import { useAuth } from "@/lib/auth-context";
import { getNavItems } from "./nav-items";
import { cn } from "@/lib/utils";

export function SidebarContent({ onNavigate }: { onNavigate?: () => void }) {
  const { user } = useAuth();
  const pathname = usePathname();
  const items = getNavItems(user);

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center gap-2 px-4 py-4">
        <div className="flex size-8 items-center justify-center rounded-lg bg-primary text-primary-foreground">
          <LayoutGrid className="size-4" />
        </div>
        <div>
          <p className="text-sm font-semibold leading-tight">PRESENCE</p>
          <p className="text-xs leading-tight text-muted-foreground">Admin</p>
        </div>
      </div>

      {items.length > 0 && (
        <nav className="flex-1 px-2 py-2">
          <p className="px-2 pb-1 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            Overview
          </p>
          <ul className="space-y-0.5">
            {items.map((item) => {
              const active =
                item.href === "/" ? pathname === "/" : pathname.startsWith(item.href);
              const Icon = item.icon;
              return (
                <li key={item.href}>
                  <Link
                    href={item.href}
                    onClick={onNavigate}
                    className={cn(
                      "flex items-center gap-2.5 rounded-md border border-transparent px-2.5 py-2 text-sm transition-colors",
                      active
                        ? "border-primary/20 bg-primary/10 font-medium text-primary"
                        : "text-muted-foreground hover:bg-accent hover:text-accent-foreground"
                    )}
                  >
                    <Icon className="size-4 shrink-0" />
                    {item.label}
                  </Link>
                </li>
              );
            })}
          </ul>
        </nav>
      )}
    </div>
  );
}
