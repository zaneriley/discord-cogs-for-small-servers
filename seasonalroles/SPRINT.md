# Sprint X: Business Logic Separation for Seasonal Roles

## TDD Methodology

For each story in this sprint, follow these TDD steps:
1. **Red:** Write failing tests that capture the existing behavior and define expected outputs.
2. **Green:** Implement the minimal code changes needed to make the tests pass.
3. **Verification:** Run all tests, lint checks, and static analysis to ensure the changes meet quality standards.
4. **Final Review:** Once tests pass and subtasks are verified, mark off the corresponding story's checkbox.

## TDD Red–Green–Refactor Methodology Reminder

> **Important:** For every task in this sprint, **failing tests must be written first** (this is the "Red" phase). Only after these tests are in place and are failing do you proceed to implement the minimal code changes to make the tests pass (the "Green" phase). 
>
> **Verification Steps:**
> - All unit tests must run and pass.
> - Use the command:
>   ```bash
>   pytest --maxfail=1 --disable-warnings -q
>   ```
>   to verify that tests are green before moving to the next task.

---

## Stories

### Story 1: Holiday Date Calculation and Sorting

- [ ] **1.1 Extract Holiday Date Functions**
  - [ ] **Task:** Create a new file `holiday_calculator.py` that defines pure functions for computing "days until" a given holiday.
    - Ensure that the function uses the current date from `DateUtil.now()` (or an injected date for testing) to calculate the difference.
  - [ ] **Task:** Write failing tests in `cogs/__tests__/test_seasonal_roles.py` that:
    - Provide sample holiday data (using `"MM-DD"` formats).
    - Verify that your function correctly computes the days difference.
  - [ ] **Task:** Implement the date calculation logic.
  - [ ] **Verification:** Run
    ```bash
    pytest cogs/__tests__/test_seasonal_roles.py::test_find_upcoming_holiday -v
    ```

- [ ] **1.2 Holiday Sorting Logic**
  - [ ] **Task:** In `holiday_calculator.py`, extract a function that:
    - Accepts a holiday dictionary and returns a tuple:
      - A dictionary mapping each holiday to its computed days difference.
      - The name of the holiday with the smallest positive difference.
  - [ ] **Task:** Write a failing test that verifies this sorting behavior.
  - [ ] **Task:** Implement the sorting and selection function.
  - [ ] **Verification:** Run
    ```bash
    pytest cogs/__tests__/test_seasonal_roles.py::test_get_sorted_holidays -v
    ```

- [ ] **1.3 Verify Date Utilities**
  - [ ] **Task:** Review `cogs/utilities/date_utils.py` to ensure that:
    - Functions like `normalize_date`, `str_to_date`, and `now` are consistent with your needs.
  - [ ] **Task:** Write additional unit tests (or extend existing tests) to verify that these utility methods function correctly.
  - [ ] **Verification:** Run the date utility tests along with holiday calculation tests.
  - [ ] **Final Step:** Once Story 1 is complete (all tasks pass), mark the Story 1 checkbox as complete.

### Story 2: Holiday Input Validation

- [ ] **2.1 Holiday Data Validation**
  - [ ] **Task:** Create a new file `holiday_validator.py` with pure functions for validating holiday input:
    - Check hex color format (ensuring a leading "#" and 7 characters total).
    - Validate the date string format (ensure it matches `"MM-DD"`).
    - Validate non-empty holiday names.
  - [ ] **Task:** Write failing tests for the various validation scenarios.
  - [ ] **Task:** Implement the validation functions.
  - [ ] **Verification:** Run
    ```bash
    pytest cogs/__tests__/test_seasonal_roles.py::test_validate_holiday_* -v
    ```

- [ ] **2.2 Case-Insensitive Holiday Lookup**
  - [ ] **Task:** Extract the lookup logic into a pure function that:
    - Converts holiday names to a common case and performs matching.
  - [ ] **Task:** Write failing tests that verify that different casings (e.g., `"Kids Day"` vs. `"kids day"`) result in a successful match.
  - [ ] **Task:** Implement the matching function.
  - [ ] **Verification:** Run
    ```bash
    pytest cogs/__tests__/test_seasonal_roles.py::test_validate_holiday_exists_found -v
    ```
  - [ ] **Final Step:** Once Story 2 is complete, update the Story 2 checkbox to mark it as finished.

### Story 3: Role Name Generation

- [ ] **3.1 Role Naming Logic**
  - [ ] **Task:** Create a new file `role_namer.py` containing a pure function that:
    - Generates a role name by combining the holiday name and the given date (e.g., `"HolidayName MM-DD"`).
  - [ ] **Task:** Write a failing test that supplies example inputs and verifies output.
  - [ ] **Task:** Implement the naming function.
  - [ ] **Verification:** Run
    ```bash
    pytest cogs/__tests__/test_seasonal_roles.py::test_generate_role_name -v
    ```

- [ ] **3.2 Role Update Decision Logic**
  - [ ] **Task:** Extract a pure helper function (e.g., in a new file `role_decision.py`) that, given a holiday name, date, and a list of fake roles (or their names), decides if the role should be updated (if a matching role exists) or created (if not). For example:
    - If a fake role with a name starting with the holiday name exists, return `"update"` and `"Kids Day 05-05"`.
    - Otherwise, return `"create"` and `"Kids Day 05-05"`.
  - [ ] **Task:** Write failing tests in a new test file (e.g., `cogs/__tests__/test_role_decision.py`) that simulate the following scenarios:
    - **Scenario 1:** Given a list of fake role objects where one's name matches `"Kids Day"` (case-insensitive), the function returns `"update"` and `"Kids Day 05-05"`.
    - **Scenario 2:** Given a list with no role matching the holiday name, the function returns `"create"` and `"Kids Day 05-05"`.
  - [ ] **Verification:** Run the test with:
    ```bash
    pytest cogs/__tests__/test_role_decision.py::test_decide_role_action -v
    ```
  - [ ] **Optional Task:** Write an additional test to verify case-insensitive matching:
    ```bash
    pytest cogs/__tests__/test_role_decision.py::test_role_decision_case_insensitive -v
    ```
  - [ ] **Final Step:** Once Story 3 is complete, mark its checkbox as complete.

### Story 4: Configuration Repository Pattern

- [ ] **4.1 Repository Interface**
  - [ ] **Task:** Create `holiday_repository.py` to define an interface for holiday data access.
    - The interface should support operations such as retrieving, adding, and updating holiday data.
  - [ ] **Task:** Write failing tests using the existing FakeConfig implementation.
  - [ ] **Task:** Implement the concrete repository adapters.
  - [ ] **Verification:** Run
    ```bash
    pytest cogs/__tests__/test_seasonal_roles.py::test_holiday_repository_* -v
    ```

- [ ] **4.2 Repository Integration**
  - [ ] **Task:** Update `HolidayService` to use the newly defined repository interface rather than directly accessing the config.
  - [ ] **Task:** Write integration tests to verify that the service correctly uses the repository.
  - [ ] **Verification:** Run the full test suite:
    ```bash
    pytest cogs/__tests__/test_seasonal_roles.py -v
    ```
  - [ ] **Final Step:** Once Story 4 is complete, update the checkbox accordingly.

### Story 5: Service Layer Integration

- [ ] **5.1 Holiday Service Updates**
  - [ ] **Task:** Update `HolidayService` so that holiday creation, editing, and lookup delegate to the extracted pure functions (from Stories 1 and 2).
  - [ ] **Task:** Remove any duplicated business logic from the thin Discord integration layer in `HolidayService`.
  - [ ] **Verification:** Run
    ```bash
    pytest cogs/__tests__/test_holiday_service_* -v
    ```
    and verify that the service produces the same business outcomes.

- [ ] **5.2 Role Service Updates**
  - [ ] **Task:** Update `RoleManager.create_or_update_role` to use the new role naming and decision helper functions (from Story 3).
  - [ ] **Task:** Remove or update any inline business logic from the Discord API calls so that the role update decision logic is completely driven by the extracted helpers.
  - [ ] **Verification:** Run
    ```bash
    pytest cogs/__tests__/test_role_manager_* -v
    ```
    and verify that simulated role updates follow the correct decision pathway.

- [ ] **5.3 Discord Integration Adapter Cleanup**
  - [ ] **Task:** Remove any remaining business logic triggered by Discord events in the cog (e.g., within `on_member_join` or scheduled tasks) that duplicates logic now extracted in pure functions.
  - [ ] **Task:** Ensure that each Discord event handler strictly delegates to the business logic layer and only handles API calls, such as assigning or deleting roles.
  - [ ] **Verification:** Ask the owner to check and verify it works.
  - [ ] **Final Step:** Once Story 5 is complete, mark its checkbox as complete.

---

## Final Review & Deployment

- [ ] **Code Quality Checks:**
  Run the following commands from the project root:
  ```bash
  docker-compose run lint
  docker-compose run tests --entrypoint "flake8 cogs/seasonalroles && black --check cogs/seasonalroles && mypy cogs/seasonalroles"
  ```
  *Note: You can also add separate services in docker-compose.yml for each check*

- [ ] **Full Test Suite:**
  ```bash
  docker-compose run tests
  ```

- [ ] **Documentation Review:**
  - Verify all new modules have docstrings.
  - Update the README if needed.
  - Review inline comments.

- [ ] **Final Commit:**
  - Stage changes.
  - Commit with a message: `refactor: separate business logic in seasonal roles cog`.
  - Push to main branch.

---

## Notes

- This sprint focuses solely on the unit-testable business logic.
- Discord API integration remains untouched for now.
- Leverage and test existing functionality from `cogs/utilities/date_utils.py` where possible.
- All verification steps can be tested via command line.
- Add any new test files to `cogs/__tests__/`.
