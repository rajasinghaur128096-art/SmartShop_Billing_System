# SmartShop Billing System

A Flask-based web application for managing an online shop with billing and order management capabilities.

## Features

- User authentication (Login/Register)
- Product management (Admin panel)
- Shopping cart functionality
- Order processing and checkout
- Bill generation
- Order history tracking
- SQLite database for data persistence

## Tech Stack

- **Backend**: Flask (Python)
- **Database**: SQLite
- **Frontend**: HTML, CSS, JavaScript
- **Server**: Flask development/production server

## Prerequisites

- Python 3.7+
- pip (Python package manager)

## Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/SmartShop-Billing-System.git
cd SmartShop-Billing-System
```

2. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r smartshop_build/requirements.txt
```

## Running the Application

```bash
cd smartshop_build
python app.py
```

The application will be available at `http://localhost:5000`

### Default Credentials

- Admin username: `admin`
- Admin password: `admin123`

## Project Structure

```
smartshop_build/
├── app.py              # Main Flask application
├── requirements.txt    # Python dependencies
├── shop.db            # SQLite database
├── templates/         # HTML templates
│   ├── base.html
│   ├── home.html
│   ├── login.html
│   ├── register.html
│   ├── admin.html
│   ├── cart.html
│   ├── checkout.html
│   ├── orders.html
│   ├── bill.html
│   └── error pages
└── static/            # Static files
    ├── css/
    │   └── style.css
    └── js/
        └── cart.js
```

## Usage

### Customer Features
- Register/Login to your account
- Browse products
- Add items to cart
- Checkout and place orders
- View order history

### Admin Features
- Add/Edit/Delete products
- Manage inventory
- View all orders
- Generate bills

## Database

The application uses SQLite with the following main tables:
- `users` - User accounts and authentication
- `products` - Product catalog
- `orders` - Customer orders
- `order_items` - Items in each order
- `cart` - Shopping cart data

## Security

- Passwords are hashed before storage
- Session-based authentication
- CSRF protection on forms

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Support

For issues and questions, please create an issue in the GitHub repository.
