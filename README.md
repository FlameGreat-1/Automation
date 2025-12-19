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




 **____________________________ CLICKUP STEP BY STEP GUIDE_______________________________**

________________________________FOR NOW WE ARE USING LOCAL MySQL SO WE HAVE TO SETUP_____________________________________

 # Setup MySQL Database_____________________________________

# Install MySQL:

sudo apt update
sudo apt install mysql-server -y
sudo service mysql start
sudo mysql_secure_installation

# Create database:

sudo mysql -u root -p

CREATE DATABASE clickup_local;
CREATE USER 'clickup_user'@'localhost' IDENTIFIED WITH mysql_native_password BY 'your_password';
GRANT ALL PRIVILEGES ON clickup_local.* TO 'clickup_user'@'localhost';
FLUSH PRIVILEGES;
EXIT;

#  Setup database tables__________________________

# ClickUp database

python src/database/setup_clickup.py
# Choose option 1 (Setup Database)
# Choose option 4 (Add API Key)

# Run the scripts________________________________________

# Interactive mode
python src/clickup/Ticket_Fetcher.py

# Automated mode
python src/clickup/Ticket_Fetcher.py --auto


# CRON JOBS ______________________________________

# Make cron script executable:

chmod +x src/scripts/clickup_cron.sh

# Test the script:

src/scripts/clickup_cron.sh

# Install cron job (runs daily at 2 AM):

crontab -e

# Add this line:

0 2 * * * /mnt/c/Users/HomePc/Automation/src/scripts/clickup_cron.sh  **_______CHANGE TO YOURS DIRECTORY_____**

# Verify cron job:

crontab -l


# Monitoring _________________________________

# Today's cron log
tail -f logs/cron/clickup_cron_$(date +%Y%m%d).log

# Error log
tail -f logs/cron/clickup_errors.log

# Performance log
tail -f logs/cron/clickup_performance.log


# Cron job not running:_________________________________

# Check cron service
sudo service cron status
sudo service cron start


**VERIFY IN DATABASE:**_______________________

python src/scripts/clickup_data.py


 **EMAIL SETUP FOR CRON JOBS_________________________________________**

# Install SSMTP:

sudo apt install ssmtp -y

# Configure SSMTP:

sudo nano /etc/ssmtp/ssmtp.conf

# Add this configuration:

root=softverse.com@gmail.com
mailhub=smtp.gmail.com:587
AuthUser=softverse.com@gmail.com  **______Change email to yours______**
AuthPass=your_app_password_here
UseSTARTTLS=YES
FromLineOverride=YES


# Get Gmail App Password:

Go to: https://myaccount.google.com/apppasswords

Create app password for "Mail"
Copy the 16-character password
Use it in AuthPass above