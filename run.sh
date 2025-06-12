docker build -t short_automation . && docker run -p 28080:28080 -v "$(pwd)/data":/app/data short_automation


docker run -p 8000:8000 -e RUNWARE_API_KEY="sdZwYOk5FMcV0vFUxws9qSkZc6xDw25B"