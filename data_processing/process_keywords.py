import csv
from collections import defaultdict

# Read the original CSV and collect unique keywords per file
file_keywords = defaultdict(set)

with open('original_results.csv', 'r', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    for row in reader:
        filename = row['File Name']
        keyword = row['Keyword']
        file_keywords[filename].add(keyword)

# Write the summary CSV with keywords joined by comma
with open('keyword_counts.csv', 'w', newline='', encoding='utf-8') as f:
    writer = csv.writer(f)
    writer.writerow(['Filename', 'Keywords'])
    for filename in sorted(file_keywords.keys()):
        keywords_str = ', '.join(sorted(file_keywords[filename]))
        writer.writerow([filename, keywords_str])

print(f"Processed {len(file_keywords)} unique files")
