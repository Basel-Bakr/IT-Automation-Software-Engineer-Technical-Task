# IT-Automation-Software-Engineer-Technical-Task

To start the app: simply run "python app.py" and it will initialize the database.
Default port 5000

To signup:
- POST request to /signup with the JSON format:
-     { "username" : "name", "email" : "email", "password" : "secret"}
- Expected outcomes:
- User created, 201
- Username, email, and password are required, 400
- User already exists or email is already in use, 409

To login:
- POST request to /login with the JSON format:
-     { "username" : "name", "email" : "email", "password" : "secret"}
- Expected outcomes:
- Login successful', 'user_id': user['id'], 200
- Invalid credentials, 401
- Username, email, and password are required, 400


To Create task:
- POST request to /tasks with the JSON format:
-  {"title": "name", "description": "description.",  "start_date": "date",  "due_date": "date",  "completion_date": "date",  "status": "pending"}
-  In the HTTP header, place the authenticated X-User-ID
- Expected Outcomes:
- 201 Created: When task is successfully created (returns a task_id)
- 400 Bad Request: If required fields (like title) are missing
- 401 Unauthorized: If the X-User-Id header is missing or invalid

To Get task:
- GET request to /tasks/"task_id"
- no JSON required
-  In the HTTP header, place the authenticated X-User-ID
- Expected outcomes:
- 200 OK: Returns the task details when found and owned by the authenticated user
- 404 Not Found: If the task ID does not exist
- 403 Forbidden: If the task exists but is owned by another user
- 401 Unauthorized: If authentication is missing

To Update task:
- PUT request to /tasks/"task_id" with the JSON format:
- { "title": "Updated title", "description": "updated description.", "start_date": "updated date", "due_date": "updated date",  "completion_date": "updated date", "status": "updated status"}
- Expected outcomes:
- 200 OK: When the task is successfully updated
- 400 Bad Request: If no update data is provided
- 404 Not Found: If the task ID does not exist
- 403 Forbidden: If the task is not owned by the authenticated user
- 401 Unauthorized: If authentication is missing

To Fetch tasks with filters:
- GET request to /tasks
- In the HTTP header, place the authenticated X-User-ID
- filters are provided as qeuery parameters
- e.g. ( By status: "?status=pending" , or by date range: "?date_from=2025-04-10T00:00:00&date_to=2025-04-15T23:59:59" )
- Expected outcomes:
- 200 OK: Returns a JSON array of tasks that match the filters
- 400 Bad Request: If an invalid filter is provided
- 401 Unauthorized: If authentication is missing

To Delete task:
- DELETE request to /tasks/"task_id"
- no JSON required
- In the HTTP header, place the authenticated X-User-ID
- Expected outcomes:
- 200 OK: When the task is successfully deleted (with a confirmation message)
- 404 Not Found: If the task does not exist
- 403 Forbidden: If the task is owned by another user
- 401 Unauthorized: If authentication is missing

To Batch Delete tasks:
- DELETE request to /tasks/batch_delete with the JSON format:
- { "start_date": "date", "end_date": "date" }
- Expected outcomes:
- 200 OK: With a message indicating how many tasks were deleted
- 400 Bad Request: If required fields (start_date or end_date) are missing, in invalid format, or if start_date > end_date
- 401 Unauthorized: If authentication is missing


To Restore Last Deleted task:
- POST request to /tasks/restore_last
- no JSON required
- Expected outcomes:
- 200 OK: When the last deleted task is successfully restored (returns a new task ID)
- 404 Not Found: If there are no deleted tasks to restore
- 401 Unauthorized: If authentication is missing


To Subscribe to reports:
- POST request to /subscribe with the JSON format:
- {"user_id": 1, "frequency": "desired frequency" }
- Expected outcomes:
- 201 Created: When the subscription is successfully created (with a confirmation message)
- 400 Bad Request: If the user_id is missing or if frequency is not one of the allowed values

To Unsubscribe from reports:
- POST request to /unsubscribe with the JSON format:
- {  "user_id": 1 }
- Expected outcomes:
- 200 OK: When the user is successfully unsubscribed (with a confirmation message)
- 400 Bad Request: If the user_id is missing from the request
