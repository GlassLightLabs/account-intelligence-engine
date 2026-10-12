23 scenarios: 2 rejected, 21 handled

| Scenario | What the export did | Outcome | Gate 1 | Detail |
|---|---|---|---|---|
| `rehire_duplicate_id` | Roster lists a rehired employee twice (inactive old record, active new one). | **rejected** |  | IngestError: employees.csv: duplicate employee_id values ['B1001']. Each key must appear once (for a rehire, keep only the current record). |
| `mixed_date_formats` | Half the rows use YYYY-MM-DD and half use MM/DD/YYYY. | **rejected** |  | IngestError: Source data failed type checks: |
| `utf8_bom` | Excel 'CSV UTF-8' export adds a byte-order mark to labor.csv. | **handled** | VALIDATED (0F/0W) |  |
| `header_variants` | Headers come out as 'Employee ID', 'Paid Hours', 'Earned Hours '. | **handled** | VALIDATED (0F/0W) |  |
| `title_rows` | Report export puts two title lines above the header row. | **handled** | VALIDATED (0F/0W) |  |
| `extra_and_reordered_columns` | Columns reordered and two extra columns added (shift, supervisor). | **handled** | VALIDATED (0F/0W) |  |
| `padded_numbers` | Numbers padded with spaces: ' 8.25 '. | **handled** | VALIDATED (0F/0W) |  |
| `us_dates` | Dates exported as MM/DD/YYYY instead of YYYY-MM-DD. | **handled** | VALIDATED (0F/0W) |  |
| `totals_row` | A grand-total row at the bottom of labor.csv. | **handled** | VALIDATED (0F/0W) |  |
| `trailing_blank_rows` | Trailing empty rows and empty trailing columns (',,,,'). | **handled** | VALIDATED (0F/0W) |  |
| `duplicate_rows` | An overlapping re-export duplicates 40 labor rows exactly. | **handled** | VALIDATED (0F/1W) |  / warning: labor.duplicate_rows |
| `id_case_mismatch` | Labor file has lowercase employee IDs ('b1005'); roster has 'B1005'. | **handled** | VALIDATED (0F/0W) |  |
| `reason_variants` | Same downtime reason typed three ways: 'Conveyor Jam', 'conveyor-jam', 'CONVEYOR JAM '. | **handled** | VALIDATED (0F/0W) |  |
| `reversal_pairs` | Payroll corrections: 12 entries posted and then reversed with negative hours. | **handled** | VALIDATED (0F/0W) |  |
| `late_prior_month_rows` | 15 rows dated in the prior month show up in this month's export. | **handled** | VALIDATED (0F/2W) |  / warning: labor.dates_in_period; warning: labor.out_of_period_rows |
| `blank_department` | Department left blank on 20 labor rows. | **handled** | VALIDATED (0F/0W) |  |
| `missing_downtime_file` | No downtime export this month. | **handled** | VALIDATED (0F/0W) |  |
| `xlsx_real_dates` | Labor delivered as .xlsx with real Excel date cells and numeric cells. | **handled** | VALIDATED (0F/0W) |  |
| `source_summary_labels` | Source system labels metrics 'Efficiency', 'Paid Hours' instead of snake_case. | **handled** | VALIDATED (0F/0W) |  |
| `repeated_header_rows` | Paged report repeats the header row every 200 lines. | **handled** | VALIDATED (0F/0W) |  |
| `thousands_separators` | Source-system totals exported with thousands separators: "6,089.43". | **handled** | VALIDATED (0F/0W) |  |
| `semicolon_delimited` | European-locale export uses ';' as the delimiter. | **handled** | VALIDATED (0F/0W) |  |
| `data_on_second_sheet` | Labor .xlsx has a 'Summary' sheet first and the data on sheet 2. | **handled** | VALIDATED (0F/0W) |  |
