import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

/*
 * Status tones carry real meaning (which sync state a job is in), so they are
 * functional labels, not decoration. Foreground/background pairs were checked
 * for WCAG AA (>= 4.5:1). Radius is a small tag, not a full pill, to keep the
 * console's structured rhythm.
 */
const badgeVariants = cva(
  "inline-flex items-center rounded-md border px-2 py-0.5 text-xs font-medium leading-5",
  {
    variants: {
      variant: {
        default: "border-transparent bg-primary text-primary-foreground",
        secondary: "border-transparent bg-[#e2e8f0] text-[#334155]",
        destructive: "border-transparent bg-[#fee2e2] text-[#991b1b]",
        outline: "border-border bg-card text-foreground",
        success: "border-transparent bg-[#d1fae5] text-[#065f46]",
        warning: "border-transparent bg-[#fef3c7] text-[#92400e]",
        review: "border-transparent bg-[#ede9fe] text-[#5b21b6]",
        info: "border-transparent bg-[#e0f2fe] text-[#075985]",
      },
    },
    defaultVariants: { variant: "default" },
  }
);

export interface BadgeProps
  extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof badgeVariants> {}

function Badge({ className, variant, ...props }: BadgeProps) {
  return <div className={cn(badgeVariants({ variant }), className)} {...props} />;
}

export { Badge, badgeVariants };
