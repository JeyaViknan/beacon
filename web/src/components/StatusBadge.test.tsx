import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { Status } from "../lib/types";
import { StatusBadge } from "./StatusBadge";

describe("StatusBadge", () => {
  it.each<[Status, string]>([
    ["UP", "Up"],
    ["DEGRADED", "Degraded"],
    ["DOWN", "Down"],
    ["PAUSED", "Paused"],
    ["UNKNOWN", "Waiting"],
  ])("%s shows an icon and the text %s", (status, label) => {
    const { container } = render(<StatusBadge status={status} />);
    expect(screen.getByText(label)).toBeInTheDocument();
    expect(container.querySelector("svg")).not.toBeNull();
  });
});
