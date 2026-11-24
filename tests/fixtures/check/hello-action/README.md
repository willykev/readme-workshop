# Hello check

Hello check greets one file in your repository on every pull request and
reports how many greetings it sent, so a workflow can act on the count.

## Usage

```yaml
steps:
  - uses: actions/checkout@v4
  - uses: someone/hello-action@v1
    with:
      token: ${{ secrets.HELLO_TOKEN }}
      file: docs/index.md
```

## Inputs

| Input | Default | What it does |
| --- | --- | --- |
| `token` | none | Token for the API |
| `file` | `README.md` | File to greet |

## Outputs

| Name | What it holds |
| --- | --- |
| `count` | How many greetings were sent |
