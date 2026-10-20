import { forwardRef, type InputHTMLAttributes, type ReactNode } from "react";

import styles from "./Checkbox.module.css";

type CheckboxProps = Omit<InputHTMLAttributes<HTMLInputElement>, "type"> & { label?: ReactNode };

export const Checkbox = forwardRef<HTMLInputElement, CheckboxProps>(function Checkbox(
  { label, disabled, className, ...rest },
  ref,
) {
  const input = <input ref={ref} type="checkbox" className={styles.input} disabled={disabled} {...rest} />;
  if (label === undefined) {
    return input;
  }
  return (
    <label className={[styles.row, className].filter(Boolean).join(" ")} data-disabled={disabled ? "true" : undefined}>
      {input}
      {label}
    </label>
  );
});
