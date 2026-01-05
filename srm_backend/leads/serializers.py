from django.db import transaction
from rest_framework import serializers

from botusers.models import BotUser
from catalog.models import School, Instructor
from dictionaries.models import City, Category, TrainingFormat, TariffPlan, TrainingTimeSlot
from .models import Lead, LeadStatusHistory


class BotUserSerializer(serializers.Serializer):
    """Сериализатор для данных bot_user - не ModelSerializer, т.к. используем update_or_create"""
    telegram_user_id = serializers.IntegerField(required=True)
    username = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    first_name = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    last_name = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    language = serializers.ChoiceField(choices=[("RU", "RU"), ("KZ", "KZ")], required=True)
    phone = serializers.CharField(required=False, allow_null=True, allow_blank=True)


class LeadCreateSerializer(serializers.Serializer):
    type = serializers.ChoiceField(choices=Lead.LeadType.choices)
    language = serializers.ChoiceField(choices=[("RU", "RU"), ("KZ", "KZ")], required=True)
    main_intent = serializers.ChoiceField(choices=Lead.Intent.choices, required=False, allow_null=True)
    bot_user = BotUserSerializer(required=False)
    contact = serializers.DictField(required=True)
    source = serializers.CharField(required=False, default="telegram_bot")
    utm = serializers.DictField(required=False, allow_null=True)
    payload = serializers.DictField(required=True)

    def validate_contact(self, value):
        name = value.get("name")
        phone = value.get("phone")
        if not name or len(name.strip()) < 2:
            raise serializers.ValidationError("name is required and must be >=2 chars")
        if not phone:
            raise serializers.ValidationError("phone is required")
        return value

    def validate(self, attrs):
        lead_type = attrs["type"]
        payload = attrs.get("payload", {})

        if lead_type == Lead.LeadType.SCHOOL:
            # Для онлайн-продуктов city_id необязателен
            required = ["category_id", "training_format_id", "school_id"]
            if not payload.get("tariff_plan_id"):  # Если нет tariff_plan_id, значит обычная заявка на школу
                required.append("city_id")
            missing = [f for f in required if payload.get(f) is None]
            if missing:
                raise serializers.ValidationError({"payload": f"Missing fields: {', '.join(missing)}"})
        elif lead_type == Lead.LeadType.INSTRUCTOR:
            required = ["city_id", "category_id", "gearbox", "instructor_id"]
            missing = [f for f in required if payload.get(f) is None]
            if missing:
                raise serializers.ValidationError({"payload": f"Missing fields: {', '.join(missing)}"})
        elif lead_type == Lead.LeadType.TESTS:
            required = ["iin", "whatsapp"]
            missing = [f for f in required if not payload.get(f)]
            if missing:
                raise serializers.ValidationError({"payload": f"Missing fields: {', '.join(missing)}"})
        return attrs

    def create(self, validated_data):
        payload = validated_data.get("payload", {})
        contact = validated_data.get("contact", {})
        bot_user_payload = validated_data.get("bot_user")
        utm = validated_data.get("utm", {}) or {}

        with transaction.atomic():
            bot_user_instance = None
            if bot_user_payload:
                bot_user_instance, _ = BotUser.objects.update_or_create(
                    telegram_user_id=bot_user_payload["telegram_user_id"],
                    defaults=bot_user_payload,
                )

            lead_kwargs = {
                "type": validated_data["type"],
                "language": validated_data["language"],
                "main_intent": validated_data.get("main_intent"),
                "bot_user": bot_user_instance,
                "name": contact["name"],
                "phone": contact["phone"],
                "source": validated_data.get("source", "telegram_bot"),
                "utm_source": utm.get("source"),
                "utm_campaign": utm.get("campaign"),
                "utm_medium": utm.get("medium"),
            }

            # School payload
            lead_type = validated_data["type"]
            if lead_type == Lead.LeadType.SCHOOL:
                lead_kwargs.update(
                    dict(
                        city_id=payload.get("city_id"),
                        category_id=payload.get("category_id"),
                        training_format_id=payload.get("training_format_id"),
                        training_time_id=payload.get("training_time_id"),
                        school_id=payload.get("school_id"),
                        tariff_plan_id=payload.get("tariff_plan_id"),
                        tariff_price_kzt=payload.get("tariff_price_kzt"),
                    )
                )
            elif lead_type == Lead.LeadType.INSTRUCTOR:
                lead_kwargs.update(
                    dict(
                        city_id=payload.get("city_id"),
                        category_id=payload.get("category_id"),
                        gearbox=payload.get("gearbox"),
                        preferred_instructor_gender=payload.get("preferred_instructor_gender"),
                        has_driver_license=payload.get("has_driver_license"),
                        training_time_id=payload.get("training_time_id"),
                        instructor_id=payload.get("instructor_id"),
                        instructor_tariff_id=payload.get("instructor_tariff_id"),
                        instructor_tariff_price_kzt=payload.get("instructor_tariff_price_kzt"),
                    )
                )
            elif lead_type == Lead.LeadType.TESTS:
                lead_kwargs.update(
                    dict(
                        iin=payload.get("iin"),
                        whatsapp=payload.get("whatsapp"),
                        email=payload.get("email"),
                    )
                )

            lead = Lead.objects.create(**lead_kwargs)
            LeadStatusHistory.objects.create(
                lead=lead, old_status=None, new_status=lead.status, changed_by_user=None, note="created"
            )
            return lead


class LeadShortSerializer(serializers.ModelSerializer):
    class Meta:
        model = Lead
        fields = (
            "id",
            "type",
            "status",
            "name",
            "phone",
            "city_id",
            "category_id",
            "tariff_plan_id",
            "school_id",
            "instructor_id",
            "created_at",
        )


class LeadDetailSerializer(serializers.ModelSerializer):
    status_history = serializers.SerializerMethodField()

    class Meta:
        model = Lead
        fields = "__all__"

    def get_status_history(self, obj):
        history = obj.status_history.all().order_by("-changed_at")
        return [
            {
                "old_status": h.old_status,
                "new_status": h.new_status,
                "changed_by_user": h.changed_by_user_id,
                "changed_at": h.changed_at,
                "note": h.note,
            }
            for h in history
        ]


class LeadStatusUpdateSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=Lead.LeadStatus.choices)
    manager_comment = serializers.CharField(required=False, allow_blank=True, allow_null=True)

