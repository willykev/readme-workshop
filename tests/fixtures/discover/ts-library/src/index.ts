import { transliterate } from "./transliterate.js";

/** Characters that may separate words in a slug. */
export type Separator = "-" | "_";

export interface SlugOptions {
  separator?: Separator;
  maxLength?: number;
}

export const DEFAULT_SEPARATOR: Separator = "-";

function normalizeSpaces(text: string): string {
  return text.trim().replace(/\s+/g, " ");
}

export function slugify(title: string, options: SlugOptions = {}): string {
  const sep = options.separator ?? DEFAULT_SEPARATOR;
  return normalizeSpaces(transliterate(title)).toLowerCase().split(" ").join(sep);
}

export function isSlug(text: string): boolean {
  return /^[a-z0-9]+(?:[-_][a-z0-9]+)*$/.test(text);
}

export class SlugRegistry {
  private seen = new Set<string>();
  claim(title: string): string {
    let slug = slugify(title);
    for (let n = 2; this.seen.has(slug); n++) slug = `${slugify(title)}-${n}`;
    this.seen.add(slug);
    return slug;
  }
}

export function _privateHelper(): void {}

/** @internal */
export function internalReset(): void {}

// export function legacySlug(title: string) { return title; }

export { transliterate } from "./transliterate.js";
