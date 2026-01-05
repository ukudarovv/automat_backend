from django.db.models import Q
from rest_framework import serializers

from .models import School, SchoolTariff, Instructor, InstructorTariff


class SchoolTariffSerializer(serializers.ModelSerializer):
    name_ru = serializers.CharField(source="tariff_plan.name_ru", read_only=True)
    name_kz = serializers.CharField(source="tariff_plan.name_kz", read_only=True)
    tariff_plan = serializers.SerializerMethodField()
    school_id = serializers.IntegerField(source="school.id", read_only=True)
    category_ids = serializers.SerializerMethodField()
    training_time_ids = serializers.SerializerMethodField()

    class Meta:
        model = SchoolTariff
        fields = (
            "tariff_plan_id",
            "tariff_plan",
            "school_id",
            "name_ru",
            "name_kz",
            "price_kzt",
            "currency",
            "description_ru",
            "description_kz",
            "category_ids",
            "training_format_id",
            "training_time_ids",
        )
    
    def get_tariff_plan(self, obj):
        """Возвращает объект tariff_plan с code"""
        if obj.tariff_plan:
            return {
                "id": obj.tariff_plan.id,
                "code": obj.tariff_plan.code,
                "name_ru": obj.tariff_plan.name_ru,
                "name_kz": obj.tariff_plan.name_kz,
            }
        return None
    
    def get_category_ids(self, obj):
        """Возвращает список ID категорий для тарифа"""
        return list(obj.categories.values_list('id', flat=True))
    
    def get_training_time_ids(self, obj):
        """Возвращает список ID времен обучения для тарифа"""
        return list(obj.training_times.values_list('id', flat=True))
    
    def to_representation(self, instance):
        data = super().to_representation(instance)
        # Удаляем null/None значения
        return {k: v for k, v in data.items() if v is not None}


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
        result = {}
        if obj.nearest_intake_date:
            result["date"] = obj.nearest_intake_date.isoformat()
        if obj.nearest_intake_text_ru:
            result["text_ru"] = obj.nearest_intake_text_ru
        if obj.nearest_intake_text_kz:
            result["text_kz"] = obj.nearest_intake_text_kz
        return result if result else None

    def get_description(self, obj):
        return {"ru": obj.description_ru or "", "kz": obj.description_kz or ""}
    
    def to_representation(self, instance):
        data = super().to_representation(instance)
        # Удаляем null/None значения
        return {k: v for k, v in data.items() if v is not None}


class SchoolDetailSerializer(SchoolListSerializer):
    tariffs = serializers.SerializerMethodField()
    contact_phone = serializers.CharField()
    whatsapp_phone = serializers.CharField()

    class Meta(SchoolListSerializer.Meta):
        fields = SchoolListSerializer.Meta.fields + ("contact_phone", "whatsapp_phone", "tariffs")
    
    def get_tariffs(self, obj):
        tariffs = obj.tariffs.filter(is_active=True).prefetch_related('categories', 'training_times')
        category_id = self.context.get('category_id')
        training_format_id = self.context.get('training_format_id')
        training_time_id = self.context.get('training_time_id')
        
        # Фильтрация: тариф показывается, если он не привязан к категориям (пусто) или содержит выбранную категорию
        if category_id:
            try:
                category_id = int(category_id)
                tariffs = tariffs.filter(Q(categories__id=category_id) | Q(categories__isnull=True)).distinct()
            except (ValueError, TypeError):
                pass
        
        # Фильтрация: тариф показывается, если он не привязан к формату (null) или совпадает с выбранным
        if training_format_id:
            try:
                training_format_id = int(training_format_id)
                tariffs = tariffs.filter(Q(training_format_id=training_format_id) | Q(training_format_id__isnull=True))
            except (ValueError, TypeError):
                pass
        
        # Фильтрация: тариф показывается, если у него есть выбранное время обучения
        if training_time_id:
            try:
                training_time_id = int(training_time_id)
                tariffs = tariffs.filter(training_times__id=training_time_id).distinct()
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
    
    def to_representation(self, instance):
        data = super().to_representation(instance)
        # Удаляем null/None значения
        return {k: v for k, v in data.items() if v is not None}


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
        result = []
        for cat in obj.categories.all():
            cat_data = {"id": cat.id, "name_ru": cat.name_ru, "name_kz": cat.name_kz}
            # Удаляем null/None значения
            cat_data = {k: v for k, v in cat_data.items() if v is not None}
            result.append(cat_data)
        return result


class InstructorDetailSerializer(InstructorSerializer):
    tariffs = InstructorTariffSerializer(many=True, read_only=True)
    whatsapp_phone = serializers.CharField()

    class Meta(InstructorSerializer.Meta):
        fields = InstructorSerializer.Meta.fields + ("whatsapp_phone", "tariffs")

