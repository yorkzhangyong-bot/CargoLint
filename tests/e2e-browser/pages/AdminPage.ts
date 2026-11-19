import { type Locator, type Page } from '@playwright/test';

// The operator page at /admin (ui/admin.py). "Data" is the only section these tests read: the EBTI store the app
// loaded, the TARIC snapshot and the knowledge-base coverage.
export class AdminPage {
  readonly dataRadio: Locator;
  readonly rulingsStatement: Locator;
  readonly taricStatement: Locator;
  readonly coverageStatement: Locator;
  readonly rulingsChapterClaim: Locator;

  constructor(readonly page: Page) {
    this.dataRadio = page.getByRole('radio', { name: 'Data' });
    this.rulingsStatement = page.getByText(/^EBTI rulings: /);
    this.taricStatement = page.getByText(/^TARIC snapshot: /);
    this.coverageStatement = page.getByText(/^HS 2022 \/ CN /);
    this.rulingsChapterClaim = page.getByText(/full extract of \d{4}-\d{2}-\d{2}, all chapters|chapters? \d\d/);
  }

  async goto() {
    await this.page.goto('/admin');
  }

  async selectData() {
    await this.dataRadio.click();
  }
}
