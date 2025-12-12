SETUP INSTRUCTIONS:


## Setup

1. **Clone the repository**

   git clone https://github.com/FlameGreat-1/Automation.git
   cd automation



2. **Create virtual environment**

python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate



3. **Install dependencies**

pip install -r requirements.txt



4. **Configure environment variables**

cp .env.example .env

# Edit .env and fill in your database credentials

nano .env



5. **Install Google Chrome (Ubuntu/Debian)**

wget https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
sudo apt install -y ./google-chrome-stable_current_amd64.deb



6. **Setup database**

python src/database/companies_db.py
# Choose option 1 (Setup database)

python src/database/contact_forms_db.py
# Choose option 1 (Setup database)



7. **Run the scripts**

# Company URL Finder
python src/companies/Company_URL_Finder.py

# Contact Form Scraper
python src/contact/Contact_Form_Scrapper.py