import { cva, type VariantProps } from "class-variance-authority";
import { Slot } from "radix-ui";
import type * as React from "react";

import { cn } from "@/lib/utils";

const buttonVariants = cva(
  "inline-flex shrink-0 cursor-pointer items-center justify-center gap-2 whitespace-nowrap rounded-full border font-normal transition-[background,color,border-color] duration-150 outline-none focus-visible:outline-2 focus-visible:outline-ring focus-visible:outline-offset-4 disabled:pointer-events-none disabled:opacity-50 [&_svg]:pointer-events-none [&_svg]:shrink-0 [&_svg:not([class*='size-'])]:size-4",
  {
    variants: {
      variant: {
        default: "border-primary bg-primary text-primary-foreground hover:bg-[#343a32]",
        secondary: "border-border bg-surface text-foreground hover:bg-select",
        outline: "border-[#bdc8b2] bg-[#fffef9] text-[#45513e] hover:bg-select hover:border-select",
        ghost: "border-transparent bg-transparent text-foreground hover:bg-surface",
        destructive: "border-transparent bg-transparent text-destructive hover:bg-negative-surface",
        link: "border-transparent text-foreground underline-offset-4 hover:underline",
      },
      size: {
        default: "min-h-[50px] px-[21px] text-base",
        sm: "min-h-10 px-4 text-[15px]",
        xs: "min-h-8 px-3 text-sm [&_svg:not([class*='size-'])]:size-3.5",
        icon: "size-10",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  },
);

function Button({
  className,
  variant = "default",
  size = "default",
  asChild = false,
  ...props
}: React.ComponentProps<"button"> &
  VariantProps<typeof buttonVariants> & {
    asChild?: boolean;
  }) {
  const Comp = asChild ? Slot.Root : "button";

  return (
    <Comp
      data-slot="button"
      data-variant={variant}
      data-size={size}
      className={cn(buttonVariants({ variant, size, className }))}
      {...props}
    />
  );
}

export { Button, buttonVariants };
