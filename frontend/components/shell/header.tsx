"use client";

import { Bell, Menu, Search } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { ThemeToggle } from "./theme-toggle";
import { UserMenu } from "./user-menu";

export function Header({
  title,
  subtitle,
  onMenuClick,
  onEditBusiness,
}: {
  title: string;
  subtitle?: string;
  onMenuClick: () => void;
  onEditBusiness?: () => void;
}) {
  return (
    <header className="flex items-center gap-3 border-b bg-background px-4 py-3 sm:px-6">
      <Button
        variant="ghost"
        size="icon"
        className="md:hidden"
        aria-label="Open navigation"
        onClick={onMenuClick}
      >
        <Menu className="size-5" />
      </Button>

      <div className="min-w-0 flex-1">
        <h1 className="truncate text-lg font-semibold leading-tight">{title}</h1>
        {subtitle && (
          <p className="truncate text-sm text-muted-foreground">{subtitle}</p>
        )}
      </div>

      <div className="hidden max-w-xs flex-1 sm:block">
        <div className="relative">
          <Search className="pointer-events-none absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder="Search (coming soon)"
            disabled
            className="pl-8"
          />
        </div>
      </div>

      <Tooltip>
        <TooltipTrigger asChild>
          <Button variant="ghost" size="icon" aria-label="Notifications" disabled>
            <Bell className="size-4" />
          </Button>
        </TooltipTrigger>
        <TooltipContent>Notifications — coming soon</TooltipContent>
      </Tooltip>

      <ThemeToggle />

      <UserMenu onEditBusiness={onEditBusiness} />
    </header>
  );
}
