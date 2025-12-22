from django.db.models import Q
from rest_framework import serializers

from .models import School, SchoolTariff, Instructor, InstructorTariff


class SchoolTariffSerializer(serializers.ModelSerializer):
    code = serializers.CharField(source="tariff_plan.code", read_only=True)
    name_ru = serializers.CharField(source="tariff_plan.name_ru", read_only=True)
    name_kz = serializers.CharField(source="tariff_plan.name_kz", read_only=True)

    class Meta:
        model = SchoolTariff
        fields = (
            "tariff_plan_id",
            "code",
            "name_ru",
            "name_kz",
            "price_kzt",
            "currency",
            "description_ru",
            "description_kz",
            "category_id",
            "training_format_id",
        )


class SchoolListSerializer(serializers.ModelSerializer):
    name = serializers.SerializerMethodField()
    nearest_intake = serializers.SerializerMethodField()
    address = serializers.SerializerMethodField()
    description = serializers.SerializerMethodField()

    class Meta:
        model = School
        fields = (
            "id",
            "name",
            "city_id",
            "rating",
            "trust_index",
            "nearest_intake",
            "address",
            "description",
        )

    def get_name(self, obj):
        return {"ru": obj.name_ru, "kz": obj.name_kz}

    def get_address(self, obj):
        return {"ru": obj.address_ru, "kz": obj.address_kz}

    def get_nearest_intake(self, obj):
        return {
            "date": obj.nearest_intake_date.isoformat() if obj.nearest_intake_date else None,
            "text_ru": obj.nearest_intake_text_ru,
            "text_kz": obj.nearest_intake_text_kz,
        }

    def get_description(self, obj):
        return {"ru": obj.description_ru or "", "kz": obj.description_kz or ""}


class SchoolDetailSerializer(SchoolListSerializer):
    tariffs = serializers.SerializerMethodField()
    contact_phone = serializers.CharField()
    whatsapp_phone = serializers.CharField()

    class Meta(SchoolListSerializer.Meta):
        fields = SchoolListSerializer.Meta.fields + ("contact_phone", "whatsapp_phone", "tariffs")
    
    def get_tariffs(self, obj):
        tariffs = obj.tariffs.filter(is_active=True)
        category_id = self.context.get('category_id')
        training_format_id = self.context.get('training_format_id')
        
        # Фильтрация: тариф показывается, если он не привязан к категории (null) или совпадает с выбранной
        if category_id:
            try:
                category_id = int(category_id)
                tariffs = tariffs.filter(Q(category_id=category_id) | Q(category_id__isnull=True))
            except (ValueError, TypeError):
                pass
        
        # Фильтрация: тариф показывается, если он не привязан к формату (null) или совпадает с выбранным
        if training_format_id:
            try:
                training_format_id = int(training_format_id)
                tariffs = tariffs.filter(Q(training_format_id=training_format_id) | Q(training_format_id__isnull=True))
            except (ValueError, TypeError):
                pass
        
        return SchoolTariffSerializer(tariffs, many=True).data


class InstructorTariffSerializer(serializers.ModelSerializer):
    class Meta:
        model = InstructorTariff
        fields = (
            "id",
            "tariff_type",
            "price_kzt",
            "name_ru",
            "name_kz",
            "sort_order",
        )


class InstructorSerializer(serializers.ModelSerializer):
    bio = serializers.SerializerMethodField()
    categories = serializers.SerializerMethodField()

    class Meta:
        model = Instructor
        fields = (
            "id",
            "display_name",
            "gender",
            "gearbox",
            "rating",
            "bio",
            "city_id",
            "categories",
        )

    def get_bio(self, obj):
        return {"ru": obj.bio_ru, "kz": obj.bio_kz}
    
    def get_categories(self, obj):
        return [{"id": cat.id, "code": cat.code, "name_ru": cat.name_ru, "name_kz": cat.name_kz} for cat in obj.categories.all()]


class InstructorDetailSerializer(InstructorSerializer):
    tariffs = InstructorTariffSerializer(many=True, read_only=True)
    whatsapp_phone = serializers.CharField()

    class Meta(InstructorSerializer.Meta):
        fields = InstructorSerializer.Meta.fields + ("whatsapp_phone", "tariffs")

