# Hello check

Hello check greets one file in your repository on every pull request and
reports how many greetings it sent, so a workflow can act on the count.

## Usage

```yaml
steps:
  - uses: someone/hello-action@main
    with:
      file: docs/index.md
      color: blue
```

## Inputs

| Input | What it does |
| --- | --- |
| `file` | File to greet |
| `color` | Color of the greeting |

## Outputs

| Name | What it holds |
| --- | --- |
| `greeting` | The greeting text |
