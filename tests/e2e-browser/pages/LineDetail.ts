import { type Locator, type Page } from '@playwright/test';

// The open line under its row: the expander whose label is "Line <n> · <description>". Its blocks are the only
// surface for a checked line's description, candidates and rulings (feature 014a, contracts/ui.md §1–§3).
// Nothing here asserts: the specs keep the expectations; the helpers only name the elements and the user actions.
export class LineDetail {
  readonly root: Locator;
  readonly descriptionArea: Locator;
  readonly acceptButton: Locator;

  constructor(
    readonly page: Page,
    lineNo: number,
    readonly lineText: string,
  ) {
    this.root = page.getByTestId('stExpander').filter({ hasText: `Line ${lineNo} · ${lineText}` });
    this.descriptionArea = this.root.getByRole('textbox', { name: 'Description' });
    this.acceptButton = this.root.getByRole('button', { name: 'Accept' });
  }

  // Block 1's audited original, e.g. "Original: <line>" or "Original: <line> · Stop-word check: …".
  original(lineText: string): Locator {
    return this.root.getByText(`Original: ${lineText}`);
  }

  // Block 2's candidates: an option's label starts with the dotted HS-6 code; "Other HS-6 code…" does not.
  candidate(code?: RegExp): Locator {
    return this.root.getByRole('radio', { name: code ?? /^\d{4}\.\d{2}/ });
  }

  // The "n of m agree with <code>" caption, or the "No relevant rulings found." one.
  agreement(): Locator {
    return this.root.getByText(/^\d+ of \d+ agree with \d{4}\.\d{2}$/);
  }

  noRelevantRulings(): Locator {
    return this.root.getByText('No relevant rulings found.', { exact: true });
  }

  // Block 3's vote lines, "<✓|✗> <dotted HS-6> · <countries>".
  voteLines(): Locator {
    return this.root.getByText(/^[✓✗] \d{4}\.\d{2} · /);
  }

  rulingsVeto(): Locator {
    return this.root.getByText(/^Sent to review by the rulings of the candidates' chapters? /);
  }

  notIndexedChapters(): Locator {
    return this.root.getByText(/^No rulings indexed for chapter/);
  }

  // All of the open line's paragraphs, in document order, for the caption-order check.
  paragraphs(): Locator {
    return this.root.getByRole('paragraph');
  }
}
