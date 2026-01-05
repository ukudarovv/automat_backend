from django.db import models

from dictionaries.models import City, Category, TrainingFormat, TariffPlan, TrainingTimeSlot


class School(models.Model):
    city = models.ForeignKey(City, on_delete=models.PROTECT)
    name_ru = models.CharField(max_length=255)
    name_kz = models.CharField(max_length=255)
    rating = models.DecimalField(max_digits=3, decimal_places=1, default=0)
    trust_index = models.IntegerField(default=0)
    trust_index_text_ru = models.CharField(max_length=255, null=True, blank=True)  # "высокий"
    trust_index_text_kz = models.CharField(max_length=255, null=True, blank=True)
    description_ru = models.TextField(null=True, blank=True)
    description_kz = models.TextField(null=True, blank=True)
    address_ru = models.CharField(max_length=255)
    address_kz = models.CharField(max_length=255)
    nearest_intake_date = models.DateField(null=True, blank=True)
    nearest_intake_text_ru = models.CharField(max_length=255, null=True, blank=True)
    nearest_intake_text_kz = models.CharField(max_length=255, null=True, blank=True)
    contact_phone = models.CharField(max_length=32, null=True, blank=True)
    whatsapp_phone = models.CharField(max_length=32, null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "school"
        indexes = [
            models.Index(fields=["city", "is_active"]),
            models.Index(fields=["rating"]),
        ]
        ordering = ["id"]
        constraints = [
            models.UniqueConstraint(fields=["name_ru"], name="unique_school_name_ru")
        ]

    def __str__(self):
        return self.name_ru


class SchoolTariff(models.Model):
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name="tariffs")
    tariff_plan = models.ForeignKey(TariffPlan, on_delete=models.PROTECT)
    categories = models.ManyToManyField(Category, related_name="tariffs", blank=True)
    training_format = models.ForeignKey(TrainingFormat, on_delete=models.SET_NULL, null=True, blank=True)
    training_times = models.ManyToManyField(TrainingTimeSlot, related_name="tariffs", blank=True)
    price_kzt = models.IntegerField()
    currency = models.CharField(max_length=3, default="KZT")
    description_ru = models.TextField(null=True, blank=True)
    description_kz = models.TextField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "school_tariff"
        unique_together = ("school", "tariff_plan", "training_format")
        indexes = [
            models.Index(fields=["school", "is_active"]),
            models.Index(fields=["training_format", "is_active"]),
        ]

    def __str__(self):
        return f"{self.school} - {self.tariff_plan.code}"


class Instructor(models.Model):
    GEARBOX_CHOICES = (
        ("AT", "Automatic"),
        ("MT", "Manual"),
    )
    GENDER_CHOICES = (
        ("M", "Male"),
        ("F", "Female"),
    )

    city = models.ForeignKey(City, on_delete=models.PROTECT)
    display_name = models.CharField(max_length=255)
    gender = models.CharField(max_length=1, choices=GENDER_CHOICES)
    gearbox = models.CharField(max_length=10, choices=GEARBOX_CHOICES)
    categories = models.ManyToManyField(Category, related_name="instructors")
    rating = models.DecimalField(max_digits=3, decimal_places=1, default=0)
    bio_ru = models.TextField(null=True, blank=True)
    bio_kz = models.TextField(null=True, blank=True)
    whatsapp_phone = models.CharField(max_length=32, null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "instructor"
        indexes = [
            models.Index(fields=["city", "gearbox", "gender", "is_active"]),
            models.Index(fields=["rating"]),
        ]
        ordering = ["id"]

    def __str__(self):
        return self.display_name


class InstructorTariff(models.Model):
    class TariffType(models.TextChoices):
        SINGLE_HOUR = "SINGLE_HOUR", "1 час"
        AUTODROM = "AUTODROM", "Автодром"
        PACKAGE_5 = "PACKAGE_5", "5 вождений"
        PACKAGE_10 = "PACKAGE_10", "10 вождений"
        PACKAGE_15 = "PACKAGE_15", "15 вождений"
    
    instructor = models.ForeignKey(Instructor, on_delete=models.CASCADE, related_name="tariffs")
    tariff_type = models.CharField(max_length=20, choices=TariffType.choices)
    price_kzt = models.IntegerField()
    name_ru = models.CharField(max_length=255, null=True, blank=True)
    name_kz = models.CharField(max_length=255, null=True, blank=True)
    is_active = models.BooleanField(default=True)
    sort_order = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "instructor_tariff"
        indexes = [
            models.Index(fields=["instructor", "is_active", "sort_order"]),
        ]
        ordering = ["sort_order", "id"]

    def __str__(self):
        return f"{self.instructor.display_name} - {self.get_tariff_type_display()}"

