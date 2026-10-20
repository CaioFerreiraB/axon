/** O envelope de erro da API (contracts/admin-api.md, "Erros"): a console mostra `message` junto ao campo `param`. */

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly param: string | null;
  readonly currentVersion: number | null;

  constructor(
    status: number,
    code: string,
    message: string,
    { param = null, currentVersion = null }: { param?: string | null; currentVersion?: number | null } = {},
  ) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.param = param;
    this.currentVersion = currentVersion;
  }

  /** Recusa de validação de um campo (422): aparece junto ao campo, com o motivo da API (FR-001). */
  get isFieldError(): boolean {
    return this.status === 422 && this.code === "invalid_field";
  }

  /** Outra pessoa salvou antes (409 `version_conflict`, FR-008). */
  get isVersionConflict(): boolean {
    return this.status === 409 && this.code === "version_conflict";
  }

  get isNotFound(): boolean {
    return this.status === 404;
  }
}

export function isApiError(error: unknown): error is ApiError {
  return error instanceof ApiError;
}

/** O motivo da recusa para um campo, se a API nomeou esse campo. */
export function fieldError(error: unknown, field: string): string | undefined {
  if (!isApiError(error) || error.param === null) {
    return undefined;
  }
  return error.param === field || error.param.startsWith(`${field}.`) ? error.message : undefined;
}
