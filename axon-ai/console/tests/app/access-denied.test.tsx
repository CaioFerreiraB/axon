/** 013 US8 cen. 4 (ADR-038; research R17, R18): o acesso negado mostra o lockup Axon. */

import { screen, waitFor } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { AccessDenied } from "../../src/app/AccessDenied";
import { renderAt } from "../render";

describe("AccessDenied", () => {
  it("mostra o lockup Axon e o título da aba", async () => {
    renderAt("/uso", [{ path: "/uso", element: <AccessDenied /> }]);
    expect(await screen.findAllByAltText("Axon")).toHaveLength(2);
    expect(screen.queryByText("Agentic")).not.toBeInTheDocument();
    await waitFor(() => expect(document.title).toBe("Sem acesso · Axon"));
  });
});
