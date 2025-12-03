# Pizza System (Django)

An example Django application for a small pizza shop. It includes basic e‑commerce flows for browsing a menu, adding items to a cart, and checking out, plus role‑oriented dashboards for kitchen staff and managers.

## Features
- Customer ordering: menu, cart, checkout, and success pages
- Manager dashboard with long‑term view
- Kitchen dashboard for active orders
- CSV import command for historical sales (`pizza_sales.csv`)
- SQLite out of the box; no external DB required

## Tech stack
- Python 3.11+ (recommended)
- Django 5.2
- SQLite (default)

## Project layout
```
Pizza_System/
├── manage.py
├── Pizza_System/            # Project settings/urls/wsgi/asgi
├── sales/                   # Sales app: models, views, urls, admin, mgmt cmd
├── kitchen/                 # Kitchen app: views, urls
├── managers/                # Managers app: views, urls
├── templates/               # HTML templates
├── static/                  # Static assets (CSS)
├── pizza_sales.csv          # Sample dataset for import command
└── requirements.txt
```

## Getting started (Windows PowerShell)
1) Create and activate a virtual environment
```
cd C:\pizza_project\Pizza_System
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

2) Install dependencies
```
pip install -r requirements.txt
```

3) Apply migrations and create a superuser
# Default credentials: username: admin, password: (Password123!!)
# Don't have to do this if you don't clear DB.
```
python manage.py makemigrations
python manage.py migrate
python manage.py createsuperuser
```

4) (Optional) Import sample sales data
# Don't have to do this step if you used existing sqllite database
```
python manage.py import_pizza_sales pizza_sales.csv
```

5) Run the development server
```
python manage.py runserver
```

## Default URLs
- Public/customer:
  - `/sales/menu` — Browse pizzas
  - `/sales/cart` — View cart
  - `/sales/checkout` — Checkout
  - `/sales/checkout/success` — Confirmation
- Role dashboards:
  - `/kitchen/` — Kitchen dashboard
  - `/managers/` — Manager dashboard
- Authentication:
  - `/accounts/login/` — Login page (Django auth)
- Admin:
  - `/admin/`

Note: Some pages may require authentication/permissions.

## Environment and settings
The project uses SQLite by default and should work without additional configuration. If you wish to customize settings (e.g., Secret Key, DEBUG, DB), edit `Pizza_System/Pizza_System/settings.py` or use environment variables consistent with your deployment setup.

## Development tips
- Static files: basic CSS is under `Pizza_System/static/css/pizza.css`.
- Templates live under `Pizza_System/templates/` with app‑specific subfolders.
- Management command: `sales.management.commands.import_pizza_sales` expects a CSV path; see `pizza_sales.csv` for the schema.

## License
No explicit license provided. Use internally or add a LICENSE file as needed.
