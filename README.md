# Deauville Festival du Rire

## Known bugs
- **Step 02 naive date filtering**: Filtering shows using only the first 10 characters (`perf["start"][:10]`) treats shows starting after midnight (e.g. 01:00 on 2027-06-12) as belonging to the calendar day rather than the festival night of Friday 2027-06-11 (festival days run until 06:00). To be fixed in Step 04 with real `datetime` calculations.