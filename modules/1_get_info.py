"""
Single-file Playwright parser for Brain.com.ua.

Workflow:
1. Open the search results page by query URL.
2. Open the first product result.
3. Parse product data from the product page.
4. Save the product into Django database.
5. Print parsed data.
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass
from decimal import Decimal, InvalidOperation
from typing import Any, Optional, TypedDict, cast
from urllib.parse import quote, urljoin

from playwright.sync_api import (
    Browser,
    BrowserContext,
    Locator,
    Page,
    Playwright,
    TimeoutError as PlaywrightTimeoutError,
    Error as PlaywrightError,
    sync_playwright,
)

import load_django  # noqa: F401
from parser_app.models import Product


HOME_URL = "https://brain.com.ua/"
SEARCH_QUERY = "Apple iPhone 15 128GB Black"

DEFAULT_TEXT: Optional[str] = None
DEFAULT_PRICE: Optional[Decimal] = None
WAIT_TIMEOUT_MS = 25_000

CHAR_COLOR = "Колір"
CHAR_MEMORY = "Вбудована пам'ять"
CHAR_MANUFACTURER = "Виробник"
CHAR_SCREEN_SIZE = "Діагональ екрану"
CHAR_SCREEN_RESOLUTION = "Роздільна здатність екрану"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)


class ViewportSize(TypedDict):
    width: int
    height: int


@dataclass
class ProductData:
    """Structured DTO for parsed product data."""

    name: Optional[str] = DEFAULT_TEXT
    color: Optional[str] = DEFAULT_TEXT
    memory: Optional[str] = DEFAULT_TEXT
    manufacturer: Optional[str] = DEFAULT_TEXT
    price: Optional[Decimal] = DEFAULT_PRICE
    price_discount: Optional[Decimal] = DEFAULT_PRICE
    photos: Optional[list[str]] = None
    goods_code: Optional[str] = None
    reviews_count: Optional[int] = None
    screen_size: Optional[str] = DEFAULT_TEXT
    screen_resolution: Optional[str] = DEFAULT_TEXT
    characteristics: Optional[dict[str, str]] = None

    def to_dict(self) -> dict[str, Any]:
        """Convert parsed product data to dictionary."""
        return asdict(self)


def clean_text(value: Optional[str], default: Optional[str] = DEFAULT_TEXT) -> Optional[str]:
    """Normalize whitespace and return default if value is empty."""
    if not value:
        return default
    normalized = " ".join(value.replace("\xa0", " ").split())
    return normalized if normalized else default


def to_decimal(value: Optional[str], default: Optional[Decimal] = DEFAULT_PRICE) -> Optional[Decimal]:
    """Convert a price-like string to Decimal."""
    if not value:
        return default

    cleaned = (
        value.replace("₴", "")
        .replace("\xa0", "")
        .replace(" ", "")
        .replace(",", ".")
        .strip()
    )

    if not cleaned:
        return default

    try:
        return Decimal(cleaned)
    except (InvalidOperation, ValueError):
        return default


def deduplicate_preserve_order(values: list[str]) -> list[str]:
    """Remove duplicates while preserving order."""
    result: list[str] = []
    seen: set[str] = set()

    for value in values:
        if value and value not in seen:
            seen.add(value)
            result.append(value)

    return result


def create_browser() -> tuple[Playwright, Browser, BrowserContext, Page]:
    """Create Playwright browser, context, and page."""
    playwright = sync_playwright().start()
    browser = playwright.chromium.launch(
        headless=True,
        args=[
            "--disable-blink-features=AutomationControlled",
            "--no-sandbox",
            "--disable-dev-shm-usage",
        ],
    )
    viewport = cast(ViewportSize, {"width": 1920, "height": 1080})
    context = browser.new_context(
        viewport=viewport,
        locale="uk-UA",
        user_agent=(
            "Mozilla/5.0 (X11; Linux x86_64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/122.0.0.0 Safari/537.36"
        ),
    )
    page = context.new_page()
    page.set_default_timeout(WAIT_TIMEOUT_MS)
    return playwright, browser, context, page


class BrainSearchNavigator:
    """Navigate Brain.com.ua search flow with Playwright."""

    PRODUCT_WRAPPER = ".product-wrapper"
    FIRST_PRODUCT_LINK = ".br-pp-img.br-pp-img-grid a[href]"
    PRODUCT_NAME = ".fnp-product-name"

    def __init__(self, page: Page) -> None:
        self.page = page

    def open_first_product_from_search(self, home_url: str, query: str) -> None:
        """Open search page by query URL and open first product result."""
        search_url = f"{home_url.rstrip('/')}/ukr/search/?Search={quote(query)}"
        logger.info("Opening search page: %s", search_url)
        self.page.goto(search_url, wait_until="domcontentloaded")

        first_result = self.page.locator(self.PRODUCT_WRAPPER).first
        first_result.wait_for(state="visible")

        first_result_link = first_result.locator(self.FIRST_PRODUCT_LINK).first
        product_url = first_result_link.get_attribute("href")
        if not product_url:
            raise ValueError("The first product link does not contain href.")

        product_url = urljoin(home_url, product_url)
        logger.info("Opening first product result: %s", product_url)
        self.page.goto(product_url, wait_until="domcontentloaded")

        self.page.locator(self.PRODUCT_NAME).nth(0).wait_for(state="attached")


class BrainProductParser:
    """Parse Brain.com.ua product fields from current product page using DOM only."""

    PRODUCT_NAME = ".fnp-product-name"
    MAIN_RIGHT_BLOCK = ".main-right-block"
    CHARACTERISTICS_ROOT = "#br-pr-7"
    CHARACTERISTICS_ITEMS = ".br-pr-chr-item"
    CHARACTERISTICS_BUTTON = "#br-pr-7 .br-prs-button"
    REVIEWS_LINK = 'a.scroll-to-element[href="#reviews-list"]'
    PRODUCT_CODE_BLOCK = "#product_code"
    PRODUCT_CODE_VALUE = "span.br-pr-code-val"

    PRICE_SELECTORS = [
        ".br-pr-op .price-wrapper > span",
        ".br-pr-op .price-wrapper",
        ".price-wrapper > span",
        ".price-wrapper",
        ".price",
    ]
    DISCOUNT_PRICE_SELECTORS = [
        ".red-price",
        ".br-pr-np .red-price",
        ".old-price span",
    ]
    PHOTO_SELECTORS = [
        ".main-left-block .product-block-bottom img[src]",
        ".product-block-bottom img[src]",
        ".br-pr-sf img[src]",
        ".slick-slide img[src]",
    ]

    def __init__(self, page: Page) -> None:
        self.page = page

    def parse(self) -> ProductData:
        """Parse full product data from current product page."""
        self.page.locator(self.PRODUCT_NAME).nth(0).wait_for(state="attached")
        self._expand_characteristics_if_needed()

        goods_code = self._parse_goods_code()
        characteristics = self._parse_characteristics()
        characteristics_value = characteristics if characteristics else None
        photos = self._parse_photos(goods_code)
        photos_value = photos if photos else None

        return ProductData(
            name=self._parse_name(),
            color=characteristics.get(CHAR_COLOR) if characteristics else None,
            memory=characteristics.get(CHAR_MEMORY) if characteristics else None,
            manufacturer=characteristics.get(CHAR_MANUFACTURER) if characteristics else None,
            price=self._parse_price(),
            price_discount=self._parse_price_discount(),
            photos=photos_value,
            goods_code=goods_code,
            reviews_count=self._parse_reviews_count(),
            screen_size=characteristics.get(CHAR_SCREEN_SIZE) if characteristics else None,
            screen_resolution=characteristics.get(CHAR_SCREEN_RESOLUTION) if characteristics else None,
            characteristics=characteristics_value,
        )

    def _first_optional(self, selector: str, parent: Optional[Locator] = None) -> Optional[Locator]:
        """Return first matching locator or None if it does not exist."""
        root = parent if parent is not None else self.page
        locator = root.locator(selector)
        return locator.first if locator.count() > 0 else None

    @staticmethod
    def _locator_text(locator: Optional[Locator], default: str = "") -> str:
        """Return normalized visible text from locator."""
        if locator is None:
            return default
        try:
            return clean_text(locator.inner_text(), default=default)
        except PlaywrightError:
            return default

    @staticmethod
    def _locator_text_content(locator: Optional[Locator], default: str = "") -> str:
        """Return normalized textContent from locator."""
        if locator is None:
            return default
        try:
            return clean_text(locator.text_content(), default=default)
        except PlaywrightError:
            return default

    def _get_text_by_selectors(
        self,
        selectors: list[str],
        default: Optional[str] = DEFAULT_TEXT,
        parent: Optional[Locator] = None,
    ) -> Optional[str]:
        """Return first non-empty text found by selectors."""
        for selector in selectors:
            locator = self._first_optional(selector, parent=parent)
            text = self._locator_text(locator, default="")
            if text:
                return text
        return default

    def _get_decimal_by_selectors(
        self,
        selectors: list[str],
        parent: Optional[Locator] = None,
    ) -> Optional[Decimal]:
        """Return first non-zero decimal parsed from selectors."""
        raw_value = self._get_text_by_selectors(selectors, default="", parent=parent)
        return to_decimal(raw_value, default=DEFAULT_PRICE)

    def _expand_characteristics_if_needed(self) -> None:
        """Expand characteristics section if expand button is present."""
        button = self._first_optional(self.CHARACTERISTICS_BUTTON)
        if button is None:
            return

        try:
            button.wait_for(state="visible", timeout=5_000)
        except PlaywrightTimeoutError:
            logger.warning("Characteristics expand button not visible.")
            return

        button_text = self._locator_text(button, default="")
        if "Всі характеристики" not in button_text:
            return

        logger.info("Expanding characteristics section.")
        button.scroll_into_view_if_needed()
        try:
            button.click(force=True)
        except PlaywrightError:
            logger.warning("Failed to click characteristics expand button.")
            return

        try:
            button.wait_for(state="attached", timeout=2_000)
            self.page.wait_for_timeout(300)
            class_attr = button.get_attribute("class") or ""
            if "open" not in class_attr:
                logger.warning("Characteristics section did not expand before timeout.")
        except PlaywrightError:
            logger.warning("Characteristics section did not expand before timeout.")

    def _parse_name(self) -> Optional[str]:
        """Parse product full name."""
        locators = self.page.locator(self.PRODUCT_NAME)
        count = locators.count()

        for index in range(count):
            text = self._locator_text(locators.nth(index), default="")
            if text:
                return text

        return DEFAULT_TEXT

    def _parse_price(self) -> Optional[Decimal]:
        """Parse regular price from main right block."""
        container = self._first_optional(self.MAIN_RIGHT_BLOCK)
        if container is None:
            logger.warning("Regular price container not found.")
            return DEFAULT_PRICE

        price = self._get_decimal_by_selectors(self.PRICE_SELECTORS, parent=container)
        if price is None:
            logger.warning("Regular price not found. Using default price.")
        return price

    def _parse_price_discount(self) -> Optional[Decimal]:
        """Parse old price shown before discount. Return 0.00 if absent."""
        container = self._first_optional(self.MAIN_RIGHT_BLOCK)
        if container is None:
            return DEFAULT_PRICE

        return self._get_decimal_by_selectors(self.DISCOUNT_PRICE_SELECTORS, parent=container)

    def _parse_goods_code(self) -> Optional[str]:
        """Parse product code from dedicated product code block."""
        try:
            product_code_block = self.page.locator(self.PRODUCT_CODE_BLOCK).first
            product_code_block.wait_for(state="attached", timeout=10_000)
            value_locator = product_code_block.locator(self.PRODUCT_CODE_VALUE).first
            goods_code = self._locator_text_content(value_locator, default="")
            if goods_code:
                return goods_code
        except (PlaywrightTimeoutError, PlaywrightError):
            pass

        logger.warning("Product code not found.")
        return None

    def _parse_reviews_count(self) -> Optional[int]:
        """Parse reviews count from reviews link span."""
        links = self.page.locator(self.REVIEWS_LINK)
        count = links.count()

        for index in range(count):
            try:
                raw_value = clean_text(
                    links.nth(index).locator("span").first.inner_text(),
                    default="",
                )
                if raw_value:
                    return int(raw_value)
            except (PlaywrightTimeoutError, PlaywrightError, ValueError):
                continue

        return None

    def _parse_photos(self, goods_code: Optional[str]) -> list[str]:
        """Parse unique product photo URLs from gallery DOM elements."""
        photos: list[str] = []

        for selector in self.PHOTO_SELECTORS:
            images = self.page.locator(selector)
            count = images.count()

            for index in range(count):
                try:
                    src = (images.nth(index).get_attribute("src") or "").strip()
                except PlaywrightError:
                    src = ""

                if not src:
                    continue
                if goods_code and goods_code not in src:
                    continue

                photos.append(src)

        return deduplicate_preserve_order(photos)

    def _parse_characteristics(self) -> dict[str, str]:
        """Parse all product characteristics as flat key-value dictionary."""
        characteristics: dict[str, str] = {}

        root = self._first_optional(self.CHARACTERISTICS_ROOT)
        if root is None:
            logger.warning("Characteristics root block '#br-pr-7' not found.")
            return characteristics

        items = root.locator(self.CHARACTERISTICS_ITEMS)
        item_count = items.count()
        if item_count == 0:
            logger.warning("No characteristic groups found inside '#br-pr-7'.")
            return characteristics

        for item_index in range(item_count):
            item = items.nth(item_index)
            rows = item.locator("xpath=./div/div")
            row_count = rows.count()

            for row_index in range(row_count):
                parsed_row = self._parse_characteristic_row(rows.nth(row_index))
                if parsed_row:
                    key, value = parsed_row
                    characteristics[key] = value

        return characteristics

    @staticmethod
    def _parse_characteristic_row(row: Locator) -> Optional[tuple[str, str]]:
        """Parse one characteristic row into a (key, value) tuple."""
        spans = row.locator("xpath=./span")
        if spans.count() < 2:
            return None

        key = clean_text(spans.nth(0).inner_text(), default="")
        value = clean_text(spans.nth(1).inner_text(), default="")
        if not key:
            return None

        return key, value


class ProductRepository:
    """Persistence layer for Product model."""

    @staticmethod
    def save(product_data: ProductData) -> Product:
        """Save product using update_or_create."""
        if not product_data.goods_code:
            raise ValueError("Cannot save product without goods_code.")

        product, created = Product.objects.update_or_create(
            goods_code=product_data.goods_code,
            defaults={
                "name": product_data.name,
                "color": product_data.color,
                "memory": product_data.memory,
                "manufacturer": product_data.manufacturer,
                "price": product_data.price,
                "price_discount": product_data.price_discount,
                "photos": product_data.photos,
                "reviews_count": product_data.reviews_count,
                "screen_size": product_data.screen_size,
                "screen_resolution": product_data.screen_resolution,
                "characteristics": product_data.characteristics,
            },
        )

        logger.info(
            "%s product with goods_code=%s",
            "Created" if created else "Updated",
            product.goods_code,
        )
        return product


class ProductParseService:
    """Orchestrate search, parse, and save flow."""

    def __init__(self) -> None:
        self.playwright, self.browser, self.context, self.page = create_browser()
        self.navigator = BrainSearchNavigator(self.page)
        self.parser = BrainProductParser(self.page)
        self.repository = ProductRepository()

    def execute(self, home_url: str, query: str) -> ProductData:
        """Run full workflow."""
        try:
            self.navigator.open_first_product_from_search(home_url, query)
            product_data = self.parser.parse()
        finally:
            logger.info("Closing browser.")
            self.context.close()
            self.browser.close()
            self.playwright.stop()

        if product_data is None:
            raise ValueError("Failed to parse product data.")

        self.repository.save(product_data)
        return product_data


def main() -> None:
    """Application entry point."""
    service = ProductParseService()

    try:
        product_data = service.execute(HOME_URL, SEARCH_QUERY)
    except PlaywrightTimeoutError as exc:
        logger.exception("Timeout while interacting with the website: %s", exc)
        raise
    except PlaywrightError as exc:
        logger.exception("Playwright error during parsing workflow: %s", exc)
        raise
    except ValueError as exc:
        logger.exception("Value error during parsing workflow: %s", exc)
        raise

    print(json.dumps(product_data.to_dict(), ensure_ascii=False, indent=4, default=str))


if __name__ == "__main__":
    main()
