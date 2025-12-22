from rest_framework import generics
from rest_framework.exceptions import ValidationError

from accounts.permissions import ApiKeyPermission
from .models import School, Instructor
from .serializers import SchoolListSerializer, SchoolDetailSerializer, InstructorSerializer, InstructorDetailSerializer


class SchoolListView(generics.ListAPIView):
    serializer_class = SchoolListSerializer
    permission_classes = [ApiKeyPermission]

    def get_queryset(self):
        city_id = self.request.query_params.get("city_id")
        if not city_id:
            raise ValidationError({"city_id": "city_id is required"})
        qs = School.objects.filter(is_active=True, city_id=city_id).prefetch_related("tariffs", "tariffs__tariff_plan")
        return qs


class SchoolDetailView(generics.RetrieveAPIView):
    serializer_class = SchoolDetailSerializer
    permission_classes = [ApiKeyPermission]
    queryset = School.objects.filter(is_active=True).prefetch_related("tariffs", "tariffs__tariff_plan", "tariffs__category", "tariffs__training_format")
    
    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['category_id'] = self.request.query_params.get('category_id')
        context['training_format_id'] = self.request.query_params.get('training_format_id')
        return context


class InstructorListView(generics.ListAPIView):
    serializer_class = InstructorSerializer
    permission_classes = [ApiKeyPermission]

    def get_queryset(self):
        params = self.request.query_params
        city_id = params.get("city_id")
        category_id = params.get("category_id")
        if not city_id or not category_id:
            raise ValidationError({"city_id": "city_id is required", "category_id": "category_id is required"})
        qs = Instructor.objects.filter(is_active=True, city_id=city_id, categories__id=category_id).distinct().prefetch_related("categories", "tariffs")
        gearbox = params.get("gearbox")
        if gearbox:
            qs = qs.filter(gearbox=gearbox)
        gender = params.get("gender")
        if gender:
            qs = qs.filter(gender=gender)
        return qs


class InstructorDetailView(generics.RetrieveAPIView):
    serializer_class = InstructorDetailSerializer
    permission_classes = [ApiKeyPermission]
    queryset = Instructor.objects.filter(is_active=True).prefetch_related("categories", "tariffs")

