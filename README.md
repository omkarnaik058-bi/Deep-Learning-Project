# Smart Dairy Farming + E-Commerce System

A Flask + SQLite application implementing all 12 requested modules:
- **Customer (5):** Authentication, Shopping, Delivery Details, Payment, Order Status
- **Admin (7):** Product Management, Order Management, Reports/PDF, Database, Animal Management, Pregnancy Tracking, Delivery Tracking

## Quick start

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install flask
python app.py
```

Open: http://localhost:5000

## Default admin login
- Username: `admin`
- Password: `admin123`

## Database
On first run the app initializes `dairy_farm.db` with 6 tables:
1. `users`
2. `products`
3. `orders`
4. `animals`
5. `pregnancies`
6. `deliveries`

## Demo customer flow
1. Register user: `ramu / 123 / 9876543210`
2. Login as customer
3. Add products to cart
4. Enter delivery details
5. Confirm payment
6. Track order status

## Notes
- Payment is simulated with a **Confirm Payment** action.
- Stock is auto-decreased after successful payment.
- Admin can mark orders delivered, and SMS status auto-switches to sent.
