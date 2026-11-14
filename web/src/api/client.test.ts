import { describe, expect, it } from "vitest";
import { ApiFailure, shouldRetry } from "./client";

describe("shouldRetry", () => {
  it("shows errors that a retry cannot fix at once", () => {
    for (const [status, code] of [
      [404, "unknown_weapon"],
      [429, "rate_limited"],
      [503, "no_release"],
      [503, "release_mismatch"],
      [500, "internal_error"],
    ] as const) {
      expect(shouldRetry(0, new ApiFailure("x", status, code))).toBe(false);
    }
  });

  it("retries network errors and server waits, twice at most", () => {
    expect(shouldRetry(0, new TypeError("network"))).toBe(true);
    expect(shouldRetry(1, new ApiFailure("x", 503, "busy"))).toBe(true);
    expect(shouldRetry(2, new ApiFailure("x", 503, "busy"))).toBe(false);
  });
});
