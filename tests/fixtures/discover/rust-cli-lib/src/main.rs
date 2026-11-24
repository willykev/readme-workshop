use clap::{Parser, Subcommand};
use std::path::PathBuf;

/// Count the words in text files.
#[derive(Parser)]
#[command(name = "wordfreq", version, about)]
struct Cli {
    /// Only show the top N words
    #[arg(short = 'n', long, default_value_t = 10)]
    top: usize,

    /// Print the counts as JSON
    #[arg(long)]
    json: bool,

    #[arg(long, hide = true)]
    debug_dump: bool,

    #[command(subcommand)]
    command: Option<Command>,
}

#[derive(Subcommand)]
enum Command {
    /// Count the words in files
    Count { files: Vec<PathBuf> },
    /// Compare the words of two files
    Compare { a: PathBuf, b: PathBuf },
    #[command(hide = true)]
    SelfTest,
    // Legacy { path: PathBuf },
}

fn main() {
    let cli = Cli::parse();
    let color = std::env::var("WORDFREQ_COLOR").is_ok();
    let _ = (cli.top, cli.json, color);
}
