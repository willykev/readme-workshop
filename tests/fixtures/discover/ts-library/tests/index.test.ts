import { describe, expect, it } from "vitest";
import { slugify } from "../src/index.js";

export function testOnlyHelper() { return slugify("A B"); }

describe("slugify", () => {
  it("joins words", () => expect(slugify("Hello World")).toBe("hello-world"));
});
