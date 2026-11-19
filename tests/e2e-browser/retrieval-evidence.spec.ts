import { test, expect } from '@playwright/test';
import { readFile } from 'node:fs/promises';
import { AdminPage } from './pages/AdminPage';
import { MainPage } from './pages/MainPage';

// Feature 014a, retrieval and evidence (results/plan.md). Scenarios 2–4 check one line through the app, so they need a
// run with a usable OPENROUTER_API_KEY; with the platform's placeholder key the check ends as "Check failed" (401),
// which is an environment condition and is reported as such, not asserted around.

// The store's export, column for column (agent/store.py CSV_COLUMNS) plus the clerk_changed the page adds (FR-013).
const EXPORT_COLUMNS = [
  'line_no', 'text_zh', 'text_en', 'qty', 'flag', 'flag_rule', 'hs6_1', 'conf_1', 'hs6_2', 'conf_2', 'hs6_3',
  'conf_3', 'precedent_1', 'route', 'route_set_by', 'decided_code', 'decided_how', 'version_no', 'last_change',
  'status', 'note', 'cn8', 'taric10', 'clerk_changed',
];

// One CSV line to its fields; the app quotes a field that holds a comma (the German line does).
function parseCsvLine(line: string): string[] {
  const fields: string[] = [];
  let field = '';
  let quoted = false;
  for (let i = 0; i < line.length; i++) {
    const char = line[i];
    if (quoted) {
      if (char === '"' && line[i + 1] === '"') {
        field += '"';
        i++;
      } else if (char === '"') {
        quoted = false;
      } else {
        field += char;
      }
    } else if (char === '"') {
      quoted = true;
    } else if (char === ',') {
      fields.push(field);
      field = '';
    } else {
      field += char;
    }
  }
  fields.push(field);
  return fields;
}

test.describe('Retrieval and evidence (014a)', () => {
  /** Covers 014a/FR-010, US2 AC6 */
  test('1. admin data states the rulings the app loaded [014a/FR-010]', async ({ page }) => {
    const main = new MainPage(page);
    await main.goto();
    const headerCaption = (await main.originCaption.innerText()).trim();
    expect(headerCaption).toMatch(/^TARIC snapshot \d{4}-\d{2}-\d{2} · EBTI rulings( built)? \d{4}-\d{2}-\d{2}$/);
    const headerEbtiDate = headerCaption.match(/EBTI rulings(?: built)? (\d{4}-\d{2}-\d{2})$/)![1];

    const admin = new AdminPage(page);
    await admin.goto();
    await admin.selectData();
    await expect(admin.dataRadio).toBeChecked();

    const statement = (await admin.rulingsStatement.innerText()).trim();
    const built = statement.match(/^EBTI rulings: ([\d,]+) · built (\d{4}-\d{2}-\d{2})$/);
    const extract = statement.match(/^EBTI rulings: ([\d,]+) · extract (\d{4}-\d{2}-\d{2})(?: · (.+))?$/);
    expect(built ?? extract).toBeTruthy();
    const [, count, date, source] = (built ?? extract)!;
    expect(Number(count.replace(/,/g, ''))).toBeGreaterThanOrEqual(1);
    expect(date).toBe(headerEbtiDate);
    if (built) {
      // The CI demo store records no extract, so it names no chapters: no claim of a coverage it cannot name.
      expect(statement).not.toMatch(/chapter|full extract/i);
      await expect(admin.rulingsChapterClaim).toHaveCount(0);
    } else {
      // A store built from a source version names the chapters it covers, all of them for an all-chapter store.
      expect(source).toBeTruthy();
      await expect(admin.rulingsStatement).toContainText(
        new RegExp(`full extract of ${date}, all chapters|chapters? \\d\\d`),
      );
    }

    await expect(admin.taricStatement).toHaveText(
      /^TARIC snapshot: \d{4}-\d{2}-\d{2} · [\d,]+ CN-8 mismatch(es)? · Swedish Customs Tariff File Distribution( · batch \S+)?$/,
    );
    await expect(admin.coverageStatement).toHaveText(
      /^HS 2022 \/ CN \d{4} · [\d,]+ subheadings · ICS2 \d+ terms · firm list \d+ · [\d,]+ BTI rulings · updated \d{4}-\d{2}-\d{2}$/,
    );
  });

  /** Covers 014a/FR-015, 014a/FR-017, 014a/FR-018, US4 AC1/AC2/AC3/AC5 */
  test('2. a checked coolant line shows the deciding vote and never the retired sentence [014a/FR-015] [014a/FR-017] [014a/FR-018]', async ({ page }) => {
    test.setTimeout(60_000);
    const lineText = '金属加工用的冷却液，不含矿物油';
    const main = new MainPage(page);
    await main.goto();
    await main.checkSingleLine(lineText);

    const line = main.openLine(1, lineText);
    await expect(line.root).toBeVisible({ timeout: 45_000 });
    // The scenarios read the result of a check; a check that did not finish (for example with no usable model key) is
    // an environment condition, not the state described here.
    await expect(main.checkFailureAlert).toHaveCount(0);

    // Block 3: the heading, the vote, and never the retired sentence (FR-018).
    await expect(line.root.getByText('3 Similar rulings (5 nearest, EBTI)')).toBeVisible();
    await expect(page.getByText('No ruling was within the similarity floor.')).toHaveCount(0);
    const voteTexts = await line.voteLines().allInnerTexts();
    expect(voteTexts.length).toBeLessThanOrEqual(5);
    for (const text of voteTexts) {
      expect(text).toMatch(/^[✓✗] \d{4}\.\d{2} · (\?\?|[A-Z]{2})(, (\?\?|[A-Z]{2}))*$/);
    }

    // FR-015: exactly one of the two states, and only when the model returned a candidate ("No relevant rulings
    // found." holds exactly when the deciding vote has no voter).
    const candidates = await line.candidate().count();
    if (candidates > 0) {
      await expect(line.agreement().or(line.noRelevantRulings())).toHaveCount(1);
    } else {
      await expect(line.agreement()).toHaveCount(0);
      await expect(line.noRelevantRulings()).toHaveCount(0);
    }

    // AC3: at most one "No rulings indexed" caption, two-digit chapters, ascending and unique.
    const notIndexed = line.notIndexedChapters();
    expect(await notIndexed.count()).toBeLessThanOrEqual(1);
    if ((await notIndexed.count()) === 1) {
      const text = (await notIndexed.innerText()).trim();
      expect(text).toMatch(
        /^No rulings indexed for chapter \d\d\.$|^No rulings indexed for chapters \d\d and \d\d\.$|^No rulings indexed for chapters \d\d, \d\d and \d\d\.$/,
      );
      const chapters = [...text.matchAll(/\d\d/g)].map((match) => Number(match[0]));
      expect(chapters).toEqual([...chapters].sort((a, b) => a - b));
      expect(new Set(chapters).size).toBe(chapters.length);
    }

    // FR-018 caption 2, when the candidates' chapters sent the line to review.
    const veto = line.rulingsVeto();
    expect(await veto.count()).toBeLessThanOrEqual(1);
    if ((await veto.count()) === 1) {
      await expect(veto).toHaveText(
        /^Sent to review by the rulings of the candidates' chapters? .+: (\d+ of \d+ at \d{4}\.\d{2}|split, .+)\.$/,
      );
    }

    // FR-018's caption order: (1) agreement / no relevant, (2) the veto, (3) the chapters without rulings.
    const paragraphs = await line.paragraphs().allInnerTexts();
    const at = (pattern: RegExp) => paragraphs.findIndex((text) => pattern.test(text.trim()));
    const order = [
      at(/^(\d+ of \d+ agree with \d{4}\.\d{2}|No relevant rulings found\.)$/),
      at(/^Sent to review by the rulings of the candidates' chapters? /),
      at(/^No rulings indexed for chapter/),
    ].filter((index) => index >= 0);
    expect(order).toEqual([...order].sort((a, b) => a - b));

    // After the check: the rest of the line, its badge and its counts card are consistent.
    await expect(line.original(lineText)).toBeVisible();
    await expect(line.root.getByText('4 Tariff (Origin CN)')).toBeVisible();
    const badge = main.statusBadge(1);
    await expect(badge).toHaveCount(1);
    const badgeText = (await badge.innerText()).trim();
    const card = badgeText === 'Ready' ? 'ready' : badgeText === 'Review' ? 'review' : 'ask';
    await expect(main.countCard(card).getByRole('heading', { level: 3 })).toHaveText('1');
  });

  /** Covers 014a/FR-023, 014a/FR-025, 014a/FR-026, US6 AC2/AC10 */
  test('3. with the switch off the line keeps its raw text and the export has no new field [014a/FR-025] [014a/FR-026] [014a/FR-023]', async ({ page }) => {
    test.setTimeout(60_000);
    const lineText = 'Kühlschmierstoff für die Metallbearbeitung, ohne Mineralöl';
    const main = new MainPage(page);
    await main.goto();
    await main.checkSingleLine(lineText);

    const line = main.openLine(1, lineText);
    await expect(line.root).toBeVisible({ timeout: 45_000 });
    // The scenarios read the result of a check; a check that did not finish (for example with no usable model key) is
    // an environment condition, not the state described here.
    await expect(main.checkFailureAlert).toHaveCount(0);

    // Block 1 keeps the raw line, and the switch off leaves no customs-wording caption (FR-025).
    await expect(line.descriptionArea).toHaveValue(lineText);
    await expect(line.original(lineText)).toBeVisible();
    await expect(page.getByText(/Rulings also searched in customs wording \(/)).toHaveCount(0);

    // The CSV export is unchanged: the documented columns, the raw line, and no new column (FR-023).
    const [download] = await Promise.all([page.waitForEvent('download'), main.downloadCsvButton.click()]);
    const path = await download.path();
    const csv = (await readFile(path!, 'utf8')).replace(/^\uFEFF/, '');
    const [headerLine, ...dataLines] = csv.split(/\r?\n/).filter((row) => row.length > 0);
    const header = parseCsvLine(headerLine);
    expect(header).toEqual(EXPORT_COLUMNS);
    expect(header.filter((column) => /customs|wording|citation|reason/i.test(column))).toEqual([]);
    const zhAt = header.indexOf('text_zh');
    const enAt = header.indexOf('text_en');
    const row = dataLines.map(parseCsvLine).find((fields) => fields[zhAt] === lineText || fields[enAt] === lineText);
    expect(row).toBeTruthy();
  });

  /** Covers 014a/FR-019, US6 AC7 */
  test('4. the plain coolant line still goes to the shipper [014a/FR-019]', async ({ page }) => {
    test.setTimeout(60_000);
    const lineText = '冷却液';
    const main = new MainPage(page);
    await main.goto();
    await main.checkSingleLine(lineText);

    const line = main.openLine(1, lineText);
    await expect(line.root).toBeVisible({ timeout: 45_000 });
    // The scenarios read the result of a check; a check that did not finish (for example with no usable model key) is
    // an environment condition, not the state described here.
    await expect(main.checkFailureAlert).toHaveCount(0);

    // The row's badge and the card's caption both read "Ask shipper", so each is scoped to its own container.
    await expect(main.statusBadge(1)).toHaveText('Ask shipper');
    await expect(main.countCard('ask').getByText('Ask shipper')).toBeVisible();
    await expect(main.countCard('ask').getByRole('heading', { level: 3 })).toHaveText('1');
    // The flagged line is locked, whatever its candidates and vote.
    await expect(line.acceptButton).toBeDisabled();
    await expect(line.root.getByText(/^Reason: /)).toHaveText(
      /^(Reason: vague description — .+|Reason: candidates too close)$/,
    );
    await expect(page.getByText('Check failed', { exact: true })).toHaveCount(0);
  });

  test('5. an empty description is refused [no FR: line-check surface guard]', async ({ page }) => {
    const main = new MainPage(page);
    await main.goto();
    await main.singleLineTab.click();
    await main.checkLineButton.click();

    await expect(main.emptyDescriptionAlert).toBeVisible();
    await expect(main.emptyDescriptionAlert).toHaveText('Write the goods description first.');
    await expect(main.linesHeading).toHaveCount(0);
  });
});
