from django.db import models


class Product(models.Model):
    name = models.CharField(max_length=255)
    color = models.CharField(max_length=50, default="None")
    memory = models.CharField(max_length=50, default="None")
    manufacturer = models.CharField(max_length=100, default="None")
    price = models.DecimalField(decimal_places=2, max_digits=10, default=0.00)
    price_discount = models.DecimalField(decimal_places=2, max_digits=10, default=0.00)
    photos = models.JSONField(default=list)  # List of photo URLs
    goods_code = models.CharField(max_length=20, unique=True)
    reviews_count = models.IntegerField(default=0)
    screen_size = models.CharField(max_length=50, default="None")
    screen_resolution = models.CharField(max_length=50, default="None")
    characteristics = models.JSONField(default=dict)  # Dictionary of characteristics

    def __str__(self):
        return f"Name: {self.name}"

    class Meta:
        verbose_name = "Product"
        verbose_name_plural = "Products"
