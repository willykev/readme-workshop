const MAP: Record<string, string> = { "ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss" };

export function transliterate(text: string): string {
  return text.replace(/[äöüß]/g, (ch) => MAP[ch] ?? ch);
}

export function unexportedFromIndex(): string {
  return "not part of the package entry";
}
