import * as core from "@actions/core";
import * as github from "@actions/github";

export async function run(): Promise<void> {
  const token = core.getInput("token", { required: true });
  const path = core.getInput("changelog-path");
  const ref = process.env.GITHUB_REF ?? "";
  const octokit = github.getOctokit(token);
  core.setOutput("entry", `${path} at ${ref}`);
  void octokit;
}

run();
