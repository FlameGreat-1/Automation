from database.connection import execute_query

# Query 1: Forms on original sub_urls (MATCHED)
query1 = """
SELECT 
    cf.company_id,
    cf.company_name,
    cf.page_url,
    'Found on original sub_url' as status
FROM contact_forms cf
INNER JOIN company_sub_urls cs 
    ON cf.company_id = cs.company_id
    AND LOWER(TRIM(TRAILING '/' FROM cf.page_url)) = LOWER(TRIM(TRAILING '/' FROM cs.sub_url))
ORDER BY cf.company_id
"""

# Query 2: Forms on discovered URLs (NOT MATCHED)
query2 = """
SELECT 
    cf.company_id,
    cf.company_name,
    cf.page_url,
    'Found on discovered URL' as status
FROM contact_forms cf
WHERE NOT EXISTS (
    SELECT 1 FROM company_sub_urls cs
    WHERE cs.company_id = cf.company_id
    AND LOWER(TRIM(TRAILING '/' FROM cf.page_url)) = LOWER(TRIM(TRAILING '/' FROM cs.sub_url))
)
ORDER BY cf.company_id
"""

print("\n" + "="*80)
print("FORMS FOUND ON ORIGINAL SUB_URLS (form column updated)")
print("="*80)
results1 = execute_query(query1, fetch=True)
for row in results1:
    print(f"Company {row[0]}: {row[2]}")
print(f"\nTotal: {len(results1)} forms")

print("\n" + "="*80)
print("FORMS FOUND ON DISCOVERED URLs (not in company_sub_urls table)")
print("="*80)
results2 = execute_query(query2, fetch=True)
for row in results2:
    print(f"Company {row[0]}: {row[2]}")
print(f"\nTotal: {len(results2)} forms")

print("\n" + "="*80)
print(f"TOTAL FORMS: {len(results1) + len(results2)}")
print(f"Forms on original sub_urls: {len(results1)}")
print(f"Forms on discovered URLs: {len(results2)}")
print("="*80)
