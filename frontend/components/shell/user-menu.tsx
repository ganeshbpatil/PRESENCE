"use client";

import { LogOut, Pencil } from "lucide-react";
import { useAuth } from "@/lib/auth-context";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

function initials(email: string): string {
  return email.slice(0, 2).toUpperCase();
}

export function UserMenu({ onEditBusiness }: { onEditBusiness?: () => void }) {
  const { user, logout } = useAuth();
  if (!user) return null;

  // Preserves the existing gap: smb_owner accounts never got a Sign-out
  // control in the old top-of-page layout.
  const canSignOut = user.role !== "smb_owner";

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" className="gap-2 px-2">
          <Avatar className="size-7">
            <AvatarFallback className="text-xs">{initials(user.email)}</AvatarFallback>
          </Avatar>
          <span className="hidden text-sm font-medium sm:inline">{user.email}</span>
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-56">
        <DropdownMenuLabel className="font-normal">
          <p className="truncate text-sm font-medium">{user.email}</p>
          <p className="text-xs text-muted-foreground">{user.role.replace(/_/g, " ")}</p>
        </DropdownMenuLabel>
        {onEditBusiness && (
          <>
            <DropdownMenuSeparator />
            <DropdownMenuItem onClick={onEditBusiness}>
              <Pencil />
              Edit business details
            </DropdownMenuItem>
          </>
        )}
        {canSignOut && (
          <>
            <DropdownMenuSeparator />
            <DropdownMenuItem onClick={logout} variant="destructive">
              <LogOut />
              Sign out
            </DropdownMenuItem>
          </>
        )}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
