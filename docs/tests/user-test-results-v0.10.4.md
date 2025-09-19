# Test Results AIDIARY v0.10.4 ADDENDUM

[WARNING] *ONLY THE USER IS ALLOWED TO EDIT THIS/THESE FILE(s)*


# Minor Improvements Needed (v0.10.4) ADDENDUM
1. Search box needs to be a standard Angular 17 search bar like in, e.g: [<button class="primary" type="button" (click)="filterResults(filter.value)">Search</button>]
2. Search box needs to be centred in the top bar.
4. Filter should be inside the search bar as it will be designed to be an in-place pop out box with toggles (checkboxes) for Tags, Date, Keywords, People’s Names as seen in the Wireframes. Use a chevron to 'collapse' the pop out box. Activated filters should show a small red dot when at least one of the check boxes is selected.
- Tags: filters the users search by the tags stored in all entries.
- Date: filters the users serach by a date stored in the entries (if the user has entered a date, such as 'august 5th' it should match to entries that are '05/08/YYY' etc)
- Keywords: filters the users search by the keywords stored in all entries.
- People’s Names: filters the users search by the 'people's names' stored in all entries.