import { type Locator, type Page } from '@playwright/test';
import { LineDetail } from './LineDetail';

// The clerk's page (ui/main_page.py): the header with the snapshot caption, the two input tabs and, once a line is
// checked, the counts row and the sorted list with the open line.
export class MainPage {
  readonly originCaption: Locator;
  readonly singleLineTab: Locator;
  readonly descriptionInput: Locator;
  readonly checkLineButton: Locator;
  readonly linesHeading: Locator;
  readonly downloadCsvButton: Locator;
  readonly emptyDescriptionAlert: Locator;
  readonly checkFailureAlert: Locator;

  constructor(readonly page: Page) {
    this.originCaption = page.getByText(
      /^TARIC snapshot \d{4}-\d{2}-\d{2} · EBTI rulings( built)? \d{4}-\d{2}-\d{2}$/,
    );
    this.singleLineTab = page.getByRole('tab', { name: 'Check a single line' });
    this.descriptionInput = page.getByRole('textbox', { name: 'Goods description, in English or Chinese' });
    this.checkLineButton = page.getByRole('button', { name: 'Check this line' });
    this.linesHeading = page.getByText('Lines (sorted: ask shipper → review → ready)');
    this.downloadCsvButton = page.getByRole('button', { name: 'Download CSV' });
    this.emptyDescriptionAlert = page
      .getByRole('alert')
      .filter({ hasText: 'Write the goods description first.' });
    this.checkFailureAlert = page.getByRole('alert').filter({ hasText: 'The check did not finish' });
  }

  async goto() {
    await this.page.goto('/');
  }

  async checkSingleLine(text: string) {
    await this.singleLineTab.click();
    await this.descriptionInput.fill(text);
    await this.checkLineButton.click();
  }

  // One line's row (table.py's `st.container(key=f"line_{n}")`). Streamlit renders an author's container key as the
  // `st-key-<key>` class; the row has no role or name of its own and its badge text also appears in the counts card,
  // so the stable author key is the only way to scope the badge to its row.
  lineRow(lineNo: number): Locator {
    return this.page.locator(`.st-key-line_${lineNo}`);
  }

  // The row's status badge. Streamlit renders the badge twice (once inside the help tooltip's hover target), so only
  // the visible copy counts.
  statusBadge(lineNo: number): Locator {
    return this.lineRow(lineNo).getByText(/^(Review|Ready|Ask shipper)$/).filter({ visible: true });
  }

  // One counts card (main_page.py's `st.container(border=True, key=key)`); same author-key scoping as the row, because
  // "Ask shipper" is both a row badge and a card caption.
  countCard(key: 'ready' | 'review' | 'ask'): Locator {
    return this.page.locator(`.st-key-count_${key}`);
  }

  openLine(lineNo: number, lineText: string): LineDetail {
    return new LineDetail(this.page, lineNo, lineText);
  }
}
