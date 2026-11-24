use crate::Frequencies;

pub fn render(freq: &Frequencies) -> String {
    format!("{} words", freq.words.len())
}
