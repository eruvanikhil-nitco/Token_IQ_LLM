import { useDisableShowPrompts } from "@/app/(dashboard)/hooks/useDisableShowPrompts";
import { buttonVariants } from "@/components/ui/button";
import { ButtonGroup } from "@/components/ui/button-group";
import { cn } from "@/lib/cva.config";
import { Github, Slack } from "lucide-react";
import React from "react";

// Placeholders. They previously linked to litellm.ai/support and the BerriAI
// GitHub repo, which are not this deployment's community. Rendered as inert
// spans rather than links so nothing navigates away, and hidden from assistive
// tech because a control that does nothing should not be announced as one.
// Give an entry an `href` to make it a real link again.
const COMMUNITY_ICONS = [
  { key: "slack", Icon: Slack },
  { key: "github", Icon: Github },
] as const;

export const CommunityEngagementButtons: React.FC = () => {
  const disableShowPrompts = useDisableShowPrompts();

  if (disableShowPrompts) {
    return null;
  }

  return (
    <ButtonGroup aria-hidden>
      {COMMUNITY_ICONS.map(({ key, Icon }) => (
        <span
          key={key}
          data-testid={`community-icon-${key}`}
          className={cn(
            buttonVariants({ variant: "outline", size: "icon" }),
            "pointer-events-none text-muted-foreground",
          )}
        >
          <Icon />
        </span>
      ))}
    </ButtonGroup>
  );
};
