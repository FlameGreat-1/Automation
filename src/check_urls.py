from database.connection import execute_query

query = """
SELECT 
    cf.company_id,
    cf.company_name,
    cf.page_url as form_url,
    cs.sub_url as database_url,
    cs.form as form_column_value,
    CASE 
        WHEN LOWER(TRIM(TRAILING '/' FROM cf.page_url)) = LOWER(TRIM(TRAILING '/' FROM cs.sub_url)) 
        THEN 'MATCH' 
        ELSE 'NO MATCH' 
    END as match_status
FROM contact_forms cf
LEFT JOIN company_sub_urls cs 
    ON cf.company_id = cs.company_id
WHERE cs.sub_url IS NOT NULL
ORDER BY cf.company_id, match_status DESC
"""

results = execute_query(query, fetch=True)

print(f"\nTotal rows: {len(results)}\n")
print(f"{'Company ID':<12} {'Match Status':<15} {'Form Column':<12}")
print("-" * 80)

matches = 0
no_matches = 0

for row in results:
    company_id, company_name, form_url, db_url, form_value, match_status = row
    print(f"{company_id:<12} {match_status:<15} {form_value:<12}")
    
    if match_status == 'MATCH':
        matches += 1
    else:
        no_matches += 1

print("-" * 80)
print(f"\nMatches: {matches}")
print(f"No Matches: {no_matches}")
print(f"\nSub_urls with form=1: {sum(1 for row in results if row[4] == 1)}")
