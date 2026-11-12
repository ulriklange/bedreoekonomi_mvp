from datetime import date as Date
from decimal import Decimal
from enum import Enum

from pydantic import BaseModel, Field, field_validator


class BankCategory(str, Enum):
    MORTGAGE = "Realkreditlån"
    MAINTENANCE = "Vedligeholdelse"
    HOME_LOAN = "Boliglån"
    HEATING = "Varme"
    WATER = "Vand"
    WASTE = "Renovation"
    FURNITURE_HOME_ACCESSORIES = "Møbler og boligtilbehør"
    ELECTRICITY = "El"
    HOUSE_GARDEN_SERVICES = "Hus- og haveservice"
    GROCERIES = "Dagligvarer"
    TAKEAWAY_FAST_FOOD = "Take away og fast food"
    SPECIALTY_SHOP = "Specialbutik"
    UNION_UNEMPLOYMENT_INSURANCE = "Fagforening, A-kasse og lønsikring"
    ACCIDENT_HEALTH_INSURANCE = "Ulykkes- og sundhedsforsikring"
    INSURANCE_OTHER = "Forsikringer (Andet)"
    HOME_INSURANCE = "Husforsikring"
    CAR_INSURANCE_ROADSIDE = "Bilforsikring og vejhjælp"
    CONTENTS_INSURANCE = "Indboforsikring"
    CONSUMER_LOAN = "Forbrugslån"
    INTEREST_FEES = "Renter og gebyrer"
    LOANS_DEBT_OTHER = "Lån og gæld (Andet)"
    TRANSPORT_OTHER = "Transport (Andet)"
    SERVICE_REPAIR = "Service og reparation"
    FUEL = "Brændstof"
    LOAN_LEASING_PAYMENT = "Låne- og leasingydelse"
    VEHICLE_TAX = "Ejer-, registrerings- og vægtafgift"
    PARKING = "Parkering og pladsleje"
    TAXI_PUBLIC_TRANSPORT = "Taxa og offentlig transport"
    LEISURE_OTHER = "Fritid (Andet)"
    GIFTS_CHARITY = "Gaver og velgørenhed"
    SPORTS_LEISURE = "Sport og fritidsaktiviteter"
    CAFE_RESTAURANT_BAR = "Café, restaurant og bar"
    HOLIDAY_TRAVEL = "Ferie og rejser"
    CONCERT_CINEMA_MUSEUM = "Koncert, biograf og museum"
    PETS = "Kæledyr"
    ELECTRONICS_GADGETS = "Elektronik og gadgets"
    HOTEL_CAMPING = "Hotel og camping"
    INTEREST_ORGANIZATIONS = "Interesseorganisationer"
    GAMES_TOYS = "Spil og legetøj"
    SAVINGS = "Opsparing"
    CLOTHING_SHOES_ACCESSORIES = "Tøj, sko og accessories"
    HAIR_SKINCARE = "Hår- og hudpleje"
    DENTIST_DOCTOR_MEDICINE = "Tandlæge, læge og medicin"
    CLOTHING_PERSONAL_CARE_OTHER = "Sko, tøj og personlig pleje (Andet)"
    OTHER_EXPENSE = "Anden udgift"
    OTHER_TRANSFER = "Andet (Overførsel)"
    OTHER_CASH = "Andet (Kontanter)"
    PHONE_INTERNET_STREAMING_TV = "Telefon, internet, streaming og TV"
    FILM_MUSIC_APPS_SOFTWARE = "Film, musik, apps og software"
    NEWSPAPERS_MAGAZINES_BOOKS = "Aviser, blade og bøger"
    CHILDCARE = "Børnepasning"
    SCHOOL_EDUCATION_COURSES = "Skole-, uddannelses- og kursusudgifter"
    UNCATEGORIZED = "Ingen kategori"
    OTHER_INCOME = "Anden indtægt"


EXCLUDED_MAIN_CATEGORY = "Indgår ikke i budget og forbrug"


# Mapping from the bank's subcategory (stored as `category`) to its parent.
CATEGORY_PARENTS: dict[BankCategory, str] = {
    BankCategory.MORTGAGE: "Bolig",
    BankCategory.MAINTENANCE: "Bolig",
    BankCategory.HOME_LOAN: "Bolig",
    BankCategory.HEATING: "Bolig",
    BankCategory.WATER: "Bolig",
    BankCategory.WASTE: "Bolig",
    BankCategory.FURNITURE_HOME_ACCESSORIES: "Bolig",
    BankCategory.ELECTRICITY: "Bolig",
    BankCategory.HOUSE_GARDEN_SERVICES: "Bolig",
    BankCategory.GROCERIES: "Mad og indkøb",
    BankCategory.TAKEAWAY_FAST_FOOD: "Mad og indkøb",
    BankCategory.SPECIALTY_SHOP: "Mad og indkøb",
    BankCategory.UNION_UNEMPLOYMENT_INSURANCE: "Forsikringer",
    BankCategory.ACCIDENT_HEALTH_INSURANCE: "Forsikringer",
    BankCategory.INSURANCE_OTHER: "Forsikringer",
    BankCategory.HOME_INSURANCE: "Forsikringer",
    BankCategory.CAR_INSURANCE_ROADSIDE: "Forsikringer",
    BankCategory.CONTENTS_INSURANCE: "Forsikringer",
    BankCategory.CONSUMER_LOAN: "Lån og gæld",
    BankCategory.INTEREST_FEES: "Lån og gæld",
    BankCategory.LOANS_DEBT_OTHER: "Lån og gæld",
    BankCategory.TRANSPORT_OTHER: "Transport",
    BankCategory.SERVICE_REPAIR: "Transport",
    BankCategory.FUEL: "Transport",
    BankCategory.LOAN_LEASING_PAYMENT: "Transport",
    BankCategory.VEHICLE_TAX: "Transport",
    BankCategory.PARKING: "Transport",
    BankCategory.TAXI_PUBLIC_TRANSPORT: "Transport",
    BankCategory.LEISURE_OTHER: "Fritid",
    BankCategory.GIFTS_CHARITY: "Fritid",
    BankCategory.SPORTS_LEISURE: "Fritid",
    BankCategory.CAFE_RESTAURANT_BAR: "Fritid",
    BankCategory.HOLIDAY_TRAVEL: "Fritid",
    BankCategory.CONCERT_CINEMA_MUSEUM: "Fritid",
    BankCategory.PETS: "Fritid",
    BankCategory.ELECTRONICS_GADGETS: "Fritid",
    BankCategory.HOTEL_CAMPING: "Fritid",
    BankCategory.INTEREST_ORGANIZATIONS: "Fritid",
    BankCategory.GAMES_TOYS: "Fritid",
    BankCategory.SAVINGS: "Opsparing og investering",
    BankCategory.CLOTHING_SHOES_ACCESSORIES: "Sko, tøj og personlig pleje",
    BankCategory.HAIR_SKINCARE: "Sko, tøj og personlig pleje",
    BankCategory.DENTIST_DOCTOR_MEDICINE: "Sko, tøj og personlig pleje",
    BankCategory.CLOTHING_PERSONAL_CARE_OTHER: "Sko, tøj og personlig pleje",
    BankCategory.OTHER_EXPENSE: "Andet",
    BankCategory.OTHER_TRANSFER: "Andet",
    BankCategory.OTHER_CASH: "Andet",
    BankCategory.PHONE_INTERNET_STREAMING_TV: "Medier",
    BankCategory.FILM_MUSIC_APPS_SOFTWARE: "Medier",
    BankCategory.NEWSPAPERS_MAGAZINES_BOOKS: "Medier",
    BankCategory.CHILDCARE: "Uddannelse og pasning",
    BankCategory.SCHOOL_EDUCATION_COURSES: "Uddannelse og pasning",
    BankCategory.UNCATEGORIZED: EXCLUDED_MAIN_CATEGORY,
    BankCategory.OTHER_INCOME: "Indtægter",
}


def main_category_for(category: str) -> str:
    try:
        return CATEGORY_PARENTS[BankCategory(category)]
    except ValueError:
        # Keep legacy rows such as the earlier test category `Mad` readable.
        return "Ukategoriseret"


def category_hierarchy() -> dict[str, list[str]]:
    hierarchy: dict[str, list[str]] = {}
    for category in BankCategory:
        hierarchy.setdefault(CATEGORY_PARENTS[category], []).append(category.value)
    return hierarchy


class TransactionFields(BaseModel):
    merchant: str = Field(min_length=1, examples=["Netto"])
    amount: Decimal = Field(max_digits=10, decimal_places=2, examples=[-245.50])
    date: Date = Field(examples=["2026-11-11"])

    @field_validator("amount")
    @classmethod
    def amount_must_not_be_zero(cls, value: Decimal) -> Decimal:
        if value == 0:
            raise ValueError("Amount cannot be zero")
        return value


class TransactionCreate(TransactionFields):
    category: BankCategory = Field(examples=["Dagligvarer"])


class Transaction(TransactionFields):
    id: int
    main_category: str
    category: str


class CategoryTotal(BaseModel):
    main_category: str
    category: str
    transaction_count: int
    expense_total: Decimal
    income_total: Decimal
    net_total: Decimal


class MainCategoryTotal(BaseModel):
    main_category: str
    transaction_count: int
    expense_total: Decimal
    income_total: Decimal
    net_total: Decimal
    subcategories: list[CategoryTotal]


class TransactionSummary(BaseModel):
    year: int
    month: int
    transaction_count: int
    expense_total: Decimal
    income_total: Decimal
    net_total: Decimal
    categories: list[CategoryTotal]
    main_categories: list[MainCategoryTotal]
    excluded_from_budget: MainCategoryTotal | None
