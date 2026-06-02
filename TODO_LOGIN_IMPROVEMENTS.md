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

## ✅ Task 2: Logout Timer with Warning Modal (IMPLEMENTED - PENDING VALIDATION)

**Status**: IMPLEMENTED (manual validation pending)
**Priority**: Medium
**Description**: Logout timer functionality is implemented in code and covered by unit tests (disabled in dev).

**Implemented**:

- ✅ Inactivity service with configurable timeout and activity tracking
- ✅ Warning modal with countdown and "Stay logged in" / "Log out" actions
- ✅ App-level integration for timer lifecycle and logout flow
- ✅ Cross-tab sync for inactivity/logout state
- ✅ Unit tests added for service/component and integration behaviour

---

## 📋 Next Steps

1. **Manual validation for Task 2 (required)**
   - Confirm inactivity timer starts/resets correctly with user activity
   - Confirm warning modal appears with correct dynamic countdown
   - Confirm "Stay logged in" keeps session active and closes modal
   - Confirm "Log out" (and countdown expiry) logs user out correctly
   - Confirm cross-tab behaviour stays in sync across multiple open tabs
   - Confirm dev mode keeps timer disabled as configured

2. **Closure**
   - Mark Task 2 as COMPLETED after manual validation passes
   - Continue with remaining deliverables

---

## ⚠️ Development Notes

- **Testing Required**: All changes require user testing before proceeding
- **Server/Client Restart**: May be needed after significant changes
- **Focus**: Avoid tangents, stay on track with deliverables
- **Environment**: User running server and client in separate terminals
