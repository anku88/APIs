# Use the official Python image
FROM python:3.8-slim

# Set the working directory in the container
WORKDIR /app
# Copy the requirements file into the container
COPY hstrinf.txt .

# Install any needed packages specified in requirements3.txt
RUN pip install --no-cache-dir -r hstrinf.txt

# Copy the rest of the application code into the container
COPY . .

# Expose the port on which the Flask app will run (the port your Flask app is listening on)
EXPOSE 5002

# Run the Python application
CMD ["python", "hstrinfapinew.py"]


