# SmartShop Live Prototype

Responsive Flask + SQLite shopping and billing prototype.

## Included
- Customer registration/login before ordering
- Real product photos using Unsplash image URLs
- Product search, categories, cart and stock control
- Checkout with UPI, Card and Cash on Delivery demo methods
- PDF receipt/invoice + browser print
- My Orders page
- Admin dashboard with product add/edit/delete
- Customer shopping counters: registered customers, customers who shopped, today's shoppers
- Sales, low-stock alerts and recent orders

## Run in VS Code / PowerShell

1. Open this folder in VS Code.
2. Install packages:

```powershell
& "C:\Users\Raja singh\AppData\Local\Python\pythoncore-3.14-64\python.exe" -m pip install -r requirements.txt
```

3. Start the app:

```powershell
& "C:\Users\Raja singh\AppData\Local\Python\pythoncore-3.14-64\python.exe" app.py
```

4. Open http://127.0.0.1:5000

## Demo admin
- Username: `admin`
- Password: `admin123`

The database `shop.db` is created automatically on first run. UPI/Card are simulated demo payments; connect a payment gateway such as Razorpay/Stripe for real transactions.
