from django.db import models


class Product(models.Model):
    name = models.CharField(max_length=255, null=True, blank=True, default=None)
    color = models.CharField(max_length=50, null=True, blank=True, default=None)
    memory = models.CharField(max_length=50, null=True, blank=True, default=None)
    manufacturer = models.CharField(max_length=100, null=True, blank=True, default=None)
    price = models.DecimalField(
        decimal_places=2, max_digits=10, null=True, blank=True, default=None
    )
    price_discount = models.DecimalField(
        decimal_places=2, max_digits=10, null=True, blank=True, default=None
    )
    photos = models.JSONField(null=True, blank=True, default=None)  # List of photo URLs
    goods_code = models.CharField(max_length=20)
    reviews_count = models.IntegerField(null=True, blank=True, default=None)
    screen_size = models.CharField(max_length=50, null=True, blank=True, default=None)
    screen_resolution = models.CharField(
        max_length=50, null=True, blank=True, default=None
    )
    characteristics = models.JSONField(
        null=True, blank=True, default=None
    )  # Dictionary of characteristics

    def __str__(self):
        return f"Name: {self.name}"

    class Meta:
        verbose_name = "Product"
        verbose_name_plural = "Products"
