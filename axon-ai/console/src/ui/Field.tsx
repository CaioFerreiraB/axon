/** Campo com rótulo, ajuda, erro da API (FR-001) e o estado "Definido na instalação" (ADR-033). */

import { cloneElement, isValidElement, useId, type ReactElement, type ReactNode } from "react";
import { forwardRef, type InputHTMLAttributes, type SelectHTMLAttributes } from "react";

import { InstallationBadge } from "./Badge";
import styles from "./Field.module.css";

type FieldProps = {
  label: ReactNode;
  help?: ReactNode;
  error?: string | undefined;
  installation?: boolean;
  hideLabel?: boolean;
  children: ReactElement<{ id?: string; "aria-describedby"?: string; "aria-invalid"?: boolean }>;
};

export function Field({ label, help, error, installation = false, hideLabel = false, children }: FieldProps) {
  const id = useId();
  const helpId = `${id}-ajuda`;
  const errorId = `${id}-erro`;
  const described = [error ? errorId : null, help ? helpId : null].filter(Boolean).join(" ") || undefined;
  const control = isValidElement(children)
    ? cloneElement(children, { id, "aria-describedby": described, "aria-invalid": error ? true : undefined })
    : children;
  return (
    <div className={styles.field}>
      <div className={hideLabel ? "visually-hidden" : styles.labelRow}>
        <label htmlFor={id} className={styles.label}>
          {label}
        </label>
        {installation ? <InstallationBadge /> : null}
      </div>
      {control}
      {error ? (
        <p id={errorId} className={styles.error} role="alert">
          {error}
        </p>
      ) : null}
      {help ? (
        <p id={helpId} className={styles.help}>
          {help}
        </p>
      ) : null}
    </div>
  );
}

type InputProps = InputHTMLAttributes<HTMLInputElement> & { mono?: boolean };

export const TextInput = forwardRef<HTMLInputElement, InputProps>(function TextInput(
  { mono = false, className, ...rest },
  ref,
) {
  return (
    <input ref={ref} className={[styles.control, mono && styles.mono, className].filter(Boolean).join(" ")} {...rest} />
  );
});

type SelectProps = SelectHTMLAttributes<HTMLSelectElement> & { mono?: boolean; compact?: boolean };

export const Select = forwardRef<HTMLSelectElement, SelectProps>(function Select(
  { mono = false, compact = false, className, children, ...rest },
  ref,
) {
  return (
    <select
      ref={ref}
      className={[styles.control, styles.select, mono && styles.mono, compact && styles.compact, className]
        .filter(Boolean)
        .join(" ")}
      {...rest}
    >
      {children}
    </select>
  );
});

export const fieldStyles = styles;
