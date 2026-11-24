import * as core from "@actions/core";
export function debugOnly() { return core.getInput("debug-only"); }
