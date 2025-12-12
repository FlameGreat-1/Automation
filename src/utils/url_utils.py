"""
URL Utility Functions
Shared utilities for URL processing and label detection
"""

def detect_url_label(url: str) -> str:
    """Detect label from URL path based on keywords"""
    url_lower = url.lower()
    
    if any(keyword in url_lower for keyword in ['/karriere', '/career', '/careers', '/jobs', '/job', '/stellenangebote', '/employment', '/join-us', '/arbeiten-bei', '/deine-karriere', '/offene-stellen', '/vacancies', '/opportunities']):
        return "Career"
    
    if any(keyword in url_lower for keyword in ['/about', '/ueber-uns', '/uber-uns', '/company', '/unternehmen', '/who-we-are', '/our-story', '/vision', '/mission', '/unternehmensvideos']):
        return "About Us"
    
    if any(keyword in url_lower for keyword in ['/contact', '/kontakt', '/impressum', '/imprint', '/get-in-touch', '/reach-us', '/anfahrt']):
        return "Contact"
    
    if any(keyword in url_lower for keyword in ['/service', '/services', '/leistung', '/leistungen', '/dienstleistung', '/dienstleistungen', '/solutions', '/offerings', '/what-we-do', '/pflegedienst', '/pflegedienste']):
        return "Services"
    
    if any(keyword in url_lower for keyword in ['/product', '/products', '/produkt', '/produkte', '/shop', '/store', '/catalog', '/katalog', '/lathes', '/equipment']):
        return "Products"
    
    if any(keyword in url_lower for keyword in ['/pricing', '/price', '/prices', '/plan', '/plans', '/preise', '/tarif', '/tarife', '/packages', '/pakete']):
        return "Pricing"
    
    if any(keyword in url_lower for keyword in ['/news', '/blog', '/aktuell', '/press', '/media', '/artikel', '/article', '/post', '/presse']):
        return "News"
    
    if any(keyword in url_lower for keyword in ['/faq', '/help', '/support', '/hilfe', '/kundenservice', '/customer-service', '/helpdesk', '/assistance']):
        return "Support"
    
    if any(keyword in url_lower for keyword in ['/24-stunden', '/24-hour', '/24h', '/emergency', '/notfall', '/notdienst', '/on-call', '/erreichbarkeit']):
        return "Emergency Service"
    
    if any(keyword in url_lower for keyword in ['/why-', '/warum-', '/advantages', '/vorteile', '/benefits', '/value-proposition', '/why-choose']):
        return "Why Us"
    
    if any(keyword in url_lower for keyword in ['/personal/', '/hr/', '/human-resources', '/personalwesen', '/mitarbeiter-info', '/employee-info']):
        return "HR"
    
    if any(keyword in url_lower for keyword in ['/vor-ort', '/on-site', '/field-service', '/installation', '/montage', '/vor-ort-service']):
        return "Field Service"
    
    if any(keyword in url_lower for keyword in ['/testimonial', '/testimonials', '/review', '/reviews', '/reference', '/references', '/referenz', '/referenzen', '/kunden', '/success-stories', '/feedback']):
        return "Testimonials"
    
    if any(keyword in url_lower for keyword in ['/partner', '/partners', '/cooperation', '/kooperation', '/alliance', '/collaboration']):
        return "Partners"
    
    if any(keyword in url_lower for keyword in ['/event', '/events', '/veranstaltung', '/veranstaltungen', '/seminar', '/seminare', '/webinar', '/webinars', '/conference', '/messe']):
        return "Events"
    
    if any(keyword in url_lower for keyword in ['/download', '/downloads', '/resource', '/resources', '/whitepaper', '/guide', '/guides', '/documentation', '/dokument']):
        return "Resources"
    
    if any(keyword in url_lower for keyword in ['/privacy', '/datenschutz', '/terms', '/agb', '/legal', '/compliance', '/disclaimer', '/cookie', '/gdpr', '/dsgvo']):
        return "Legal"
    
    if any(keyword in url_lower for keyword in ['/location', '/locations', '/standort', '/standorte', '/branch', '/branches', '/office', '/offices', '/niederlassung', '/niederlassungen', '/find-us']):
        return "Locations"
    
    if any(keyword in url_lower for keyword in ['/industry', '/industries', '/industrie', '/industrien', '/sector', '/sectors', '/branche', '/branchen', '/vertical']):
        return "Industries"
    
    if any(keyword in url_lower for keyword in ['/technology', '/technologies', '/technologie', '/technologien', '/innovation', '/research', '/forschung', '/development', '/entwicklung', '/r-d', '/rd']):
        return "Technology"
    
    if any(keyword in url_lower for keyword in ['/investor', '/investors', '/ir/', '/finance', '/financial', '/finanz', '/finanzen', '/shareholder', '/annual-report', '/quarterly', '/earnings']):
        return "Finance"
    
    if any(keyword in url_lower for keyword in ['/sustainability', '/nachhaltigkeit', '/csr', '/responsibility', '/environment', '/umwelt', '/green', '/esg', '/social-responsibility']):
        return "Sustainability"
    
    if any(keyword in url_lower for keyword in ['/quality', '/qualität', '/certification', '/certifications', '/zertifizierung', '/zertifizierungen', '/iso', '/standard', '/standards', '/accreditation']):
        return "Quality"
    
    if any(keyword in url_lower for keyword in ['/education', '/bildung', '/ausbildung', '/training', '/trainings', '/academy', '/akademie', '/learning', '/course', '/courses', '/workshop']):
        return "Education"
    
    if any(keyword in url_lower for keyword in ['/team', '/people', '/staff', '/mitarbeiter', '/employees', '/leadership', '/management', '/executives']):
        return "Team"
    
    if any(keyword in url_lower for keyword in ['/portfolio', '/project', '/projects', '/projekte', '/work', '/works', '/case-stud', '/showcase', '/gallery']):
        return "Portfolio"
    
    if any(keyword in url_lower for keyword in ['/history', '/historie', '/geschichte', '/timeline', '/milestones', '/meilensteine', '/heritage', '/tradition']):
        return "History"
    
    if any(keyword in url_lower for keyword in ['/sport', '/sports', '/athletic', '/fitness']):
        return "Sports"
    
    return "Other"