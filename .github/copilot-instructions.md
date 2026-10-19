# Project guidance

- This is a small Flask application using AWS DynamoDB and server-rendered Jinja templates.
- Keep the application dependency-light and accessible on mobile and desktop.
- Use boto3 with the configured DynamoDB table for persistence; render user-provided values through Jinja escaping or escape them before DOM insertion.
- Preserve the shared weekend board and update-on-submit workflow when making changes.
- Configure AWS credentials and the DynamoDB table/region, then run with `python app.py`; install dependencies from `requirements.txt`.
