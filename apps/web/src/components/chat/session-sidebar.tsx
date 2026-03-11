"use client";

import { MessageSquarePlus, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { useChat } from "@/lib/chat-context";
import { cn } from "@/lib/utils";

export function SessionSidebar() {
  const { sessions, sessionId, switchSession, startNewChat, removeSession } = useChat();

  return (
    <div className="w-64 border-r bg-muted/30 flex flex-col h-full shrink-0">
      {/* New chat button */}
      <div className="p-3 border-b">
        <Button
          variant="outline"
          size="sm"
          className="w-full gap-2 justify-start"
          onClick={startNewChat}
        >
          <MessageSquarePlus className="h-4 w-4" />
          New Chat
        </Button>
      </div>

      {/* Session list */}
      <ScrollArea className="flex-1">
        <div className="p-2 space-y-0.5">
          {sessions.length === 0 && (
            <p className="text-xs text-muted-foreground text-center py-6 px-2">
              No conversations yet
            </p>
          )}
          {sessions.map((s) => (
            <div
              key={s.session_id}
              className={cn(
                "group flex items-center gap-1 rounded-md px-2 py-1.5 text-sm cursor-pointer transition-colors",
                s.session_id === sessionId
                  ? "bg-primary/10 text-primary"
                  : "hover:bg-muted text-muted-foreground hover:text-foreground",
              )}
              onClick={() => switchSession(s.session_id)}
            >
              <span className="truncate flex-1 text-xs">{s.title}</span>
              <button
                className="opacity-0 group-hover:opacity-100 shrink-0 p-0.5 hover:text-destructive transition-opacity"
                onClick={(e) => {
                  e.stopPropagation();
                  removeSession(s.session_id);
                }}
                title="Delete"
              >
                <Trash2 className="h-3 w-3" />
              </button>
            </div>
          ))}
        </div>
      </ScrollArea>
    </div>
  );
}
