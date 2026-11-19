const monthPicker = document.querySelector("#month-picker");
const loadingMessage = document.querySelector("#loading-message");
const errorMessage = document.querySelector("#error-message");
const dashboardContent = document.querySelector("#dashboard-content");
const categoryList = document.querySelector("#category-list");
const emptyCategories = document.querySelector("#empty-categories");

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

function appendText(parent, tagName, className, text) {
  const element = document.createElement(tagName);
  if (className) element.className = className;
  element.textContent = text;
  parent.append(element);
  return element;
}

function renderCategories(categories) {
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
      `${category.transaction_count} posteringer · indtægter ${formatAmount(category.income_total)}`,
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

async function loadMonth() {
  const [year, month] = monthPicker.value.split("-").map(Number);
  if (!year || !month) return;

  loadingMessage.hidden = false;
  errorMessage.hidden = true;
  dashboardContent.hidden = true;

  try {
    const response = await fetch(`/transactions/summary?year=${year}&month=${month}`);
    if (!response.ok) {
      const detail = await response.json().catch(() => ({}));
      throw new Error(detail.detail || `API'en svarede med status ${response.status}`);
    }
    const summary = await response.json();

    document.querySelector("#expense-total").textContent = formatAmount(summary.expense_total);
    document.querySelector("#income-total").textContent = formatAmount(summary.income_total);
    const netElement = document.querySelector("#net-total");
    netElement.textContent = formatAmount(summary.net_total);
    netElement.classList.toggle("negative", Number(summary.net_total) < 0);
    netElement.classList.toggle("positive", Number(summary.net_total) >= 0);
    document.querySelector("#transaction-count").textContent =
      `${summary.transaction_count} posteringer · ${formatMonth(year, month)}`;
    document.querySelector("#report-period").textContent = formatMonth(year, month);

    renderCategories(summary.main_categories || []);

    const excludedCount = summary.excluded_from_budget?.transaction_count || 0;
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
loadMonth();
