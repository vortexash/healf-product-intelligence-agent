import * as React from "react";
import { cn } from "@/lib/utils";

type Variant = "primary" | "gradient" | "ghost" | "outline";
type Size = "sm" | "md" | "icon";

const variants: Record<Variant, string> = {
  primary: "bg-healf text-white hover:bg-healf-dark shadow-soft",
  gradient: "bg-healf-gradient bg-[length:200%_auto] text-white shadow-soft hover:bg-[position:right_center] transition-[background-position] duration-500",
  ghost: "bg-transparent hover:bg-healf-soft text-ink",
  outline: "border border-line bg-card hover:bg-cream text-ink",
};
const sizes: Record<Size, string> = {
  sm: "h-8 px-3 text-sm",
  md: "h-10 px-4 text-sm",
  icon: "h-9 w-9",
};

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: Size;
}

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant = "primary", size = "md", ...props }, ref) => (
    <button
      ref={ref}
      className={cn(
        "inline-flex items-center justify-center gap-2 rounded-full font-medium transition-colors disabled:opacity-50 disabled:pointer-events-none",
        variants[variant],
        sizes[size],
        className,
      )}
      {...props}
    />
  ),
);
Button.displayName = "Button";
