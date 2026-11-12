from datetime import date as Date
from decimal import Decimal
from enum import Enum

from pydantic import BaseModel, Field


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
    SERVICE_REPAIR = "Service og reperation"
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


class TransactionFields(BaseModel):
    merchant: str = Field(min_length=1, examples=["Netto"])
    amount: Decimal = Field(gt=0, max_digits=10, decimal_places=2, examples=[245.50])
    date: Date = Field(examples=["2026-11-11"])


class TransactionCreate(TransactionFields):
    category: BankCategory = Field(examples=["Dagligvarer"])


class Transaction(TransactionFields):
    id: int
    category: str


class CategoryTotal(BaseModel):
    category: str
    transaction_count: int
    total_amount: Decimal


class TransactionSummary(BaseModel):
    year: int
    month: int
    transaction_count: int
    total_amount: Decimal
    categories: list[CategoryTotal]
