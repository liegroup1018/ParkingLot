# Landing and Lot Status Template Dependencies

Based on the investigation of the codebase, the two templates (`templates/landing.html` and `templates/lot_status.html` located in the root `templates` directory) are somewhat independent in how they are rendered, but they interact directly with specific modules within your `apps` folder.

## 1. Routing and Rendering 
Both files are rendered directly from `config/urls.py` using Django's generic `TemplateView`. They do not have dedicated Python view functions written for them in the `apps` folder.

```python
# config/urls.py
path("",           TemplateView.as_view(template_name="landing.html"),    name="home"),
path("lot-status/", TemplateView.as_view(template_name="lot_status.html"), name="lot-status"),
```

## 2. `landing.html` Connections
This page acts as a gateway and statically links to two specific apps within the `apps` folder:
- The Attendant Portal (`/attendant/login/`), which maps to **`apps/attendant_ui`**
- The Admin Dashboard (`/admin-dashboard/login/`), which maps to **`apps/admin_ui`**

## 3. `lot_status.html` Connections
This file is **highly dependent** on the **`apps/inventory`** folder. The frontend uses JavaScript to periodically fetch real-time parking spot data from the `/api/v1/lot/occupancy/public/` endpoint. 
- This endpoint is powered by the `PublicLotOccupancyView` located inside **`apps/inventory/views.py`**. 

## Summary
The HTML files themselves are stand-alone templates, but they heavily depend on `apps/inventory` for live data and serve as the entry points for the `apps/attendant_ui` and `apps/admin_ui` subsystems.
