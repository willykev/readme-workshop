//! Word counting.

use std::collections::HashMap;

pub mod report;

/// How to order the counted words.
pub enum SortOrder {
    Count,
    Alphabetical,
}

/// Words and how often each appears.
pub struct Frequencies {
    pub words: HashMap<String, usize>,
}

/// Count the words in a text.
pub fn count_words(text: &str) -> Frequencies {
    let mut words = HashMap::new();
    for word in tokenize(text) {
        *words.entry(word).or_insert(0) += 1;
    }
    Frequencies { words }
}

pub(crate) fn tokenize(text: &str) -> Vec<String> {
    text.split_whitespace().map(helper).collect()
}

fn helper(word: &str) -> String {
    word.to_lowercase()
}

#[doc(hidden)]
pub fn debug_internals() {}

// pub fn legacy_count(text: &str) -> usize { text.len() }
