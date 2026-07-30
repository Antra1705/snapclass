import * as React from "react";
import { cn } from "@/lib/cn";

/**
 * Button variants mirror the original Streamlit theme:
 * primary = blurple, secondary = pink, tertiary = black — all pill-shaped
 * white-text buttons that scale slightly on hover.
 */
type Variant = "primary" | "secondary" | "tertiary" | "outline";
type Size = "sm" | "md" | "lg";

const variants: Record<Variant, string> = {
  primary: "bg-blurple text-white hover:bg-blurple disabled:opacity-50",
  secondary: "bg-snappink text-white hover:bg-snappink disabled:opacity-50",
  tertiary: "bg-black text-white hover:bg-black disabled:opacity-50",
  outline: "border border-slate-300 bg-white text-ink hover:bg-slate-50 disabled:opacity-50",
};

const sizes: Record<Size, string> = {
  sm: "h-9 px-4 text-sm",
  md: "h-11 px-5 text-sm",
  lg: "h-12 px-6 text-base",
};

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: Size;
  loading?: boolean;
}

export function Button({
  variant = "primary",
  size = "md",
  loading = false,
  className,
  children,
  disabled,
  ...props
}: ButtonProps) {
  return (
    <button
      className={cn(
        "inline-flex items-center justify-center gap-2 rounded-3xl font-body font-semibold transition-transform duration-200 ease-in-out hover:scale-105 focus:outline-none focus-visible:ring-2 focus-visible:ring-blurple disabled:cursor-not-allowed disabled:hover:scale-100",
        variants[variant],
        sizes[size],
        className
      )}
      disabled={disabled || loading}
      {...props}
    >
      {loading && (
        <span className="h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent" />
      )}
      {children}
    </button>
  );
}
