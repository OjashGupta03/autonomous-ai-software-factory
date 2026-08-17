import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { StatusBadge } from "../StatusBadge";

describe("StatusBadge", () => {
  it("renders a human-readable label for a known status", () => {
    render(<StatusBadge status="running" />);
    expect(screen.getByText("Running")).toBeInTheDocument();
  });

  it("falls back to the raw status string for an unrecognized value", () => {
    render(<StatusBadge status="some_future_status" />);
    expect(screen.getByText("some_future_status")).toBeInTheDocument();
  });

  it("applies the failure color class for a failed status", () => {
    render(<StatusBadge status="failed" />);
    expect(screen.getByText("Failed").className).toContain("text-status-failure");
  });
});
