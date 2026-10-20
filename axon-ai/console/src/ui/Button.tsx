import type { ButtonHTMLAttributes, ReactNode } from "react";
import { forwardRef } from "react";

import styles from "./Button.module.css";
import { Icon, type IconName } from "./icons";

type Variant = "primary" | "secondary" | "ghost" | "danger";

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: Variant;
  size?: "sm" | "md" | "lg";
  icon?: IconName;
  busy?: boolean;
  children?: ReactNode;
};

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { variant = "secondary", size = "md", icon, busy = false, className, children, disabled, type = "button", ...rest },
  ref,
) {
  const iconOnly = icon !== undefined && children === undefined;
  const classes = [
    styles.button,
    styles[variant],
    size !== "md" && styles[size],
    iconOnly && styles.iconOnly,
    className,
  ]
    .filter(Boolean)
    .join(" ");
  return (
    <button
      ref={ref}
      type={type}
      className={classes}
      disabled={disabled || busy}
      aria-busy={busy || undefined}
      {...rest}
    >
      {busy ? <span className={styles.spinner} aria-hidden="true" /> : icon ? <Icon name={icon} /> : null}
      {children}
    </button>
  );
});
