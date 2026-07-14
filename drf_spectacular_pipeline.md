# DRF-Spectacular Documentation Pipeline

This guide outlines the complete pipeline for generating OpenAPI (Swagger) documentation in the ParkingLot project using `drf-spectacular`. It explains how the different layers of your application work together to automatically generate a rich API schema.

## 1. Global Configuration (`settings.py` & `urls.py`)
`drf-spectacular` is configured globally in `settings.py` as the default schema class for Django REST Framework. 

```python
REST_FRAMEWORK = {
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
}
```
In `urls.py`, specific endpoints are exposed to serve the raw YAML/JSON schema and the visual UI:
- `/api/schema/`: Serves the raw OpenAPI 3.0 schema.
- `/api/schema/swagger-ui/`: Serves the interactive Swagger UI.
- `/api/schema/redoc/`: Serves the ReDoc UI.

## 2. Model Layer (`models.py`)
The foundation of the documentation pipeline starts at the database level. `drf-spectacular` inspects your Django models.

**How to use it:** Add `help_text` to your model fields.
```python
class ParkingSpot(models.Model):
    status = models.CharField(
        max_length=20,
        choices=SpotStatus.choices,
        default=SpotStatus.ACTIVE,
        help_text="Operational state. Only ACTIVE spots count towards lot capacity."
    )
```
**Impact:** When this model is serialized, `drf-spectacular` automatically reads the `help_text` and injects it into the Swagger UI as the field description.

## 3. Serializer Layer (`serializers.py`)
Serializers define the structure of your payloads. `drf-spectacular` uses them to define the request bodies and response schemas.

**How to use it:**
1. **Class Docstrings:** Add a docstring to the Serializer class to describe the component itself.
2. **Type Hints (`@extend_schema_field`):** When you use a `SerializerMethodField` or a custom property, `drf-spectacular` doesn't know what type of data it returns (string, int, dict, etc.). You must explicitly tell it using a decorator.

```python
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

class LotOccupancySerializer(serializers.ModelSerializer):
    available = serializers.SerializerMethodField()

    @extend_schema_field(serializers.IntegerField())
    def get_available(self, obj):
        return max(0, obj.total_capacity - obj.current_count)
```

## 4. View Layer (`views.py`)
The view layer is where you document the specific endpoints (e.g., GET `/gates/entry/`, POST `/payments/`).

**How to use it:** Use the `@extend_schema` decorator on your view methods to provide endpoint-specific metadata.

```python
from drf_spectacular.utils import extend_schema, OpenApiResponse

class GateEntryView(APIView):
    @extend_schema(
        summary="Process Vehicle Entry",
        description="Records a vehicle entry, assigns a spot, and issues a ticket.",
        request=GateEntrySerializer,
        responses={
            201: OpenApiResponse(response=TicketReadSerializer, description="Ticket created successfully"),
            400: OpenApiResponse(description="Validation Error (e.g., Lot Full)"),
            409: OpenApiResponse(description="Concurrent OCC Conflict (Retry)")
        }
    )
    def post(self, request, *args, **kwargs):
        # Implementation...
```

## The Pipeline Flow
1. A developer adds a new endpoint in `views.py` and decorates it with `@extend_schema`.
2. The decorator references a serializer in `serializers.py`.
3. `drf-spectacular` inspects the serializer for fields and `@extend_schema_field` decorators.
4. If it's a `ModelSerializer`, it inspects the underlying `models.py` and grabs the `help_text` for descriptions.
5. You visit `/api/schema/swagger-ui/`, and `drf-spectacular` renders all this extracted metadata into an interactive web page.
