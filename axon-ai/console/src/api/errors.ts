import { deletionReportSchema, type DeletionReport } from "./schemas";

/** O envelope de erro da API (contracts/admin-api.md, "Erros"): a console mostra `message` junto ao campo `param`. */

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly param: string | null;
  readonly currentVersion: number | null;
  /** O corpo JSON da resposta de erro, para extensões como o `report` do apagamento incompleto (013 R33). */
  readonly body: unknown;

  constructor(
    status: number,
    code: string,
    message: string,
    {
      param = null,
      currentVersion = null,
      body = null,
    }: { param?: string | null; currentVersion?: number | null; body?: unknown } = {},
  ) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.param = param;
    this.currentVersion = currentVersion;
    this.body = body;
  }

  /** O apagamento da conta não terminou (503 `deletion_incomplete`): repetir retoma (008 FR-049). */
  get isDeletionIncomplete(): boolean {
    return this.status === 503 && this.code === "deletion_incomplete";
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

/** O relatório parcial do 503 `deletion_incomplete`, se a resposta o traz no formato do contrato. */
export function deletionReportOf(error: unknown): DeletionReport | null {
  if (!isApiError(error) || !error.isDeletionIncomplete || typeof error.body !== "object" || error.body === null) {
    return null;
  }
  const parsed = deletionReportSchema.safeParse((error.body as Record<string, unknown>).report);
  return parsed.success ? parsed.data : null;
}
