use clap::Parser;

#[derive(Parser)]
struct TestCli {
    #[arg(long)]
    test_only_flag: bool,
}

#[test]
fn parses() {
    let _ = TestCli::parse_from(["x", "--test-only-flag"]);
}
