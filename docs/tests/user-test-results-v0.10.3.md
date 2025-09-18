# Test Results AIDIARY v0.10.3 ADDENDUM

[WARNING] *ONLY THE USER IS ALLOWED TO EDIT THIS/THESE FILE(s)*


# Minor Improvements Needed (v0.10.3) ADDENDUM
1. Disable entering a date in the FUTURE for both diary entries.
2. Date should also be UK/Europe format; "DD/MM/YYYY"
3. When on 'NEW ENTRY' and later during EDITING, clicking away (anything that takes the user away from this page and ultimately deletes their content) should be guarded by a popup "do you want to disgard your entry/edits and naviagate away?" Y/N (something along those lines).
4. Tag entry, once entered and a comma is typed or enter is pressed, should show tags as comma delimiated text 'chips', like in "https://stackblitz.com/angular/lyqkbervyjy?file=app%2Fchips-input-example.ts" 
5. Entry button logic: without the AI toggle (off), buttons are 'Cancel', 'Save Entry' and 'Save & Analayse' - but would it make more sense if 'Save & Analyse' is only visible when the AI toggle is ON? When I click 'Save & Analyse' it responds with "AI analysis failed. Please try again later." this is fine as we've not implemented it yet, but a change;
- When "AI Toggle" = OFF, show buttons; 'Cancel', 'Upload Image' and 'Save Entry'
- When "AI Toggle" = ON, show buttons; 'Cancel' and 'Save & Analayse'
- 'Save & Analayse' will do our AI analysis, and 'Save Entry' will save manual entries, 'Upload Image' will enable the user to upload an image associated with the entry.
6. Clicking the user icon in the top right should pull down a menu with Settings and Logout routes listed (as a list, no icons)
7. Top bar and search bar: the Search bar needs to be centred and next to it should be the filter icon.
8. The users name needs to show next to the user icon in the top bar (to the left of the icon, as it is in the wireframes)