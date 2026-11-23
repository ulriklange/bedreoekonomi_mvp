const monthPicker = document.querySelector("#month-picker");
const loadingMessage = document.querySelector("#loading-message");
const errorMessage = document.querySelector("#error-message");
const dashboardContent = document.querySelector("#dashboard-content");
const categoryList = document.querySelector("#category-list");
const emptyCategories = document.querySelector("#empty-categories");
const billsList = document.querySelector("#bills-list");
const emptyBills = document.querySelector("#empty-bills");
const billsSort = document.querySelector("#bills-sort");
let upcomingBills = [];
let upcomingBillsLoaded = false;
let currentSummary = null;

const danishCurrency = new Intl.NumberFormat("da-DK", {
  style: "currency",
  currency: "DKK",
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

const formatAmount = (value) => danishCurrency.format(Number(value || 0));

function formatMonth(year, month) {
  return new Intl.DateTimeFormat("da-DK", { month: "long", year: "numeric" })
    .format(new Date(year, month - 1, 1));
}

function formatDate(value) {
  return new Intl.DateTimeFormat("da-DK", { day: "numeric", month: "short" })
    .format(new Date(`${value}T12:00:00`));
}

function appendText(parent, tagName, className, text) {
  const element = document.createElement(tagName);
  if (className) element.className = className;
  element.textContent = text;
  parent.append(element);
  return element;
}

function renderCategories(categories, isForecast = false) {
  categoryList.replaceChildren();
  const visibleCategories = [...categories]
    .filter((category) => Number(category.expense_total) > 0)
    .sort((a, b) => Number(b.expense_total) - Number(a.expense_total));
  const largestExpense = Math.max(1, ...visibleCategories.map((item) => Number(item.expense_total)));

  emptyCategories.hidden = visibleCategories.length > 0;
  for (const category of visibleCategories) {
    const row = document.createElement("article");
    row.className = "category-row";
    const topLine = document.createElement("div");
    topLine.className = "category-topline";
    appendText(topLine, "span", "category-name", category.main_category);
    appendText(topLine, "span", "category-amount", formatAmount(category.expense_total));
    row.append(topLine);

    appendText(
      row,
      "p",
      "category-meta",
      isForecast
        ? `Estimerede indtægter ${formatAmount(category.income_total)}`
        : `${category.transaction_count} posteringer · indtægter ${formatAmount(category.income_total)}`,
    );

    const track = document.createElement("div");
    track.className = "bar-track";
    track.setAttribute("aria-label", `Udgifter i ${category.main_category}`);
    const fill = document.createElement("div");
    fill.className = "bar-fill";
    fill.style.width = `${Math.max(2, (Number(category.expense_total) / largestExpense) * 100)}%`;
    track.append(fill);
    row.append(track);

    if (category.subcategories?.length) {
      const subcategoryList = document.createElement("div");
      subcategoryList.className = "subcategory-list";
      const sortedSubcategories = [...category.subcategories].sort(
        (a, b) => Number(b.expense_total) - Number(a.expense_total),
      );
      for (const subcategory of sortedSubcategories) {
        const subcategoryRow = document.createElement("div");
        subcategoryRow.className = "subcategory";
        appendText(subcategoryRow, "span", "", subcategory.category);
        appendText(subcategoryRow, "span", "", formatAmount(subcategory.expense_total));
        subcategoryList.append(subcategoryRow);
      }
      row.append(subcategoryList);
    }

    categoryList.append(row);
  }
}

function renderUpcomingBills() {
  billsList.replaceChildren();
  emptyBills.hidden = upcomingBills.length > 0;
  const sortedBills = [...upcomingBills].sort((a, b) => {
    if (billsSort.value === "category") {
      return a.category.localeCompare(b.category, "da")
        || a.expected_date.localeCompare(b.expected_date);
    }
    return a.expected_date.localeCompare(b.expected_date)
      || a.category.localeCompare(b.category, "da");
  });

  for (const bill of sortedBills) {
    const row = document.createElement("article");
    row.className = "bill-row";
    const details = document.createElement("div");
    details.className = "bill-details";
    appendText(details, "span", "bill-merchant", bill.merchant);
    appendText(
      details,
      "span",
      "bill-meta",
      `${formatDate(bill.expected_date)} · ${bill.account_name || "Konto ikke angivet"} · ${bill.category}`,
    );
    row.append(details);
    appendText(row, "span", "bill-amount", formatAmount(bill.estimated_amount));

    const evidence = document.createElement("details");
    evidence.className = "bill-evidence";
    appendText(evidence, "summary", "", `Grundlag: ${bill.occurrences} betalinger`);
    const sampleList = document.createElement("ul");
    for (const sample of bill.recent_occurrences) {
      appendText(sampleList, "li", "", `${formatDate(sample.date)} · ${formatAmount(sample.amount)}`);
    }
    evidence.append(sampleList);
    row.append(evidence);
    billsList.append(row);
  }
}

function renderAvailableAmount() {
  const card = document.querySelector("#available-card");
  const [selectedYear, selectedMonth] = monthPicker.value.split("-").map(Number);
  const now = new Date();
  const currentMonth = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}`;
  if (!currentSummary || !upcomingBillsLoaded || monthPicker.value !== currentMonth) {
    card.hidden = true;
    return;
  }

  const finalDay = new Date(selectedYear, selectedMonth, 0).getDate();
  const billsDueThisMonth = upcomingBills
    .filter((bill) => bill.expected_date.startsWith(monthPicker.value))
    .reduce((total, bill) => total + Number(bill.estimated_amount), 0);
  const available = Number(currentSummary.net_total) - billsDueThisMonth;
  const amountElement = document.querySelector("#available-total");
  amountElement.textContent = formatAmount(available);
  amountElement.classList.toggle("negative", available < 0);
  amountElement.classList.toggle("positive", available >= 0);
  card.hidden = false;
  card.querySelector(".card-footnote").textContent =
    `Efter forventede faste betalinger resten af måneden (til og med ${finalDay}.).`;
}

async function loadUpcomingBills() {
  const billsError = document.querySelector("#bills-error");
  const billsTotal = document.querySelector("#bills-total");
  billsError.hidden = true;
  try {
    const response = await fetch("/forecast/upcoming-bills");
    if (!response.ok) throw new Error(`API'en svarede med status ${response.status}`);
    const result = await response.json();
    upcomingBills = result.bills;
    upcomingBillsLoaded = true;
    billsTotal.textContent = `Ca. ${formatAmount(result.estimated_total)}`;
    renderUpcomingBills();
    renderAvailableAmount();
  } catch (error) {
    billsTotal.textContent = "—";
    emptyBills.hidden = true;
    billsError.textContent = `Kunne ikke hente estimaterne. ${error.message}`;
    billsError.hidden = false;
    renderAvailableAmount();
  }
}

async function loadMonth() {
  const [year, month] = monthPicker.value.split("-").map(Number);
  if (!year || !month) return;

  loadingMessage.hidden = false;
  errorMessage.hidden = true;
  dashboardContent.hidden = true;

  try {
    const now = new Date();
    const isForecast = year > now.getFullYear()
      || (year === now.getFullYear() && month > now.getMonth() + 1);
    const lastCompleteMonth = new Date(now.getFullYear(), now.getMonth(), 0);
    const historyFrom = `${lastCompleteMonth.getFullYear()}-01-01`;
    const historyTo = `${lastCompleteMonth.getFullYear()}-${String(lastCompleteMonth.getMonth() + 1).padStart(2, "0")}-${String(lastCompleteMonth.getDate()).padStart(2, "0")}`;
    const url = isForecast
      ? `/forecast/monthly?forecast_year=${year}&forecast_month=${month}&history_from=${historyFrom}&history_to=${historyTo}`
      : `/transactions/summary?year=${year}&month=${month}`;
    const response = await fetch(url);
    if (!response.ok) {
      const detail = await response.json().catch(() => ({}));
      throw new Error(detail.detail || `API'en svarede med status ${response.status}`);
    }
    const result = await response.json();
    const summary = isForecast
      ? {
          ...result,
          expense_total: result.expense_forecast,
          income_total: result.income_forecast,
          net_total: result.net_forecast,
          main_categories: result.main_categories.map((category) => ({
            main_category: category.main_category,
            transaction_count: 0,
            expense_total: category.expense_forecast,
            income_total: category.income_forecast,
            subcategories: category.subcategories.map((subcategory) => ({
              category: subcategory.category,
              expense_total: subcategory.expense_forecast,
            })),
          })),
        }
      : result;
    currentSummary = isForecast ? null : summary;

    document.querySelector("#expense-total").textContent = formatAmount(summary.expense_total);
    document.querySelector("#income-total").textContent = formatAmount(summary.income_total);
    const expenseFootnote = isForecast
      ? `Gennemsnit fra ${result.months_used} afsluttede måneder`
      : "Registreret i den valgte måned";
    const incomeFootnote = isForecast
      ? `Gennemsnit fra ${result.income_months_used} hele måneder (første måned udeladt)`
      : "Registreret i den valgte måned";
    document.querySelector("#income-label").textContent = isForecast ? "Prognose indtægter" : "Indtægter";
    document.querySelector("#expense-label").textContent = isForecast ? "Prognose udgifter" : "Udgifter";
    document.querySelector("#net-label").textContent = isForecast ? "Prognose netto" : "Netto";
    document.querySelector(".expense-card .card-footnote").textContent = expenseFootnote;
    document.querySelector(".income-card .card-footnote").textContent = incomeFootnote;
    const forecastNote = document.querySelector("#forecast-note");
    forecastNote.hidden = !isForecast;
    forecastNote.textContent = isForecast
      ? "Dette er et gennemsnitsestimat, ikke faktiske posteringer. Store enkeltudgifter kan udelades, når de ligger markant over det sædvanlige niveau i kategorien eller hovedkategorien. De faktiske posteringer ændres ikke, og prognosen påvirker ikke rådighedsbeløbet."
      : "";
    const excludedExpenses = isForecast ? result.excluded_one_off_expenses || [] : [];
    const outlierDetails = document.querySelector("#forecast-outliers");
    const outlierList = document.querySelector("#forecast-outlier-list");
    outlierList.replaceChildren();
    outlierDetails.hidden = excludedExpenses.length === 0;
    document.querySelector("#forecast-outlier-count").textContent =
      `${excludedExpenses.length} store enkeltudgifter udeladt fra prognosen`;
    for (const expense of excludedExpenses) {
      appendText(
        outlierList,
        "li",
        "",
        `${formatDate(expense.date)} · ${expense.merchant} · ${expense.category}: ${formatAmount(expense.amount)} (grænse ${formatAmount(expense.threshold)})`,
      );
    }
    const netElement = document.querySelector("#net-total");
    netElement.textContent = formatAmount(summary.net_total);
    netElement.classList.toggle("negative", Number(summary.net_total) < 0);
    netElement.classList.toggle("positive", Number(summary.net_total) >= 0);
    document.querySelector("#transaction-count").textContent = isForecast
      ? `Prognose · ${formatMonth(year, month)}`
      : `${summary.transaction_count} posteringer · ${formatMonth(year, month)}`;
    document.querySelector("#report-period").textContent = isForecast
      ? `Prognose · ${result.months_used} mdr. historik`
      : formatMonth(year, month);
    document.querySelector("#categories-heading").textContent = isForecast
      ? "Prognose pr. kategori"
      : "Forbrug pr. kategori";
    renderAvailableAmount();

    renderCategories(summary.main_categories || [], isForecast);

    const excludedCount = isForecast ? 0 : summary.excluded_from_budget?.transaction_count || 0;
    const excludedNote = document.querySelector("#excluded-note");
    excludedNote.hidden = excludedCount === 0;
    excludedNote.textContent = excludedCount
      ? `${excludedCount} posteringer uden for budgettet er udeladt fra totalerne.`
      : "";

    loadingMessage.hidden = true;
    dashboardContent.hidden = false;
  } catch (error) {
    loadingMessage.hidden = true;
    errorMessage.textContent = `Kunne ikke hente månedens økonomi. ${error.message}`;
    errorMessage.hidden = false;
  }
}

const today = new Date();
monthPicker.value = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, "0")}`;
monthPicker.addEventListener("change", loadMonth);
billsSort.addEventListener("change", renderUpcomingBills);
loadMonth();
loadUpcomingBills();
