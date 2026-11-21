# Repanier

Open-source web application (**Django** / **django CMS**) designed for local purchasing groups, food co-ops, and short supply chains.

Repanier was created to relieve volunteer groups from repetitive administrative tasks so they can focus on what truly matters: **people**. At its heart, a local food group is about building human connections around a shared everyday need—good, local food.

## Key Features

- **Order & Pickup Cycles ("Permanences"):** Create recurring or one-off ordering windows with clear deadlines, automatic order closing, and pickup scheduling.
- **Producer & Product Catalogs:** Manage local producers, seasonal products, stock/availability, units, pricing, and delivery or pickup rules.
- **Member Shopping & Carts:** Simple member experience to browse catalogs, place or adjust orders before closing, and track pickup details.
- **Accounting & Balances:** Track member balances, invoices/statements, producer payouts, and optional accounting workflows.
- **Automated Notifications:** Email reminders, order updates, and delivery/pickup communication to keep coordinators and members aligned.
- **Multilingual Support:** Built with internationalization support for community and regional groups.

## Why Repanier?

Volunteer coordinators often spend too much energy wrestling with spreadsheets, payment tracking, and order lists—leaving less time for welcoming members, talking with producers, and sharing moments at pickup sessions.

- **More time for people, less admin:** Automates order closing, summaries, and routine follow-ups so the group can focus on human connection around food.
- **Collective ordering cycles:** Open/close windows, pickup sessions ("permanences"), and instant order summaries per producer and member.
- **Built-in balances & accounting:** Track member accounts, orders, and settlements in one structured place instead of fragile spreadsheets.
- **CMS + ordering in one app:** Powered by **django CMS**, so you can publish project pages, guidelines, and updates alongside the shop.

## Tech Stack

- **Backend:** Python, Django, django CMS
- **Database:** PostgreSQL
- **Application & Web Server:** uWSGI, Nginx

## Quick Overview & Getting Started

Setting up a multi-site or production instance involves a few moving parts (database, settings, web server, and scheduled tasks), so don't worry if the initial configuration feels involved—you don't have to guess your way through it.

1. Clone the repository and create a virtual environment:
   ```bash
   git clone [https://github.com/pcolmant/repanier.git](https://github.com/pcolmant/repanier.git)
   cd repanier
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements/requirement.txt

2. Configure PostgreSQL and your instance settings (`DJANGO_SETTINGS_MODULE`, database credentials, email, and site options), then apply migrations and collect static assets:
   ```bash
   python manage.py migrate
   python manage.py collectstatic


3. Run the development server to explore the interface locally, or deploy behind uWSGI and Nginx with HTTPS for production.

## Scheduled Tasks

Recurring jobs—such as closing orders on schedule, cleaning up unconfirmed carts, and running backups—are exposed as `manage.py` commands that you can trigger manually while testing or automate via `cron` / systemd timers.

## Questions, Feedback & Contact

Curious to test Repanier for a local food group, need guidance on setup or workflows, or spotted an improvement? Feel free to open an issue or reach out—I'm happy to help in **French (FR)**, **English (EN)**, or **Dutch (NL)**.

## License

See the license files in this repository for terms of use and distribution.