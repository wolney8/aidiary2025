# Login Improvements TODOs

## ✅ Task 1: Login Error Messaging (COMPLETED)

**Status**: COMPLETED
**Description**: Add error message display to login form when username/password is invalid.

**Implementation Details**:

- ✅ Added `errorMessage` and `isLoading` properties to LoginComponent
- ✅ Updated template to display error messages with red styling and error icon
- ✅ Enhanced error handling in `onSubmit()` method with specific messages:
  - 401/400 errors: "Incorrect username or password. Please try again."
  - Connection errors: "Unable to connect to server. Please check your connection."
  - Other errors: "Login failed. Please try again."
- ✅ Added loading state with disabled button and "Logging in..." text
- ✅ Added input validation for empty username/password fields

**Files Modified**:

- `client/src/app/auth/login/login.component.ts`

---

## 🔄 Task 2: Logout Timer with Warning Modal (TODO)

**Status**: NOT STARTED
**Priority**: Medium
**Description**: Design and implement logout timer functionality for security (disabled in dev).

**Requirements**:

- Create a configurable inactivity timer
- Show modal warning: "You've been inactive for <X time>, you will be automatically logged out in <X dynamic countdown>"
- Include buttons: "Stay logged in" and "Log out"
- Must be configurable and disabled during development
- Should track user activity (mouse moves, clicks, keyboard input)

**Implementation Plan**:

1. **Create Inactivity Service** (`src/app/core/services/inactivity.service.ts`)
   - Track user activity with HostListener for document events
   - Configurable timeout settings
   - Observable for inactivity warnings
   - Dev mode detection

2. **Create Warning Modal Component** (`src/app/shared/components/inactivity-warning/`)
   - Angular Material Dialog
   - Countdown timer display
   - "Stay logged in" and "Log out" buttons
   - Auto-logout when countdown reaches zero

3. **Configuration Service Updates**
   - Add inactivity settings to app config
   - Environment-based enabling/disabling
   - Configurable timeout durations

4. **Integration Points**:
   - Add to main app component or auth guard
   - Subscribe to inactivity service in TopBar component
   - Handle modal responses appropriately

**Files to Create/Modify**:

- `client/src/app/core/services/inactivity.service.ts` (new)
- `client/src/app/shared/components/inactivity-warning/inactivity-warning.component.ts` (new)
- `client/src/app/app.component.ts` (modify)
- `client/src/environments/environment.ts` (modify)

**Testing Requirements**:

- Test with different timeout values
- Verify dev mode disabling works
- Test modal interactions
- Verify actual logout functionality
- Test activity tracking accuracy

---

## 📋 Next Steps

1. **HANDOFF TO USER**: Test Task 1 (Login Error Messaging)
   - Try logging in with incorrect credentials
   - Verify error message appears correctly
   - Test loading states
   - Verify successful login still works

2. **After Testing Task 1**: Proceed with Task 2 implementation if needed

3. **Continue with other deliverables** once login improvements are completed

---

## ⚠️ Development Notes

- **Testing Required**: All changes require user testing before proceeding
- **Server/Client Restart**: May be needed after significant changes
- **Focus**: Avoid tangents, stay on track with deliverables
- **Environment**: User running server and client in separate terminals
