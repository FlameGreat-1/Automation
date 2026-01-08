"""
Database Product URL Verification Script
Prints all saved product URLs to verify correct data
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from database.companies_db import CompaniesDB
from database.connection import execute_query

def verify_product_urls():
    print("="*80)
    print("PRODUCT URL VERIFICATION - DATABASE CHECK")
    print("="*80 + "\n")
    
    db = CompaniesDB()
    
    try:
        stats = db.get_statistics()
        
        print(f"📊 Database Overview:")
        print(f"  Total URLs: {stats.get('total_urls', 0)}")
        print(f"  Product URLs: {stats.get('product_urls', 0)}")
        print(f"  Base URLs: {stats.get('base_urls', 0)}")
        print(f"  Sub URLs: {stats.get('sub_urls', 0)}")
        print(f"  Additional URLs: {stats.get('additional_urls', 0)}")
        print()
        
        results = execute_query("""
            SELECT id, url, product, created_at 
            FROM urls 
            WHERE product IS NOT NULL 
            ORDER BY id ASC
        """, fetch=True)
        
        if not results:
            print("❌ NO PRODUCT URLS FOUND IN DATABASE\n")
            return
        
        print(f"✅ Found {len(results)} product URLs in database\n")
        print("="*80)
        
        for idx, (url_id, url, product_label, created_at) in enumerate(results, 1):
            print(f"\n[{idx}] ID: {url_id}")
            print(f"    URL: {url}")
            print(f"    Label: {product_label}")
            print(f"    Saved: {created_at}")
            print("-"*80)
        
        print("\n" + "="*80)
        print("ANALYSIS:")
        print("="*80)
        
        # Match all patterns from ProductPage.py
        product_patterns = [
            '/products', '/shop', '/catalog', '/catalogue', '/store',
            '/produkte', '/sortiment', '/artikel', '/kollektion',
            '/all-products', '/collections', '/items',
            '/category', '/categories', '/browse',
            '/men', '/women', '/kids', '/sale', '/new',
            '/clothing', '/shoes', '/accessories', '/c/'
        ]
        
        base_urls = []
        product_pages = []
        
        for url_id, url, product_label, created_at in results:
            url_lower = url.lower()
            
            if any(pattern in url_lower for pattern in product_patterns):
                product_pages.append(url)
            else:
                base_urls.append(url)
        
        print(f"\n✅ Product catalog pages (CORRECT): {len(product_pages)}")
        if product_pages:
            print("\nExamples:")
            for url in product_pages[:10]:
                print(f"  ✓ {url}")
        
        print(f"\n⚠️  URLs without standard patterns (QUESTIONABLE): {len(base_urls)}")
        if base_urls:
            print("\nExamples:")
            for url in base_urls[:10]:
                print(f"  ⚠ {url}")
        
        print("\n" + "="*80)
        if len(results) > 0:
            success_rate = (len(product_pages)/len(results)*100)
            print(f"SUCCESS RATE: {success_rate:.1f}% have standard product URL patterns")
        else:
            print(f"SUCCESS RATE: 0.0% (no data)")
        print("="*80 + "\n")
        
    except Exception as e:
        print(f"❌ ERROR: {e}\n")

if __name__ == "__main__":
    verify_product_urls()
