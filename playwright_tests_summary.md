# Playwright HTML Interaction Tests Summary

The `apps/payments/tests_html_interaction.py` file contains the `PaymentsHtmlInteractionTests` test case, which uses the **Playwright** framework to perform browser-level end-to-end testing of the Attendant UI. These tests verify the integration between the DOM, frontend JavaScript, and the backend Django REST Framework APIs.

Here is a summary of the specific functionality tested by each test method:

### Authentication & Redirection
- **`test_scan_page_redirects_without_jwt`**
  Verifies that unauthenticated users attempting to access the scan page (`/attendant/app/scan/`) are correctly redirected to the attendant login page.

### Ticket Scanning
- **`test_scan_valid_ticket_displays_fee_breakdown`**
  Ensures that when a valid ticket code is submitted, the UI correctly displays the calculated fee amount, ticket code, vehicle type, duration, spot size, and hourly rate.
- **`test_scan_invalid_ticket_displays_error`**
  Checks that submitting an invalid ticket code displays the appropriate error alert, hides the fee result container, and re-enables the scan button for another attempt.
- **`test_scan_proceed_to_checkout_stores_pending_ticket`**
  Validates that clicking "Proceed to Payment" after a successful scan correctly stores the ticket payload (code, vehicle type, amount owed) in the browser's `sessionStorage` and navigates the user to the checkout page.

### Checkout & Payment Processing
- **`test_checkout_without_pending_ticket_shows_warning`**
  Ensures that accessing the checkout page directly without a pending ticket in `sessionStorage` displays a warning alert and hides the payment form to prevent invalid operations.
- **`test_checkout_renders_pending_ticket_summary`**
  Confirms that the checkout page correctly reads the pending ticket from `sessionStorage` and accurately populates the UI with the ticket code, vehicle type, spot size, duration, and total amount due.
- **`test_cash_tendered_displays_change`**
  Verifies that entering a cash amount in the "Cash Tendered" input dynamically calculates and displays the correct change amount due to the customer in the UI.
- **`test_cash_payment_updates_ui_and_backend`**
  Tests the complete end-to-end cash payment flow: clicking "Pay", displaying the success receipt in the UI, clearing `sessionStorage`, updating the backend `Ticket` status to `PAID`, creating a `Payment` record, and correctly decrementing the `LotOccupancy` counter to release the parking spot.
- **`test_credit_payment_updates_backend_method`**
  Ensures that selecting "CREDIT" from the payment method dropdown and submitting the payment correctly records the payment method as "CREDIT" in the backend database.
- **`test_mobile_payment_updates_backend_method`**
  Ensures that selecting "MOBILE" from the payment method dropdown and submitting the payment correctly records the payment method as "MOBILE" in the backend database.
- **`test_payment_failure_shows_error_and_does_not_duplicate_payment`**
  Validates that attempting to pay a ticket that is already paid (or fails backend validation) displays an error message in the UI, keeps the payment button enabled, prevents the success message from displaying, and ensures no duplicate `Payment` records are created in the database.
- **`test_lost_ticket_payment_charges_daily_max_if_supported`**
  Verifies that proceeding to checkout with a surrogate `LOST` ticket correctly charges the customer and records the maximum daily rate in the backend database.

  # Trace Viewer
  Viewed tests_html_interaction.py:70-90
Edited tests_html_interaction.py
Ran command: `python manage.py test apps.payments.tests_html_interaction --noinput`

I've added the Playwright Trace Viewer functionality to `apps/payments/tests_html_interaction.py`. 

It will now automatically start tracing (including DOM snapshots, screenshots, and network sources) at the beginning of each test during `setUp`, and upon completion in `tearDown`, it will package the trace into a zip file named after the specific test (e.g., `playwright_traces/apps.payments.tests_html_interaction.PaymentsHtmlInteractionTests.test_scan_valid_ticket_displays_fee_breakdown.zip`).

I'm currently running the test suite in the background to verify that the trace archives are being generated successfully. You can then view these traces locally using the Playwright CLI (`python -m playwright show-trace path/to/trace.zip`). I'll let you know when the run finishes!

Listed directory playwright_traces

Great! The test run has finished successfully, and all 13 tests passed!

I verified the traces directory (`playwright_traces/`), and the system generated a detailed `.zip` trace archive for every single test case. 

You can now use the Playwright CLI to open and visually inspect the timeline of any of these traces. For example, to view the trace for the lost ticket flow you can run:
```powershell
python -m playwright show-trace "playwright_traces/apps.payments.tests_html_interaction.PaymentsHtmlInteractionTests.test_generate_lost_ticket_flow.zip"
```

The trace viewer will let you step through every DOM snapshot, network request, console log, and action taken during the test. Let me know if there's anything else you'd like to tweak!
