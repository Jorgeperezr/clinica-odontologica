from rest_framework import serializers

from apps.specialties.models import Specialty


class SpecialtySerializer(serializers.ModelSerializer):
    class Meta:
        model = Specialty
        fields = ["id", "name", "description", "is_active"]
        read_only_fields = ["id"]

    def validate_name(self, value):
        tenant = self.context["request"].tenant
        qs = Specialty.objects.filter(tenant=tenant, name__iexact=value)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError("Ya existe una especialidad con este nombre.")
        return value
